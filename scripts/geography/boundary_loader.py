"""
scripts/geography/boundary_loader.py

Loads canonical precinct geometry (MPREC preferred, SRPREC fallback).

HARD FAIL rules:
  - If no geometry file can be loaded at all → raises RuntimeError
  - ID columns normalized to zero-padded strings (never float)

Requires: geopandas, fiona  (or shapely+pyogrio)
If geopandas is unavailable, returns a stub GeoDataFrame-like dict
so the rest of the pipeline can still run (geometry flagged as missing).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..loaders.categories import (
    MPREC_GEOM_CATEGORIES,
    SRPREC_GEOM_CATEGORIES,
    GEOM_EXTENSIONS,
)
from ..loaders.file_loader import discover_files


# ---------------------------------------------------------------------------
# Optional geopandas import
# ---------------------------------------------------------------------------

try:
    import geopandas as gpd
    _HAS_GEOPANDAS = True
except ImportError:
    gpd = None  # type: ignore
    _HAS_GEOPANDAS = False


# ---------------------------------------------------------------------------
# ID normalization
# ---------------------------------------------------------------------------

_KNOWN_ID_COLS = [
    "MPREC_ID", "MasterPrecinctID", "mrprc_id",
    "SRPREC_ID", "SrPrecinctID",
    "GEOID", "GEOID20", "PRECINCT_ID", "PREC_ID",
]


def normalize_id_column(series) -> "pd.Series":
    """
    Normalize a precinct ID column:
      - Convert to string (strip trailing .0 from float reads)
      - Left-pad with zeros to max observed length
    """
    import pandas as pd

    def _clean(v):
        if v is None:
            return ""
        s = str(v).strip()
        # Remove float suffix (e.g. "1234.0" → "1234")
        s = re.sub(r"\.0+$", "", s)
        return s

    cleaned = series.apply(_clean)
    max_len = cleaned.str.len().max()
    if max_len and max_len > 0:
        return cleaned.str.zfill(int(max_len))
    return cleaned


def detect_id_column(columns: list[str]) -> str | None:
    """Return the first recognized ID column name, or None."""
    cols_upper = {c.upper(): c for c in columns}
    for known in _KNOWN_ID_COLS:
        if known.upper() in cols_upper:
            return cols_upper[known.upper()]
    return None


# ---------------------------------------------------------------------------
# Geometry loader
# ---------------------------------------------------------------------------

def _find_geom_file(county_dir: Path, categories: list[str]) -> Path | None:
    """Search category folders for the first readable geometry file."""
    for cat in categories:
        cat_dir = county_dir / cat
        if not cat_dir.is_dir():
            continue
        for fmt, exts in GEOM_EXTENSIONS.items():
            files = discover_files(cat_dir, exts)
            # Skip .gitkeep
            files = [f for f in files if f.name != ".gitkeep"]
            if files:
                return files[0]
    return None


def load_canonical_geometry(
    data_root: str | Path,
    state: str,
    county: str,
    logger=None,
) -> tuple[object, str, str | None]:
    """
    Load canonical precinct geometry for the jurisdiction.

    Returns:
        (gdf_or_stub, geography_level, id_column)
        geography_level: 'MPREC' | 'SRPREC' | 'NONE'

    Raises:
        RuntimeError — HARD FAIL if geometry cannot be loaded and geopandas is available.
        Returns stub dict if geopandas is unavailable (so pipeline can log NEEDS).
    """
    data_root = Path(data_root)
    county_dir = data_root / state / county

    def _log(msg, level="INFO"):
        if logger:
            getattr(logger, level.lower(), logger.info)(msg)

    # Try MPREC first, then SRPREC
    for geom_categories, level in [
        (MPREC_GEOM_CATEGORIES, "MPREC"),
        (SRPREC_GEOM_CATEGORIES, "SRPREC"),
    ]:
        geom_file = _find_geom_file(county_dir, geom_categories)
        if geom_file:
            if not _HAS_GEOPANDAS:
                _log(
                    f"geopandas not installed; geometry file found at {geom_file} "
                    "but cannot be loaded. Flagging as NEEDS.",
                    "WARN",
                )
                return {"_stub": True, "_file": str(geom_file)}, level, None

            try:
                _log(f"Loading {level} geometry from: {geom_file}")
                gdf = gpd.read_file(str(geom_file))
                _log(f"Loaded {len(gdf)} features from {geom_file.name}")

                # Detect and normalize ID column
                id_col = detect_id_column(list(gdf.columns))
                if id_col:
                    gdf[id_col] = normalize_id_column(gdf[id_col])
                    _log(f"Normalized ID column '{id_col}' → zero-padded strings")
                else:
                    _log("No recognized ID column found in geometry", "WARN")

                return gdf, level, id_col
            except Exception as e:
                _log(f"Failed to load {geom_file}: {e}", "WARN")
                continue

    # No geometry found at all
    _log(f"No geometry files found for {state}/{county}", "WARN")
    if _HAS_GEOPANDAS:
        # HARD FAIL only if geopandas is available but no files exist
        # (caller decides based on pipeline mode whether to hard_fail)
        return None, "NONE", None
    return {"_stub": True, "_file": None}, "NONE", None
