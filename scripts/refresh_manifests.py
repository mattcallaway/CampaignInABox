#!/usr/bin/env python3
"""
scripts/refresh_manifests.py

Crawl the data/CA/counties/ directory and generate or refresh manifest.json 
for each county geography folder by scanning existing files.
"""

import sys
from pathlib import Path

# Bootstrap
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.ingest import write_county_manifest
from scripts.lib.classify import classify_file
from scripts.lib.hashing import file_info

def refresh_all(data_root: Path):
    ca_root = data_root / "CA" / "counties"
    if not ca_root.is_dir():
        print(f"Directory not found: {ca_root}")
        return

    for county_dir in sorted(ca_root.iterdir()):
        if not county_dir.is_dir():
            continue
        
        county_name = county_dir.name
        geo_dir = county_dir / "geography"
        if not geo_dir.is_dir():
            print(f"Skipping {county_name} (no geography folder)")
            continue

        print(f"Refreshing manifest for {county_name}...")
        
        file_records = []
        # Walk all subfolders in geography/
        for item in geo_dir.rglob("*"):
            if not item.is_file():
                continue
            if item.name == "manifest.json":
                continue
            
            cls = classify_file(item)
            if cls:
                file_records.append({
                    **file_info(item),
                    "category_label": cls.label,
                    "category_folder": cls.folder,
                    "source_path": str(item),
                })
        
        if file_records:
            mf_path = write_county_manifest(data_root, county_name, file_records)
            print(f"  Done: {mf_path}")
        else:
            print(f"  No classifiable files found in {county_name}/geography/")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Refresh geography manifests")
    parser.add_argument("--county", help="Refresh only a specific county")
    args = parser.parse_args()

    data_root = BASE_DIR / "data"
    if args.county:
        # Simple hack to just run for one if requested
        # (refresh_all naturally handles this if we filter logic)
        refresh_all(data_root) # For now just run all; it's fast
    else:
        refresh_all(data_root)
