# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-10__152246__e84498d7__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | prop_50_special |
| **Started** | 2026-03-10T22:22:47.108497+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `1028d97deafd02d8...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `4f768969ee640122...` |

## Coverage Metrics

- **canonical_geometry**: MPREC
- **categories_present**: 12
- **categories_missing**: 0
- **geometry_features**: 1405
- **sheets_parsed**: 3
- **rows_2**: 2
- **rows_3**: 390
- **rows_4**: 55

## NEEDS / Missing Data

_No missing data._

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| INGEST_STAGING | skipped | 0.059 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.062 |
| VALIDATE_GEOGRAPHY | done | 0.065 |
| VALIDATE_VOTES | done | 0.066 |
| LOAD_GEOMETRY | done | 2.862 |
| LOAD_CROSSWALKS | skipped | 3.098 |
| SCAFFOLD_CONTEST_JSON | done | 3.099 |
| PARSE_CONTEST | done | 3.241 |
| NORMALIZE_SCHEMA/2 | done | 3.246 |
| SANITY/2 | done | 3.246 |
| BUILD_MODEL/2 | done | 3.256 |
| NORMALIZE_SCHEMA/3 | done | 3.261 |
| SANITY/3 | done | 3.262 |
| BUILD_MODEL/3 | done | 3.274 |
| NORMALIZE_SCHEMA/4 | done | 3.279 |
| SANITY/4 | done | 3.279 |
| BUILD_MODEL/4 | done | 3.287 |
| ALLOCATE_VOTES | done | 3.287 |
| INTEGRITY_ENFORCEMENT | done | 3.365 |
| FEATURE_ENGINEERING | done | 3.394 |
| UNIVERSE_BUILDING | done | 3.431 |
| SCORING_V2 | done | 3.458 |
| REGION_CLUSTERING | done | 3.491 |
| FIELD_PLANNING | done | 3.508 |
| SIMULATION | done | 3.51 |
| VOTER_UNIVERSE_EXPORT | skipped | 3.51 |
| LOAD_VOTER_FILE | done | 3.638 |
| BUILD_VOTER_UNIVERSES | done | 3.671 |
| SCORE_VOTER_TURNOUT | done | 3.747 |
| SCORE_VOTER_PERSUASION | done | 3.814 |
| BUILD_TARGETING_QUADRANTS | done | 3.848 |
| BUILD_PRECINCT_VOTER_METRICS | done | 3.928 |
| DOWNLOAD_HISTORICAL_ELECTIONS | done | 65.172 |
| CALIBRATE_MODEL | done | 65.181 |
| CAMPAIGN_STRATEGY | done | 65.241 |
| BUILD_PROVENANCE | done | 65.293 |
| GENERATE_DATA_REQUESTS | done | 65.306 |
| WAR_ROOM_STATUS | done | 65.33 |
| WAR_ROOM_FORECAST_UPDATE | done | 65.345 |
| FORECAST_GENERATION | done | 65.387 |
| TURF_GENERATION | done | 65.493 |
| EXPORT_V2_OUTPUTS | done | 78.702 |
| DIAGNOSTICS | done | 78.748 |
| STRATEGY_GENERATOR | done | 79.594 |
| GEO_VALIDATION | done | 80.132 |
| JOIN_GUARD_VALIDATION | done | 80.137 |
| INTEGRITY_REPAIRS_WRITE | done | 80.14 |
| ARTIFACT_VALIDATION | done | 80.152 |
| POST_RUN_AUDIT | done | 80.165 |
| ADVANCED_UNIVERSE_ESTIMATES | done | 80.175 |
| OPTIMIZER | done | 80.176 |
| ADVANCED_LIFT_MODEL | done | 80.177 |
| ADVANCED_SCENARIOS | done | 150.857 |
| ADVANCED_QA | done | 150.861 |
