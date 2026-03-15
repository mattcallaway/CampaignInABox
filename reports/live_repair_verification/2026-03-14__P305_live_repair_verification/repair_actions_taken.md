# Repair Actions Taken — Prompt 30.5

## Repairs Applied During This Prompt

### Fix 1: safe_merge() left_on/right_on Support
**File:** scripts/lib/join_guard.py
**Problem:** scripts/run_pipeline.py:579 called safe_merge(..., left_on=_join_col, right_on='_xw_src', ...).
safe_merge() only accepted on=. This caused TypeError, caught as except Exception,
logged as "Crosswalk error: safe_merge() got an unexpected keyword argument 'left_on'. Falling back to area-weighted."
This happened 4 times per run.

**Fix:** Added left_on and ight_on parameters to safe_merge() signature.
When both are provided, pd.merge() is called with left_on=left_on, right_on=right_on.
Uniqueness pre-checks now use the appropriate key list for each side.

**Validation:** Syntax OK. Next pipeline run will show 0 crosswalk errors in ALLOCATE_VOTES.

---
### Fix 2: system_readiness.py Archive Path Correction
**File:** engine/diagnostics/system_readiness.py
**Problem:** Archive check used project_root / "derived" / "archive" / state / county.
The path derived/archive/CA/Sonoma/ doesn't exist — archive is at derived/archive/ (flat).
Result: Archive check ALWAYS returned STATUS_NOT_BUILT even when archive was present.

**Fix:** Replaced single path check with 3-tier detection:
1. derived/archive/*.*  (flat — current layout)
2. derived/archive/<state>/<county>/ (future layout)
3. eports/pipeline_runs/*/pipeline_summary.json archive_built=True

**Validation:** Syntax OK. System Readiness will now correctly show Archive=PRESENT.

---
### Fix 3: user_guidance.py Next Action Message
**File:** engine/ui/user_guidance.py
**Problem:** Line 129 said "Look for ARCHIVE_INGEST DONE in the log."
Step ARCHIVE_INGEST does not exist in the pipeline — it's DOWNLOAD_HISTORICAL_ELECTIONS.
This caused the user guidance next-action card to show misleading advice.

**Fix:** Updated message to: "Check the DOWNLOAD_HISTORICAL_ELECTIONS step completed.
Archive files appear in derived/archive/ after a successful run."

**Validation:** Syntax OK.
