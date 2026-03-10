# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-10__145503__00b7b2b1__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | prop_50_special |
| **Started** | 2026-03-10T21:55:04.003948+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `1028d97deafd02d8...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `172ee173fff76dfd...` |

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
| INGEST_STAGING | skipped | 0.065 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.067 |
| VALIDATE_GEOGRAPHY | done | 0.071 |
| VALIDATE_VOTES | done | 0.072 |
| LOAD_GEOMETRY | done | 3.129 |
| LOAD_CROSSWALKS | skipped | 3.354 |
| SCAFFOLD_CONTEST_JSON | done | 3.355 |
| PARSE_CONTEST | done | 3.506 |
| NORMALIZE_SCHEMA/2 | done | 3.512 |
| SANITY/2 | done | 3.513 |
| BUILD_MODEL/2 | done | 3.524 |
| NORMALIZE_SCHEMA/3 | done | 3.529 |
| SANITY/3 | done | 3.529 |
| BUILD_MODEL/3 | done | 3.539 |
| NORMALIZE_SCHEMA/4 | done | 3.545 |
| SANITY/4 | done | 3.546 |
| BUILD_MODEL/4 | done | 3.553 |
| ALLOCATE_VOTES | done | 3.553 |
| INTEGRITY_ENFORCEMENT | done | 3.629 |
| FEATURE_ENGINEERING | done | 3.666 |
| UNIVERSE_BUILDING | done | 3.732 |
| SCORING_V2 | done | 3.799 |
| REGION_CLUSTERING | done | 3.84 |
| FIELD_PLANNING | done | 3.858 |
| SIMULATION | done | 3.862 |
| VOTER_UNIVERSE_EXPORT | skipped | 3.862 |
| LOAD_VOTER_FILE | done | 4.032 |
| BUILD_VOTER_UNIVERSES | done | 4.07 |
| SCORE_VOTER_TURNOUT | done | 4.185 |
| SCORE_VOTER_PERSUASION | done | 4.255 |
| BUILD_TARGETING_QUADRANTS | done | 4.294 |
| BUILD_PRECINCT_VOTER_METRICS | done | 4.384 |
| DOWNLOAD_HISTORICAL_ELECTIONS | done | 65.284 |
| CALIBRATE_MODEL | done | 65.304 |
| CAMPAIGN_STRATEGY | done | 65.442 |
| FORECAST_GENERATION | done | 65.482 |
| TURF_GENERATION | done | 65.584 |
| EXPORT_V2_OUTPUTS | done | 80.337 |
| DIAGNOSTICS | done | 80.823 |
| STRATEGY_GENERATOR | done | 81.947 |
| GEO_VALIDATION | done | 82.327 |
| JOIN_GUARD_VALIDATION | done | 82.33 |
| INTEGRITY_REPAIRS_WRITE | done | 82.332 |
| ARTIFACT_VALIDATION | done | 82.342 |
| POST_RUN_AUDIT | done | 82.351 |
| ADVANCED_UNIVERSE_ESTIMATES | done | 82.361 |
| OPTIMIZER | done | 82.362 |
| ADVANCED_LIFT_MODEL | done | 82.362 |
| ADVANCED_SCENARIOS | done | 149.465 |
| ADVANCED_QA | done | 149.468 |
