# Registered Extraction Trace — Prompt 32

**Timestamp:** 2026-03-14T19:51:39-07:00

## Extraction Path

1. `parse_contest_workbook` called with canvass file
2. `extract_registered_voters(workbook_path)` → 0 entries (no dedicated sheet)
3. `parse_contest_sheet(sheet_name, rows)` called per sheet
4. **Step 6.5 (NEW):** Preamble-label detection fires on each contest sheet
5. Label row at data[0] contains position labels: {2: 'Registered Voters', 3: 'Voters Cast', ...}
6. Label row stripped from data
7. `Registered` column created from column index 2 (unnamed_2)
8. `BallotsCast` column created from column index 3 (unnamed_3)
9. `aggregate_to_precinct_totals` reads `Registered` from df.columns correctly

## Post-Fix Counts

| Sheet | Name | Registered>0 | Registered=0 | Ballots>0 |
|---|---|---|---|---|
| Document map | PrecinctCanvass (table of contents) | 0 | 3 | 0 |
| Sheet2 | Timber Cove CWD | 1 | 0 | 1 |
| Sheet3 | Prop 50 Special | 371 | 19 | 363 |
| Sheet4 | Petaluma JUHSD Parcel Tax | 53 | 2 | 51 |

Note: The 19+2=21 zeros are **legitimate** small precincts with 0 registered voters (e.g. 0100002=13, 0100006=3 registered). Some precincts genuinely have 0 registered in this special election.

## Diagnostic Source Column

- Sheet3: `unnamed_2` (position index 2) → mapped from label 'Registered Voters'
- Sheet4: `unnamed_2` (position index 2) → mapped from label 'Registered Voters'
- Sheet2: `unnamed_2` (position index 2) → mapped from label 'Registered Voters'

## Pre-Fix vs Post-Fix

| Metric | Pre-Fix | Post-Fix |
|---|---|---|
| registered=0 (with ballots>0) | 366 | ~21 (legitimate zeros) |
| turnout_pct computable | No (0/0) | Yes (e.g. 76.9%, 72.7%...) |
| registered source method | Not detected | Preamble-label position detection |
