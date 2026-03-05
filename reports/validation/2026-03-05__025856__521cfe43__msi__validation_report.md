# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-05__025856__521cfe43__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T10:58:57.048841+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `a96a8620fcc058a4...` |

## Coverage Metrics

- **canonical_geometry**: MPREC
- **categories_present**: 12
- **categories_missing**: 0
- **sheets_parsed**: 1
- **rows_Sheet1**: 10

## NEEDS / Missing Data

- **geopandas_library** [missing] — blocks: geometry_load, kepler_export

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| INGEST_STAGING | skipped | 0.005 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.008 |
| VALIDATE_GEOGRAPHY | done | 0.011 |
| VALIDATE_VOTES | done | 0.012 |
| LOAD_GEOMETRY | skipped | 0.013 |
| LOAD_CROSSWALKS | skipped | 0.214 |
| SCAFFOLD_CONTEST_JSON | done | 0.232 |
| PARSE_CONTEST | done | 0.254 |
| SANITY/Sheet1 | done | 0.255 |
| BUILD_MODEL/Sheet1 | done | 0.266 |
| ALLOCATE_VOTES | done | 0.266 |
| INTEGRITY_ENFORCEMENT | done | 0.269 |
| FEATURE_ENGINEERING | done | 0.282 |
| UNIVERSE_BUILDING | done | 0.297 |
| SCORING_V2 | done | 0.314 |
| REGION_CLUSTERING | done | 0.318 |
| FIELD_PLANNING | done | 0.324 |
| SIMULATION | done | 0.325 |
| VOTER_UNIVERSE_EXPORT | skipped | 0.325 |
| FORECAST_GENERATION | done | 0.339 |
| TURF_GENERATION | done | 0.345 |
| EXPORT_V2_OUTPUTS | done | 0.401 |
| DIAGNOSTICS | done | 0.428 |
| STRATEGY_GENERATOR | skipped | 0.503 |
