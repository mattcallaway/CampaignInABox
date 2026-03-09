# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-09__150530__cc2e639f__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | prop_50_special |
| **Started** | 2026-03-09T22:05:30.826489+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `1028d97deafd02d8...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `77f8cf249ee3476e...` |

## Coverage Metrics

- **canonical_geometry**: MPREC
- **categories_present**: 12
- **categories_missing**: 0
- **sheets_parsed**: 3
- **rows_2**: 2
- **rows_3**: 390
- **rows_4**: 55

## NEEDS / Missing Data

- **geopandas_library** [missing] — blocks: geometry_load, kepler_export

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| INGEST_STAGING | skipped | 0.005 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.008 |
| VALIDATE_GEOGRAPHY | done | 0.019 |
| VALIDATE_VOTES | done | 0.021 |
| LOAD_GEOMETRY | skipped | 0.023 |
| LOAD_CROSSWALKS | skipped | 0.276 |
| SCAFFOLD_CONTEST_JSON | done | 0.277 |
| PARSE_CONTEST | done | 0.628 |
| NORMALIZE_SCHEMA/2 | done | 0.636 |
| SANITY/2 | done | 0.636 |
| BUILD_MODEL/2 | done | 0.653 |
| NORMALIZE_SCHEMA/3 | done | 0.658 |
| SANITY/3 | done | 0.658 |
| BUILD_MODEL/3 | done | 0.667 |
| NORMALIZE_SCHEMA/4 | done | 0.671 |
| SANITY/4 | done | 0.672 |
| BUILD_MODEL/4 | done | 0.679 |
| ALLOCATE_VOTES | done | 0.679 |
| INTEGRITY_ENFORCEMENT | done | 0.758 |
| FEATURE_ENGINEERING | done | 0.79 |
| UNIVERSE_BUILDING | done | 0.829 |
| SCORING_V2 | done | 0.879 |
| REGION_CLUSTERING | done | 0.93 |
| FIELD_PLANNING | done | 0.952 |
| SIMULATION | done | 0.954 |
| VOTER_UNIVERSE_EXPORT | skipped | 0.955 |
| FORECAST_GENERATION | done | 1.006 |
| TURF_GENERATION | done | 1.046 |
| EXPORT_V2_OUTPUTS | done | 1.421 |
| DIAGNOSTICS | done | 1.635 |
| STRATEGY_GENERATOR | done | 1.935 |
| GEO_VALIDATION | done | 1.939 |
| JOIN_GUARD_VALIDATION | done | 1.945 |
| INTEGRITY_REPAIRS_WRITE | done | 1.949 |
| ARTIFACT_VALIDATION | done | 1.961 |
| POST_RUN_AUDIT | done | 1.981 |
| ADVANCED_UNIVERSE_ESTIMATES | done | 1.99 |
| OPTIMIZER | done | 1.991 |
| ADVANCED_LIFT_MODEL | done | 1.991 |
| ADVANCED_SCENARIOS | done | 121.333 |
| ADVANCED_QA | done | 121.337 |
