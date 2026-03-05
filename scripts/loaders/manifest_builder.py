"""
scripts/loaders/manifest_builder.py

Builds manifest.json for a jurisdiction data pack.
Walks Campaign in a box Data/<STATE>/<COUNTY>/ and records:
  - which category folders exist / are missing
  - files found per category (path, hash, size)
  - canonical geography (MPREC preferred over SRPREC)
  - detected ID fields
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .categories import (
    ALL_CATEGORIES,
    CROSSWALK_EXTENSIONS,
    FOLDER_TO_LABEL,
    GEOM_EXTENSIONS,
    MPREC_GEOM_CATEGORIES,
    SRPREC_GEOM_CATEGORIES,
)
from .file_loader import discover_files, sha256_file, file_size


GEOM_ALL_EXTENSIONS = [ext for exts in GEOM_EXTENSIONS.values() for ext in exts]


def build_manifest(data_root: str | Path, state: str, county: str) -> dict:
    """
    Build and return the manifest dict for a single jurisdiction.
    Does NOT write to disk — caller decides when to write.
    """
    data_root = Path(data_root)
    county_dir = data_root / state / county

    manifest: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "county": county,
        "county_dir": str(county_dir),
        "canonical_geography": None,
        "categories": {},
        "missing_categories": [],
        "present_categories": [],
        "known_id_fields": [],
        "normalization_rules": {
            "id_type": "string",
            "left_pad": True,
            "pad_char": "0",
            "note": "All precinct IDs normalized to zero-padded strings. Never float.",
        },
    }

    for cat_folder in ALL_CATEGORIES:
        cat_dir = county_dir / cat_folder
        human_label = FOLDER_TO_LABEL.get(cat_folder, cat_folder)

        # Determine what extensions to search
        if "GeoJSON" in cat_folder:
            exts = [".geojson"]
        elif "GeoPackage" in cat_folder:
            exts = [".gpkg"]
        elif "Shapefile" in cat_folder:
            exts = [".shp"]
        else:
            exts = CROSSWALK_EXTENSIONS + GEOM_ALL_EXTENSIONS

        files = discover_files(cat_dir, exts) if cat_dir.is_dir() else []
        # Exclude .gitkeep and other non-data files
        files = [f for f in files if f.suffix.lower() not in ("", ".gitkeep") and f.name != ".gitkeep"]

        file_records = []
        for f in files:
            file_records.append({
                "path": str(f),
                "filename": f.name,
                "size_bytes": file_size(f),
                "sha256": sha256_file(f),
            })

        present = len(file_records) > 0
        if present:
            manifest["present_categories"].append(cat_folder)
        else:
            manifest["missing_categories"].append(cat_folder)

        manifest["categories"][cat_folder] = {
            "label": human_label,
            "folder": str(cat_dir),
            "present": present,
            "files": file_records,
        }

    # Determine canonical geography
    mprec_present = any(
        manifest["categories"].get(c, {}).get("present")
        for c in MPREC_GEOM_CATEGORIES
    )
    srprec_present = any(
        manifest["categories"].get(c, {}).get("present")
        for c in SRPREC_GEOM_CATEGORIES
    )
    if mprec_present:
        manifest["canonical_geography"] = "MPREC"
    elif srprec_present:
        manifest["canonical_geography"] = "SRPREC"
    else:
        manifest["canonical_geography"] = "NONE"

    # Common CA precinct ID field names
    manifest["known_id_fields"] = [
        "MPREC_ID", "MasterPrecinctID", "mrprc_id",
        "SRPREC_ID", "SrPrecinctID",
        "GEOID", "GEOID20",
    ]

    return manifest


def write_manifest(data_root: str | Path, state: str, county: str) -> Path:
    """Build manifest and write to manifest.json. Returns path written."""
    data_root = Path(data_root)
    mf = build_manifest(data_root, state, county)
    out_path = data_root / state / county / "manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mf, f, indent=2, default=str)
    return out_path
