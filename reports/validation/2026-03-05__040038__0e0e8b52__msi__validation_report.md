# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-05__040038__0e0e8b52__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T12:00:38.946302+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `525c8b61dc2c776b...` |

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
| INGEST_STAGING | skipped | 0.004 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.007 |
| VALIDATE_GEOGRAPHY | done | 0.011 |
| VALIDATE_VOTES | done | 0.011 |
| LOAD_GEOMETRY | skipped | 0.012 |
| LOAD_CROSSWALKS | skipped | 0.154 |
| SCAFFOLD_CONTEST_JSON | done | 0.169 |
| PARSE_CONTEST | done | 0.187 |
| NORMALIZE_SCHEMA/Sheet1 | done | 0.193 |
| SANITY/Sheet1 | done | 0.193 |
| BUILD_MODEL/Sheet1 | done | 0.202 |
| ALLOCATE_VOTES | done | 0.202 |
| INTEGRITY_ENFORCEMENT | done | 0.209 |
| FEATURE_ENGINEERING | done | 0.219 |
| UNIVERSE_BUILDING | done | 0.229 |
| SCORING_V2 | done | 0.238 |
| REGION_CLUSTERING | done | 0.244 |
| FIELD_PLANNING | done | 0.249 |
| SIMULATION | done | 0.25 |
| VOTER_UNIVERSE_EXPORT | skipped | 0.25 |
| FORECAST_GENERATION | done | 0.263 |
| TURF_GENERATION | done | 0.267 |
| EXPORT_V2_OUTPUTS | done | 0.303 |
| DIAGNOSTICS | done | 0.317 |
| STRATEGY_GENERATOR | done | 0.393 |
| GEO_VALIDATION | done | 0.394 |
| JOIN_GUARD_VALIDATION | done | 0.399 |
| INTEGRITY_REPAIRS_WRITE | done | 0.401 |
| ARTIFACT_VALIDATION | done | 0.405 |
| POST_RUN_AUDIT | done | 0.427 |
