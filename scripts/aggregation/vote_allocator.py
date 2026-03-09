"""
scripts/aggregation/vote_allocator.py

Parsic contest workbook using contest_parser, aggregates votes,
allocates to canonical geography via weighted crosswalk,
and enforces sanity constraints.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any
import pandas as pd

from ..loaders.file_loader import load_excel_workbook, iter_excel_sheets
from ..loaders.contest_registry import update_contest_from_parse
from ..loaders.contest_parser import discover_contests, parse_contest_sheet, extract_registered_voters, is_contest_sheet
from ..lib.naming import normalize_precinct_id

# ---------------------------------------------------------------------------
# Vote aggregation
# ---------------------------------------------------------------------------

def aggregate_to_precinct_totals(parsed: dict, logger=None) -> pd.DataFrame:
    """
    Aggregate vote choices into per-precinct totals.
    Uses parsed results from contest_parser.
    """
    df = parsed["df"].copy()
    prec_col = parsed["prec_col"]
    choice_cols = parsed["choice_cols"]

    if prec_col is None:
        prec_col = df.columns[0] if len(df.columns) > 0 else None

    result = pd.DataFrame()
    if prec_col:
        raw_series = df[prec_col].astype(str).str.strip()
        result["PrecinctID_Raw"] = raw_series
        
        # Filter out "Total" rows
        mask = ~raw_series.str.lower().str.startswith("total")
        result = result[mask].reset_index(drop=True)
        raw_series = raw_series[mask].reset_index(drop=True)
        df = df[mask].reset_index(drop=True)

        result["PrecinctID"] = raw_series.apply(lambda x: normalize_precinct_id(x, pad_to=0))

    def _to_num(col):
        if col and col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(0)
        return 0

    # Fill Choices
    for choice in choice_cols:
        result[choice] = _to_num(choice)

    # Registered — pull from df if available (set by parse_contest_sheet from inline data)
    if "Registered" in df.columns:
        result["Registered"] = pd.to_numeric(df["Registered"], errors="coerce").fillna(0).astype(int)[mask].reset_index(drop=True)
    elif prec_col and "Registered" not in df.columns:
        result["Registered"] = 0
    else:
        result["Registered"] = 0

    # BallotsCast — if already set by parse_contest_sheet, use it; otherwise derive from choices
    if "BallotsCast" in df.columns:
        result["BallotsCast"] = pd.to_numeric(df["BallotsCast"], errors="coerce").fillna(0).astype(int)[mask].reset_index(drop=True)
    else:
        result["BallotsCast"] = result[choice_cols].sum(axis=1)

    result = result.dropna(subset=["PrecinctID"]).reset_index(drop=True)
    return result


# ---------------------------------------------------------------------------
# Vote allocation to canonical geography
# ---------------------------------------------------------------------------

def allocate_votes_crosswalk(
    votes_df: pd.DataFrame,
    crosswalk: dict[str, list[tuple[str, float]]],
    src_id_col: str = "PrecinctID",
    tgt_id_col: str = "MPREC_ID",
    logger=None
) -> pd.DataFrame:
    """
    Allocate votes from source precincts to target precincts via weighted crosswalk.
    Numeric columns are weighted-summed.
    """
    numeric_cols = [c for c in votes_df.columns if c != src_id_col 
                    and c != "PrecinctID_Raw"
                    and pd.api.types.is_numeric_dtype(votes_df[c])]

    allocated_records = []
    
    for _, row in votes_df.iterrows():
        src = str(row[src_id_col]).strip()
        targets = crosswalk.get(src, [(src, 1.0)])
        
        for tgt, weight in targets:
            rec = {tgt_id_col: tgt}
            for col in numeric_cols:
                rec[col] = float(row[col]) * weight
            allocated_records.append(rec)

    if not allocated_records:
        return pd.DataFrame(columns=[tgt_id_col] + numeric_cols)

    result = pd.DataFrame(allocated_records)
    result = result.groupby(tgt_id_col, as_index=False)[numeric_cols].sum()
    
    # Conservation check
    for col in numeric_cols:
        orig = votes_df[col].sum()
        new = result[col].sum()
        if abs(orig - new) > 0.1:
            if logger:
                logger.warn(f"Allocation drift in {col}: {orig:.1f} -> {new:.1f}")

    return result


def area_weighted_fallback(
    votes_df: pd.DataFrame,
    src_id_col: str = "PrecinctID",
) -> pd.DataFrame:
    """Identity mapping fallback."""
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
    """Basic sanity checks: Ballots vs Registration, etc."""
    config = config or {}
    sanity_cfg = config.get("sanity", {})
    ballots_tol = float(sanity_cfg.get("max_ballots_over_registered_pct", 0.0))

    violations = []
    all_passed = True

    if logger:
        def _log(name, p, d=""): logger.register_sanity(name, p, d)
    else:
        def _log(name, p, d=""): pass

    if "Registered" in df.columns and "BallotsCast" in df.columns:
        over = df.loc[df["Registered"] > 0].copy()
        if not over.empty:
            diff = (over["BallotsCast"] - over["Registered"]) / over["Registered"]
            n_bad = (diff > ballots_tol).sum()
            if n_bad > 0:
                msg = f"{n_bad} precincts have BallotsCast > Registered (tol={ballots_tol})"
                violations.append(msg)
                all_passed = False
                _log("BallotsCast <= Registered", False, msg)
            else:
                _log("BallotsCast <= Registered", True)

    if len(df) == 0:
        violations.append("No precinct rows")
        all_passed = False
        _log("Non-empty model", False)
    else:
        _log("Non-empty model", True, f"{len(df)} rows")

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
    """Parse workbook and return structured contest data."""
    import math
    workbook_path = Path(workbook_path)

    def _log(msg, level="INFO"):
        if logger: getattr(logger, level.lower(), logger.info)(msg)

    if not workbook_path.exists():
        raise RuntimeError(f"Cannot open workbook: {workbook_path}")

    # 1. Registration Discovery (openpyxl path is fine here — single-column sheet)
    reg_voters = extract_registered_voters(workbook_path)
    if reg_voters:
        _log(f"Extracted registration for {len(reg_voters)} precincts")

    # 2. Discover contest sheet names using openpyxl (just for names)
    wb = load_excel_workbook(workbook_path)
    all_sheet_names_wb = wb.sheetnames

    # 3. Build rows using pandas (correctly reads all columns for CA XLS format)
    import warnings as _warnings
    sheet_rows: dict[str, list[list]] = {}
    try:
        import pandas as _pd
        xl = _pd.ExcelFile(workbook_path)
        for sname in all_sheet_names_wb:
            try:
                with _warnings.catch_warnings():
                    _warnings.simplefilter("ignore")
                    df = _pd.read_excel(xl, sheet_name=sname, header=None, dtype=object)
                rows = []
                for _, row in df.iterrows():
                    rows.append([
                        None if (v is None or (isinstance(v, float) and math.isnan(v))) else v
                        for v in row
                    ])
                sheet_rows[sname] = rows
            except Exception:
                sheet_rows[sname] = []
    except Exception:
        # Fallback to openpyxl if pandas unavailable
        for sname, rows in iter_excel_sheets(wb):
            sheet_rows[sname] = rows

    # 4. Filter to contest sheets and parse
    found_sheets = [s for s in all_sheet_names_wb if is_contest_sheet(s, sheet_rows.get(s, []))]
    parsed_sheets = []
    contest_types = []
    all_sheet_names = []

    for sheet_name in found_sheets:
        rows = sheet_rows.get(sheet_name, [])
        _log(f"Parsing sheet: {sheet_name!r}")
        try:
            parsed = parse_contest_sheet(sheet_name, rows, logger=logger)
            totals = aggregate_to_precinct_totals(parsed, logger=logger)

            if reg_voters:
                totals["Registered"] = totals["PrecinctID"].map(reg_voters).fillna(0).astype(int)

            parsed["totals_df"] = totals
            parsed_sheets.append(parsed)
            contest_types.append(parsed["contest_type"])
            all_sheet_names.append(sheet_name)
            _log(f"  -> {len(totals)} precincts, type={parsed['contest_type']}")
        except Exception as e:
            _log(f"  Failed parsing {sheet_name}: {e}", "WARN")

    if not parsed_sheets:
        raise RuntimeError("No contest sheets discovered or parsed")

    # 5. Update contest.json
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
                    candidates.extend(p["choice_cols"])
                elif p["contest_type"] == "ballot_measure":
                    measures.append(p["contest_title"])

            update_contest_from_parse(
                contest_json_path,
                all_sheet_names,
                primary_type,
                candidates=list(dict.fromkeys(candidates)) or None,
                measures=list(dict.fromkeys(measures)) or None,
            )

    return parsed_sheets


