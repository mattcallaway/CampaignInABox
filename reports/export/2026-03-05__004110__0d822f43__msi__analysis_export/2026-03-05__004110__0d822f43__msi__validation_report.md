# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-05__004110__0d822f43__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T08:41:10.806817+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `15704823393468d9...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |
| `contest.json` | `39bcb9a42a308867...` |
| `2026-03-05__004110__0d822f43__msi__precinct_model.csv` | `972c11ed94e24664...` |
| `2026-03-05__004110__0d822f43__msi__targeting_list.csv` | `9cc7a850ef7e134a...` |
| `2026-03-05__004110__0d822f43__msi__district_aggregates.csv` | `8859f7d371481d33...` |

## Coverage Metrics

- **canonical_geometry**: MPREC
- **categories_present**: 12
- **categories_missing**: 0
- **sheets_parsed**: 1
- **rows_Sheet1**: 10

## NEEDS / Missing Data

- **geopandas_library** [missing] — blocks: geometry_load, kepler_export
- **geometry_for_kepler** [blocked] — blocks: kepler_geojson
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\precinct_shapes\MPREC_GeoJSON`

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| INGEST_STAGING | skipped | 0.003 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.006 |
| VALIDATE_GEOGRAPHY | done | 0.009 |
| VALIDATE_VOTES | done | 0.011 |
| LOAD_GEOMETRY | skipped | 0.011 |
| LOAD_CROSSWALKS | skipped | 0.058 |
| SCAFFOLD_CONTEST_JSON | done | 0.073 |
| PARSE_CONTEST | done | 0.095 |
| SANITY/Sheet1 | done | 0.096 |
| BUILD_MODEL/Sheet1 | done | 0.105 |
| ALLOCATE_VOTES | done | 0.105 |
| KEPLER/Sheet1 | skipped | 0.119 |
| EXPORT_OUTPUTS | done | 0.14 |
