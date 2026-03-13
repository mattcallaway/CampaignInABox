# Modeling Calibration Audit
**Score:** 1.00 (SAFE)

## Availability Checks
| Check | Status |
|-------|--------|
| calibration_summary_exists | Yes |
| model_parameters_exist | Yes |
| persuasion_parameters_exist | Yes |
| turnout_parameters_exist | Yes |
| calibration_engine_present | Yes |
| forecast_engine_present | Yes |
| strategy_loads_calibration | Yes |
| swing_model_gated_by_backtest | Yes |

## Key Metrics
- Calibration confidence: **0.00**
- Strategy engine loads calibrated params: **Yes**
- Fallback/default overrides detected: **1** references
- Swing model gated by backtest validation: **Yes**

## Calibration Summary
```json
{
  "run_id": "2026-03-10__152246__e84498d7__msi",
  "contest_id": "2026_CA_sonoma_prop_50_special",
  "generated_at": "2026-03-10T23:27:50.551147",
  "calibration_status": "prior_only",
  "calibration_confidence": "none",
  "calibration_sources": [],
  "n_historical_records": 0,
  "n_historical_elections": 0,
  "n_precincts_historical": 0,
  "gotv_universe_size": 0,
  "persuasion_universe_size": 0,
  "runtime_has_data": false,
  "turnout_parameters": {
    "method": "prior",
    "baseline_turnout_probability": 0.45,
    "turnout_variance": 0.08,
    "confidence": "none",
    "n_precincts": 0,
    "n_elections": 0
  },
  "persuasion_parameters": {
    "method": "prior",
    "persuasion_lift_per_contact": 0.006,
    "persuasion_variance": 0.003,
    "confidence": "none",
    "notes": "Using
```
