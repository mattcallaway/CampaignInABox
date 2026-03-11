"""
engine/intelligence/registration_trends.py — Prompt 17

Track voter registration trends over time.

Inputs (place in data/intelligence/registration/):
    - One or more registration snapshots (CSV/XLSX)
    - Fields: snapshot_date, total_registered, dem, rep, npp, other
              (can be at county OR precinct level)

Outputs:
    derived/intelligence/registration_trends.csv
    derived/intelligence/registration_summary.json

Computed fields:
    registration_growth   — % change vs earliest snapshot
    party_shift           — change in D/R ratio
    new_voter_rate        — new registrations as % of total
    net_partisan_score    — D% - R% (positive = Dem-leaning)

Provenance: EXTERNAL (official data) | ESTIMATED (interpolated)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

REG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "intelligence" / "registration"
DERIVED = Path(__file__).resolve().parent.parent.parent / "derived" / "intelligence"

_ALIASES = {
    "snapshot_date":   ["snapshot_date", "date", "report_date", "as_of"],
    "total_registered":["total_registered", "total", "registered", "all"],
    "dem":             ["dem", "democratic", "d", "democrat"],
    "rep":             ["rep", "republican", "r", "republican"],
    "npp":             ["npp", "npa", "no_party", "independent", "other_party"],
    "other":           ["other", "third_party", "green", "libertarian"],
    "precinct_id":     ["precinct_id", "canonical_precinct_id", "precinct"],
}


def _normalize_reg(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    col_lower = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    col_map = {}
    for norm, aliases in _ALIASES.items():
        for a in aliases:
            if a in col_lower:
                col_map[col_lower[a]] = norm
                break
    df = df.rename(columns=col_map)
    for col in ["total_registered", "dem", "rep", "npp", "other"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["source_file"] = source_file
    return df


def compute_registration_trends(logger=None) -> tuple[pd.DataFrame, dict]:
    """
    Load all registration snapshots and compute trend metrics.
    Returns (trends_df, summary_dict).
    """
    _log = logger or log
    DERIVED.mkdir(parents=True, exist_ok=True)

    all_dfs = []
    for path in sorted(REG_DIR.glob("*")):
        if path.name.startswith(".") or ".gitkeep" in path.name:
            continue
        try:
            raw = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
            df = _normalize_reg(raw, path.name)
            all_dfs.append(df)
            _log.info(f"[REG] Loaded {len(df)} rows from {path.name}")
        except Exception as e:
            _log.warning(f"[REG] Could not parse {path.name}: {e}")

    summary: dict = {
        "generated_at": datetime.utcnow().isoformat(),
        "has_registration_data": False,
        "n_snapshots": 0,
        "registration_growth": None,
        "party_shift": None,
        "new_voter_rate": None,
        "net_partisan_score": None,
        "latest_total_registered": None,
        "source_type": "MISSING",
        "note": "No registration data. Add files to data/intelligence/registration/",
    }

    if not all_dfs:
        _log.info("[REG] No registration files found")
        pd.DataFrame().to_csv(DERIVED / "registration_trends.csv", index=False)
        (DERIVED / "registration_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return pd.DataFrame(), summary

    combined = pd.concat(all_dfs, ignore_index=True)

    # If snapshot_date exists, sort and compute trends
    if "snapshot_date" in combined.columns and "total_registered" in combined.columns:
        combined["snapshot_date"] = pd.to_datetime(combined["snapshot_date"], errors="coerce")
        county_level = combined[combined.get("precinct_id", pd.Series(dtype=str)).isna().all()] \
            if "precinct_id" in combined.columns else combined

        agg = combined.groupby("snapshot_date").agg({
            "total_registered": "sum",
            "dem": "sum",
            "rep": "sum",
            "npp": "sum",
        }).reset_index().sort_values("snapshot_date")

        if len(agg) >= 2:
            earliest = agg.iloc[0]
            latest   = agg.iloc[-1]
            growth = (latest["total_registered"] - earliest["total_registered"]) / max(earliest["total_registered"], 1)
            dem_pct_earliest = earliest.get("dem", 0) / max(earliest["total_registered"], 1)
            dem_pct_latest   = latest.get("dem", 0)  / max(latest["total_registered"], 1)
            rep_pct_earliest = earliest.get("rep", 0) / max(earliest["total_registered"], 1)
            rep_pct_latest   = latest.get("rep", 0)  / max(latest["total_registered"], 1)

            party_shift = (dem_pct_latest - rep_pct_latest) - (dem_pct_earliest - rep_pct_earliest)
            net_partisan = float(dem_pct_latest - rep_pct_latest)
            total_now = float(latest["total_registered"])

            summary.update({
                "has_registration_data": True,
                "n_snapshots": len(agg),
                "registration_growth": round(float(growth), 4),
                "party_shift": round(float(party_shift), 4),
                "net_partisan_score": round(net_partisan, 4),
                "latest_total_registered": round(total_now, 0),
                "source_type": "EXTERNAL",
                "note": f"{len(agg)} registration snapshots from {agg['snapshot_date'].min().date()} to {agg['snapshot_date'].max().date()}",
            })
        elif len(agg) == 1:
            row = agg.iloc[0]
            total = float(row.get("total_registered", 0) or 0)
            dem   = float(row.get("dem", 0) or 0)
            rep   = float(row.get("rep", 0) or 0)
            summary.update({
                "has_registration_data": True,
                "n_snapshots": 1,
                "latest_total_registered": total,
                "net_partisan_score": round((dem - rep) / max(total, 1), 4),
                "source_type": "EXTERNAL",
                "note": "Single registration snapshot — no trend computed.",
            })

    combined.to_csv(DERIVED / "registration_trends.csv", index=False)
    (DERIVED / "registration_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    _log.info(f"[REG] Trends computed | growth={summary.get('registration_growth', 'N/A')}")
    return combined, summary


def load_registration_summary() -> dict:
    path = DERIVED / "registration_summary.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}
