# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-05__030049__521cfe43__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T11:00:49.697978+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `b78910951b53c0ea...` |

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
| INGEST_STAGING | skipped | 0.005 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.008 |
| VALIDATE_GEOGRAPHY | done | 0.011 |
| VALIDATE_VOTES | done | 0.012 |
| LOAD_GEOMETRY | skipped | 0.013 |
| LOAD_CROSSWALKS | skipped | 0.232 |
| SCAFFOLD_CONTEST_JSON | done | 0.252 |
| PARSE_CONTEST | done | 0.274 |
| SANITY/Sheet1 | done | 0.275 |
| BUILD_MODEL/Sheet1 | done | 0.288 |
| ALLOCATE_VOTES | done | 0.288 |
| INTEGRITY_ENFORCEMENT | done | 0.291 |
| FEATURE_ENGINEERING | done | 0.304 |
| UNIVERSE_BUILDING | done | 0.314 |
| SCORING_V2 | done | 0.326 |
| REGION_CLUSTERING | done | 0.33 |
| FIELD_PLANNING | done | 0.337 |
| SIMULATION | done | 0.338 |
| VOTER_UNIVERSE_EXPORT | skipped | 0.338 |
| FORECAST_GENERATION | done | 0.352 |
| TURF_GENERATION | done | 0.357 |
| EXPORT_V2_OUTPUTS | done | 0.429 |
| DIAGNOSTICS | done | 0.451 |
| STRATEGY_GENERATOR | done | 0.58 |
