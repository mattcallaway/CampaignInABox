# Legacy Contest Path Compatibility Report
**RUN_ID:** `2026-03-14__011318__p28`
**Generated:** 2026-03-14T08:28:24.849136

## Policy (P28)
- **No new writes** may go to old contest-data paths (`data/elections/`, `votes/`, `data/*/counties/*/votes/`)
- **All legacy reads** route through `ContestResolver` which checks canonical path first
- Legacy paths still appear in `_discover_contests()` as **read-only fallback** with `⚠️ LEGACY` label

## Legacy Path Inventory
| Path | Status | Written by |
|---|---|---|
| `data/elections/` | ❌ Cleared (P28 purge) | Old Data Manager uploads |
| `votes/{year}/{state}/{county}/{slug}/` | ❌ Cleared (P28 purge) | Old pipeline native path |
| `data/CA/counties/Sonoma/votes/` | ❌ Cleared (P28 purge) | Old pipeline vote files |
| `data/election_archive/normalized/` | ❌ Cleared (P28 purge) | Archive normalizer output |

## Remaining Legacy Code References
- `scripts\ingest.py:11` — pattern `data/CA/counties`
- `scripts\refresh_manifests.py:5` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:174` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:175` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:176` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:177` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:178` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:179` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:180` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:181` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:341` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:342` — pattern `data/CA/counties`
- `scripts\run_pipeline.py:357` — pattern `votes/{year}`
- `scripts\run_pipeline.py:861` — pattern `data/elections`
- `scripts\geography\boundary_loader.py:113` — pattern `data/CA/counties`
- `scripts\tools\run_audit_discovery.py:276` — pattern `data/elections`
- `scripts\validation\geography_validator.py:162` — pattern `data/CA/counties`
- `scripts\validation\geography_validator.py:162` — pattern `/votes/`
- `engine\calibration\calibration_engine.py:505` — pattern `data/elections`
- `engine\calibration\election_downloader.py:12` — pattern `data/elections`
- `engine\calibration\election_downloader.py:89` — pattern `data/elections`
- `engine\calibration\election_downloader.py:90` — pattern `data/elections`
- `engine\calibration\election_downloader.py:110` — pattern `data/elections`
- `engine\calibration\historical_parser.py:100` — pattern `data/elections`
- `engine\calibration\model_calibrator.py:233` — pattern `data/elections`
- `engine\contest_data\contest_health.py:34` — pattern `data/elections`
- `engine\contest_data\contest_health.py:41` — pattern `data/elections`
- `engine\contest_data\contest_health.py:42` — pattern `data/CA/counties`
- `engine\contest_data\contest_health.py:43` — pattern `votes/{year}`
- `engine\contest_data\contest_health.py:44` — pattern `/votes/`