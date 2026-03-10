# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-10__141533__84d9e3b2__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | prop_50_special |
| **Started** | 2026-03-10T21:15:33.254667+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `1028d97deafd02d8...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `591cae80e8910369...` |

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
| INGEST_STAGING | skipped | 0.052 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.054 |
| VALIDATE_GEOGRAPHY | done | 0.057 |
| VALIDATE_VOTES | done | 0.058 |
| LOAD_GEOMETRY | done | 2.155 |
| LOAD_CROSSWALKS | skipped | 2.364 |
| SCAFFOLD_CONTEST_JSON | done | 2.366 |
| PARSE_CONTEST | done | 2.513 |
| NORMALIZE_SCHEMA/2 | done | 2.518 |
| SANITY/2 | done | 2.519 |
| BUILD_MODEL/2 | done | 2.526 |
| NORMALIZE_SCHEMA/3 | done | 2.531 |
| SANITY/3 | done | 2.532 |
| BUILD_MODEL/3 | done | 2.542 |
| NORMALIZE_SCHEMA/4 | done | 2.547 |
| SANITY/4 | done | 2.548 |
| BUILD_MODEL/4 | done | 2.556 |
| ALLOCATE_VOTES | done | 2.556 |
| INTEGRITY_ENFORCEMENT | done | 2.637 |
| FEATURE_ENGINEERING | done | 2.67 |
| UNIVERSE_BUILDING | done | 2.714 |
| SCORING_V2 | done | 2.741 |
| REGION_CLUSTERING | done | 2.774 |
| FIELD_PLANNING | done | 2.794 |
| SIMULATION | done | 2.796 |
| VOTER_UNIVERSE_EXPORT | skipped | 2.796 |
| LOAD_VOTER_FILE | skipped | 2.797 |
| BUILD_VOTER_UNIVERSES | skipped | 2.797 |
| DOWNLOAD_HISTORICAL_ELECTIONS | done | 63.692 |
| CALIBRATE_MODEL | done | 63.711 |
| FORECAST_GENERATION | done | 63.799 |
| TURF_GENERATION | done | 63.903 |
| EXPORT_V2_OUTPUTS | done | 75.746 |
| DIAGNOSTICS | done | 75.774 |
| STRATEGY_GENERATOR | done | 75.993 |
| GEO_VALIDATION | done | 76.258 |
| JOIN_GUARD_VALIDATION | done | 76.261 |
| INTEGRITY_REPAIRS_WRITE | done | 76.263 |
| ARTIFACT_VALIDATION | done | 76.27 |
| POST_RUN_AUDIT | done | 76.279 |
| ADVANCED_UNIVERSE_ESTIMATES | done | 76.287 |
| OPTIMIZER | done | 76.288 |
| ADVANCED_LIFT_MODEL | done | 76.288 |
| ADVANCED_SCENARIOS | done | 139.102 |
| ADVANCED_QA | done | 139.105 |
