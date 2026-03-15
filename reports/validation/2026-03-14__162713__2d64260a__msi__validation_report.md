# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-14__162713__2d64260a__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2025_special |
| **Started** | 2026-03-14T23:27:14.090378+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `1c558d828c8f1ff3...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `08a14c62f6fb6a3f...` |

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
| DATA_INTAKE_ANALYSIS | done | 0.268 |
| INGEST_STAGING | skipped | 0.268 |
| SCAFFOLD_BOUNDARY_INDEX_Sonoma | done | 0.273 |
| VALIDATE_GEOGRAPHY | done | 0.293 |
| VALIDATE_VOTES | done | 0.31 |
| LOAD_GEOMETRY | done | 9.792 |
| LOAD_CROSSWALKS | done | 11.329 |
| SCAFFOLD_CONTEST_JSON | done | 11.347 |
| PARSE_CONTEST | done | 12.551 |
| NORMALIZE_SCHEMA/Document map | done | 12.924 |
| SANITY/Document map | done | 12.925 |
| BUILD_MODEL/Document map | done | 13.5 |
| NORMALIZE_SCHEMA/Sheet2 | done | 13.71 |
| SANITY/Sheet2 | done | 13.711 |
| BUILD_MODEL/Sheet2 | done | 13.933 |
| NORMALIZE_SCHEMA/Sheet3 | done | 14.216 |
| SANITY/Sheet3 | done | 14.216 |
| BUILD_MODEL/Sheet3 | done | 14.281 |
| NORMALIZE_SCHEMA/Sheet4 | done | 14.444 |
| SANITY/Sheet4 | done | 14.445 |
| BUILD_MODEL/Sheet4 | done | 14.524 |
| ALLOCATE_VOTES | done | 14.525 |
| INTEGRITY_ENFORCEMENT | done | 14.899 |
| FEATURE_ENGINEERING | done | 15.121 |
| UNIVERSE_BUILDING | done | 15.424 |
| SCORING_V2 | done | 15.646 |
| REGION_CLUSTERING | done | 15.904 |
| FIELD_PLANNING | done | 16.205 |
| SIMULATION | done | 16.223 |
| VOTER_UNIVERSE_EXPORT | skipped | 16.223 |
| LOAD_VOTER_FILE | skipped | 16.225 |
| BUILD_VOTER_UNIVERSES | skipped | 16.225 |
| SCORE_VOTER_TURNOUT | skipped | 16.227 |
| SCORE_VOTER_PERSUASION | skipped | 16.227 |
| BUILD_TARGETING_QUADRANTS | skipped | 16.227 |
| BUILD_PRECINCT_VOTER_METRICS | skipped | 16.227 |
| DOWNLOAD_HISTORICAL_ELECTIONS | done | 76.924 |
| CALIBRATE_MODEL | done | 76.985 |
| CAMPAIGN_STRATEGY | done | 77.776 |
| CALIBRATION | done | 78.135 |
| INTELLIGENCE | done | 78.377 |
| BUILD_PROVENANCE | done | 78.412 |
| GENERATE_DATA_REQUESTS | done | 78.417 |
| WAR_ROOM_STATUS | done | 78.464 |
| WAR_ROOM_FORECAST_UPDATE | done | 78.477 |
| PERFORMANCE_RECONCILIATION | done | 78.506 |
| FORECAST_GENERATION | done | 78.606 |
| TURF_GENERATION | done | 78.659 |
| EXPORT_V2_OUTPUTS | done | 99.728 |
| DIAGNOSTICS | done | 99.856 |
| STRATEGY_GENERATOR | done | 100.702 |
| GEO_VALIDATION | done | 101.115 |
| JOIN_GUARD_VALIDATION | done | 101.12 |
| INTEGRITY_REPAIRS_WRITE | done | 101.126 |
| ARTIFACT_VALIDATION | done | 101.149 |
| POST_RUN_AUDIT | done | 101.165 |
| STATE_BUILD | done | 101.311 |
| STATE_DIFF | done | 101.316 |
| ADVANCED_UNIVERSE_ESTIMATES | done | 101.33 |
| OPTIMIZER | done | 101.332 |
| ADVANCED_LIFT_MODEL | done | 101.332 |
| ADVANCED_SCENARIOS | done | 176.208 |
| ADVANCED_QA | done | 176.211 |
