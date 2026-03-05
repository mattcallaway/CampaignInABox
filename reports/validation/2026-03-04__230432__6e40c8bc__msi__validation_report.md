# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-04__230432__6e40c8bc__msi` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T07:04:32.660656+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| detail.xlsx | `ee753d99eb6ccd44...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `8057bff9429da8b9...` |
| `contest.json` | `469679607840f192...` |
| `2026-03-04__230432__6e40c8bc__msi__precinct_model.csv` | `951109f49584fc66...` |
| `2026-03-04__230432__6e40c8bc__msi__targeting_list.csv` | `e04574dc78faf642...` |
| `2026-03-04__230432__6e40c8bc__msi__district_aggregates.csv` | `9203bdbf2067bd1a...` |
| `2026-03-04__230432__6e40c8bc__msi__precinct_model.csv` | `c70cf26e7f8fe3ac...` |
| `2026-03-04__230432__6e40c8bc__msi__targeting_list.csv` | `22393d720e87fcac...` |
| `2026-03-04__230432__6e40c8bc__msi__district_aggregates.csv` | `041c6ecb806d4e27...` |

## Coverage Metrics

- **canonical_geometry**: NONE
- **categories_present**: 0
- **categories_missing**: 12
- **sheets_parsed**: 2
- **rows_Measure A**: 5
- **rows_DA Race**: 5

## NEEDS / Missing Data

- **MPREC GeoJSON** [missing] — blocks: geometry_load, kepler_export, precinct_model
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\precinct_shapes\MPREC_GeoJSON`
- **MPREC GeoPackage** [missing] — blocks: geometry_load, kepler_export, precinct_model
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\precinct_shapes\MPREC_GeoPackage`
- **MPREC Shapefile** [missing] — blocks: geometry_load, kepler_export, precinct_model
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\precinct_shapes\MPREC_Shapefile`
- **SRPREC GeoJSON** [missing] — blocks: geometry_load, kepler_export, precinct_model
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\precinct_shapes\SRPREC_GeoJSON`
- **SRPREC GeoPackage** [missing] — blocks: geometry_load, kepler_export, precinct_model
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\precinct_shapes\SRPREC_GeoPackage`
- **SRPREC Shapefile** [missing] — blocks: geometry_load, kepler_export, precinct_model
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\precinct_shapes\SRPREC_Shapefile`
- **2020 BLK TO MPREC** [missing] — blocks: crosswalk_2020_BLK_TO_MPREC
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\crosswalks`
- **RGPREC TO 2020 BLK** [missing] — blocks: crosswalk_RGPREC_TO_2020_BLK
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\crosswalks`
- **SRPREC TO 2020 BLK** [missing] — blocks: crosswalk_SRPREC_TO_2020_BLK
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\crosswalks`
- **RG to RR to SR to SVPREC** [missing] — blocks: crosswalk_allocation
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\crosswalks`
- **MPREC to SRPREC** [missing] — blocks: crosswalk_allocation
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\crosswalks`
- **SRPREC to CITY** [missing] — blocks: crosswalk_SRPREC_to_CITY
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\crosswalks`
- **geometry_for_kepler** [blocked] — blocks: kepler_geojson
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\precinct_shapes\MPREC_GeoJSON`
- **geometry_for_kepler** [blocked] — blocks: kepler_geojson
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\geography\precinct_shapes\MPREC_GeoJSON`

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| INGEST_STAGING | skipped | 0.004 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.007 |
| VALIDATE_GEOGRAPHY | done | 0.009 |
| VALIDATE_VOTES | done | 0.01 |
| LOAD_GEOMETRY | skipped | 0.014 |
| LOAD_CROSSWALKS | skipped | 0.016 |
| SCAFFOLD_CONTEST_JSON | done | 0.024 |
| PARSE_CONTEST | done | 0.044 |
| SANITY/Measure A | done | 0.046 |
| BUILD_MODEL/Measure A | done | 0.054 |
| SANITY/DA Race | done | 0.056 |
| BUILD_MODEL/DA Race | done | 0.061 |
| ALLOCATE_VOTES | done | 0.061 |
| KEPLER/Measure A | skipped | 0.075 |
| KEPLER/DA Race | skipped | 0.084 |
| EXPORT_OUTPUTS | done | 0.111 |
