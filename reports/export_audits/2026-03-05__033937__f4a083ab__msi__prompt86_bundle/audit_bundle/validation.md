# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-05__033937__f4a083ab__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T11:39:37.082752+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `19e540dc5eae3bec...` |

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
| VALIDATE_GEOGRAPHY | done | 0.011 |
| VALIDATE_VOTES | done | 0.011 |
| LOAD_GEOMETRY | skipped | 0.012 |
| LOAD_CROSSWALKS | skipped | 0.168 |
| SCAFFOLD_CONTEST_JSON | done | 0.182 |
| PARSE_CONTEST | done | 0.2 |
| NORMALIZE_SCHEMA/Sheet1 | done | 0.205 |
| SANITY/Sheet1 | done | 0.205 |
| BUILD_MODEL/Sheet1 | done | 0.215 |
| ALLOCATE_VOTES | done | 0.215 |
| INTEGRITY_ENFORCEMENT | done | 0.222 |
| FEATURE_ENGINEERING | done | 0.233 |
| UNIVERSE_BUILDING | done | 0.244 |
| SCORING_V2 | done | 0.255 |
| REGION_CLUSTERING | done | 0.275 |
| FIELD_PLANNING | done | 0.281 |
| SIMULATION | done | 0.283 |
| VOTER_UNIVERSE_EXPORT | skipped | 0.283 |
| FORECAST_GENERATION | done | 0.298 |
| TURF_GENERATION | done | 0.306 |
| EXPORT_V2_OUTPUTS | done | 0.367 |
| DIAGNOSTICS | done | 0.387 |
| STRATEGY_GENERATOR | done | 0.503 |
