"""
scripts/geo/kepler_export.py

Kepler.gl GeoJSON export for precinct modeling results.
Requires geopandas. Skips gracefully if unavailable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Properties to include in kepler export
KEPLER_PROPERTIES = [
    "canonical_precinct_id",
    "registered", "ballots_cast", "turnout_pct", "support_pct",
    "target_score", "target_tier", "walk_priority_rank",
    "persuasion_potential", "turnout_opportunity",
    "confidence_level", "region_id",
]

# Aliases from model columns → kepler property names
KEPLER_ALIASES = {
    "canonical_precinct_id": "PrecinctID",
    "registered":            "Registered",
    "ballots_cast":          "BallotsCast",
    "turnout_pct":           "TurnoutPct",
    "support_pct":           "SupportPct",
    "target_score":          "TargetScore",
    "target_tier":           "Tier",
    "walk_priority_rank":    "WalkPriorityRank",
    "persuasion_potential":  "PersuasionPotential",
    "turnout_opportunity":   "TurnoutOpportunity",
    "confidence_level":      "ConfidenceLevel",
    "region_id":             "RegionId",
}


def export_kepler_geojson(
    model_df,  # pd.DataFrame
    geo_root: Path,
    contest_id: str,
    run_id: str,
    logger=None,
) -> Optional[Path]:
    """
    Join model_df to precinct geometry and write a Kepler-ready GeoJSON.

    Returns path if written, None if geopandas or geometry unavailable.
    """
    from scripts.lib.deps import gate
    if not gate("geopandas", logger=logger, feature="kepler_export"):
        if logger: logger.info("[KEPLER] Skipped: geopandas not installed")
        return None

    import geopandas as gpd
    import pandas as pd

    # ── Find geometry ─────────────────────────────────────────────────────────
    geojson_path = _find_geometry(geo_root)
    if geojson_path is None:
        if logger: logger.info("[KEPLER] Skipped: no precinct GeoJSON found")
        return None

    try:
        gdf = gpd.read_file(geojson_path)
    except Exception as e:
        if logger: logger.warn(f"[KEPLER] Could not read geometry: {e}")
        return None

    if gdf.empty:
        if logger: logger.warn("[KEPLER] Geometry file is empty")
        return None

    if logger: logger.info(f"[KEPLER] Loaded geometry: {len(gdf)} precincts from {geojson_path.name}")

    # ── Find join key ─────────────────────────────────────────────────────────
    geo_id_col = _find_id_col(gdf)
    mod_id_col = _find_id_col(model_df)
    if geo_id_col is None or mod_id_col is None:
        if logger: logger.warn("[KEPLER] Cannot find precinct id column for join")
        return None

    # ── Prepare model data subset ─────────────────────────────────────────────
    props = [c for c in KEPLER_PROPERTIES if c in model_df.columns]
    model_sub = model_df[[mod_id_col] + [p for p in props if p != mod_id_col]].copy()

    # ── Join ──────────────────────────────────────────────────────────────────
    # Normalise join keys to string for safe merge
    gdf[geo_id_col]      = gdf[geo_id_col].astype(str).str.strip()
    model_sub[mod_id_col] = model_sub[mod_id_col].astype(str).str.strip()

    merged = gdf.merge(model_sub, left_on=geo_id_col, right_on=mod_id_col, how="left")
    match_count = merged[mod_id_col].notna().sum()
    if logger: logger.info(f"[KEPLER] Joined {match_count}/{len(gdf)} precincts to model data")

    # ── Rename to kepler aliases ───────────────────────────────────────────────
    merged = merged.rename(columns={k: v for k, v in KEPLER_ALIASES.items() if k in merged.columns})

    # ── Write GeoJSON ─────────────────────────────────────────────────────────
    out_dir = BASE_DIR / "derived" / "maps"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{contest_id}__kepler.geojson"

    try:
        merged.to_file(out_path, driver="GeoJSON")
        if logger: logger.info(f"[KEPLER] Wrote {out_path.relative_to(BASE_DIR)} ({out_path.stat().st_size:,} bytes)")
        return out_path
    except Exception as e:
        if logger: logger.warn(f"[KEPLER] Write failed: {e}")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────
def _find_geometry(geo_root: Path) -> Optional[Path]:
    """Search geo_root and subdirs for MPREC/SRPREC geojson."""
    for pattern in ["*mprec*.geojson", "*MPREC*.geojson", "*srprec*.geojson", "*SRPREC*.geojson"]:
        matches = sorted(geo_root.rglob(pattern), key=lambda p: p.stat().st_size, reverse=True)
        if matches:
            return matches[0]
    return None


def _find_id_col(df) -> Optional[str]:
    """Return the first precinct id column found."""
    candidates = [
        "canonical_precinct_id", "MPREC_ID", "SRPREC_ID",
        "PrecinctID", "Precinct_ID", "precinct_id", "mprec", "srprec",
    ]
    for c in candidates:
        if c in df.columns:
            return c
    # Last resort: first column that contains "prec" case-insensitive
    for c in df.columns:
        if "prec" in str(c).lower():
            return c
    return None
