"""
scripts/ops/operations_planner.py

Consolidated Operations Planner — Region Builder + Field Plan Generator.
Produces regions.csv and field_plan.csv for use by the Strategy Generator.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ── Config defaults ───────────────────────────────────────────────────────────
DEFAULT_FIELD = {
    "doors_per_hour":               25,
    "hours_per_shift":               3,
    "contact_rate":                 0.18,
    "volunteer_hours_per_week":      6,
    "target_shift_count_per_weekend":5,
    "volunteers_per_turf_per_weekend":2,
    "max_precincts_per_turf":       12,
}


def _load_field_config() -> dict:
    p = BASE_DIR / "config" / "field_ops.yaml"
    if p.exists():
        try:
            return {**DEFAULT_FIELD, **(yaml.safe_load(p.read_text()) or {})}
        except Exception:
            pass
    return DEFAULT_FIELD


# ══════════════════════════════════════════════════════════════════════════════
# Region Builder
# ══════════════════════════════════════════════════════════════════════════════
def build_regions(df: pd.DataFrame, n_regions: int = 10) -> pd.DataFrame:
    """
    Group precincts into regions.
    Priority:
      1. Use 'city' or 'jurisdiction' column if available
      2. Otherwise use K-Means on turnout_pct + support_pct
    """
    if df.empty:
        return pd.DataFrame()

    out = df.copy()

    # Canonical ID
    id_col = next((c for c in ["canonical_precinct_id", "precinct_id", "Precinct_ID"]
                   if c in out.columns), out.columns[0])

    # Try city-based grouping
    city_col = next((c for c in ["city", "jurisdiction", "City", "Jurisdiction"] if c in out.columns), None)
    if city_col:
        grp = out.groupby(city_col)
        region_map = {}
        cities_sorted = sorted(out[city_col].dropna().unique())
        for i, city in enumerate(cities_sorted):
            region_map[city] = f"R{i+1:02d}_{city.replace(' ', '_')[:12]}"
        out["region_id"]   = out[city_col].map(region_map).fillna("R00_Other")
        out["region_name"] = out[city_col].fillna("Other")
    else:
        # K-Means on numeric features
        try:
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler

            feat_cols = [c for c in ["turnout_pct", "support_pct", "registered"] if c in out.columns]
            if not feat_cols:
                out["region_id"]   = "R01"
                out["region_name"] = "All Precincts"
            else:
                X = StandardScaler().fit_transform(
                    pd.to_numeric(out[feat_cols].stack(), errors="coerce").unstack().fillna(0)
                )
                k = min(n_regions, max(1, len(out) // 3))
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                lbls = km.fit_predict(X)
                out["region_id"]   = [f"R{l+1:02d}" for l in lbls]
                out["region_name"] = out["region_id"]
        except ImportError:
            # Fallback: simple quantile split on registered
            reg = pd.to_numeric(out.get("registered", pd.Series([0]*len(out))), errors="coerce").fillna(0)
            # Determine how many actual unique quantile bins are available
            try:
                _, bins = pd.qcut(reg, q=min(4, max(2, len(out))), retbins=True, duplicates="drop")
                n_bins = len(bins) - 1
                if n_bins < 1:
                    n_bins = 1
                labels = [f"R{i+1:02d}" for i in range(n_bins)]
                quartile = pd.qcut(reg, q=min(4, max(2, len(out))), labels=labels, duplicates="drop")
            except Exception:
                quartile = pd.Series(["R01"] * len(out), index=out.index)
            out["region_id"]   = quartile.astype(str).fillna("R01")
            out["region_name"] = out["region_id"]

    # Aggregate region summary
    agg: dict = {"precinct_count": (id_col, "count")}
    if "registered" in out.columns:
        agg["registered_total"] = ("registered", "sum")
    if "target_score" in out.columns:
        agg["avg_target_score"] = ("target_score", "mean")
    if "support_pct" in out.columns:
        agg["avg_support_pct"] = ("support_pct", "mean")

    # Numeric conversion
    for c in ["registered", "target_score", "support_pct"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")

    summary = out.groupby(["region_id", "region_name"]).agg(**{k: v for k, v in agg.items()}).reset_index()
    summary = summary.sort_values("region_id").reset_index(drop=True)

    # Write region_id back to original df
    # Return the summary; callers merge region_id via out
    summary.attrs["precinct_region_map"] = out[[id_col, "region_id"]].set_index(id_col)["region_id"].to_dict()
    return summary


# ══════════════════════════════════════════════════════════════════════════════
# Field Plan Generator
# ══════════════════════════════════════════════════════════════════════════════
def build_field_plan(
    region_summary: pd.DataFrame,
    config: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Per-region field plan: doors, contacts, volunteers, weeks.
    """
    if region_summary.empty:
        return pd.DataFrame()

    cfg = config or _load_field_config()
    doors_per_hour   = cfg.get("doors_per_hour", 25)
    hrs_per_shift    = cfg.get("hours_per_shift", 3)
    contact_rate     = cfg.get("contact_rate", 0.18)
    vol_hrs_per_week = cfg.get("volunteer_hours_per_week", 6)

    doors_per_shift = doors_per_hour * hrs_per_shift

    rows = []
    for _, row in region_summary.iterrows():
        reg   = float(row.get("registered_total", 0) or 0)
        score = float(row.get("avg_target_score", 0.5) or 0.5)

        # Doors to knock: higher-score regions get more coverage
        coverage    = min(0.95, 0.4 + score * 0.5)
        doors_total = round(reg * coverage)
        contacts    = round(doors_total * contact_rate)
        vol_hrs     = doors_total / doors_per_hour if doors_per_hour > 0 else 0
        weeks       = max(1, round(vol_hrs / vol_hrs_per_week))
        vols_needed = max(1, round(doors_total / (doors_per_shift * 10)))  # 10 shifts target

        rows.append({
            "region_id":        row.get("region_id", "R01"),
            "region_name":      row.get("region_name", ""),
            "registered_total": int(reg),
            "doors_to_knock":   doors_total,
            "expected_contacts":contacts,
            "volunteers_needed":vols_needed,
            "weeks_required":   weeks,
        })

    return pd.DataFrame(rows).sort_values("region_id").reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# Write outputs
