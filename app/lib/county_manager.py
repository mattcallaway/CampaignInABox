"""
app/lib/county_manager.py

Utilities for discovering and initializing counties.
"""
from __future__ import annotations
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Campaign In A Box/
DATA_ROOT = BASE_DIR / "data"
GEOGRAPHY_SUBFOLDERS = [
    "precinct_shapes/MPREC_GeoJSON",
    "precinct_shapes/MPREC_GeoPackage",
    "precinct_shapes/MPREC_Shapefile",
    "precinct_shapes/SRPREC_GeoJSON",
    "precinct_shapes/SRPREC_GeoPackage",
    "precinct_shapes/SRPREC_Shapefile",
    "crosswalks",
    "boundaries/supervisorial",
    "boundaries/city_council",
    "boundaries/school",
    "boundary_index",
]

ALL_CATEGORY_LABELS = [
    "MPREC GeoJSON", "MPREC GeoPackage", "MPREC Shapefile",
    "SRPREC GeoJSON", "SRPREC GeoPackage", "SRPREC Shapefile",
    "2020 BLK TO MPREC", "RGPREC TO 2020 BLK", "SRPREC TO 2020 BLK",
    "RG to RR to SR to SVPREC", "MPREC to SRPREC", "SRPREC to CITY",
]

CATEGORY_TO_FOLDER = {
    "MPREC GeoJSON":             "precinct_shapes/MPREC_GeoJSON",
    "MPREC GeoPackage":          "precinct_shapes/MPREC_GeoPackage",
    "MPREC Shapefile":           "precinct_shapes/MPREC_Shapefile",
    "SRPREC GeoJSON":            "precinct_shapes/SRPREC_GeoJSON",
    "SRPREC GeoPackage":         "precinct_shapes/SRPREC_GeoPackage",
    "SRPREC Shapefile":          "precinct_shapes/SRPREC_Shapefile",
    "2020 BLK TO MPREC":         "crosswalks",
    "RGPREC TO 2020 BLK":        "crosswalks",
    "SRPREC TO 2020 BLK":        "crosswalks",
    "RG to RR to SR to SVPREC":  "crosswalks",
    "MPREC to SRPREC":           "crosswalks",
    "SRPREC to CITY":            "crosswalks",
}

GEO_EXTS = {".geojson", ".gpkg", ".shp"}
CROSSWALK_EXTS = {".csv", ".tsv", ".xlsx", ".xls"}
SHAPEFILE_SIDECAR = {".shx", ".dbf", ".prj", ".cpg", ".qix"}


def discover_counties(state: str = "CA") -> list[str]:
    """Return sorted list of county names that have been initialized."""
    county_root = DATA_ROOT / state / "counties"
    if not county_root.is_dir():
        return []
    return sorted(d.name for d in county_root.iterdir() if d.is_dir())


def initialize_county(county: str, state: str = "CA") -> Path:
    """Create full folder skeleton for a county. Safe to call if already exists."""
    geo_dir = DATA_ROOT / state / "counties" / county / "geography"
    for sub in GEOGRAPHY_SUBFOLDERS:
        p = geo_dir / sub
        p.mkdir(parents=True, exist_ok=True)
        gk = p / ".gitkeep"
        if not gk.exists():
            gk.touch()
    # Scaffold empty boundary index
    bi = geo_dir / "boundary_index" / "boundaries_index.csv"
    if not bi.exists():
        bi.write_text("boundary_type,jurisdiction_name,level,file_path,id_field_name,name_field_name\n",
                      encoding="utf-8")
    return geo_dir


def get_geography_status(county: str, state: str = "CA") -> dict:
    """Return presence/absence for all 12 named categories."""
    geo_dir = DATA_ROOT / state / "counties" / county / "geography"
    status = {}
    for label in ALL_CATEGORY_LABELS:
        folder = geo_dir / CATEGORY_TO_FOLDER.get(label, "")
        is_geo = label in ("MPREC GeoJSON","MPREC GeoPackage","MPREC Shapefile",
                           "SRPREC GeoJSON","SRPREC GeoPackage","SRPREC Shapefile")
        exts = GEO_EXTS if is_geo else CROSSWALK_EXTS
        present = folder.is_dir() and any(
            f.suffix.lower() in exts
            for f in folder.iterdir()
            if f.is_file() and f.name != ".gitkeep"
        ) if folder.is_dir() else False
        status[label] = present
    return status


def discover_contests(state: str = "CA") -> list[dict]:
    """Scan votes/ tree and return list of {year, county, contest_slug, detail_path}."""
    votes_root = BASE_DIR / "votes"
    results = []
    if not votes_root.is_dir():
        return results
    for year_dir in sorted(votes_root.iterdir()):
        if not year_dir.is_dir(): continue
        state_dir = year_dir / state
        if not state_dir.is_dir(): continue
        for county_dir in sorted(state_dir.iterdir()):
            if not county_dir.is_dir(): continue
            for contest_dir in sorted(county_dir.iterdir()):
                if not contest_dir.is_dir(): continue
                detail = None
                for ext in (".xlsx", ".xls"):
                    c = contest_dir / f"detail{ext}"
                    if c.exists():
                        detail = c
                        break
                # Peek at contest.json
                meta = {}
                cj = contest_dir / "contest.json"
                if cj.exists():
                    try:
                        meta = json.loads(cj.read_text(encoding="utf-8"))
                    except Exception:
                        pass

                results.append({
                    "year": year_dir.name,
                    "county": county_dir.name,
                    "contest_slug": contest_dir.name,
                    "detail_path": str(detail) if detail else None,
                    "has_votes": detail is not None,
                    "type": meta.get("contest_type", "unknown"),
                    "candidates": meta.get("candidates", []),
                    "measures": meta.get("measures", []),
                })
    return results


def read_manifest(county: str, state: str = "CA") -> dict | None:
    mp = DATA_ROOT / state / "counties" / county / "geography" / "manifest.json"
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        return None
