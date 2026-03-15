# Repair Actions Taken — Prompt 32

## Primary Fix: parse_contest_sheet Preamble-Label Detection

**File:** scripts/loaders/contest_parser.py
**Lines added:** ~60 new lines after existing Step 6 (build DataFrame)

**Problem:** Canvass-format workbooks (gov't election results PDF-to-Excel) have 6-row preambles.
The column header row appears at row 6 but parse_contest_sheet picked a different row as header_idx,
leaving the column labels ('Registered Voters', 'Voters Cast') as data row 0.

**Fix logic:**
1. Check df.iloc[0] for recognized label strings
2. Build position→label map from that row
3. Strip label row from data
4. Extract Registered from column at posn(label='Registered Voters')
5. Extract BallotsCast from column at posn(label='Voters Cast'/'Total Votes')

**Validation:** 
- registered>0: 371/392 precincts in Sheet3 (pre-fix: 0/392)
- 0 CRITICAL violations in post-fix pipeline run (pre-fix: 366)

---

## Secondary Fix: DATA_QUALITY_WARNING Guardrail

**File:** scripts/run_pipeline.py
**Lines added:** ~40 lines after INTEGRITY_ENFORCEMENT

After the INTEGRITY step, count precincts where registered=0 AND ballots_cast>0.
If >10% of rows have this pattern, emit a loud [DATA_QUALITY] WARN in the pipeline log.
This ensures future workbook layout changes or new contests trigger a visible alert.

---

## Tertiary Fix: safe_merge() left_on/right_on

**File:** scripts/lib/join_guard.py
**From:** Prompt 30.5 carry-over

un_pipeline.py:579 calls safe_merge with left_on=_join_col, right_on='_xw_src'.
Previously this caused a TypeError and area-weighted fallback (4x per run).
Now safe_merge accepts and correctly uses left_on/right_on parameters.

**Validation:** 0 crosswalk errors in post-fix pipeline run (pre-fix: 4 errors per run).
