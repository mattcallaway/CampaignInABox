"""
engine/archive/precinct_profiles.py — Prompt 24 Rebuild

Builds long-term behavioral fingerprints for each precinct from the
normalized historical election archive.

Metrics computed per precinct:
  - avg_turnout, turnout_variance, turnout_sd
  - avg_support, support_variance, support_sd
  - partisan_tilt, ballot_measure_tilt
  - special_election_turnout_penalty
  - trend_slope (turnout trend over years), trend_confidence
  - elections_counted

Requires: derived/archive/normalized_elections.csv
Outputs:  derived/archive/precinct_profiles.csv
          reports/archive/<run_id>__precinct_profiles_report.md
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
REPORTS_DIR = BASE_DIR / "reports" / "archive"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _trend_slope(years: pd.Series, values: pd.Series) -> tuple[float, float]:
    """
    Compute OLS trend slope and R² confidence.
    Returns (slope, r_squared).
    """
    if len(years) < 2:
        return 0.0, 0.0
    try:
        slope, intercept, r, p, se = scipy_stats.linregress(years.astype(float), values.astype(float))
        return round(float(slope), 6), round(float(r**2), 4)
    except Exception:
        return 0.0, 0.0


def build_profiles(run_id: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Build precinct behavior profiles from normalized election archive.
    """
    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M%S") + "__profiles"

    infile = DERIVED_DIR / "normalized_elections.csv"
    if not infile.exists():
        log.error("[PROFILES] normalized_elections.csv not found — run archive_ingest first")
        return None

    df = pd.read_csv(infile)
    if df.empty:
        log.warning("[PROFILES] normalized_elections.csv is empty")
        return None

    # Ensure numeric types
    for col in ["turnout_rate", "support_rate", "year", "registered"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    log.info(f"[PROFILES] Building profiles from {len(df):,} records across "
             f"{df['precinct'].nunique()} precincts, {df['year'].nunique()} years")

    profiles_list = []

    for (state, county, precinct), grp in df.groupby(["state", "county", "precinct"]):
        grp = grp.sort_values("year")

        # Base turnout stats
        to_vals = grp["turnout_rate"].dropna()
        avg_turnout     = float(to_vals.mean()) if len(to_vals) > 0 else np.nan
        turnout_var     = float(to_vals.var())  if len(to_vals) > 1 else 0.0
        turnout_sd      = float(to_vals.std())  if len(to_vals) > 1 else 0.0

        # Base support stats
        sup_vals = grp["support_rate"].dropna()
        avg_support     = float(sup_vals.mean()) if len(sup_vals) > 0 else np.nan
        support_var     = float(sup_vals.var())  if len(sup_vals) > 1 else 0.0
        support_sd      = float(sup_vals.std())  if len(sup_vals) > 1 else 0.0

        # Partisan and ballot measure tilt
        partisan_tilt       = round(avg_support - 0.5, 4)          if not np.isnan(avg_support) else 0.0
        ballot_measure_tilt = round(partisan_tilt * 0.85, 4)        # scaled proxy for ballot measures

        # Special election turnout penalty
        special_rows = grp[grp["contest_type"].isin(["local_special", "municipal"])]
        normal_rows  = grp[~grp["contest_type"].isin(["local_special", "municipal"])]
        if len(special_rows) > 0 and len(normal_rows) > 0:
            sp_penalty = float(
                special_rows["turnout_rate"].mean() - normal_rows["turnout_rate"].mean()
            )
        else:
            sp_penalty = 0.0

        # Turnout trend slope (OLS over years)
        trend_data = grp[["year", "turnout_rate"]].dropna()
        if len(trend_data) >= 2:
            to_slope, to_r2 = _trend_slope(trend_data["year"], trend_data["turnout_rate"])
        else:
            to_slope, to_r2 = 0.0, 0.0

        # Support trend slope
        supp_trend = grp[["year", "support_rate"]].dropna()
        if len(supp_trend) >= 2:
            sup_slope, sup_r2 = _trend_slope(supp_trend["year"], supp_trend["support_rate"])
        else:
            sup_slope, sup_r2 = 0.0, 0.0

        # Average registered voters
        avg_registered = float(grp["registered"].mean()) if "registered" in grp.columns else np.nan

        # Data provenance — REAL if any REAL row
        prov = "REAL" if grp.get("provenance", pd.Series([])).isin(["REAL", "EXTERNAL"]).any() else "SYNTHETIC"

        profiles_list.append({
            "state":                     state,
            "county":                    county,
            "precinct":                  precinct,
            "elections_counted":          int(len(grp)),
            "avg_registered":            round(avg_registered, 1) if not np.isnan(avg_registered) else None,
            "avg_turnout":               round(avg_turnout, 4)    if not np.isnan(avg_turnout) else None,
            "turnout_variance":           round(turnout_var, 6),
            "turnout_sd":                round(turnout_sd, 6),
            "avg_support":               round(avg_support, 4)    if not np.isnan(avg_support) else None,
            "support_variance":           round(support_var, 6),
            "support_sd":                round(support_sd, 6),
            "partisan_tilt":             partisan_tilt,
            "ballot_measure_tilt":       ballot_measure_tilt,
            "special_election_penalty":  round(sp_penalty, 4),
            "turnout_trend_slope":        to_slope,
            "turnout_trend_r2":           to_r2,
            "support_trend_slope":        sup_slope,
            "support_trend_r2":           sup_r2,
            "provenance":                prov,
        })

    profiles = pd.DataFrame(profiles_list)
    out_path = DERIVED_DIR / "precinct_profiles.csv"
    profiles.to_csv(out_path, index=False)
    log.info(f"[PROFILES] Built {len(profiles):,} precinct profiles → {out_path}")

    # Write report
    _write_profiles_report(run_id, profiles)

    return profiles


def _write_profiles_report(run_id: str, profiles: pd.DataFrame):
    real_count = int(profiles["provenance"].eq("REAL").sum())
    lines = [
        f"# Precinct Profiles Report",
        f"**Run ID:** {run_id}  |  **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"## Summary",
        f"- Total precincts profiled: {len(profiles):,}",
        f"- Based on REAL archive data: {real_count:,}",
        f"- Based on SYNTHETIC data: {len(profiles) - real_count:,}",
        "",
        f"## Turnout Statistics",
        f"- Mean avg_turnout: {profiles['avg_turnout'].mean():.3f}",
        f"- Mean turnout_sd: {profiles['turnout_sd'].mean():.4f}",
        f"- Mean turnout_trend_slope: {profiles['turnout_trend_slope'].mean():.6f} (per year)",
        "",
        f"## Support Statistics",
        f"- Mean avg_support: {profiles['avg_support'].mean():.3f}",
        f"- Mean support_sd: {profiles['support_sd'].mean():.4f}",
        "",
        f"## Tilt Distribution",
        f"- Precincts leaning YES (>50%): {int((profiles['partisan_tilt'] > 0).sum()):,}",
        f"- Precincts leaning NO (<50%): {int((profiles['partisan_tilt'] < 0).sum()):,}",
        "",
        f"## Special Election Penalty",
        f"- Mean penalty: {profiles['special_election_penalty'].mean():.4f} (turnout reduction vs normal elections)",
    ]

    rpath = REPORTS_DIR / f"{run_id}__precinct_profiles_report.md"
    rpath.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[PROFILES] Wrote report: {rpath.name}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_profiles()
    print("Precinct profiles complete.")
