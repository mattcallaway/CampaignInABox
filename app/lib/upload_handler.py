"""
app/lib/upload_handler.py

Handles file uploads: routes to correct county geography folder,
detects incomplete shapefile bundles, updates manifest.json.
"""
from __future__ import annotations
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_ROOT = BASE_DIR / "data"
VOTES_ROOT = BASE_DIR / "votes"
VOTERS_ROOT = BASE_DIR / "voters"

SHAPEFILE_SIDECAR = {".shx", ".dbf", ".prj", ".cpg", ".qix"}
SHAPEFILE_REQUIRED = {".shp", ".shx", ".dbf"}

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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def save_geography_files(
    uploaded_files: list,  # Streamlit UploadedFile objects
    category: str,
    county: str,
    state: str = "CA",
) -> tuple[list[dict], list[str]]:
    """
    Save uploaded geography/crosswalk files to correct folder.
    Returns (saved_records, warnings).
    """
    folder_rel = CATEGORY_TO_FOLDER.get(category, "crosswalks")
    dest_dir = DATA_ROOT / state / "counties" / county / "geography" / folder_rel
    dest_dir.mkdir(parents=True, exist_ok=True)

    saved: list[dict] = []
    warnings: list[str] = []
    uploaded_names = {f.name for f in uploaded_files}
    is_shapefile_category = "Shapefile" in category

    # Shapefile bundle completeness check
    if is_shapefile_category:
        shp_files = [f for f in uploaded_files if f.name.lower().endswith(".shp")]
        for shp in shp_files:
            stem = Path(shp.name).stem
            missing = []
            for req_ext in (".shx", ".dbf"):
                if f"{stem}{req_ext}" not in uploaded_names and f"{stem}{req_ext.upper()}" not in uploaded_names:
                    missing.append(req_ext)
            if missing:
                warnings.append(f"Shapefile bundle incomplete for '{shp.name}': missing {missing}")

    for uf in uploaded_files:
        data = uf.getvalue()
        dest = dest_dir / uf.name
        dest.write_bytes(data)
        saved.append({
            "filename": uf.name,
            "path": str(dest),
            "size_bytes": len(data),
            "sha256": _sha256_bytes(data),
            "category_label": category,
            "category_folder": folder_rel,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        })

    # Refresh manifest
    _update_geo_manifest(county, state, saved)
    return saved, warnings


def save_votes_file(
    uploaded_file,
    year: str,
    county: str,
    contest_slug: str,
    state: str = "CA",
) -> tuple[Path, Path]:
    """
    Save detail.xlsx/xls to votes/<year>/<state>/<county>/<contest_slug>/.
    Creates contest.json placeholder and manifest.json.
    Returns (detail_path, contest_json_path).
    """
    dest_dir = VOTES_ROOT / year / state / county / contest_slug
    dest_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(uploaded_file.name).suffix.lower()
    dest_name = f"detail{ext}"
    dest = dest_dir / dest_name
    data = uploaded_file.getvalue()
    dest.write_bytes(data)

    # Contest JSON placeholder
    contest_json = dest_dir / "contest.json"
    if not contest_json.exists():
        payload = {
            "contest_slug": contest_slug,
            "year": year,
            "state": state,
            "county": county,
            "detail_file": dest_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "contest_type": "unknown",
        }
        contest_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Votes manifest
    manifest = dest_dir / "manifest.json"
    mf = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "year": year, "state": state, "county": county,
        "contest_slug": contest_slug,
        "files": [{"filename": dest_name, "size_bytes": len(data),
                   "sha256": _sha256_bytes(data)}],
    }
    manifest.write_text(json.dumps(mf, indent=2), encoding="utf-8")
    return dest, contest_json


def save_voter_file(uploaded_file, county: str, state: str = "CA") -> Path:
    """Save voter file to voters/<state>/<county>/."""
    dest_dir = VOTERS_ROOT / state / county
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / uploaded_file.name
    dest.write_bytes(uploaded_file.getvalue())
    # Update manifest
    manifest = dest_dir / "manifest.json"
    mf_data = {"optional_voter_file": True, "filename": uploaded_file.name,
                "uploaded_at": datetime.now(timezone.utc).isoformat()}
    manifest.write_text(json.dumps(mf_data, indent=2), encoding="utf-8")
    return dest


def _update_geo_manifest(county: str, state: str, new_records: list[dict]):
    """Merge new file records into the county geography manifest.json."""
    mp = DATA_ROOT / state / "counties" / county / "geography" / "manifest.json"
    mf: dict = {}
    if mp.exists():
        try:
            mf = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            mf = {}

    existing = {r["filename"]: r for r in mf.get("files", [])}
    for rec in new_records:
        existing[rec["filename"]] = rec

    mf["generated_at"] = datetime.now(timezone.utc).isoformat()
    mf.setdefault("county", county)
    mf.setdefault("state", state)
    mf["files"] = list(existing.values())

    # Inline category presence scan (avoids circular import)
    geo_dir = DATA_ROOT / state / "counties" / county / "geography"
    all_labels = list(CATEGORY_TO_FOLDER.keys())
    geo_exts = {".geojson", ".gpkg", ".shp"}
    xwalk_exts = {".csv", ".tsv", ".xlsx", ".xls"}
    present, missing = [], []
    for label in all_labels:
        folder = geo_dir / CATEGORY_TO_FOLDER.get(label, "")
        is_geo = label in {"MPREC GeoJSON","MPREC GeoPackage","MPREC Shapefile",
                           "SRPREC GeoJSON","SRPREC GeoPackage","SRPREC Shapefile"}
        exts = geo_exts if is_geo else xwalk_exts
        has_data = folder.is_dir() and any(
            f.suffix.lower() in exts
            for f in folder.iterdir()
            if f.is_file() and f.name != ".gitkeep"
        ) if folder.is_dir() else False
        (present if has_data else missing).append(label)

    mf["categories_present"] = present
    mf["categories_missing"] = missing
    mf["canonical_geography"] = (
        "MPREC" if any("MPREC" in k for k in present)
        else "SRPREC" if any("SRPREC" in k for k in present)
        else "NONE"
    )
    mp.write_text(json.dumps(mf, indent=2), encoding="utf-8")
