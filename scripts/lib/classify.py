"""
scripts/lib/classify.py

Deterministic file classification rules for the ingestion pipeline.

Maps raw filenames from STAGING_DIR to:
  - canonical category folder path (relative to county geography dir)
  - human-readable label (for manifest)

All rules are pattern-based (regex on lowercased filename stem).
Do NOT rename raw files — only classify and copy.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Classification:
    label: str           # Human-readable category label (for manifest)
    folder: str          # Folder path relative to county geography dir
    shapefile_bundle: bool = False  # True if .shp and must copy full bundle


# Ordered classification rules (first match wins)
# Format: (regex_pattern, Classification)
_RULES: list[tuple[str, Classification]] = [
    # ── Precinct shapes — MPREC ──────────────────────────────────────────
    (r"mprec[_\-].*\.geojson$", Classification(
        label="MPREC GeoJSON",
        folder="precinct_shapes/MPREC_GeoJSON",
    )),
    (r"mprec[_\-].*\.gpkg$", Classification(
        label="MPREC GeoPackage",
        folder="precinct_shapes/MPREC_GeoPackage",
    )),
    (r"mprec[_\-].*\.shp$", Classification(
        label="MPREC Shapefile",
        folder="precinct_shapes/MPREC_Shapefile",
        shapefile_bundle=True,
    )),

    # ── Precinct shapes — SRPREC ─────────────────────────────────────────
    (r"srprec[_\-].*\.geojson$", Classification(
        label="SRPREC GeoJSON",
        folder="precinct_shapes/SRPREC_GeoJSON",
    )),
    (r"srprec[_\-].*\.gpkg$", Classification(
        label="SRPREC GeoPackage",
        folder="precinct_shapes/SRPREC_GeoPackage",
    )),
    (r"srprec[_\-].*\.shp$", Classification(
        label="SRPREC Shapefile",
        folder="precinct_shapes/SRPREC_Shapefile",
        shapefile_bundle=True,
    )),

    # ── Crosswalks ───────────────────────────────────────────────────────
    (r"blk[_\-]mprec[_\-]", Classification(
        label="2020 BLK TO MPREC",
        folder="crosswalks",
    )),
    (r"[_\-]rg[_\-]blk[_\-]map", Classification(
        label="RGPREC TO 2020 BLK",
        folder="crosswalks",
    )),
    (r"[_\-]sr[_\-]blk[_\-]map", Classification(
        label="SRPREC TO 2020 BLK",
        folder="crosswalks",
    )),
    (r"rg[_\-]rr[_\-]sr[_\-]svprec", Classification(
        label="RG to RR to SR to SVPREC",
        folder="crosswalks",
    )),
    (r"mprec[_\-]srprec", Classification(
        label="MPREC to SRPREC",
        folder="crosswalks",
    )),
    (r"srprec[_\-]to[_\-]city", Classification(
        label="SRPREC to CITY",
        folder="crosswalks",
    )),
]

# Shapefile sidecar extensions (copied alongside .shp)
SHAPEFILE_SIDECAR_EXTS = {".shx", ".dbf", ".prj", ".cpg", ".qix"}

# File extensions to ignore entirely (metadata/temp files)
IGNORED_EXTENSIONS = {
    ".lock", ".log", ".tmp", ".bak", ".orig",
    ".DS_Store", ".gitkeep",
}


def classify_file(path: str | Path) -> Classification | None:
    """
    Classify a file using deterministic rules.
    Returns a Classification or None if the file doesn't match any rule.
    """
    p = Path(path)
    if p.suffix.lower() in IGNORED_EXTENSIONS:
        return None
    # Match against rules (case-insensitive on filename)
    name_lower = p.name.lower()
    for pattern, cls in _RULES:
        if re.search(pattern, name_lower):
            return cls
    return None


def get_shapefile_bundle(shp_path: Path) -> list[Path]:
    """
    Return all sidecar files for a .shp file that exist on disk.
    Includes the .shp itself.
    """
    stem = shp_path.stem
    parent = shp_path.parent
    files = [shp_path]
    for ext in SHAPEFILE_SIDECAR_EXTS:
        candidate = parent / (stem + ext)
        if candidate.exists():
            files.append(candidate)
    return files


def label_to_folder_name(label: str) -> str:
    """Convert a human-readable label to a filesystem folder name."""
    return re.sub(r"[^a-zA-Z0-9]+", "_", label).strip("_")
