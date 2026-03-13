"""
engine/archive/trend_analysis.py — Prompt 24

Analyzes turnout and support trends across historical elections.
Computes per-precinct and county-level trend metrics.

Requires: derived/archive/normalized_elections.csv
          derived/archive/precinct_profiles.csv
Outputs:  derived/archive/precinct_trends.csv
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

log = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
DERIVED_DIR = BASE_DIR / "derived" / "archive"


def compute_trends(run_id: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Compute time-series trends per precinct and aggregate county trends.
    Returns trends DataFrame.
    """
    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M%S") + "__trends"

    elections_path = DERIVED_DIR / "normalized_elections.csv"
    if not elections_path.exists():
        log.error("[TRENDS] normalized_elections.csv not found — run archive_ingest first")
        return None

    df = pd.read_csv(elections_path)
    for col in ["turnout_rate", "support_rate", "year"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Filter to general + ballot measure election types for trend (skip presidential outliers option)
    trends_list = []

    for (state, county, precinct), grp in df.groupby(["state", "county", "precinct"]):
        grp = grp.sort_values("year")
        years = grp["year"].dropna()

        # Turnout trend
        to_data = grp[["year", "turnout_rate"]].dropna()
        if len(to_data) >= 2:
            sl, intcp, r, p, se = scipy_stats.linregress(to_data["year"], to_data["turnout_rate"])
            to_slope = round(float(sl), 6)
            to_r2    = round(float(r**2), 4)
            to_pval  = round(float(p), 4)
        else:
            to_slope = to_r2 = to_pval = 0.0

        # Support trend
        sup_data = grp[["year", "support_rate"]].dropna()
        if len(sup_data) >= 2:
            sl, intcp, r, p, se = scipy_stats.linregress(sup_data["year"], sup_data["support_rate"])
            sup_slope = round(float(sl), 6)
            sup_r2    = round(float(r**2), 4)
            sup_pval  = round(float(p), 4)
        else:
            sup_slope = sup_r2 = sup_pval = 0.0

        # Year range
        year_min = int(years.min()) if len(years) > 0 else 0
        year_max = int(years.max()) if len(years) > 0 else 0

        trends_list.append({
            "state":          state,
            "county":         county,
            "precinct":       precinct,
            "year_min":       year_min,
            "year_max":       year_max,
            "elections_n":    int(len(grp)),
            "turnout_slope":  to_slope,
            "turnout_r2":     to_r2,
            "turnout_pval":   to_pval,
            "turnout_trend":  "rising" if to_slope > 0.005 else ("falling" if to_slope < -0.005 else "stable"),
            "support_slope":  sup_slope,
            "support_r2":     sup_r2,
            "support_pval":   sup_pval,
            "support_trend":  "rising" if sup_slope > 0.005 else ("falling" if sup_slope < -0.005 else "stable"),
        })

    trends = pd.DataFrame(trends_list)
    out = DERIVED_DIR / "precinct_trends.csv"
    trends.to_csv(out, index=False)
    log.info(f"[TRENDS] Computed trends for {len(trends):,} precincts → {out}")
    return trends


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    compute_trends()
    print("Trend analysis complete.")
