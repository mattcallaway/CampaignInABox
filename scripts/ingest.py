"""
scripts/ingest.py

STAGING_DIR → canonical data store ingestion pipeline.

Scans STAGING_DIR recursively:
  - Extracts any .zip archives to staging/extracted/<zipname>/
  - Classifies each file by deterministic filename rules
  - Identifies county from FIPS code in filename
  - Copies (never renames) files into:
      data/CA/counties/<CountyName>/geography/<category_subfolder>/
  - Writes/refreshes manifest.json per county

Usage (standalone):
    python scripts/ingest.py --staging-dir <path> [--dry-run] [--log-level verbose]

Also called internally by run_pipeline.py before the modeling steps.
"""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .lib.ca_fips import extract_fips_from_filename, fips_to_county
from .lib.classify import (
    Classification,
    classify_file,
    get_shapefile_bundle,
    IGNORED_EXTENSIONS,
)
from .lib.hashing import file_info, sha256_file

BASE_DIR = Path(__file__).resolve().parent.parent  # Campaign In A Box/

# ── Category labels for manifest completeness check ──────────────────────────
ALL_CATEGORY_LABELS = [
    "MPREC GeoJSON",
    "MPREC GeoPackage",
    "MPREC Shapefile",
    "SRPREC GeoJSON",
    "SRPREC GeoPackage",
    "SRPREC Shapefile",
    "2020 BLK TO MPREC",
    "RGPREC TO 2020 BLK",
    "SRPREC TO 2020 BLK",
    "RG to RR to SR to SVPREC",
    "MPREC to SRPREC",
    "SRPREC to CITY",
]

MPREC_LABELS = {"MPREC GeoJSON", "MPREC GeoPackage", "MPREC Shapefile"}
SRPREC_LABELS = {"SRPREC GeoJSON", "SRPREC GeoPackage", "SRPREC Shapefile"}


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Discover files in STAGING_DIR (including inside zips)
# ─────────────────────────────────────────────────────────────────────────────

def discover_staging_files(
    staging_dir: Path,
    extract_root: Path,
    log=None,
) -> list[Path]:
    """
    Recursively walk staging_dir. Extract any .zip files encountered.
    Returns flat list of all concrete file paths to classify.
    """
    def _log(msg, level="INFO"):
        if log:
            getattr(log, level.lower(), log.info)(msg)

    all_files: list[Path] = []

    for item in sorted(staging_dir.rglob("*")):
        if not item.is_file():
            continue
        if item.suffix.lower() in IGNORED_EXTENSIONS:
            continue

        if item.suffix.lower() == ".zip":
            _log(f"  Found zip: {item.name} — extracting...")
            extract_dir = extract_root / item.stem
            extract_dir.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(item, "r") as zf:
                    zf.extractall(extract_dir)
                _log(f"    Extracted to: {extract_dir}")
                # Add all extracted files
                for extracted in sorted(extract_dir.rglob("*")):
                    if extracted.is_file() and extracted.suffix.lower() not in IGNORED_EXTENSIONS:
                        all_files.append(extracted)
            except Exception as e:
                _log(f"    Failed to extract {item.name}: {e}", "WARN")
        else:
            all_files.append(item)

    _log(f"Discovered {len(all_files)} files in staging (after zip extraction)")
    return all_files


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Classify and route files to canonical county geography paths
# ─────────────────────────────────────────────────────────────────────────────

def route_file(
    src_path: Path,
    data_root: Path,
    county_name: str,
    cls: Classification,
    dry_run: bool = False,
    log=None,
) -> list[dict]:
    """
    Copy src_path (and shapefile bundle if applicable) to canonical location.
    Returns list of file_info dicts for manifest.
    """
    def _log(msg, level="INFO"):
        if log:
            getattr(log, level.lower(), log.info)(msg)

    geo_dir = data_root / "CA" / "counties" / county_name / "geography"
    dest_dir = geo_dir / cls.folder
    dest_dir.mkdir(parents=True, exist_ok=True)

    files_to_copy = (
        get_shapefile_bundle(src_path) if cls.shapefile_bundle
        else [src_path]
    )
    results = []
    for src in files_to_copy:
        dest = dest_dir / src.name
        if not dry_run:
            shutil.copy2(src, dest)
        _log(f"  {'[DRY-RUN] would copy' if dry_run else 'Copied'}: {src.name} -> {cls.folder}/")
        results.append({
            **file_info(dest if not dry_run else src),
            "category_label": cls.label,
            "category_folder": cls.folder,
            "source_path": str(src),
        })
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Build/refresh manifest.json
# ─────────────────────────────────────────────────────────────────────────────

