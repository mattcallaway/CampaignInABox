# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-05__040056__0e0e8b52__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T12:00:56.925186+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `17c7dd43670203f9...` |

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
| VALIDATE_GEOGRAPHY | done | 0.01 |
| VALIDATE_VOTES | done | 0.011 |
| LOAD_GEOMETRY | skipped | 0.011 |
| LOAD_CROSSWALKS | skipped | 0.15 |
| SCAFFOLD_CONTEST_JSON | done | 0.164 |
| PARSE_CONTEST | done | 0.181 |
| NORMALIZE_SCHEMA/Sheet1 | done | 0.187 |
| SANITY/Sheet1 | done | 0.187 |
| BUILD_MODEL/Sheet1 | done | 0.194 |
| ALLOCATE_VOTES | done | 0.195 |
| INTEGRITY_ENFORCEMENT | done | 0.2 |
| FEATURE_ENGINEERING | done | 0.209 |
| UNIVERSE_BUILDING | done | 0.232 |
| SCORING_V2 | done | 0.241 |
| REGION_CLUSTERING | done | 0.249 |
| FIELD_PLANNING | done | 0.254 |
| SIMULATION | done | 0.254 |
| VOTER_UNIVERSE_EXPORT | skipped | 0.254 |
| FORECAST_GENERATION | done | 0.268 |
| TURF_GENERATION | done | 0.272 |
| EXPORT_V2_OUTPUTS | done | 0.314 |
| DIAGNOSTICS | done | 0.33 |
| STRATEGY_GENERATOR | done | 0.415 |
| GEO_VALIDATION | done | 0.417 |
| JOIN_GUARD_VALIDATION | done | 0.42 |
| INTEGRITY_REPAIRS_WRITE | done | 0.423 |
| ARTIFACT_VALIDATION | done | 0.429 |
| POST_RUN_AUDIT | done | 0.441 |
