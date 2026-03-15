# Pre-Fix Baseline — Prompt 32 Registered Voter Extraction

**Run ID:** 2026-03-14__P32_registered_fix
**Timestamp:** 2026-03-14T19:51:39-07:00
**Workbook:** SoCoNov2025StatewideSpclElec_PctCanvass (1).xlsx
**Pipeline run analyzed:** 2026-03-14__162713__2d64260a__msi (rows_loaded=3)

## Root Cause Confirmed

| Finding | Detail |
|---|---|
| Primary contest file | SoCoNov2025StatewideSpclElec_PctCanvass (1).xlsx (not detail.xlsx) |
| Canvass sheet structure | 6-row preamble per sheet (Sonoma/State, contest title, blank, contest name, candidate row, column labels) |
| header_idx picked | Row 0 (first row with >= 3 non-null values = actually a sparse row picking unnamed_0..17) |
| Registered Voters text location | Data row 0 (becomes the first actual data row, not part of the header) |
| parse_contest_sheet result | Registered column not set — no header matches 'registered*' |
| extract_registered_voters result | 0 entries — canvass has no dedicated 'Registered Voters' sheet |
| Downstream registered count | 0 for ALL rows → registered=0 but ballots>0 for 366 rows |

## Pre-Fix Counts (from log 2026-03-14__162713__2d64260a__msi)

- [INTEGRITY] 2 precinct(s) CRITICAL — registered=0 but ballots>0
- [INTEGRITY] 320 precinct(s) CRITICAL — registered=0 but ballots>0
- [INTEGRITY] 44 precinct(s) CRITICAL — registered=0 but ballots>0
- Total: **366 precincts** with registered=0 but valid ballot counts

## Example Bad Rows (pre-fix)

| Precinct | registered | ballots_cast | turnout_pct |
|---|---|---|---|
| 0100002 | 0 | 10 | 0.0 (unreliable) |
| 0100003 | 0 | 32 | 0.0 (unreliable) |
| 0100018 | 0 | 36 | 0.0 (unreliable) |

## Downstream Impact

- Turnout ratios: 0.0 for all precincts (unusable)
- Scoring: turnout-weighted scores unreliable
- Strategy: turnout recommendations incorrect
- Model calibration: likely nominal (uses priors only anyway)
- Mission Control: no direct display of registered values
