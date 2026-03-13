# Campaign Switch Cache Validation Report
**Run ID:** 20260313__prompt27_validation  **Generated:** 2026-03-13T19:47:40.298017

## Validation Results

| Check | Status | Detail |
|-------|--------|--------|
| campaign_state_resolver routes to campaign-scoped paths | PASS | Verified in Phase 1 |
| Single active campaign enforcement | PASS | validate_registry() auto-repairs >1 active |
| Legacy path populated as compat alias only | PASS | seed_legacy_alias() called in _write_state() |
| app.py does not hardcode derived/state/latest | PASS | grep found 0 references |
| state_builder raises RuntimeError if no active campaign | PASS | Verified in Phase 2 |

## Cache Invalidation
- When campaign is switched via campaign_manager.set_active(), active_campaign.yaml is updated.
- Bootstrap in app.py reads active_campaign.yaml on each page load.
- Streamlit's st.cache_data is keyed by function arguments; on campaign switch,
  callers should call `st.cache_data.clear()` or reload the page.
- Recommendation: add explicit cache clear in campaign_admin_view.py on set_active confirmation.

## Cross-Campaign Contamination Risk
- PRIMARY: Eliminated — state writes go to per-campaign dirs.
- LEGACY ALIAS: Present — derived/state/latest/ is overwritten on every build.
  This is acceptable because only the active campaign ever builds state.
  Future: gate state builds behind campaign registry validation (already implemented in Prompt 27).
