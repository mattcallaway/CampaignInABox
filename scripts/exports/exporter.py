"""
scripts/exports/exporter.py

Exports pipeline outputs:
  - Precinct model CSV → derived/precinct_models/
  - Targeting list CSV → derived/campaign_targets/
  - Kepler-ready GeoJSON → derived/maps/
  - District aggregates CSV → derived/district_aggregates/
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _ts_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def export_precinct_model(
    df: pd.DataFrame,
    base_dir: str | Path,
    run_id: str,
    state: str,
    county: str,
    contest_slug: str,
) -> Path:
    """
    Write precinct model to CSV.
    Returns output path.
    """
    base_dir = Path(base_dir)
    out_dir = base_dir / "derived" / "precinct_models" / state / county / contest_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Drop geometry if present (for CSV export)
    export_df = df.copy()
    if "geometry" in export_df.columns:
        export_df = export_df.drop(columns=["geometry"])

    out_path = out_dir / f"{run_id}__precinct_model.csv"
    export_df.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


def export_targeting_list(
    targeting_df: pd.DataFrame,
    base_dir: str | Path,
    run_id: str,
    state: str,
    county: str,
    contest_slug: str,
) -> Path:
    """
    Write targeting list to CSV.
    Returns output path.
    """
    base_dir = Path(base_dir)
    out_dir = base_dir / "derived" / "campaign_targets" / state / county / contest_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    export_df = targeting_df.copy()
    if "geometry" in export_df.columns:
        export_df = export_df.drop(columns=["geometry"])

    out_path = out_dir / f"{run_id}__targeting_list.csv"
    export_df.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


def export_district_aggregates(
    df: pd.DataFrame,
    base_dir: str | Path,
    run_id: str,
    state: str,
    county: str,
    contest_slug: str,
) -> Path:
    """
    Compute and write district-level aggregates.
    """
    base_dir = Path(base_dir)
    out_dir = base_dir / "derived" / "district_aggregates" / state / county / contest_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    agg_cols = {}
    for col in ["Registered", "BallotsCast", "Yes", "No"]:
        if col in df.columns:
            agg_cols[col] = "sum"
    if not agg_cols:
        agg_cols["BallotsCast"] = "sum"

    # Simple countywide aggregate (one row)
    agg = df[list(agg_cols.keys())].agg("sum").to_frame().T
    agg.insert(0, "Scope", "countywide")
    agg.insert(1, "State", state)
    agg.insert(2, "County", county)
    agg.insert(3, "ContestSlug", contest_slug)

    # Add computed pcts
    if "BallotsCast" in agg.columns and "Registered" in agg.columns:
        total_reg = agg["Registered"].sum()
        total_bal = agg["BallotsCast"].sum()
        agg["TurnoutPct"] = (total_bal / total_reg).round(6) if total_reg > 0 else 0.0
    if "Yes" in agg.columns and "No" in agg.columns:
        total_yn = agg["Yes"].sum() + agg["No"].sum()
        agg["YesPct"] = (agg["Yes"].sum() / total_yn).round(6) if total_yn > 0 else 0.0

    out_path = out_dir / f"{run_id}__district_aggregates.csv"
    agg.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


def export_kepler_geojson(
    df: pd.DataFrame,
    base_dir: str | Path,
    run_id: str,
    state: str,
    county: str,
    contest_slug: str,
    id_col: str = "PrecinctID",
) -> Path | None:
    """
    Write Kepler.gl-ready GeoJSON with vote properties embedded.
    Returns output path, or None if no geometry present.
    """
    base_dir = Path(base_dir)

    if "geometry" not in df.columns:
        return None

    try:
        import geopandas as gpd
        from shapely.geometry import mapping

        # Build property columns (exclude geometry; include vote metrics)
        prop_cols = [
            c for c in df.columns
            if c != "geometry" and not (hasattr(df[c], "dtype") and str(df[c].dtype) == "geometry")
        ]
        kepler_props = [
            "Registered", "BallotsCast", "TurnoutPct", "YesPct",
            "CompositeScore", "Tier", "Rank", "SwingIndex", "GeographyLevel",
        ]
        # Prefer kepler-specific columns first
        ordered = [c for c in kepler_props if c in prop_cols]
        rest = [c for c in prop_cols if c not in kepler_props]
        final_cols = [id_col] + ordered + rest if id_col in prop_cols else ordered + rest

        features = []
        for _, row in df.iterrows():
            geom = row.get("geometry")
            if geom is None or (hasattr(geom, "is_empty") and geom.is_empty):
                continue
            props = {c: row[c] for c in final_cols if c in row.index}
            # Convert numpy types for JSON serialization
            props = {
                k: (float(v) if hasattr(v, "item") and isinstance(v.item(), float) else
                    int(v) if hasattr(v, "item") and isinstance(v.item(), int) else
                    str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v)
                for k, v in props.items()
            }
            features.append({
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": props,
            })

        if not features:
            return None

        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "_meta": {
                "run_id": run_id,
                "state": state,
                "county": county,
                "contest_slug": contest_slug,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "kepler_config_hint": {
                    "color_by": "CompositeScore",
                    "tooltip_fields": ["Registered", "BallotsCast", "TurnoutPct", "YesPct", "Tier"],
                },
            },
        }

        out_dir = base_dir / "derived" / "maps" / state / county / contest_slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{run_id}__kepler.geojson"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
        return out_path

    except ImportError:
        return None
    except Exception:
        return None
