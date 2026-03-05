# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-05__010336__74fbdd60__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T09:03:36.755763+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `a27687f7c0780fc1...` |

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
| LOAD_CROSSWALKS | skipped | 0.057 |
| SCAFFOLD_CONTEST_JSON | done | 0.073 |
| PARSE_CONTEST | done | 0.092 |
| SANITY/Sheet1 | done | 0.093 |
| BUILD_MODEL/Sheet1 | done | 0.102 |
| ALLOCATE_VOTES | done | 0.102 |
| FEATURE_ENGINEERING | done | 0.111 |
| UNIVERSE_BUILDING | done | 0.12 |
| SCORING_V2 | done | 0.128 |
| FORECASTING | done | 0.141 |
| TURF_GENERATION | done | 0.148 |
| EXPORT_V2_OUTPUTS | done | 0.163 |
| DIAGNOSTICS | done | 0.182 |
