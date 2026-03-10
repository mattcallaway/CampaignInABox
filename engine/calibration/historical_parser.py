"""
engine/calibration/historical_parser.py — Prompt 11

Parse historical CA election detail workbooks into a normalized
precinct-level results CSV for model calibration.

Reuses existing scripts/aggregation/vote_allocator.py logic.

Output:
  derived/calibration/historical_precinct_results.csv
  Columns: year, canonical_precinct_id, turnout_rate, support_rate,
           contest_type, registered, ballots_cast, yes_votes
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.aggregation.vote_allocator import parse_contest_workbook

log = logging.getLogger(__name__)

ELECTIONS_DIR = BASE_DIR / "data" / "elections" / "CA" / "Sonoma"
CALIBRATION_DIR = BASE_DIR / "derived" / "calibration"


def parse_single_election(year: int, detail_path: Path) -> Optional[pd.DataFrame]:
    """
    Parse one historical detail workbook into a normalized DataFrame.
    Returns None if the file can't be parsed.
    """
    log.info(f"[HIST_PARSER] Parsing {year}: {detail_path}")
    try:
        sheets = parse_contest_workbook(detail_path)
    except Exception as e:
        log.warning(f"[HIST_PARSER] Could not parse {detail_path}: {e}")
        return None

    if not sheets:
        return None

    rows = []
    for sheet_name, df_raw in sheets:
        # Expect columns from vote_allocator: canonical_precinct_id, registered,
        # ballots_cast, yes_votes, no_votes
        df = df_raw.copy()

        # Normalize precinct ID
        if "canonical_precinct_id" not in df.columns:
            # Try common fallbacks
            for col in ["precinct", "PRECINCT", "Precinct"]:
                if col in df.columns:
                    df["canonical_precinct_id"] = df[col].astype(str).str.strip().str.lstrip("0")
                    break
            else:
                log.debug(f"[HIST_PARSER] {year}/{sheet_name}: no precinct column — skipping")
                continue

        # Ensure numeric columns
        for col in ["registered", "ballots_cast", "yes_votes", "no_votes"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Compute rates
        df["year"] = year
        df["contest_type"] = "ballot_measure"
        if "registered" in df.columns and "ballots_cast" in df.columns:
            df["turnout_rate"] = (df["ballots_cast"] / df["registered"].replace(0, pd.NA)).round(4)
        else:
            df["turnout_rate"] = None

        if "ballots_cast" in df.columns and "yes_votes" in df.columns:
            df["support_rate"] = (df["yes_votes"] / df["ballots_cast"].replace(0, pd.NA)).round(4)
        else:
            df["support_rate"] = None

        keep_cols = [
            "year", "canonical_precinct_id", "turnout_rate", "support_rate",
            "contest_type", "registered", "ballots_cast",
        ]
        available = [c for c in keep_cols if c in df.columns]
        rows.append(df[available])

    if not rows:
        return None

    return pd.concat(rows, ignore_index=True)


def parse_all_historical(logger=None) -> Optional[pd.DataFrame]:
    """
    Iterate all years in data/elections/CA/Sonoma/ and parse each detail.xls.

    Returns combined DataFrame, or None if no history found.
    Writes: derived/calibration/historical_precinct_results.csv
    """
    _log = logger or log

    if not ELECTIONS_DIR.exists():
        _log.info("[HIST_PARSER] No elections directory found — skipping historical parsing")
        return None

    year_dirs = sorted([d for d in ELECTIONS_DIR.iterdir() if d.is_dir() and d.name.isdigit()])
    if not year_dirs:
        _log.info("[HIST_PARSER] No historical election directories found")
        return None

    all_results = []
    for year_dir in year_dirs:
        year = int(year_dir.name)
        # Look for detail workbook in multiple formats
        for pattern in ("detail.xls", "detail.xlsx", "detail.xlsb"):
            detail_path = year_dir / pattern
            if detail_path.exists():
                df = parse_single_election(year, detail_path)
                if df is not None and not df.empty:
                    all_results.append(df)
                break
        else:
            _log.debug(f"[HIST_PARSER] {year}: no detail workbook found")

    if not all_results:
        _log.info("[HIST_PARSER] No parseable historical elections found")
        return None

    combined = pd.concat(all_results, ignore_index=True)
    combined = combined.dropna(subset=["canonical_precinct_id", "turnout_rate"])

    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CALIBRATION_DIR / "historical_precinct_results.csv"
    combined.to_csv(out_path, index=False)
    _log.info(
        f"[HIST_PARSER] Wrote {len(combined):,} historical precinct-year records "
        f"across {combined['year'].nunique()} elections → {out_path}"
    )
    return combined
