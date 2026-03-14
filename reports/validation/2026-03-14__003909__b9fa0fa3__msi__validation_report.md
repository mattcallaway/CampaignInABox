# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-14__003909__b9fa0fa3__msi` |
| **Status** | PARTIAL |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | 2020_general |
| **Started** | 2026-03-14T07:39:09.221861+00:00 |

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
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\data\CA\counties\Sonoma\votes\2024\2020_general\detail.xlsx`

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| DATA_INTAKE_ANALYSIS | done | 0.059 |
| INGEST_STAGING | skipped | 0.059 |
| SCAFFOLD_BOUNDARY_INDEX_Sonoma | done | 0.061 |
| VALIDATE_GEOGRAPHY | done | 0.065 |
| VALIDATE_VOTES | skipped | 0.065 |
