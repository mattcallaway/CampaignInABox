# Crosswalk Repair Summary
**Run:** `2026-03-14__032119__p29_repair`  **Generated:** 2026-03-14 03:37
**Contest:** `nov2020_general`  **State:** `CA`  **County:** `Sonoma`

---

## Status

| Item | Result |
|---|---|
| Crosswalk files inspected | 6 |
| Detection OK | 6 |
| Detection failed (identity fallback risk) | 0 |
| Join quality verdict | **FAILED** |
| Total contest rows | 0 |
| Joined to geometry | 0 (0.0%) |
| Unjoined | 0 |
| Identity fallbacks | 0 |

---

## What Was Repaired (Prompt 29)

- `detect_crosswalk_columns()` upgraded from uppercase-only alias matching to a 3-tier
  resolution system: (1) per-file config override, (2) expanded alias table including
  lowercase column names, (3) filename heuristic tiebreaker.
- `config/precinct_id/crosswalk_column_hints.yaml` created with explicit column hints
  for all 5 Sonoma crosswalk files.
- `load_crosswalk_from_category()` now emits an explicit `IDENTITY_FALLBACK_USED`
  diagnostic instead of silently returning `{}, False`.
- Join outcome taxonomy added (`engine/precinct_ids/join_outcomes.py`).
- Per-row ID trace module added (`engine/precinct_ids/id_trace.py`).
- Join quality metrics module added (`engine/precinct_ids/join_quality.py`).
- Human review queue writer added (`engine/precinct_ids/review_queue.py`).

## Quality Notes

- 0% join rate — no precinct IDs matched geometry. Check contest schema and crosswalks.

## Next Recommended Action

1. Review `pre_audit_human_review.md` for any outstanding ambiguities.
2. If identity fallbacks still occur, add entries to `config/precinct_id/crosswalk_column_hints.yaml`.
3. Re-run the pipeline and check that join quality verdict improves to GOOD.
4. If precinct value remaps are needed, add them to `config/precinct_id/manual_mapping_overrides.yaml`.