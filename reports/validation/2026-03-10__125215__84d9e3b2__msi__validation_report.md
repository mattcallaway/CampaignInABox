# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-10__125215__84d9e3b2__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-10T19:52:15.878674+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `f6d59ec4075e5988...` |

## Coverage Metrics

- **canonical_geometry**: MPREC
- **categories_present**: 12
- **categories_missing**: 0
- **geometry_features**: 1405
- **sheets_parsed**: 1
- **rows_Sheet1**: 10

## NEEDS / Missing Data

_No missing data._

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| INGEST_STAGING | skipped | 0.025 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.038 |
| VALIDATE_GEOGRAPHY | done | 0.056 |
| VALIDATE_VOTES | done | 0.057 |
| LOAD_GEOMETRY | done | 7.686 |
| LOAD_CROSSWALKS | skipped | 8.09 |
| SCAFFOLD_CONTEST_JSON | done | 8.092 |
| PARSE_CONTEST | done | 8.168 |
| NORMALIZE_SCHEMA/Sheet1 | done | 8.187 |
| SANITY/Sheet1 | done | 8.188 |
| BUILD_MODEL/Sheet1 | done | 8.212 |
| ALLOCATE_VOTES | done | 8.212 |
| INTEGRITY_ENFORCEMENT | done | 8.225 |
| FEATURE_ENGINEERING | done | 8.258 |
| UNIVERSE_BUILDING | done | 8.29 |
| SCORING_V2 | done | 8.326 |
| REGION_CLUSTERING | done | 8.352 |
| FIELD_PLANNING | done | 8.369 |
| SIMULATION | done | 8.371 |
| VOTER_UNIVERSE_EXPORT | skipped | 8.372 |
| FORECAST_GENERATION | done | 8.41 |
| TURF_GENERATION | done | 8.432 |
| EXPORT_V2_OUTPUTS | done | 18.521 |
| DIAGNOSTICS | done | 18.541 |
| STRATEGY_GENERATOR | done | 19.33 |
| GEO_VALIDATION | done | 20.198 |
| JOIN_GUARD_VALIDATION | done | 20.213 |
| INTEGRITY_REPAIRS_WRITE | done | 20.219 |
| ARTIFACT_VALIDATION | done | 20.238 |
| POST_RUN_AUDIT | done | 20.253 |
| ADVANCED_UNIVERSE_ESTIMATES | done | 20.277 |
| OPTIMIZER | done | 20.28 |
| ADVANCED_LIFT_MODEL | done | 20.281 |
| ADVANCED_SCENARIOS | done | 236.198 |
| ADVANCED_QA | done | 236.221 |
