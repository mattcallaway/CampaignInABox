# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-10__143525__030abb27__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | prop_50_special |
| **Started** | 2026-03-10T21:35:25.157582+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `1028d97deafd02d8...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `aec53a14e07cfe83...` |

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
| INGEST_STAGING | skipped | 0.055 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.057 |
| VALIDATE_GEOGRAPHY | done | 0.06 |
| VALIDATE_VOTES | done | 0.061 |
| LOAD_GEOMETRY | done | 2.529 |
| LOAD_CROSSWALKS | skipped | 2.729 |
| SCAFFOLD_CONTEST_JSON | done | 2.731 |
| PARSE_CONTEST | done | 2.877 |
| NORMALIZE_SCHEMA/2 | done | 2.881 |
| SANITY/2 | done | 2.882 |
| BUILD_MODEL/2 | done | 2.893 |
| NORMALIZE_SCHEMA/3 | done | 2.898 |
| SANITY/3 | done | 2.898 |
| BUILD_MODEL/3 | done | 2.908 |
| NORMALIZE_SCHEMA/4 | done | 2.913 |
| SANITY/4 | done | 2.913 |
| BUILD_MODEL/4 | done | 2.921 |
| ALLOCATE_VOTES | done | 2.921 |
| INTEGRITY_ENFORCEMENT | done | 2.996 |
| FEATURE_ENGINEERING | done | 3.033 |
| UNIVERSE_BUILDING | done | 3.071 |
| SCORING_V2 | done | 3.099 |
| REGION_CLUSTERING | done | 3.13 |
| FIELD_PLANNING | done | 3.145 |
| SIMULATION | done | 3.147 |
| VOTER_UNIVERSE_EXPORT | skipped | 3.147 |
| LOAD_VOTER_FILE | done | 3.425 |
| BUILD_VOTER_UNIVERSES | done | 3.463 |
| SCORE_VOTER_TURNOUT | done | 3.544 |
| SCORE_VOTER_PERSUASION | done | 3.614 |
| BUILD_TARGETING_QUADRANTS | done | 3.649 |
| BUILD_PRECINCT_VOTER_METRICS | done | 3.732 |
| DOWNLOAD_HISTORICAL_ELECTIONS | done | 64.678 |
| CALIBRATE_MODEL | done | 64.683 |
| FORECAST_GENERATION | done | 64.725 |
| TURF_GENERATION | done | 64.839 |
| EXPORT_V2_OUTPUTS | done | 79.968 |
| DIAGNOSTICS | done | 80.002 |
| STRATEGY_GENERATOR | done | 80.372 |
| GEO_VALIDATION | done | 80.829 |
| JOIN_GUARD_VALIDATION | done | 80.834 |
| INTEGRITY_REPAIRS_WRITE | done | 80.837 |
| ARTIFACT_VALIDATION | done | 80.846 |
| POST_RUN_AUDIT | done | 80.859 |
| ADVANCED_UNIVERSE_ESTIMATES | done | 80.875 |
| OPTIMIZER | done | 80.876 |
| ADVANCED_LIFT_MODEL | done | 80.876 |
| ADVANCED_SCENARIOS | done | 149.521 |
| ADVANCED_QA | done | 149.525 |
