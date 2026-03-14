# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-14__000846__25f8d317__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-14T07:08:46.778102+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `f61ad621d92db945...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `b724c88e9233fabf...` |

## Coverage Metrics

- **canonical_geometry**: MPREC
- **categories_present**: 12
- **categories_missing**: 0
- **geometry_features**: 1405
- **sheets_parsed**: 2
- **rows_1**: 4
- **rows_Registration**: 4

## NEEDS / Missing Data

_No missing data._

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| DATA_INTAKE_ANALYSIS | skipped | 0.08 |
| INGEST_STAGING | skipped | 0.08 |
| SCAFFOLD_BOUNDARY_INDEX_Sonoma | done | 0.084 |
| VALIDATE_GEOGRAPHY | done | 0.089 |
| VALIDATE_VOTES | done | 0.09 |
| LOAD_GEOMETRY | done | 2.576 |
| LOAD_CROSSWALKS | skipped | 2.87 |
| SCAFFOLD_CONTEST_JSON | done | 2.872 |
| PARSE_CONTEST | done | 2.9 |
| NORMALIZE_SCHEMA/1 | done | 2.905 |
| SANITY/1 | done | 2.905 |
| BUILD_MODEL/1 | done | 2.912 |
| NORMALIZE_SCHEMA/Registration | done | 2.919 |
| SANITY/Registration | done | 2.919 |
| BUILD_MODEL/Registration | done | 2.929 |
| ALLOCATE_VOTES | done | 2.929 |
| INTEGRITY_ENFORCEMENT | done | 2.941 |
| FEATURE_ENGINEERING | done | 2.989 |
| UNIVERSE_BUILDING | done | 3.032 |
| SCORING_V2 | done | 3.065 |
| REGION_CLUSTERING | done | 3.097 |
| FIELD_PLANNING | done | 3.111 |
| SIMULATION | done | 3.113 |
| VOTER_UNIVERSE_EXPORT | skipped | 3.113 |
| LOAD_VOTER_FILE | skipped | 3.115 |
| BUILD_VOTER_UNIVERSES | skipped | 3.115 |
| SCORE_VOTER_TURNOUT | skipped | 3.115 |
| SCORE_VOTER_PERSUASION | skipped | 3.115 |
| BUILD_TARGETING_QUADRANTS | skipped | 3.115 |
| BUILD_PRECINCT_VOTER_METRICS | skipped | 3.115 |
| DOWNLOAD_HISTORICAL_ELECTIONS | done | 63.669 |
| CALIBRATE_MODEL | done | 63.676 |
| CAMPAIGN_STRATEGY | done | 63.789 |
| CALIBRATION | done | 63.897 |
| INTELLIGENCE | done | 64.048 |
| BUILD_PROVENANCE | done | 64.097 |
| GENERATE_DATA_REQUESTS | done | 64.111 |
| WAR_ROOM_STATUS | done | 64.135 |
| WAR_ROOM_FORECAST_UPDATE | done | 64.151 |
| PERFORMANCE_RECONCILIATION | done | 64.209 |
| FORECAST_GENERATION | done | 64.262 |
| TURF_GENERATION | done | 64.281 |
| EXPORT_V2_OUTPUTS | done | 75.03 |
| DIAGNOSTICS | done | 75.092 |
| STRATEGY_GENERATOR | done | 75.558 |
| GEO_VALIDATION | done | 76.173 |
| JOIN_GUARD_VALIDATION | done | 76.18 |
| INTEGRITY_REPAIRS_WRITE | done | 76.183 |
| ARTIFACT_VALIDATION | done | 76.207 |
| POST_RUN_AUDIT | done | 76.225 |
| STATE_BUILD | skipped | 76.358 |
| STATE_DIFF | done | 76.369 |
| ADVANCED_UNIVERSE_ESTIMATES | done | 76.382 |
| OPTIMIZER | done | 76.384 |
| ADVANCED_LIFT_MODEL | done | 76.384 |
| ADVANCED_SCENARIOS | done | 192.345 |
| ADVANCED_QA | done | 192.351 |
