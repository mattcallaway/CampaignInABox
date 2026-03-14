# Next Audit Readme — Post Prompt 29
**Written:** 2026-03-14T03:21:00-07:00

## Which Files to Inspect First

1. `reports/crosswalk_repair/*/crosswalk_repair_summary.md` — overall repair status
2. `derived/precinct_id_review/*__crosswalk_review.csv` — any remaining detection failures
3. `derived/precinct_id_review/*__join_review.csv` — any unresolved precinct IDs
4. `config/precinct_id/crosswalk_column_hints.yaml` — verify all 5 Sonoma files have hints
5. `data/contests/CA/Sonoma/2020/nov2020_general/registry.json` — verify contest is registered

## What Success Looks Like

- `crosswalk_repair_summary.md` shows Detection OK: 5/5 files (after running pipeline)
- `*__crosswalk_review.csv` is empty (no detection failures)
- Pipeline LOAD_CROSSWALKS step shows DONE [OK] (not SKIP)
- Precinct map shows full Sonoma precinct coverage (~approx 400 precincts)
- Archive precinct profiles are non-empty

## Pending Human Decisions

1. Confirm crosswalk vintage is correct for 2020 contest (g24 crosswalks used for 2020 data)
2. Decide on any precinct value remaps if join rate < 85% after repair
3. Fill out `pre_audit_human_review.md` after running full pipeline

## Platform Readiness

- Code repair: COMPLETE
- Config hints: COMPLETE (5 files)
- Smoke tests: PASS (4/4 files detect)
- Full pipeline validation: PENDING (requires user to run pipeline via UI)
- Human review decisions: PENDING
