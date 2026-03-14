# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-14__001450__25f8d317__msi` |
| **Status** | PARTIAL |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | prop_50_special |
| **Started** | 2026-03-14T07:14:50.601844+00:00 |

## Input Files

| Label | SHA-256 (first 16) |
|---|---|

## Output Files

| Path | SHA-256 (first 16) |
|---|---|
| `boundaries_index.csv` | `b4dff0e71c422e61...` |

## Coverage Metrics

- **canonical_geometry**: MPREC
- **categories_present**: 12
- **categories_missing**: 0

## NEEDS / Missing Data

- **detail.xlsx** [missing] — blocks: parse_contest, allocate_votes, export_model
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\votes\2024\prop_50_special\detail.xlsx`

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| DATA_INTAKE_ANALYSIS | skipped | 0.066 |
| INGEST_STAGING | skipped | 0.066 |
| SCAFFOLD_BOUNDARY_INDEX_Sonoma | done | 0.068 |
| VALIDATE_GEOGRAPHY | done | 0.071 |
| VALIDATE_VOTES | skipped | 0.072 |
