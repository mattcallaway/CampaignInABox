# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-05__035835__0e0e8b52__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T11:58:35.489009+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `d225b654abdcdd79...` |

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
| INGEST_STAGING | skipped | 0.011 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.02 |
| VALIDATE_GEOGRAPHY | done | 0.028 |
| VALIDATE_VOTES | done | 0.029 |
| LOAD_GEOMETRY | skipped | 0.031 |
| LOAD_CROSSWALKS | skipped | 0.304 |
| SCAFFOLD_CONTEST_JSON | done | 0.324 |
| PARSE_CONTEST | done | 0.356 |
| NORMALIZE_SCHEMA/Sheet1 | done | 0.367 |
| SANITY/Sheet1 | done | 0.367 |
| BUILD_MODEL/Sheet1 | done | 0.379 |
| ALLOCATE_VOTES | done | 0.379 |
| INTEGRITY_ENFORCEMENT | done | 0.388 |
| FEATURE_ENGINEERING | done | 0.399 |
| UNIVERSE_BUILDING | done | 0.41 |
| SCORING_V2 | done | 0.423 |
| REGION_CLUSTERING | done | 0.437 |
| FIELD_PLANNING | done | 0.442 |
| SIMULATION | done | 0.444 |
| VOTER_UNIVERSE_EXPORT | skipped | 0.444 |
| FORECAST_GENERATION | done | 0.466 |
| TURF_GENERATION | done | 0.472 |
| EXPORT_V2_OUTPUTS | done | 0.5 |
| DIAGNOSTICS | done | 0.519 |
| STRATEGY_GENERATOR | skipped | 0.605 |
| GEO_VALIDATION | done | 0.607 |
| JOIN_GUARD_VALIDATION | done | 0.613 |
| INTEGRITY_REPAIRS_WRITE | done | 0.618 |
| ARTIFACT_VALIDATION | done | 0.625 |
| POST_RUN_AUDIT | done | 0.655 |
