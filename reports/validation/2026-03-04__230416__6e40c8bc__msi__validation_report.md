# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-04__230416__6e40c8bc__msi` |
| **Status** | PARTIAL |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | nov2024_general |
| **Started** | 2026-03-05T07:04:16.220538+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `8057bff9429da8b9...` |

## Coverage Metrics

- **canonical_geometry**: NONE
- **categories_present**: 0
- **categories_missing**: 12

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
- **detail.xlsx** [missing] — blocks: parse_contest, allocate_votes, export_model
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\votes\2024\CA\Sonoma\nov2024_general\detail.xlsx`

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| INGEST_STAGING | skipped | 0.003 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.011 |
| VALIDATE_GEOGRAPHY | done | 0.014 |
| VALIDATE_VOTES | skipped | 0.014 |
