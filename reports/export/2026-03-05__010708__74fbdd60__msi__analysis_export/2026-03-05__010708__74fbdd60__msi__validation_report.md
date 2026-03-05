# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-05__010708__74fbdd60__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T09:07:09.039909+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `8cb175dd6ce18a0f...` |

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
| INGEST_STAGING | skipped | 0.003 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.006 |
| VALIDATE_GEOGRAPHY | done | 0.009 |
| VALIDATE_VOTES | done | 0.01 |
| LOAD_GEOMETRY | skipped | 0.011 |
| LOAD_CROSSWALKS | skipped | 0.056 |
| SCAFFOLD_CONTEST_JSON | done | 0.071 |
| PARSE_CONTEST | done | 0.091 |
| SANITY/Sheet1 | done | 0.092 |
| BUILD_MODEL/Sheet1 | done | 0.101 |
| ALLOCATE_VOTES | done | 0.101 |
| FEATURE_ENGINEERING | done | 0.11 |
| UNIVERSE_BUILDING | done | 0.12 |
| SCORING_V2 | done | 0.128 |
| FORECASTING | done | 0.142 |
| TURF_GENERATION | done | 0.146 |
| EXPORT_V2_OUTPUTS | done | 0.154 |
| DIAGNOSTICS | done | 0.167 |
