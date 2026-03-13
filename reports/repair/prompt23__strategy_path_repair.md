# Repair Report: Strategy Forecast Path
**Report ID:** prompt23_repair | **Generated:** 2026-03-12T22:30:00-07:00

## Summary
Fixed C02: `campaign_strategy_ai.py` was searching `derived/scenario_forecasts/` — a directory that does not exist. Strategy engine never loaded real simulation data.

## Root Cause

`load_campaign_inputs()` in `campaign_strategy_ai.py` contained:
```python
"simulations": _find_latest(BASE_DIR / "derived" / "scenario_forecasts", "**/*.csv"),
```

The actual simulation output path is `derived/advanced_modeling/<contest_id>/<run_id>__advanced_scenarios.csv`.

## What Was Fixed

### New: `engine/utils/derived_data_reader.py`

Created a canonical `DerivedDataReader` class that:
1. Searches `derived/advanced_modeling/<contest_id>/` first (contest-specific)
2. Falls back to `derived/advanced_modeling/` → `derived/simulation/` → `derived/forecasts/`
3. Prefers run_id-exact match before falling back to latest-by-mtime
4. Logs a clear WARNING if no simulation data found (never silently skips)
5. Never reads another contest's data when `contest_id` is set

### Updated: `campaign_strategy_ai.py`

Replaced `load_campaign_inputs(run_id="latest")` with:
```python
def load_campaign_inputs(contest_id=None, run_id=None) -> dict:
    reader = DerivedDataReader(contest_id=contest_id, run_id=run_id)
    return { ... "simulations": reader.simulations(), ... }
```

### Also Fixed in Same Patch

- **M-02 (Hardcoded 65/35 split):** Now reads `strategy.persuasion_gotv_split` from `campaign_config.yaml`. Default remains 0.65 if not set. Contest type overrides are now possible.
- **Shared `_g()`, `_find_latest()`, `BASE_DIR`:** Now imported from `engine.utils.helpers` — eliminates local duplication.

## Resolved Strategy Inputs (Current Run)

See: `derived/repair/prompt23__resolved_strategy_inputs.json`

## Canonical Search Paths (Post-Fix)

```
1. derived/advanced_modeling/<contest_id>/*advanced_scenarios*.csv  ← preferred
2. derived/advanced_modeling/**/*advanced_scenarios*.csv
3. derived/simulation/**/*.csv
4. derived/forecasts/**/*.csv
```
