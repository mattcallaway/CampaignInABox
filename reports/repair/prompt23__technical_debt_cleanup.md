# Repair Report: Technical Debt Cleanup
**Report ID:** prompt23_repair | **Generated:** 2026-03-12T22:30:00-07:00

## Summary
Deleted 20 `tmp_patch_*.py` files from repository root. Created shared utility modules to replace duplicated patterns.

## Deleted Files Manifest

| File | Original Purpose | Why Deleted |
|------|----------------|-------------|
| `tmp_fix_pipeline.py` | Pipeline fix script | Development artifact; logic merged |
| `tmp_gen_ca.py` | CA data generator | Superseded by archive_ingest.py |
| `tmp_patch_app.py` | App routing patch | Logic merged into app.py |
| `tmp_patch_app_login.py` | Login flow | Logic in auth_manager.py |
| `tmp_patch_app_v.py` | App versioning | Not needed |
| `tmp_patch_diag.py` | Diagnostics | Logic in diagnostics_view.py |
| `tmp_patch_dm.py` | Data manager | Logic in data_manager_view.py |
| `tmp_patch_footer.py` | Footer rendering | Logic in app.py |
| `tmp_patch_lift_models.py` | Lift model patch | Superseded by C01 fix |
| `tmp_patch_map.py` | Map view patch | Logic in map_view.py |
| `tmp_patch_nav.py` | Navigation patch | Logic in ui_pages.yaml + app.py |
| `tmp_patch_readme.py` | README patch | Documentation complete |
| `tmp_patch_strat.py` | Strategy view | Logic in strategy_view.py |
| `tmp_patch_strategy.py` | Strategy engine | Superseded by C02 fix |
| `tmp_patch_ui.py` | UI general | Logic in app.py |
| `tmp_patch_wr.py` | War room | Logic in war_room_view.py |
| `tmp_refactor.py` | Refactor helper | Done |
| `tmp_update_collab.py` | Collaboration | Done |
| `tmp_update_sim.py` | Simulation | Done |
| `tmp_update_state_builder.py` | State builder | Done |

**Total deleted: 20 files**

## New Shared Utilities Created

| Module | Replaces |
|--------|---------|
| `engine/utils/helpers.py` | `_g()` in 5+ files, `_find_latest()` in 4+ files, `BASE_DIR` in 20+ files |
| `engine/utils/derived_data_reader.py` | All file-finding patterns in strategy, war room, state builder |

## Remaining Known Debt (Not Critical — Future Work)

- `engine/audit/post_prompt86_audit.py` — named after "prompt 86" but not current; assess if refactor needed
- `engine/advanced_modeling/model_card.py` — informational only; not called from pipeline
- `engine/advanced_modeling/qa_checks.py` — not wired into pipeline
- `engine/data_intake/source_finder.py` — not wired into pipeline

These are low-risk orphan modules and can be addressed in a future cleanup pass.
