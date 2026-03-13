"""
engine/archive/archive_ingest.py — Prompt 24 Rebuild

Historical election archive ingestion and normalization pipeline.

Supports:
  - Manual file placement in data/election_archive/<state>/<county>/<year>/
  - Multiple file formats: .csv, .xls, .xlsx, .tsv
  - Source metadata preservation (URL if downloaded, file date, contest type)
  - Precinct ID normalization to MPREC-compatible canonical form
  - Multiple contests per source file (contest column or single-contest detection)
  - Graceful fallback to synthetic mock data when archive is empty

Outputs:
  derived/archive/normalized_elections.csv
  derived/archive/contest_classification.csv
  derived/archive/archive_summary.json
  reports/archive/<run_id>__archive_ingest_report.md
  reports/archive/<run_id>__archive_coverage_report.md
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = BASE_DIR / "data" / "election_archive"
DERIVED_DIR = BASE_DIR / "derived" / "archive"
REPORTS_DIR = BASE_DIR / "reports" / "archive"
LOG_DIR     = BASE_DIR / "logs" / "archive"

for _d in (DERIVED_DIR, REPORTS_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ── Contest Classifier ────────────────────────────────────────────────────────

def classify_contest(contest_id: str) -> str:
    s = str(contest_id).lower()
    if any(x in s for x in ["pres", "president"]): return "presidential"
    if any(x in s for x in ["midterm", "gov", "governor"]): return "midterm"
    if any(x in s for x in ["prop", "measure", "initiative", "bond"]): return "ballot_measure"
    if any(x in s for x in ["senate", "assembly", "congress", "district"]): return "legislative"
    if any(x in s for x in ["school", "board", "trustee"]): return "school_board"
    if any(x in s for x in ["mayor", "city council", "municipal"]): return "municipal"
    if "special" in s: return "local_special"
    return "local_general"


# ── Precinct ID Normalizer ────────────────────────────────────────────────────

def normalize_precinct_id(raw: str) -> str:
    """Normalize precinct ID to canonical MPREC-compatible form (stripped of leading zeros)."""
    s = str(raw).strip().lstrip("0")
    return s or "0"


# ── File Readers ──────────────────────────────────────────────────────────────

def _read_file(filepath: Path) -> Optional[pd.DataFrame]:
    """Read election result file in any supported format."""
    ext = filepath.suffix.lower()
    try:
        if ext in (".xls", ".xlsx"):
            return pd.read_excel(filepath, dtype=str)
        elif ext == ".tsv":
            return pd.read_csv(filepath, sep="\t", dtype=str, low_memory=False)
        elif ext == ".csv":
            return pd.read_csv(filepath, dtype=str, low_memory=False)
        else:
            log.debug(f"[INGEST] Unsupported format {ext}: {filepath.name}")
            return None
    except Exception as e:
        log.warning(f"[INGEST] Could not read {filepath}: {e}")
        return None


# ── Column Detection ──────────────────────────────────────────────────────────

_COL_ALIASES = {
    "precinct":      ["precinct", "srprec", "mprec", "precinct_id", "prec_id", "pct", "vtd"],
    "registered":    ["registered", "reg", "reg_voters", "total_reg", "eligible"],
    "ballots_cast":  ["ballots_cast", "ballots", "total_votes", "votes_cast", "turnout_count"],
    "turnout_rate":  ["turnout_rate", "turnout", "turnout_pct", "pct_turnout"],
    "yes_votes":     ["yes", "yes_votes", "for", "for_votes", "candidate_yes"],
    "no_votes":      ["no", "no_votes", "against", "against_votes", "candidate_no"],
    "support_rate":  ["support_rate", "yes_pct", "pct_yes", "yes_share"],
    "contest":       ["contest", "contest_name", "race", "measure", "office", "contest_id"],
}

def _detect_col(columns: list[str], aliases: list[str]) -> Optional[str]:
    col_lower = {c.lower().strip(): c for c in columns}
    for a in aliases:
        if a.lower() in col_lower:
            return col_lower[a.lower()]
    return None


# ── Single-File Parser ────────────────────────────────────────────────────────

def parse_result_file(
    filepath: Path,
    state: str,
    county: str,
    year: int,
    source_metadata: Optional[dict] = None,
) -> list[dict]:
    """
    Parse one election result file into a list of normalized precinct-level records.
    Handles both single-contest files and multi-contest files.
    """
    df = _read_file(filepath)
    if df is None or df.empty:
        log.warning(f"[INGEST] Empty or unreadable: {filepath}")
        return []

    cols = list(df.columns)
    meta = source_metadata or {}

    # Detect columns
    prec_col     = _detect_col(cols, _COL_ALIASES["precinct"])
    reg_col      = _detect_col(cols, _COL_ALIASES["registered"])
    ballots_col  = _detect_col(cols, _COL_ALIASES["ballots_cast"])
    turnout_col  = _detect_col(cols, _COL_ALIASES["turnout_rate"])
    yes_col      = _detect_col(cols, _COL_ALIASES["yes_votes"])
    no_col       = _detect_col(cols, _COL_ALIASES["no_votes"])
    support_col  = _detect_col(cols, _COL_ALIASES["support_rate"])
    contest_col  = _detect_col(cols, _COL_ALIASES["contest"])

    if prec_col is None:
        log.warning(f"[INGEST] No precinct column found in {filepath.name} — skipping")
        return []

    records = []

    # Group by contest if multi-contest file
    if contest_col:
        groups = df.groupby(contest_col)
        contest_names = df[contest_col].unique()
    else:
        # Single contest — infer from filename or parent dir
        inferred_name = filepath.stem.replace("_", " ").replace("-", " ")
        groups = [(inferred_name, df)]
        contest_names = [inferred_name]

    for contest_name, grp in (groups if not contest_col else groups):
        ctype = classify_contest(str(contest_name))

        for _, row in grp.iterrows():
            prec_raw = str(row.get(prec_col, "UNKNOWN")).strip()
            prec_id  = normalize_precinct_id(prec_raw)

            try:
                reg  = float(row[reg_col])  if reg_col  and pd.notna(row.get(reg_col)) else np.nan
                ballots = float(row[ballots_col]) if ballots_col and pd.notna(row.get(ballots_col)) else np.nan
            except (ValueError, TypeError):
                reg, ballots = np.nan, np.nan

            # Compute turnout rate
            if turnout_col and pd.notna(row.get(turnout_col)):
                try:
                    tr = float(str(row[turnout_col]).replace("%", "").strip())
                    turnout_rate = tr / 100 if tr > 1.0 else tr
                except (ValueError, TypeError):
                    turnout_rate = ballots / reg if (reg and reg > 0) else np.nan
            elif not np.isnan(reg) and not np.isnan(ballots) and reg > 0:
                turnout_rate = min(ballots / reg, 1.0)
            else:
                turnout_rate = np.nan

            # Compute support rate from yes/no votes or direct column
            try:
                yes = float(row[yes_col]) if yes_col and pd.notna(row.get(yes_col)) else np.nan
                no  = float(row[no_col])  if no_col  and pd.notna(row.get(no_col))  else np.nan
            except (ValueError, TypeError):
                yes, no = np.nan, np.nan

            if support_col and pd.notna(row.get(support_col)):
                try:
                    sr = float(str(row[support_col]).replace("%", "").strip())
                    support_rate = sr / 100 if sr > 1.0 else sr
                except (ValueError, TypeError):
                    support_rate = yes / (yes + no) if (not np.isnan(yes) and not np.isnan(no) and yes + no > 0) else np.nan
            elif not np.isnan(yes) and not np.isnan(no) and yes + no > 0:
                support_rate = yes / (yes + no)
            else:
                support_rate = np.nan

            vote_margin = (support_rate - (1 - support_rate)) if not np.isnan(support_rate) else np.nan

            records.append({
                "year":         year,
                "state":        state,
                "county":       county,
                "contest":      str(contest_name),
                "contest_type": ctype,
                "precinct":     prec_id,
                "registered":   reg,
                "ballots_cast": ballots,
                "turnout_rate": round(turnout_rate, 4) if not np.isnan(turnout_rate) else None,
                "yes_votes":    yes,
                "no_votes":     no,
                "support_rate": round(support_rate, 4) if not np.isnan(support_rate) else None,
                "vote_margin":  round(vote_margin, 4)  if not np.isnan(vote_margin)  else None,
                "source_file":  filepath.name,
                "source_date":  meta.get("source_date", datetime.now().strftime("%Y-%m-%d")),
                "source_url":   meta.get("source_url", ""),
                "provenance":   meta.get("provenance", "REAL"),
            })

    log.info(f"[INGEST] {filepath.name}: {len(records)} records ({len(contest_names)} contests)")
    return records


# ── Archive Walker ────────────────────────────────────────────────────────────

def walk_archive(archive_dir: Path) -> list[dict]:
    """
    Walk data/election_archive/<state>/<county>/<year>/ and parse all result files.
    Returns all parsed records.
    """
    all_records = []
    files_found = 0
    files_parsed = 0

    if not archive_dir.exists():
        return []

    for state_dir in sorted(archive_dir.iterdir()):
        if not state_dir.is_dir():
            continue
        state = state_dir.name

        for county_dir in sorted(state_dir.iterdir()):
            if not county_dir.is_dir():
                continue
            county = county_dir.name

            for year_dir in sorted(county_dir.iterdir()):
                if not year_dir.is_dir():
                    continue
                try:
                    year = int(year_dir.name)
                except ValueError:
                    continue

                # Load source metadata if present
                meta_path = year_dir / "contest_metadata.json"
                source_meta: dict = {}
                if meta_path.exists():
                    try:
                        source_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass

                # Parse all eligible files
                for fpath in sorted(year_dir.iterdir()):
                    if fpath.suffix.lower() in (".csv", ".xls", ".xlsx", ".tsv"):
                        # Skip metadata-only or summary files
                        if fpath.stem.lower() in ("contest_metadata",):
                            continue
                        files_found += 1
                        records = parse_result_file(fpath, state, county, year, source_meta)
                        if records:
                            all_records.extend(records)
                            files_parsed += 1

    log.info(f"[INGEST] Archive walk complete: {files_found} files found, {files_parsed} parsed, {len(all_records)} records")
    return all_records


# ── Mock Generator ────────────────────────────────────────────────────────────

def generate_mock_archive() -> list[dict]:
    """
    Generate synthetic historical data when no real archive files are present.
    Clearly tagged with provenance=SYNTHETIC.
    Used as a fallback ONLY.
    """
    log.info("[INGEST] No real archive files found — generating synthetic mock data (provenance=SYNTHETIC)")

    years = [2016, 2018, 2020, 2022, 2024]
    contests = {
        2016: ("Presidential General 2016",    "presidential"),
        2018: ("Governor Midterm 2018",         "midterm"),
        2020: ("Presidential General 2020",     "presidential"),
        2022: ("Local General 2022",            "local_general"),
        2024: ("Prop 1 Ballot Measure 2024",    "ballot_measure"),
    }

    rng = np.random.RandomState(42)
    records = []

    for prec_id in range(1, 101):
        base_turnout = rng.uniform(0.38, 0.72)
        base_support = rng.uniform(0.30, 0.70)

        for year, (contest_name, ctype) in contests.items():
            t_boost = 0.14 if ctype == "presidential" else (0.05 if ctype == "midterm" else 0.0)
            # Special election turnout penalty
            special_penalty = -0.08 if ctype == "local_special" else 0.0

            registered   = max(int(rng.normal(1000, 200)), 100)
            turnout_rate = float(np.clip(base_turnout + t_boost + special_penalty + rng.normal(0, 0.04), 0.05, 0.98))
            ballots      = int(registered * turnout_rate)
            support_rate = float(np.clip(base_support + rng.normal(0, 0.04), 0.05, 0.98))
            yes_votes    = int(ballots * support_rate)
            no_votes     = ballots - yes_votes
            vote_margin  = round(support_rate - (1 - support_rate), 4)

            records.append({
                "year":         year,
                "state":        "CA",
                "county":       "Sonoma",
                "contest":      contest_name,
                "contest_type": ctype,
                "precinct":     f"PCT_{prec_id:04d}",
                "registered":   registered,
                "ballots_cast": ballots,
                "turnout_rate": round(turnout_rate, 4),
                "yes_votes":    yes_votes,
                "no_votes":     no_votes,
                "support_rate": round(support_rate, 4),
                "vote_margin":  vote_margin,
                "source_file":  "SYNTHETIC",
                "source_date":  "",
                "source_url":   "",
                "provenance":   "SYNTHETIC",
            })

    return records


# ── Coverage Reporter ─────────────────────────────────────────────────────────

def compute_coverage(df: pd.DataFrame) -> dict:
    """Compute coverage stats from normalized elections DataFrame."""
    real_df = df[df["provenance"].isin(["REAL", "EXTERNAL"])]
    return {
        "total_records":     int(len(df)),
        "real_records":      int(len(real_df)),
        "synthetic_records": int(len(df) - len(real_df)),
        "years_ingested":    sorted(df["year"].unique().tolist()),
        "counties":          sorted(df["county"].unique().tolist()),
        "states":            sorted(df["state"].unique().tolist()),
        "contests":          int(df["contest"].nunique()),
        "contest_types":     df["contest_type"].unique().tolist(),
        "precincts":         int(df["precinct"].nunique()),
        "has_real_data":     len(real_df) > 0,
        "turnout_null_pct":  round(df["turnout_rate"].isna().mean() * 100, 1),
        "support_null_pct":  round(df["support_rate"].isna().mean() * 100, 1),
    }


# ── Main Ingest Runner ────────────────────────────────────────────────────────

def run_ingest(run_id: Optional[str] = None) -> pd.DataFrame:
    """
    Full archive ingestion pipeline.
    Returns normalized elections DataFrame.
    """
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d__%H%M%S") + "__archive"

    t0 = time.time()
    log.info(f"[INGEST] Starting archive ingest | run_id={run_id}")

    # 1. Walk real archive files
    records = walk_archive(ARCHIVE_DIR)

    # 2. Fall back to synthetic if empty
    has_real_data = len(records) > 0
    if not has_real_data:
        records = generate_mock_archive()

    # 3. Build DataFrame
    df = pd.DataFrame(records)
    df = df.sort_values(["year", "county", "precinct", "contest"]).reset_index(drop=True)

    # 4. Write normalized elections CSV
    out_csv = DERIVED_DIR / "normalized_elections.csv"
    df.to_csv(out_csv, index=False)
    log.info(f"[INGEST] Wrote {len(df):,} records to {out_csv}")

    # 5. Write contest classification
    class_df = df[["contest", "contest_type", "year", "county", "state"]].drop_duplicates()
    class_csv = DERIVED_DIR / "contest_classification.csv"
    class_df.to_csv(class_csv, index=False)

    # 6. Compute coverage
    coverage = compute_coverage(df)

    # 7. Write archive summary JSON
    summary = {
        "run_id":           run_id,
        "generated_at":     datetime.now().isoformat(),
        "has_real_data":    has_real_data,
        "coverage":         coverage,
        "archive_dir":      str(ARCHIVE_DIR),
    }
    summary_path = DERIVED_DIR / "archive_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    elapsed = time.time() - t0

    # 8. Write ingest report
    _write_ingest_report(run_id, df, coverage, has_real_data, elapsed)

    # 9. Write coverage report
    _write_coverage_report(run_id, df, coverage, has_real_data)

    log.info(f"[INGEST] Archive ingest complete in {elapsed:.1f}s | has_real_data={has_real_data}")
    return df


def _write_ingest_report(run_id, df, coverage, has_real_data, elapsed):
    real_label = "REAL" if has_real_data else "SYNTHETIC (no real archive data found)"
    lines = [
        f"# Archive Ingest Report",
        f"**Run ID:** {run_id}  |  **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"## Data Provenance",
        f"- Source type: **{real_label}**",
        f"- Archive directory: `{ARCHIVE_DIR}`",
        f"- Elapsed: {elapsed:.1f}s",
        "",
        f"## Record Summary",
        f"- Total records: {coverage['total_records']:,}",
        f"- Real records: {coverage['real_records']:,}",
        f"- Synthetic records: {coverage['synthetic_records']:,}",
        f"- Precincts: {coverage['precincts']:,}",
        f"- Contests: {coverage['contests']:,}",
        "",
        f"## Contest Types Found",
    ] + [f"- {ct}" for ct in sorted(coverage["contest_types"])] + [
        "",
        "## Data Quality",
        f"- Turnout null rate: {coverage['turnout_null_pct']}%",
        f"- Support null rate: {coverage['support_null_pct']}%",
    ]

    if not has_real_data:
        lines += [
            "",
            "> **NOTE:** No real election archive files were found. To populate the archive:",
            "> Place election result files in `data/election_archive/<STATE>/<COUNTY>/<YEAR>/`",
            "> Supported formats: .csv, .xls, .xlsx, .tsv",
        ]

    rpath = REPORTS_DIR / f"{run_id}__archive_ingest_report.md"
    rpath.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[INGEST] Wrote ingest report: {rpath.name}")


def _write_coverage_report(run_id, df, coverage, has_real_data):
    real_df = df[df["provenance"].isin(["REAL", "EXTERNAL"])]
    lines = [
        f"# Archive Coverage Report",
        f"**Run ID:** {run_id}  |  **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Coverage Matrix",
        "",
        "| Year | County | Contests | Records | Provenance |",
        "|------|--------|----------|---------|------------|",
    ]
    for (year, county), grp in df.groupby(["year", "county"]):
        prov = "REAL" if grp["provenance"].isin(["REAL","EXTERNAL"]).any() else "SYNTHETIC"
        lines.append(f"| {year} | {county} | {grp['contest'].nunique()} | {len(grp):,} | {prov} |")

    lines += [
        "",
        "## Missing Years / Jurisdictions",
    ]
    expected_years = [2016, 2018, 2020, 2022, 2024]
    found_years = coverage["years_ingested"]
    missing = [str(y) for y in expected_years if y not in found_years]
    if missing:
        lines.append(f"- Missing years: {', '.join(missing)}")
    else:
        lines.append("- All expected years present")

    rpath = REPORTS_DIR / f"{run_id}__archive_coverage_report.md"
    rpath.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[INGEST] Wrote coverage report: {rpath.name}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = run_ingest()
    print(f"Ingest complete: {len(df):,} records, has_real_data={df['provenance'].eq('REAL').any()}")
