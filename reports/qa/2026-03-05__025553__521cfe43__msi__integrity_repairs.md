# Integrity Repair Report
**Contest:** `2024_CA_sonoma_nov2024_general`
**Run ID:** `2026-03-05__025553__521cfe43__msi`
**Generated:** 2026-03-05T02:55:53.475247

## Status: ✅ No violations

| Rule | Count |
|---|---|

| _(no repairs)_ | — |

## Rule Definitions

| Rule | Description |
|---|---|
| `registered_not_integer` | Fractional `registered` value; rounded to nearest integer |
| `ballots_exceeds_registered` | `ballots_cast > registered`; proportionally scaled down |
| `yes_no_exceeds_ballots` | `yes_votes + no_votes > ballots_cast`; proportionally scaled down |

_Output: `derived/diagnostics/2024_CA_sonoma_nov2024_general__integrity_repairs.csv`_
