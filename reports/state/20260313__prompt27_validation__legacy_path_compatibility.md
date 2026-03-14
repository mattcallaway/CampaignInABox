# Legacy Path Compatibility Report
**Run ID:** 20260313__prompt27_validation  **Timestamp:** 2026-03-13T19:47:40.297514

## Legacy Paths Still Referenced

| Path | Usage | Status |
|------|-------|--------|
| `derived/state/latest/campaign_state.json` | Written as READ-ONLY alias by `seed_legacy_alias()` in `state_builder.py` | Compat shim — not primary write target |
| `derived/state/latest/campaign_metrics.csv` | Copied from scoped path by `_write_state()` | Compat shim |
| `derived/state/latest/data_requests.json` | Copied from scoped path by `_write_state()` | Compat shim |
| `derived/state/latest/recommendations.json` | Copied from scoped path by `_write_state()` | Compat shim |
| `derived/state/history/<RUN_ID>__campaign_state.json` | Copied as legacy compat by `_write_state()` | Compat shim |

## Status
- All new primary writes go to `derived/state/campaigns/<campaign_id>/latest/`
- Legacy paths are populated as second copies for backward compat only
- No module may READ from legacy paths as their primary source
- Legacy paths should be removed in a future cleanup pass once all UI pages use the resolver

## Cleanup Recommendation
Future prompt: update each UI page loader to call `campaign_state_resolver.get_latest_campaign_state()`
instead of reading `derived/state/latest/campaign_state.json` directly.
