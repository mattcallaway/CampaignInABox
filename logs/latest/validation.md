# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-14__044900__9b7d76d6__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2025_special |
| **Started** | 2026-03-14T11:49:00.652352+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `1c558d828c8f1ff3...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `9129a9460800db63...` |

## Coverage Metrics

- **canonical_geometry**: MPREC
- **categories_present**: 12
- **categories_missing**: 0
- **geometry_features**: 1405
- **sheets_parsed**: 4
- **rows_Document map**: 3
- **rows_Sheet2**: 4
- **rows_Sheet3**: 393
- **rows_Sheet4**: 58

## NEEDS / Missing Data

_No missing data._

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| DATA_INTAKE_ANALYSIS | done | 0.064 |
| INGEST_STAGING | skipped | 0.064 |
| SCAFFOLD_BOUNDARY_INDEX_Sonoma | done | 0.066 |
| VALIDATE_GEOGRAPHY | done | 0.07 |
| VALIDATE_VOTES | done | 0.074 |
| LOAD_GEOMETRY | done | 2.308 |
| LOAD_CROSSWALKS | done | 2.583 |
| SCAFFOLD_CONTEST_JSON | done | 2.586 |
| PARSE_CONTEST | done | 2.809 |
| NORMALIZE_SCHEMA/Document map | done | 2.829 |
| SANITY/Document map | done | 2.829 |
| BUILD_MODEL/Document map | done | 2.85 |
| NORMALIZE_SCHEMA/Sheet2 | done | 2.881 |
| SANITY/Sheet2 | done | 2.881 |
| BUILD_MODEL/Sheet2 | done | 2.892 |
| NORMALIZE_SCHEMA/Sheet3 | done | 2.91 |
| SANITY/Sheet3 | done | 2.91 |
| BUILD_MODEL/Sheet3 | done | 2.923 |
| NORMALIZE_SCHEMA/Sheet4 | done | 2.98 |
| SANITY/Sheet4 | done | 2.98 |
| BUILD_MODEL/Sheet4 | done | 2.991 |
| ALLOCATE_VOTES | done | 2.991 |
| INTEGRITY_ENFORCEMENT | done | 3.063 |
| FEATURE_ENGINEERING | done | 3.136 |
| UNIVERSE_BUILDING | done | 3.208 |
| SCORING_V2 | done | 3.257 |
| REGION_CLUSTERING | done | 3.305 |
| FIELD_PLANNING | done | 3.332 |
| SIMULATION | done | 3.338 |
| VOTER_UNIVERSE_EXPORT | skipped | 3.338 |
| LOAD_VOTER_FILE | skipped | 3.34 |
| BUILD_VOTER_UNIVERSES | skipped | 3.34 |
| SCORE_VOTER_TURNOUT | skipped | 3.34 |
| SCORE_VOTER_PERSUASION | skipped | 3.34 |
| BUILD_TARGETING_QUADRANTS | skipped | 3.34 |
| BUILD_PRECINCT_VOTER_METRICS | skipped | 3.34 |
| DOWNLOAD_HISTORICAL_ELECTIONS | done | 63.974 |
| CALIBRATE_MODEL | done | 64.01 |
| CAMPAIGN_STRATEGY | done | 64.082 |
| CALIBRATION | done | 64.133 |
| INTELLIGENCE | done | 64.171 |
| BUILD_PROVENANCE | done | 64.195 |
| GENERATE_DATA_REQUESTS | done | 64.198 |
| WAR_ROOM_STATUS | done | 64.212 |
| WAR_ROOM_FORECAST_UPDATE | done | 64.223 |
| PERFORMANCE_RECONCILIATION | done | 64.245 |
| FORECAST_GENERATION | done | 64.314 |
| TURF_GENERATION | done | 64.351 |
| EXPORT_V2_OUTPUTS | done | 78.797 |
| DIAGNOSTICS | done | 78.889 |
| STRATEGY_GENERATOR | done | 79.324 |
| GEO_VALIDATION | done | 79.638 |
| JOIN_GUARD_VALIDATION | done | 79.643 |
| INTEGRITY_REPAIRS_WRITE | done | 79.646 |
| ARTIFACT_VALIDATION | done | 79.667 |
| POST_RUN_AUDIT | done | 79.678 |
| STATE_BUILD | done | 79.768 |
| STATE_DIFF | done | 79.771 |
| ADVANCED_UNIVERSE_ESTIMATES | done | 79.787 |
| OPTIMIZER | done | 79.789 |
| ADVANCED_LIFT_MODEL | done | 79.789 |
| ADVANCED_SCENARIOS | done | 150.44 |
| ADVANCED_QA | done | 150.444 |