def build_county_manifest(
    data_root: Path,
    county_name: str,
    file_records: list[dict],
) -> dict:
    """Build the county geography manifest dict."""
    geo_dir = data_root / "CA" / "counties" / county_name / "geography"

    # Group by category label
    by_label: dict[str, list[dict]] = {}
    for rec in file_records:
        label = rec.get("category_label", "unknown")
        by_label.setdefault(label, []).append(rec)

    present = [lbl for lbl in ALL_CATEGORY_LABELS if lbl in by_label]
    missing = [lbl for lbl in ALL_CATEGORY_LABELS if lbl not in by_label]

    has_mprec = any(lbl in by_label for lbl in MPREC_LABELS)
    has_srprec = any(lbl in by_label for lbl in SRPREC_LABELS)
    canonical_geo = "MPREC" if has_mprec else ("SRPREC" if has_srprec else "NONE")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "county": county_name,
        "state": "CA",
        "geography_dir": str(geo_dir),
        "canonical_geography": canonical_geo,
        "categories_present": present,
        "categories_missing": missing,
        "known_id_fields": [
            "MPREC_ID", "MasterPrecinctID", "mrprc_id",
            "SRPREC_ID", "SrPrecinctID", "GEOID", "GEOID20",
        ],
        "normalization_rules": {
            "id_type": "string",
            "left_pad": True,
            "pad_char": "0",
            "note": "IDs normalized to zero-padded strings. Never float.",
        },
        "files": file_records,
    }


def write_county_manifest(data_root: Path, county_name: str, file_records: list[dict]) -> Path:
    """Write/refresh manifest.json. Returns path written."""
    mf = build_county_manifest(data_root, county_name, file_records)
    out_path = (
        data_root / "CA" / "counties" / county_name / "geography" / "manifest.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mf, f, indent=2, default=str)
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Main ingestion orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def run_ingestion(
    staging_dir: str | Path,
    data_root: str | Path | None = None,
    dry_run: bool = False,
    log=None,
) -> dict[str, list[dict]]:
    """
    Full ingestion: staging → canonical data store.

    Parameters
    ----------
    staging_dir : path to STAGING_DIR (user-provided)
    data_root   : path to data/ directory (default: BASE_DIR/data)
    dry_run     : if True, classify but do not copy files
    log         : RunLogger instance or None

    Returns
    -------
    dict mapping county_name → list of file_info records ingested
    """
    staging_dir = Path(staging_dir)
    data_root = Path(data_root) if data_root else BASE_DIR / "data"
    extract_root = BASE_DIR / "staging" / "extracted"

    def _log(msg, level="INFO"):
        if log:
            getattr(log, level.lower(), log.info)(msg)
        else:
            print(f"[INGEST][{level}] {msg}")

    _log(f"Ingestion starting")
    _log(f"  STAGING_DIR : {staging_dir}")
    _log(f"  data_root   : {data_root}")
    _log(f"  dry_run     : {dry_run}")

    if not staging_dir.exists():
        _log(f"STAGING_DIR does not exist: {staging_dir}", "WARN")
        return {}

    # ── Discover files ────────────────────────────────────────────────────
    all_files = discover_staging_files(staging_dir, extract_root, log=type('L', (), {
        'info': lambda self, m: _log(m), 'warn': lambda self, m: _log(m, "WARN")
    })())

    # ── Classify + route ──────────────────────────────────────────────────
    county_records: dict[str, list[dict]] = {}
    unclassified: list[Path] = []

    for src in all_files:
        cls = classify_file(src)
        if cls is None:
            unclassified.append(src)
            continue

        # Identify county
        fips = extract_fips_from_filename(src.name)
        county = fips_to_county(fips) if fips else None

        # Fallback: try parent directory names
        if not county:
            for part in reversed(src.parts):
                fips2 = extract_fips_from_filename(part)
                if fips2:
                    county = fips_to_county(fips2)
                    break

        if not county:
            _log(f"  Cannot identify county for: {src.name} — skipping", "WARN")
            unclassified.append(src)
            continue

        _log(f"  {src.name} -> [{cls.label}] county={county}")
        records = route_file(src, data_root, county, cls, dry_run=dry_run, log=type('L', (), {
            'info': lambda self, m: _log(m), 'warn': lambda self, m: _log(m, "WARN")
        })())
        county_records.setdefault(county, []).extend(records)

    if unclassified:
        _log(f"  {len(unclassified)} files not classified (no matching rule):")
        for u in unclassified:
            _log(f"    unclassified: {u.name}")

    # ── Write manifests ───────────────────────────────────────────────────
    for county_name, records in county_records.items():
        if not dry_run:
            manifest_path = write_county_manifest(data_root, county_name, records)
            _log(f"  Manifest written: {manifest_path}")
        _log(f"  County {county_name}: {len(records)} files ingested")

    total = sum(len(v) for v in county_records.values())
    _log(f"Ingestion complete: {total} files across {len(county_records)} counties")
    return county_records


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point (standalone)
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest STAGING_DIR into canonical data store")
    parser.add_argument("--staging-dir", required=True, help="Path to STAGING_DIR")
    parser.add_argument("--data-root", default=None, help="Override data/ root path")
    parser.add_argument("--dry-run", action="store_true", help="Classify only; do not copy files")
    parser.add_argument("--log-level", default="verbose", choices=["verbose", "summary"])
    args = parser.parse_args()

    result = run_ingestion(
        staging_dir=args.staging_dir,
        data_root=args.data_root,
        dry_run=args.dry_run,
    )
    if not result:
        print("[INGEST] No files ingested.")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
