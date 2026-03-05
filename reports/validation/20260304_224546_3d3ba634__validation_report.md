# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `20260304_224546_3d3ba634` |
| **Status** | SUCCESS |
| **State** | CA |
| **County** | SAMPLE_COUNTY |
| **Contest** | MEASURE_A |
| **Started** | 2026-03-05T06:45:46.613971+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|
| contest_file | `ee753d99eb6ccd44...` |

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `manifest.json` | `16f5a2d8ffb76764...` |
| `contest.json` | `a2804ef0e7071f4b...` |
| `20260304_224546_3d3ba634__precinct_model.csv` | `951109f49584fc66...` |
| `20260304_224546_3d3ba634__targeting_list.csv` | `e04574dc78faf642...` |
| `20260304_224546_3d3ba634__district_aggregates.csv` | `b3526d7d19293717...` |
| `20260304_224546_3d3ba634__precinct_model.csv` | `c70cf26e7f8fe3ac...` |
| `20260304_224546_3d3ba634__targeting_list.csv` | `22393d720e87fcac...` |
| `20260304_224546_3d3ba634__district_aggregates.csv` | `4bfc4ea2171e9987...` |

## Coverage Metrics

- **sheets_parsed**: 2
- **precinct_rows_Measure A**: 5
- **precinct_rows_DA Race**: 5

## NEEDS / Missing Data

- **geopandas_library** [missing] — blocks: geometry_load, kepler_export
- **SRPREC_TO_2020_BLK** [missing] — blocks: crosswalk_SRPREC_TO_2020_BLK
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\Campaign in a box Data\CA\SAMPLE_COUNTY\SRPREC_TO_2020_BLK`
- **RGPREC_TO_2020_BLK** [missing] — blocks: crosswalk_RGPREC_TO_2020_BLK
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\Campaign in a box Data\CA\SAMPLE_COUNTY\RGPREC_TO_2020_BLK`
- **2020_BLK_TO_MPREC** [missing] — blocks: crosswalk_2020_BLK_TO_MPREC
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\Campaign in a box Data\CA\SAMPLE_COUNTY\2020_BLK_TO_MPREC`
- **RG_to_RR_to_SR_to_SVPREC** [missing] — blocks: crosswalk_RG_to_RR_to_SR_to_SVPREC
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\Campaign in a box Data\CA\SAMPLE_COUNTY\RG_to_RR_to_SR_to_SVPREC`
- **MPREC_to_SRPREC** [missing] — blocks: crosswalk_MPREC_to_SRPREC
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\Campaign in a box Data\CA\SAMPLE_COUNTY\MPREC_to_SRPREC`
- **SRPREC_to_CITY** [missing] — blocks: crosswalk_SRPREC_to_CITY
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\Campaign in a box Data\CA\SAMPLE_COUNTY\SRPREC_to_CITY`
- **geometry_for_kepler** [blocked] — blocks: kepler_geojson
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\Campaign in a box Data\CA\SAMPLE_COUNTY\MPREC_GeoJSON`
- **geometry_for_kepler** [blocked] — blocks: kepler_geojson
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\Campaign in a box Data\CA\SAMPLE_COUNTY\MPREC_GeoJSON`

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| DISCOVER_INPUTS | done | 0.034 |
| VALIDATE_INPUTS | done | 0.034 |
| LOAD_GEOMETRY | skipped | 0.04 |
| LOAD_CROSSWALKS | skipped | 0.045 |
| PARSE_CONTEST | done | 0.078 |
| SANITY_CHECKS/Measure A | done | 0.083 |
| BUILD_MODEL/Measure A | done | 0.095 |
| SANITY_CHECKS/DA Race | done | 0.096 |
| BUILD_MODEL/DA Race | done | 0.104 |
| ALLOCATE_VOTES | done | 0.104 |
| KEPLER_EXPORT/Measure A | skipped | 0.123 |
| KEPLER_EXPORT/DA Race | skipped | 0.133 |
| EXPORT_OUTPUTS | done | 0.179 |
