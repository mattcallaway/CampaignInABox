# System Readiness Report
**Generated:** 2026-03-14T12:31:26Z
**Overall Status:** ⚠️ PARTIAL

## Checks

| Check | Status | Detail |
|---|---|---|
| Contest Data | ✅ PRESENT | 3 file(s) in data/contests/CA/Sonoma/*/raw/ |
| Pipeline Run | ✅ OK | Last run: 20260304_224546_3d3ba634__run.log |
| Archive | ⏳ NOT BUILT | 0 archive directory(s) in derived/archive/CA/Sonoma/ |
| Crosswalk Files | ✅ PRESENT | 7 file(s) in data/CA/counties/Sonoma/geography/crosswalks/ |
| Precinct Geometry | ✅ PRESENT | 6 file(s) in precinct_shapes/ |
| Map Outputs | ✅ PRESENT | 10 GeoJSON map(s) in derived/maps/ |
| Precinct Join Rate | ❓ UNKNOWN | UNKNOWN |
| Model Calibration | ✅ OK | 2 model file(s) in derived/models/ |

## Actions Required

- Ensure ARCHIVE_INGEST step completes without error in pipeline run