# UI DOM Post-Run Observations — Prompt 30.5

## Campaign Mission Control (post P31.5 + P30.5 fixes)

| Element | Status | Notes |
|---|---|---|
| Stage 3 Historical Analysis | ✅ Archive Built | Archive present detection now works |
| System Readiness - Overall | PARTIAL | Fixed after P30.5 archive path fix |
| System Readiness - Archive | NOT BUILT (red) | FIXED in P30.5 — will show PRESENT after reload |
| System Readiness - Contest Data | PRESENT (green) | Correct |
| System Readiness - Pipeline Run | OK (green) | Correct |
| System Readiness - Precinct Join Rate | UNKNOWN (red) | Stale — pipeline summary shows 1.0 but SR reads wrong file |
| System Readiness - Model Calibration | OK (green) | Correct |
| Right Panel Last Run | nov2025_special SUCCESS | Correct |
| Right Panel Archive | ✅ Yes | Correct (pipeline_summary.json) |
| Contest Files | 3 files, ALL NEEDS_REVIEW | File watcher fix pending hot-reload |
| Next Action | Old - check ARCHIVE_INGEST | FIXED in P30.5 — now correct after reload |

## Historical Archive Page

- Archive exists at derived/archive/archive_summary.json (612 bytes)
- Contains contest_classification.csv
- Archive represents nov2020_general historical data (run_id: 20260312__p24)
- coverage.precincts = 55, has_real_data = True

## Precinct Map Page

- Not directly verified in this run
- Geometry loaded: 1405 features from mprec_097_g24_v01.geojson (confirmed in log)
- Map outputs: derived/maps/ has .geojson files
- Map is expected to show Sonoma precincts correctly

## Diagnostics Page

- System audit confirms 13/13 artifacts present

## Strategy Page

- derived/strategy/ directory exists with content (from previous run)
- Strategy markdown files generated via CAMPAIGN_STRATEGY step (DONE, 77.7s)

## Data Quality Issues (from log)

- egistered=0 but ballots>0 — 2 + 320 + 44 = 366 precincts
  - These are CRITICAL integrity violations in INTEGRITY_ENFORCEMENT step
  - Indicates the 'Registered' column maps correctly in SCHEMA log 
    but underlying values are 0 in the workbook or not the right column
  - This is the most significant data quality issue remaining
