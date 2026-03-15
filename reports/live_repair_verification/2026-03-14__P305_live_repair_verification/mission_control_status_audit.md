# Mission Control Status Audit — Prompt 30.5

**Timestamp:** 2026-03-14T17:24:39-07:00

## Comparison: Mission Control vs Pipeline Truth

| MC Element | MC Shows | Pipeline Truth | Match? |
|---|---|---|---|
| Stage 3 Archive | ✅ Archive Built | archive_built=true in pipeline_summary.json | ✅ CORRECT |
| Right Panel Archive | ✅ Yes | archive_built=true | ✅ CORRECT |
| System Readiness Archive | ❌ NOT BUILT (red) | derived/archive/ has content | ❌ BUG — fixed P30.5 |
| Last Run | nov2025_special — SUCCESS | pipeline_summary.json overall=SUCCESS | ✅ CORRECT |
| Precinct Join Rate | UNKNOWN | precinct_join_rate=1.0 | ❌ UNKNOWN — join quality JSON not written |
| NEEDS_REVIEW (all files) | Still showing | file_watcher fix present but app hot-reload needed | ⚠️ STALE |
| Next Action | "Check ARCHIVE_INGEST DONE" | Archive is already built | ❌ MISLEADING — fixed P30.5 |

## Mismatch Analysis

### Mission Control vs Reality: Archive
- **Before P30.5:** Stage 3 showed "Not Built" — WRONG (archive exists at derived/archive/)
- **After P30.5 (P31.5 fixes):** Stage 3 shows "Archive Built" — CORRECT
- **Remaining issue:** System Readiness panel (right column) still shows Archive=NOT BUILT
  because system_readiness.py checked derived/archive/CA/Sonoma/ which doesn't exist
  — FIXED in P30.5 (now checks flat derived/archive/ + pipeline_summary.json)

### Mission Control vs Reality: NEEDS_REVIEW
- **Before P30.5:** All 3 contest files show NEEDS_REVIEW
- **Root cause:** file_watcher._sniff_precinct_column only tried skiprows=0
- **After fix:** Tries skiprows 0-5 + prefix matching — should resolve
- **Status:** Hot-reload required for running app to pick up watcher change

### Mission Control vs Reality: Precinct Join Rate
- **MC shows:** UNKNOWN
- **Pipeline truth:** precinct_join_rate=1.0 (100%)
- **Root cause:** system_readiness.py reads derived/precinct_id_review/*__join_quality.json
  but pipeline writes precinct_join_rate to pipeline_summary.json
- **Recommendation:** Update precinct join rate check to also read pipeline_summary.json

## Recommended Further Changes

1. Add pipeline_summary.json fallback to Precinct Join Rate check in system_readiness.py
2. Force contest file watcher re-scan on each Mission Control page render (not cached from startup)
3. Consider caching system_readiness at session level with TTL, not indefinitely
