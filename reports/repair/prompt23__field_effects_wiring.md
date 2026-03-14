# Repair Report: Field Effects Wiring
**Report ID:** prompt23_repair | **Generated:** 2026-03-12T22:30:00-07:00

## Summary
Fixed C01: `field_effects.yaml` was not being read by `lift_models.py`. Changes in the YAML had no effect on lift calculations.

## What Was Found

| Config Key | Expected Location | Was It Used? |
|-----------|------------------|-------------|
| `gotv.door_knock_lift` | `config/field_effects.yaml` | ❌ NO — never loaded |
| `persuasion.door_knock_swing` | `config/field_effects.yaml` | ❌ NO — never loaded |
| `k_turnout` | `config/advanced_modeling.yaml:curves` | ~ PARTIAL — only if key present |
| `k_persuasion` | `config/advanced_modeling.yaml:curves` | ~ PARTIAL — only if key present |
| Hardcoded default `k_to=0.0008` | `lift_models.py:L31` | ✅ YES — always used as final fallback |

## What Was Fixed

Added module-level `_load_field_effects()` with caching in `engine/advanced_modeling/lift_models.py`.

**Parameter resolution priority (post-fix):**
1. `config/advanced_modeling.yaml → curves → k_turnout / k_persuasion` (highest)
2. `config/field_effects.yaml → gotv.door_knock_lift` / `persuasion.door_knock_swing` (scaled to k)
3. Hardcoded defaults `(k_to=0.0008, k_pe=0.0010)` (lowest — only if both configs missing)

Scaling formula: `k = field_effect_per_contact × 40` (turnout) or `× 50` (persuasion)
This maps a per-contact lift value to a saturation-rate compatible k for the exponential decay curve.

## Also Fixed in Same Patch

- **M-01 (Trend double-counting):** Added `apply_historical_trends` config flag (default `False`). Trend is now applied ONLY to the baseline, not additive with lift.
- **Silent _c() fallback:** `registered`, `turnout_pct`, `support_pct` now log a WARNING when missing instead of silently returning zeros.

## Current field_effects.yaml Values Used

| Parameter | Value | Scaled k |
|-----------|-------|---------|
| `gotv.door_knock_lift` | 0.025 | 0.025 × 40 = **k_to = 0.001000** |
| `persuasion.door_knock_swing` | 0.020 | 0.020 × 50 = **k_pe = 0.001000** |

These override the old hardcoded defaults of 0.0008 / 0.0010 unless `advanced_modeling.yaml:curves:k_turnout` is present.

## Effective Lift Parameters at Runtime

See: `derived/repair/prompt23__effective_lift_parameters.json`

## Fallback Rules

If `field_effects.yaml` is missing → hardcoded defaults apply. No crash.
If `advanced_modeling.yaml` `curves.k_turnout` is set → that overrides `field_effects.yaml` entirely.
