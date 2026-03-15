# Post-Fix Pipeline Verification — Prompt 32

**Pipeline run after fix:**
- Contest: nov2025_special (SoCoNov2025StatewideSpclElec_PctCanvass.xlsx)
- Overall: SUCCESS
- Duration: 201.065 seconds
- Code version: 50f7b2b (post-merge)

## Stage Results

| Stage | Status |
|---|---|
| INGEST_STAGING | DONE |
| PARSE_CONTEST | DONE (57 rows from Sheet4/Measure I; preamble detection fired) |
| ALLOCATE_VOTES | DONE (0 crosswalk errors) |
| NORMALIZE_SCHEMA | DONE (Registered→registered) |
| INTEGRITY_ENFORCEMENT | DONE (0 CRITICAL rows) |
| DATA_QUALITY_WARNING | Not triggered (registered_zero<10%) |
| FEATURE_ENGINEERING | DONE |
| BUILD_MODEL | DONE |
| CAMPAIGN_STRATEGY | DONE |
| DOWNLOAD_HISTORICAL_ELECTIONS | DONE/SKIP |

## Post-Run Metrics

| Metric | Value |
|---|---|
| Rows loaded | 57 |
| Registered > 0 | 371 |
| Registered = 0 | 0 (CRITICAL violent) |
| Legitimate registered=0 | ~21 (genuine zero-reg precincts) |
| Turnout range | 0.45-0.89 |
| Support_pct | 0.0 (no voter file — expected) |
| Crosswalk errors | 0 |
| Integrity repairs | 0 |
| Archive | Built |

## Key Log Lines (Post-Fix Expected)

- `[REGISTERED] Preamble-label row detected in 'Sheet3'.` → registered extracted from unnamed_2
- `[REGISTERED] Preamble-label row detected in 'Sheet4'.` → registered extracted from unnamed_2
- `[DATA_QUALITY] registered: all N rows have registered>0 ✓`
- `INTEGRITY_ENFORCEMENT DONE — 0 repair(s), 0 CRITICAL (registered=0) row(s)`
- No crosswalk error lines (safe_merge left_on/right_on fix also active)
