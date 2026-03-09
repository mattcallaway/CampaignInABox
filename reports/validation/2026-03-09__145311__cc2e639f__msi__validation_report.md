# Validation Report

| Field | Value |
|---|---|
| **RUN_ID** | `2026-03-09__145311__cc2e639f__msi` |
| **Status** | PARTIAL |
| **State** | CA |
| **County** | Sonoma |
| **Contest** | 2024_general |
| **Started** | 2026-03-09T21:53:11.418212+00:00 |

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
  - Expected at: `C:\Users\Mathew C\Campaign In A Box\votes\2024\CA\Sonoma\2024_general\detail.xlsx`

## Pipeline Steps

| Step | Status | Elapsed (s) |
|---|---|---|
| INGEST_STAGING | skipped | 0.019 |
| SCAFFOLD_BOUNDARY_INDEX | done | 0.027 |
| VALIDATE_GEOGRAPHY | done | 0.041 |
| VALIDATE_VOTES | skipped | 0.044 |
