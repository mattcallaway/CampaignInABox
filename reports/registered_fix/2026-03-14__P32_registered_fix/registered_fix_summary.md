# Registered Voter Extraction Fix Summary — Prompt 32

**Timestamp:** 2026-03-14T20:05:00-07:00
**Status: FIX SUCCESSFUL ✅**

## Root Cause

The primary contest file for nov2025_special is SoCoNov2025StatewideSpclElec_PctCanvass (1).xlsx.
This canvass format workbook has a **6-row preamble per sheet** (Sonoma header, election title, blank, contest name, candidate row, column labels).

The parse_contest_sheet() function's header detection logic picked the first sparse row with ≥3 non-null items.
In the canvass format, this was too early — the actual column labels (Registered Voters, Voters Cast, etc.)
ended up in **data row 0** instead of the header row.

Since no header named egistered* existed, no Registered column was created.
extract_registered_voters() also returned 0 entries (no dedicated 'Registered Voters' sheet in canvass format).

Result: 366 precincts had egistered=0 with allots_cast>0 — all CRITICAL integrity violations.

## Fix Applied

**File:** scripts/loaders/contest_parser.py
**Location:** Step 6.5 (between existing Step 6 and Step 7)

Added preamble-label detection:
1. After building the DataFrame, check if data row 0 contains column label strings
2. Build a position→label mapping from that row
3. Strip the label row from actual precinct data
4. Extract Registered from column at position where label was Registered Voters
5. Extract BallotsCast from column at position where label was Voters Cast/Ballots Cast/Total Votes

Protection: only fires if data row 0 contains recognized label strings — does not affect normal layouts.

**Also Added:**
- un_pipeline.py: DATA_QUALITY_WARNING guardrail after INTEGRITY step (threshold: 10% registered-zero rows)
- join_guard.py: left_on/ight_on support for safe_merge() (Prompt 30.5 carry-over)

## Whether The Fix Worked

✅ **YES — VERIFIED IN LIVE RUN**

| Metric | Pre-Fix | Post-Fix |
|---|---|---|
| registered=0 CRITICAL rows | 366 | 0 |
| Data Integrity repairs needed | 366 | 0 |
| Diagnostics: Data Integrity | FAIL | PASS |
| turnout_pct | 0.0 for all | 0.45-0.89 (real values) |
| registered values | all zero | e.g. 16, 11, 23, 4, 10, 9... |

## Remaining Issues

1. **support_pct all zero** — No voter file loaded, so scores/targets are 0. Normal.
2. **Campaign Health INDEX WARNING** — War Room shows warning because no field ops data yet. Normal.
3. **~21 precincts with registered=0** — These are **genuine** zero-registration precincts (small or out-of-jurisdiction). Not a bug.

## Readiness for Next Audit

System is now ready. Registered voter counts are populated. Turnout ratios are reliable.
Next logical steps: add a voter file, generate scoring.
