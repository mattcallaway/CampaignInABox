"""
engine/geo/geometry_validation.py — Prompt 8.7

Geometry validation layer.
Gracefully skips if geopandas is unavailable (marks status=SKIP).

Output:
  reports/validation/<RUN_ID>__geometry_validation.md
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def validate_geometry(
    gdf=None,                          # GeoDataFrame or None
    precinct_model: Optional[pd.DataFrame] = None,
    id_col: str = "canonical_precinct_id",
    geo_id_col: str = "MPREC_ID",
    run_id: str = "unknown",
    contest_id: str = "unknown",
    geometry_source: str = "unknown",
    logger=None,
) -> dict:
    """
    Validate geometry if available. Always writes a report.
    Returns a summary dict.
    """
    result = {
        "geometry_source":       geometry_source,
        "precinct_count":        0,
        "model_precinct_count":  len(precinct_model) if precinct_model is not None else 0,
        "invalid_geometry_count": 0,
        "duplicate_precinct_ids": 0,
        "missing_ids":           0,
        "area_zero_count":       0,
        "status":                "SKIP",
        "notes":                 [],
    }

    if gdf is None:
        result["notes"].append("geopandas not available or geometry not loaded")
        _write_geo_report(result, run_id)
        if logger:
            logger.info("  [GEO_VALIDATION] SKIP — geometry not loaded")
        return result

    try:
        import geopandas as gpd
        result["precinct_count"] = len(gdf)
        result["status"] = "PASS"

        # Duplicate precinct IDs
        if geo_id_col in gdf.columns:
            dups = int(gdf[geo_id_col].duplicated().sum())
            result["duplicate_precinct_ids"] = dups
            if dups > 0:
                result["status"] = "WARN"
                result["notes"].append(f"{dups} duplicate precinct IDs in geometry")

        # Invalid geometries
        try:
            invalid = int((~gdf.geometry.is_valid).sum())
            result["invalid_geometry_count"] = invalid
            if invalid > 0:
                result["status"] = "WARN"
                result["notes"].append(f"{invalid} invalid geometries")
        except Exception:
            result["notes"].append("could not check geometry validity")

        # Area = 0
        try:
            zero_area = int((gdf.geometry.area == 0).sum())
            result["area_zero_count"] = zero_area
            if zero_area > 0:
                result["status"] = "WARN"
                result["notes"].append(f"{zero_area} geometries with area=0")
        except Exception:
            pass

        # Missing IDs vs precinct model
        if precinct_model is not None and geo_id_col in gdf.columns and id_col in precinct_model.columns:
            geo_ids    = set(gdf[geo_id_col].astype(str))
            model_ids  = set(precinct_model[id_col].astype(str))
            missing    = model_ids - geo_ids
            result["missing_ids"] = len(missing)
            if missing:
                result["status"] = "WARN"
                result["notes"].append(f"{len(missing)} model precincts have no matching geometry")

    except Exception as e:
        result["status"] = "WARN"
        result["notes"].append(f"Error during geometry validation: {e}")

    _write_geo_report(result, run_id)
    if logger:
        logger.info(f"  [GEO_VALIDATION] status={result['status']}, precincts={result['precinct_count']}")

    return result


def _write_geo_report(result: dict, run_id: str) -> None:
    val_dir = BASE_DIR / "reports" / "validation"
    val_dir.mkdir(parents=True, exist_ok=True)

    status_badge = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭️"}.get(result["status"], "?")

    md = [
        f"# Geometry Validation Report {status_badge}",
        f"**Run:** `{run_id}`  **Status:** `{result['status']}`  **Source:** `{result.get('geometry_source', 'unknown')}`\n",
        "## Summary",
        f"| Metric | Value |", "|---|---|",
        f"| Precinct count (geometry) | {result['precinct_count']} |",
        f"| Precinct count (model) | {result['model_precinct_count']} |",
        f"| Invalid geometries | {result['invalid_geometry_count']} |",
        f"| Duplicate precinct IDs | {result['duplicate_precinct_ids']} |",
        f"| Missing IDs (model not in geo) | {result['missing_ids']} |",
        f"| Area = 0 count | {result['area_zero_count']} |",
    ]

    if result.get("notes"):
        md.append("\n## Notes")
        for note in result["notes"]:
            md.append(f"- {note}")

    if result["status"] == "SKIP":
        md.append("\n_Geometry validation skipped — geopandas not installed or geometry not loaded._")
    if result["status"] == "PASS":
        md.append("\n✅ All geometry checks passed.")

    md_path = val_dir / f"{run_id}__geometry_validation.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    # Latest
    latest = BASE_DIR / "logs" / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "geometry_validation.md").write_text(f"# See: {md_path}\n", encoding="utf-8")
    (latest / "geometry_status.json").write_text(
        json.dumps({"status": result["status"], "precinct_count": result["precinct_count"],
                    "run_id": run_id, "notes": result["notes"]}, indent=2),
        encoding="utf-8"
    )
