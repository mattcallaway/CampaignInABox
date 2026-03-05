"""
scripts/validation/boundary_index.py

Boundary aggregation framework scaffold.

Manages boundary_index/boundaries_index.csv — the registry of all
district boundary files for a county (supervisorial, city council, school, etc.).

Output schema for membership tables:
  mprec, boundary_type, jurisdiction_name, level, boundary_id, boundary_name,
  weight, method
"""

from __future__ import annotations

import csv
from pathlib import Path

# ── Index CSV columns ─────────────────────────────────────────────────────────
INDEX_COLUMNS = [
    "boundary_type",
    "jurisdiction_name",
    "level",
    "file_path",
    "id_field_name",
    "name_field_name",
]

# ── Membership table columns ──────────────────────────────────────────────────
MEMBERSHIP_COLUMNS = [
    "mprec",
    "boundary_type",
    "jurisdiction_name",
    "level",
    "boundary_id",
    "boundary_name",
    "weight",
    "method",
]

# Boundary type → canonical subfolder mapping
BOUNDARY_SUBFOLDERS = {
    "supervisorial":  "boundaries/supervisorial",
    "city_council":   "boundaries/city_council",
    "school":         "boundaries/school",
}


def get_boundary_index_path(data_root: Path, county: str) -> Path:
    """Return path to the boundaries_index.csv for a county."""
    return (
        data_root / "CA" / "counties" / county
        / "geography" / "boundary_index" / "boundaries_index.csv"
    )


def scaffold_boundary_index(data_root: Path, county: str, log=None) -> Path:
    """
    Create an empty boundaries_index.csv if it doesn't exist.
    If it exists, leave it intact.
    Returns the path.
    """
    def _log(msg, level="INFO"):
        if log:
            getattr(log, level.lower(), log.info)(msg)

    index_path = get_boundary_index_path(data_root, county)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    if not index_path.exists():
        with open(index_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS)
            writer.writeheader()
        _log(f"  Scaffolded boundary index: {index_path}")
    else:
        _log(f"  Boundary index exists: {index_path}")

    return index_path


def scan_boundary_files(data_root: Path, county: str) -> list[dict]:
    """
    Scan boundaries/ subfolders for GIS files and return index rows.
    Does NOT modify the index file; caller decides when to write.
    """
    geo_dir = data_root / "CA" / "counties" / county / "geography"
    rows = []
    for boundary_type, subfolder in BOUNDARY_SUBFOLDERS.items():
        folder = geo_dir / subfolder
        if not folder.is_dir():
            continue
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.suffix.lower() in {".geojson", ".gpkg", ".shp"} and f.name != ".gitkeep":
                rows.append({
                    "boundary_type":    boundary_type,
                    "jurisdiction_name": f.stem,
                    "level":            boundary_type,
                    "file_path":        str(f),
                    "id_field_name":    "",   # to be filled after inspection
                    "name_field_name":  "",
                })
    return rows


def refresh_boundary_index(data_root: Path, county: str, log=None) -> Path:
    """
    Scan boundary folders, update/write boundaries_index.csv.
    Returns path written.
    """
    def _log(msg, level="INFO"):
        if log:
            getattr(log, level.lower(), log.info)(msg)

    rows = scan_boundary_files(data_root, county)
    index_path = get_boundary_index_path(data_root, county)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    with open(index_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    if rows:
        _log(f"  Boundary index updated: {len(rows)} entries")
    else:
        _log("  Boundary index scaffolded (no boundary files found yet)", "WARN")
    return index_path


def build_membership_table(
    mprec_ids: list[str],
    boundary_rows: list[dict],
    method: str = "area_weighted",
) -> list[dict]:
    """
    Scaffold a membership table matching each MPREC to each boundary.
    Returns list of dicts conforming to MEMBERSHIP_COLUMNS schema.
    NOTE: weights are placeholder 1.0 until actual spatial join is run.
    """
    records = []
    for mprec_id in mprec_ids:
        for row in boundary_rows:
            records.append({
                "mprec":             mprec_id,
                "boundary_type":     row.get("boundary_type", ""),
                "jurisdiction_name": row.get("jurisdiction_name", ""),
                "level":             row.get("level", ""),
                "boundary_id":       "",      # filled after spatial join
                "boundary_name":     "",      # filled after spatial join
                "weight":            1.0,     # placeholder
                "method":            method,
            })
    return records
