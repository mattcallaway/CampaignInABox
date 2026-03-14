# Contest Data Health Report
**Generated:** 2026-03-14T08:28:24.836250
**Health Score:** 10.0/10

## Summary
| Metric | Value |
|---|---|
| Canonical contests | 0 |
| Legacy files remaining | 0 |
| Registry duplicates | 0 |
| Manifest issues | 0 |
| Legacy code references | 43 |
| Multi-primary contests | 0 |

## Canonical Contests
_No canonical contests found._

## Legacy Files Remaining
✅ No legacy contest files found outside canonical structure.

## Registry Duplicates
✅ No duplicate registry entries found.

## Legacy Code References
> [!WARNING]
> These source files still reference legacy contest data paths.

- `scripts\ingest.py:11` — `data/CA/counties/<CountyName>/geography/<category_subfolder>/`
- `scripts\refresh_manifests.py:5` — `Crawl the data/CA/counties/ directory and generate or refresh manifest.json`
- `scripts\run_pipeline.py:174` — `"data/CA/counties/Sonoma/geography/precinct_shapes/MPREC_GeoJSON",`
- `scripts\run_pipeline.py:175` — `"data/CA/counties/Sonoma/geography/precinct_shapes/MPREC_GeoPackage",`
- `scripts\run_pipeline.py:176` — `"data/CA/counties/Sonoma/geography/precinct_shapes/MPREC_Shapefile",`
- `scripts\run_pipeline.py:177` — `"data/CA/counties/Sonoma/geography/precinct_shapes/SRPREC_GeoJSON",`
- `scripts\run_pipeline.py:178` — `"data/CA/counties/Sonoma/geography/precinct_shapes/SRPREC_GeoPackage",`
- `scripts\run_pipeline.py:179` — `"data/CA/counties/Sonoma/geography/precinct_shapes/SRPREC_Shapefile",`
- `scripts\run_pipeline.py:180` — `"data/CA/counties/Sonoma/geography/crosswalks",`
- `scripts\run_pipeline.py:181` — `"data/CA/counties/Sonoma/geography/boundary_index",`
- `scripts\run_pipeline.py:341` — `f"data/CA/counties/{loop_county}/geography/precinct_shapes/",`
- `scripts\run_pipeline.py:342` — `f"data/CA/counties/{loop_county}/geography/crosswalks/",`
- `scripts\run_pipeline.py:357` — `f"votes/{year}/CA/{loop_county}/{contest_slug}/detail.xlsx"`
- `scripts\run_pipeline.py:861` — `f"{_n_failed} require manual download (see data/elections/{state}/{county}/download_status.json)"])`
- `scripts\geography\boundary_loader.py:113` — `A) New:  county_geo_dir_or_data_root = data/CA/counties (parent of county)`
- `scripts\tools\run_audit_discovery.py:276` — `"data/elections":        ["SOV or election results CSVs"],`
- `scripts\validation\geography_validator.py:162` — `1. data/CA/counties/<county>/votes/<year>/<slug>/   (canonical new path)`
- `scripts\validation\geography_validator.py:162` — `1. data/CA/counties/<county>/votes/<year>/<slug>/   (canonical new path)`
- `engine\calibration\calibration_engine.py:505` — `lines.append("- ❌ Add historical election files to `data/elections/CA/<county>/<year>/detail.xls`")`
- `engine\calibration\election_downloader.py:12` — `data/elections/CA/Sonoma/<year>/detail.xls`
