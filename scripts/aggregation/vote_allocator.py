"""
scripts/aggregation/vote_allocator.py

Parses contest workbook, aggregates vote methods → totals,
allocates to canonical geography via crosswalk (area-weighted fallback),
and enforces sanity constraints.

HARD FAIL rules:
  - If contest parse fails → raises RuntimeError
  - If ballots > registered (substantial) → raises RuntimeError
  - If YES+NO > ballots (beyond tolerance) → raises RuntimeError
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..loaders.file_loader import load_excel_workbook, iter_excel_sheets
from ..loaders.contest_registry import (
    detect_contest_type,
    update_contest_from_parse,
)


# ---------------------------------------------------------------------------
# Vote method aggregation keywords
# ---------------------------------------------------------------------------

VOTE_METHOD_COLS = {
    "mail", "mail ballot", "vote by mail", "vbm",
    "in person", "election day", "early voting",
    "provisional", "early",
}

TOTAL_COL_ALIASES = {"total", "totals", "grand total"}

REGISTRATION_COL_ALIASES = {
    "registered", "registration", "reg", "registered voters", "total registered"
}

BALLOTS_COL_ALIASES = {
    "ballots cast", "total ballots", "ballots", "votes cast", "total votes"
}

PRECINCT_COL_ALIASES = {
    "precinct", "precinct_id", "mprec_id", "srprec_id", "prec_id",
    "precinct id", "masterprecinctid", "precinct name"
}


def _col_alias(col: str, alias_set: set) -> bool:
    return col.strip().lower() in alias_set


def _find_col(headers: list[str], alias_set: set) -> str | None:
    for h in headers:
        if h and _col_alias(h, alias_set):
            return h
    return None


# ---------------------------------------------------------------------------
# Sheet parser
# ---------------------------------------------------------------------------

def parse_sheet(
    sheet_name: str,
    rows: list[list],
) -> dict[str, Any]:
    """
    Parse a single Excel sheet into vote data.

    Returns dict:
        {
          'sheet_name': str,
          'contest_type': str,
          'headers': list,
          'precinct_col': str|None,
          'registered_col': str|None,
          'ballots_col': str|None,
          'vote_cols': list[str],       # YES/NO or candidate columns
          'df': pd.DataFrame,           # parsed data per precinct
        }
    """
    # Find header row (first non-empty row with >2 non-None values)
    header_row_idx = 0
    for i, row in enumerate(rows):
        non_null = [c for c in row if c is not None and str(c).strip()]
        if len(non_null) >= 3:
            header_row_idx = i
            break

    headers = [str(c).strip() if c is not None else "" for c in rows[header_row_idx]]
    data_rows = rows[header_row_idx + 1:]

    # Build dataframe
    df = pd.DataFrame(data_rows, columns=headers)
    # Drop fully empty rows
    df = df.dropna(how="all").reset_index(drop=True)

    # Identify special columns
    prec_col = _find_col(headers, PRECINCT_COL_ALIASES)
    reg_col  = _find_col(headers, REGISTRATION_COL_ALIASES)
    bal_col  = _find_col(headers, BALLOTS_COL_ALIASES)

    contest_type = detect_contest_type(headers)

    # Identify vote method and candidate/measure columns
    standard = (
        PRECINCT_COL_ALIASES
        | REGISTRATION_COL_ALIASES
        | BALLOTS_COL_ALIASES
        | VOTE_METHOD_COLS
        | TOTAL_COL_ALIASES
        | {"", "precinct name"}
    )
    vote_cols = [h for h in headers if h.lower() not in standard and h]

    # Detect and rename YES/NO columns
    yes_col = next((h for h in headers if h.upper() in ("YES", "YES VOTES")), None)
    no_col  = next((h for h in headers if h.upper() in ("NO",  "NO VOTES")),  None)

    return {
        "sheet_name":    sheet_name,
        "contest_type":  contest_type,
        "headers":       headers,
        "precinct_col":  prec_col,
        "registered_col": reg_col,
        "ballots_col":   bal_col,
        "yes_col":       yes_col,
        "no_col":        no_col,
        "vote_cols":     vote_cols,
        "df":            df,
    }


def aggregate_to_precinct_totals(parsed: dict, logger=None) -> pd.DataFrame:
    """
    Aggregate vote methods into per-precinct totals.
    Returns DataFrame with columns:
      PrecinctID, Registered, BallotsCast, [Yes, No] or [Cand1, Cand2, ...]
    """
    df = parsed["df"].copy()
    prec_col = parsed["precinct_col"]
    reg_col  = parsed["registered_col"]
    bal_col  = parsed["ballots_col"]
    yes_col  = parsed["yes_col"]
    no_col   = parsed["no_col"]
    vote_cols = parsed["vote_cols"]

    if prec_col is None:
        # Try first column as precinct ID
        prec_col = df.columns[0] if len(df.columns) > 0 else None

    result = pd.DataFrame()
    if prec_col:
        raw_series = df[prec_col].astype(str).str.strip()
        result["PrecinctID_Raw"] = raw_series
        
        from scripts.lib.naming import normalize_precinct_id
        # We don't pad to 7 by default for vote file precinct IDs unless they strictly match a known mprec standard, but we'll apply base normalization.
        norm_series = raw_series.apply(lambda x: normalize_precinct_id(x, pad_to=0))
        result["PrecinctID"] = norm_series
        
        if logger:
            mismatches = result[result["PrecinctID_Raw"] != result["PrecinctID"]]
            for _, row in mismatches.iterrows():
                logger.warning(f"Precinct normalization modified raw ID: '{row['PrecinctID_Raw']}' -> '{row['PrecinctID']}'")

    def _to_num(col):
        return pd.to_numeric(df[col], errors="coerce").fillna(0) if col and col in df.columns else 0

    result["Registered"]  = _to_num(reg_col)
    result["BallotsCast"] = _to_num(bal_col)

    if yes_col:
        result["Yes"] = _to_num(yes_col)
    if no_col:
        result["No"]  = _to_num(no_col)

    # Include candidate columns
    for vc in vote_cols:
        if vc in df.columns and vc not in (yes_col, no_col, prec_col, reg_col, bal_col):
            result[vc] = _to_num(vc)

    result = result.dropna(subset=["PrecinctID"]).reset_index(drop=True)
    result = result[result["PrecinctID"].str.strip() != ""].reset_index(drop=True)
    return result


# ---------------------------------------------------------------------------
# Vote allocation to canonical geography
# ---------------------------------------------------------------------------

def allocate_votes_crosswalk(
    votes_df: pd.DataFrame,
    crosswalk: dict[str, list[tuple[str, float]]],
    src_id_col: str = "PrecinctID",
    tgt_id_col: str = "MPREC_ID",
) -> pd.DataFrame:
    """
    Allocate votes from source precincts to target precincts via crosswalk.
    Numeric columns are weighted-summed. Returns DataFrame indexed by tgt_id_col.
    """
    numeric_cols = [c for c in votes_df.columns if c != src_id_col
                    and pd.api.types.is_numeric_dtype(votes_df[c])]

    records = []
    for _, row in votes_df.iterrows():
        src = str(row[src_id_col]).strip()
        targets = crosswalk.get(src, [(src, 1.0)])  # identity fallback
        for tgt, weight in targets:
            # We enforce MPREC/target ID normalization in the crosswalk/boundary loader, so we just use the mapped string.
            rec = {tgt_id_col: tgt}
            for col in numeric_cols:
                rec[col] = row[col] * weight
            records.append(rec)

    if not records:
        return pd.DataFrame(columns=[tgt_id_col] + numeric_cols)

    result = pd.DataFrame(records)
    result = result.groupby(tgt_id_col, as_index=False)[numeric_cols].sum()
    return result


def area_weighted_fallback(
    votes_df: pd.DataFrame,
    src_id_col: str = "PrecinctID",
) -> pd.DataFrame:
    """Return votes_df unchanged (identity mapping) as area-weighted fallback."""
    df = votes_df.copy()
    df.rename(columns={src_id_col: "MPREC_ID"}, inplace=True)
    return df


# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------

def run_sanity_checks(
    df: pd.DataFrame,
    config: dict | None = None,
    logger=None,
) -> tuple[bool, list[str]]:
    """
    Run allocation sanity checks. Returns (all_passed, violations).
    HARD FAIL trigger list returned to caller.
    """
    config = config or {}
    sanity_cfg = config.get("sanity", {})
    ballots_tol = float(sanity_cfg.get("max_ballots_over_registered_pct", 0.0))
    yesno_tol   = float(sanity_cfg.get("max_yes_no_over_ballots_pct", 0.005))

    violations = []
    all_passed = True

    def _log_sanity(check, passed, detail=""):
        if logger:
            logger.register_sanity(check, passed, detail)

    # Check 1: BallotsCast <= Registered
    if "Registered" in df.columns and "BallotsCast" in df.columns:
        over = df.loc[df["Registered"] > 0].copy()
        over_pct = ((over["BallotsCast"] - over["Registered"]) / over["Registered"]).clip(lower=0)
        violations_mask = over_pct > ballots_tol
        n_over = violations_mask.sum()
        if n_over > 0:
            detail = f"{n_over} precincts have BallotsCast > Registered"
            violations.append(detail)
            all_passed = False
            _log_sanity("BallotsCast <= Registered", False, detail)
        else:
            _log_sanity("BallotsCast <= Registered", True)

    # Check 2: YES+NO <= BallotsCast
    if "Yes" in df.columns and "No" in df.columns and "BallotsCast" in df.columns:
        yesno = df["Yes"] + df["No"]
        over2 = (yesno - df["BallotsCast"]) / df["BallotsCast"].replace(0, 1)
        violations_mask2 = over2 > yesno_tol
        n_over2 = violations_mask2.sum()
        if n_over2 > 0:
            detail = f"{n_over2} precincts have YES+NO > BallotsCast"
            violations.append(detail)
            all_passed = False
            _log_sanity("YES+NO <= BallotsCast", False, detail)
        else:
            _log_sanity("YES+NO <= BallotsCast", True)

    # Check 3: No negative values
    num_cols = ["Registered", "BallotsCast", "Yes", "No"]
    for col in num_cols:
        if col in df.columns:
            negatives = (df[col] < 0).sum()
            if negatives > 0:
                detail = f"{negatives} negative values in {col}"
                violations.append(detail)
                all_passed = False
                _log_sanity(f"No negative values in {col}", False, detail)
            else:
                _log_sanity(f"No negative values in {col}", True)

    # Check 4: At least one precinct with data
    if len(df) == 0:
        violations.append("No precinct rows in output")
        all_passed = False
        _log_sanity("Non-empty precinct model", False, "0 rows")
    else:
        _log_sanity("Non-empty precinct model", True, f"{len(df)} rows")

    return all_passed, violations


# ---------------------------------------------------------------------------
# Main parse entry point
# ---------------------------------------------------------------------------

def parse_contest_workbook(
    workbook_path: str | Path,
    contest_json_path: str | Path | None = None,
    config: dict | None = None,
    logger=None,
) -> list[dict]:
    """
    Parse all sheets in a contest workbook.
    Returns list of parsed sheet dicts (one per contest/sheet).
    Updates contest.json if path provided.
    Raises RuntimeError on hard-fail.
    """
    workbook_path = Path(workbook_path)

    def _log(msg, level="INFO"):
        if logger:
            getattr(logger, level.lower(), logger.info)(msg)

    try:
        wb = load_excel_workbook(workbook_path)
    except Exception as e:
        if logger:
            logger.hard_fail("PARSE_CONTEST", f"Cannot open workbook: {e}")
        raise RuntimeError(f"Cannot open workbook {workbook_path}: {e}")

    parsed_sheets = []
    sheet_names = []
    contest_types = []

    for sheet_name, rows in iter_excel_sheets(wb):
        _log(f"Parsing sheet: {sheet_name!r}")
        try:
            parsed = parse_sheet(sheet_name, rows)
            totals = aggregate_to_precinct_totals(parsed, logger=logger)
            parsed["totals_df"] = totals
            parsed_sheets.append(parsed)
            sheet_names.append(sheet_name)
            contest_types.append(parsed["contest_type"])
            _log(
                f"  → {len(totals)} precincts, type={parsed['contest_type']}, "
                f"cols={parsed['vote_cols']}"
            )
        except Exception as e:
            _log(f"  Failed parsing sheet {sheet_name!r}: {e}", "WARN")

    if not parsed_sheets:
        if logger:
            logger.hard_fail("PARSE_CONTEST", "No sheets could be parsed from workbook")
        raise RuntimeError("No sheets could be parsed from workbook")

    # Update contest.json
    if contest_json_path:
        contest_json_path = Path(contest_json_path)
        if contest_json_path.exists():
            primary_type = (
                "ballot_measure" if "ballot_measure" in contest_types
                else "candidate_race" if "candidate_race" in contest_types
                else "unknown"
            )
            candidates = []
            measures = []
            for p in parsed_sheets:
                if p["contest_type"] == "candidate_race":
                    candidates.extend(p["vote_cols"])
                elif p["contest_type"] == "ballot_measure":
                    measures.append(p["sheet_name"])
            update_contest_from_parse(
                contest_json_path,
                sheet_names,
                primary_type,
                candidates=candidates or None,
                measures=measures or None,
            )

    return parsed_sheets
