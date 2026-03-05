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
import re
from pathlib import Path

from scripts.lib.naming import normalize_contest_slug, generate_contest_id
from scripts.lib.county_registry import get_county_by_fips

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

def detect_county_from_filenames(filenames: list[str]) -> tuple[str | None, str]:
    """
    Looks for pattern c###_ or _###_ where ### is a 3-digit FIPS code.
    Returns (Canonical County Name, detection_method_string).
    """
    for fname in filenames:
        # Match 'c' followed by 3 digits then underscore/dot
        match = re.search(r'(?:^|[^a-zA-Z0-9])c(\d{3})(?:_|\.)', fname, re.IGNORECASE)
        if not match:
            # Match underscore followed by 3 digits then underscore/dot
            match = re.search(r'_(\d{3})(?:_|\.)', fname)
            
        if match:
            fips = match.group(1)
            record = get_county_by_fips(fips)
            if record:
                return record["county_name"], f"regex match on {fname} for FIPS {fips}"
    return None, "explicit selection"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


from app.lib.archiver import archive_file, get_archive_dest
from app.lib.audit_logger import log_update_event
from app.lib.state_manager import mark_stale, determine_stale_domains_for_update


def save_geography_files(
    uploaded_files: list,  # Streamlit UploadedFile objects
    category: str,
    county: str,
    state: str = "CA",
    detection_method: str = "explicit selection",
) -> tuple[list[dict], list[str]]:
    """
    Save uploaded geography/crosswalk files to correct folder.
    Archives old files, logs event, and marks derivatives stale.
    Returns (saved_records, warnings).
    """
    folder_rel = CATEGORY_TO_FOLDER.get(category, "crosswalks")
    dest_dir = DATA_ROOT / state / "counties" / county / "geography" / folder_rel
    dest_dir.mkdir(parents=True, exist_ok=True)

    saved: list[dict] = []
    warnings: list[str] = []
    uploaded_names = {f.name for f in uploaded_files}
    is_shapefile_category = "Shapefile" in category

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
                
    # Log the registry resolution and detection method
    from scripts.lib.county_registry import normalize_county_input
    c_record = normalize_county_input(county)
    print(f"[INGESTION] County detected via {detection_method}. Resolved: {c_record}")

    # Generate a single timestamp for this batch upload
    from datetime import datetime, timezone
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    domains_stale = determine_stale_domains_for_update(category)
    context_key = f"{state}/{county}"

    for uf in uploaded_files:
        data = uf.getvalue()
        dest = dest_dir / uf.name
        
        old_record = None
        archive_path = None
        action = "add"

        if dest.exists():
            action = "replace"
            old_data = dest.read_bytes()
            old_record = {
                "filename": dest.name,
                "size_bytes": len(old_data),
                "sha256": _sha256_bytes(old_data),
            }
            archive_path = archive_file(dest, now_ts, "geography", county, state=state)

        dest.write_bytes(data)
        new_record = {
            "filename": uf.name,
            "path": str(dest),
            "size_bytes": len(data),
            "sha256": _sha256_bytes(data),
            "category_label": category,
            "category_folder": folder_rel,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        saved.append(new_record)

        log_update_event(
            action=action,
            category=category,
            county=county,
            contest=None,
            old_file_record=old_record,
            new_file_record=new_record,
            archive_dest=str(archive_path.parent) if archive_path else None,
            derived_stale=domains_stale,
        )

    # Refresh manifest
    _update_geo_manifest(county, state, saved)

    # Mark stale
    if saved:
        mark_stale(context_key, f"Geography replaced: {category}", domains_stale)

    return saved, warnings


def save_votes_file(
    uploaded_file,
    year: str,
    county: str,
    contest_slug: str,
    state: str = "CA",
) -> tuple[Path, Path]:
    """
    Save detail.xlsx/xls, archiving old version if present.
    Creates contest.json placeholder, manifest.json, marks derivatives stale.
    Returns (detail_path, contest_json_path).
    """
    dest_dir = VOTES_ROOT / year / state / county / contest_slug
    dest_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(uploaded_file.name).suffix.lower()
    dest_name = f"detail{ext}"
    dest = dest_dir / dest_name
    data = uploaded_file.getvalue()

    from datetime import datetime, timezone
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    
    old_record = None
    archive_path = None
    action = "add"

    if dest.exists():
        action = "replace"
        old_data = dest.read_bytes()
        old_record = {
            "filename": dest.name,
            "size_bytes": len(old_data),
            "sha256": _sha256_bytes(old_data),
        }
        archive_path = archive_file(dest, now_ts, "votes", county, year=year, contest=contest_slug, state=state)

    dest.write_bytes(data)

    new_record = {
        "filename": dest_name,
        "size_bytes": len(data),
        "sha256": _sha256_bytes(data),
    }

    domains_stale = determine_stale_domains_for_update("detail")
    context_key = f"{state}/{county}/{year}/{contest_slug}"

    log_update_event(
        action=action,
        category="detail.xlsx",
        county=county,
        contest=contest_slug,
        old_file_record=old_record,
        new_file_record=new_record,
        archive_dest=str(archive_path.parent) if archive_path else None,
        derived_stale=domains_stale,
    )
    mark_stale(context_key, f"Votes replaced: {dest_name}", domains_stale)

    # Contest JSON placeholder
    contest_json = dest_dir / "contest.json"
    
    # ALWAYS read existing to preserve or init new
    payload = {}
    if contest_json.exists():
        try:
            payload = json.loads(contest_json.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Ensure canonical IDs are stamped
    canonical_slug = normalize_contest_slug(contest_slug)
    contest_id = generate_contest_id(year, state, county.lower().replace(" ", "_"), canonical_slug)

    payload["contest_slug"] = canonical_slug
    payload["contest_id"] = contest_id
    payload["year"] = year
    payload["state"] = state
    payload["county"] = county
    payload["detail_file"] = dest_name
    payload["original_filename"] = uploaded_file.name
    
    if "created_at" not in payload:
        payload["created_at"] = datetime.now(timezone.utc).isoformat()
    if "contest_type" not in payload:
        payload["contest_type"] = "unknown"

    contest_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Votes manifest
    manifest = dest_dir / "manifest.json"
    mf = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "year": year, "state": state, "county": county,
        "contest_slug": contest_slug,
        "files": [new_record],
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