# ══════════════════════════════════════════════════════════════════════════════
def write_ops_outputs(
    regions_df: pd.DataFrame,
    field_plan_df: pd.DataFrame,
    state: str,
    county: str,
    contest: str,
    run_id: str,
) -> dict[str, Path]:
    out_dir = BASE_DIR / "derived" / "ops" / state / county / contest
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {}
    if not regions_df.empty:
        p = out_dir / f"{run_id}__regions.csv"
        regions_df.to_csv(p, index=False)
        paths["regions"] = p

    if not field_plan_df.empty:
        p = out_dir / f"{run_id}__field_plan.csv"
        field_plan_df.to_csv(p, index=False)
        paths["field_plan"] = p

    return paths


# ══════════════════════════════════════════════════════════════════════════════
# Public entry point
# ══════════════════════════════════════════════════════════════════════════════
def run_operations_planner(
    model_df: pd.DataFrame,
    state: str,
    county: str,
    contest: str,
    run_id: str,
    n_regions: int = 10,
    logger=None,
) -> dict:
    """
    Main entry point. Returns:
      paths, regions_df, field_plan_df
    """
    if logger: logger.info(f"[OPS] Building regions for {len(model_df)} precincts")

    config = _load_field_config()
    regions_df    = build_regions(model_df, n_regions=n_regions)
    field_plan_df = build_field_plan(regions_df, config=config)

    paths = write_ops_outputs(regions_df, field_plan_df, state, county, contest, run_id)

    if logger:
        logger.info(f"[OPS] {len(regions_df)} regions, field plan {len(field_plan_df)} rows")

    return {
        "paths":        paths,
        "regions":      regions_df,
        "field_plan":   field_plan_df,
        "region_count": len(regions_df),
    }
