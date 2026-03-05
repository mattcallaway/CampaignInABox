# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-05__035935__0e0e8b52__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T11:59:35.434051+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `f7e06310bfaff5ed...` |

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
| INGEST_STAGING | skipped | 0.008 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.012 |
| VALIDATE_GEOGRAPHY | done | 0.016 |
| VALIDATE_VOTES | done | 0.017 |
| LOAD_GEOMETRY | skipped | 0.018 |
| LOAD_CROSSWALKS | skipped | 0.188 |
| SCAFFOLD_CONTEST_JSON | done | 0.202 |
| PARSE_CONTEST | done | 0.221 |
| NORMALIZE_SCHEMA/Sheet1 | done | 0.229 |
| SANITY/Sheet1 | done | 0.229 |
| BUILD_MODEL/Sheet1 | done | 0.237 |
| ALLOCATE_VOTES | done | 0.237 |
| INTEGRITY_ENFORCEMENT | done | 0.243 |
| FEATURE_ENGINEERING | done | 0.253 |
| UNIVERSE_BUILDING | done | 0.266 |
| SCORING_V2 | done | 0.278 |
| REGION_CLUSTERING | done | 0.285 |
| FIELD_PLANNING | done | 0.291 |
| SIMULATION | done | 0.292 |
| VOTER_UNIVERSE_EXPORT | skipped | 0.292 |
| FORECAST_GENERATION | done | 0.306 |
| TURF_GENERATION | done | 0.312 |
| EXPORT_V2_OUTPUTS | done | 0.348 |
| DIAGNOSTICS | done | 0.364 |
| STRATEGY_GENERATOR | skipped | 0.432 |
| GEO_VALIDATION | done | 0.434 |
| JOIN_GUARD_VALIDATION | done | 0.438 |
| INTEGRITY_REPAIRS_WRITE | done | 0.44 |
| ARTIFACT_VALIDATION | done | 0.446 |
| POST_RUN_AUDIT | done | 0.465 |
