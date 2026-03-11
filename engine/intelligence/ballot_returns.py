"""
engine/intelligence/ballot_returns.py — Prompt 17

Track daily ballot return data (vote-by-mail / early voting).

Inputs (place in data/intelligence/ballot_returns/):
    - Daily return report CSVs
    - Fields: report_date, ballots_returned, ballots_issued,
              dem_returned (optional), rep_returned (optional),
              precinct_id (optional, for precinct-level)

SECURITY:
    Only AGGREGATE return counts. No individual voter records.
    Files with individual voter names/addresses must not be placed here.
    .gitignore covers data/intelligence/ballot_returns/*voter*

Outputs:
    derived/intelligence/ballot_returns_daily.csv
    derived/intelligence/ballot_returns_summary.json
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

BR_DIR  = Path(__file__).resolve().parent.parent.parent / "data" / "intelligence" / "ballot_returns"
DERIVED = Path(__file__).resolve().parent.parent.parent / "derived" / "intelligence"

_ALIASES = {
    "report_date":      ["report_date", "date", "as_of", "return_date"],
    "ballots_returned": ["ballots_returned", "returned", "ballots_cast", "returns"],
    "ballots_issued":   ["ballots_issued", "issued", "mailed", "vbm_issued"],
    "dem_returned":     ["dem_returned", "d_returned", "democratic_returned"],
    "rep_returned":     ["rep_returned", "r_returned", "republican_returned"],
    "precinct_id":      ["precinct_id", "precinct", "canonical_precinct_id"],
}


def _normalize(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    col_lower = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    col_map = {}
    for norm, aliases in _ALIASES.items():
        for a in aliases:
            if a in col_lower:
                col_map[col_lower[a]] = norm
                break
    df = df.rename(columns=col_map)
    for col in ["ballots_returned", "ballots_issued", "dem_returned", "rep_returned"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "report_date" in df.columns:
        df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
    df["source_file"] = source_file
    return df


def load_ballot_returns(logger=None) -> tuple[pd.DataFrame, dict]:
    """
    Load all daily ballot return reports.
    Computes return_rate, partisan_split, projected turnout.
    Returns (daily_df, summary_dict).
    """
    _log = logger or log
    DERIVED.mkdir(parents=True, exist_ok=True)

    all_dfs = []
    for path in sorted(BR_DIR.glob("*")):
        if path.name.startswith(".") or ".gitkeep" in path.name:
            continue
        # Safety check: skip anything that looks like a voter file
        if any(kw in path.name.lower() for kw in ["voter", "name", "address", "contact", "phone"]):
            _log.warning(f"[BALLOT_RETURNS] SKIPPED (possible voter file): {path.name}")
            continue
        try:
            raw = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
            df = _normalize(raw, path.name)
            all_dfs.append(df)
            _log.info(f"[BALLOT_RETURNS] Loaded {len(df)} rows from {path.name}")
        except Exception as e:
            _log.warning(f"[BALLOT_RETURNS] Could not parse {path.name}: {e}")

    summary: dict = {
        "generated_at": datetime.utcnow().isoformat(),
        "has_ballot_return_data": False,
        "n_reports": 0,
        "total_returned": None,
        "total_issued": None,
        "return_rate": None,
        "dem_return_pct": None,
        "rep_return_pct": None,
        "partisan_advantage": None,
        "projected_turnout": None,
        "source_type": "MISSING",
        "note": "No ballot return data. Add daily reports to data/intelligence/ballot_returns/",
    }

    if not all_dfs:
        _log.info("[BALLOT_RETURNS] No return files found")
        pd.DataFrame().to_csv(DERIVED / "ballot_returns_daily.csv", index=False)
        (DERIVED / "ballot_returns_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return pd.DataFrame(), summary

    combined = pd.concat(all_dfs, ignore_index=True)

    # Sort by date if available
    if "report_date" in combined.columns:
        combined = combined.sort_values("report_date")

    # Aggregate by date (county-wide totals)
    agg_cols = {"ballots_returned": "sum"}
    if "ballots_issued" in combined.columns:
        agg_cols["ballots_issued"] = "sum"
    if "dem_returned" in combined.columns:
        agg_cols["dem_returned"] = "sum"
    if "rep_returned" in combined.columns:
        agg_cols["rep_returned"] = "sum"

    if "report_date" in combined.columns:
        daily = combined.groupby("report_date").agg(agg_cols).reset_index()
        daily["cumulative_returned"] = daily["ballots_returned"].cumsum()
        if "ballots_issued" in daily.columns:
            daily["return_rate"] = daily["cumulative_returned"] / daily["ballots_issued"].max()
    else:
        daily = combined

    # Summary from latest values
    latest_returned = float(combined["ballots_returned"].sum()) if "ballots_returned" in combined.columns else 0.0
    latest_issued   = float(combined["ballots_issued"].max()) if "ballots_issued" in combined.columns else None
    return_rate     = latest_returned / latest_issued if latest_issued and latest_issued > 0 else None

    dem_pct = None
    rep_pct = None
    partisan_adv = None
    if "dem_returned" in combined.columns and "rep_returned" in combined.columns:
        total_dem = float(combined["dem_returned"].sum())
        total_rep = float(combined["rep_returned"].sum())
        total_partisan = total_dem + total_rep
        if total_partisan > 0:
            dem_pct = round(total_dem / total_partisan, 4)
            rep_pct = round(total_rep / total_partisan, 4)
            partisan_adv = round(dem_pct - rep_pct, 4)

    # Project final turnout based on return pace
    projected_turnout = None
    if return_rate and latest_issued:
        # Simple projection: if return_rate trend continues to election day
        projected_turnout = round(min(return_rate * 1.15, 0.95), 4)  # 15% in-person premium

    summary.update({
        "has_ballot_return_data": True,
        "n_reports": len(combined),
        "total_returned": round(latest_returned, 0),
        "total_issued": round(latest_issued, 0) if latest_issued else None,
        "return_rate": round(return_rate, 4) if return_rate else None,
        "dem_return_pct": dem_pct,
        "rep_return_pct": rep_pct,
        "partisan_advantage": partisan_adv,
        "projected_turnout": projected_turnout,
        "source_type": "EXTERNAL",
        "note": f"{len(combined)} ballot return records loaded.",
    })

    daily.to_csv(DERIVED / "ballot_returns_daily.csv", index=False)
    (DERIVED / "ballot_returns_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    _log.info(f"[BALLOT_RETURNS] return_rate={return_rate}, total_returned={latest_returned}")
    return daily, summary


def load_ballot_returns_summary() -> dict:
    path = DERIVED / "ballot_returns_summary.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}
