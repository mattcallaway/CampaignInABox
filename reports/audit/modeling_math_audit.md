# Modeling Math Audit
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

---

## 1. Lift Curve Mathematics

### Formula (from `lift_models.py:6-16`)

```
lift(contacts) = max_lift * (1 - exp(-k * contacts))
turnout_new    = clamp(turnout_base + t_lift + t_trend, 0, 1)
support_new    = clamp(support_base + p_lift * direction + s_trend, 0, 1)
expected_yes   = registered * turnout_new * support_new
```

### Validation

| Check | Result | Notes |
|-------|--------|-------|
| Formula type | ✅ PASS | Saturating exponential — standard in academic field mobilization models |
| Asymptotic bound | ✅ PASS | `max_lift` is never exceeded; clamp to [0,1] applied |
| Contacts floor | ✅ PASS | `max(0, contacts)` prevents negative contact counts |
| Direction parameter | ✅ PASS | `persuasion_direction` ∈ {-1, +1} correctly flips the lift sign |
| Historical trend additive | ⚠️ WEAK | `t_trend` and `s_trend` added **linearly** to lift — no interaction term; double-counting risk if trends already baked into baseline |

### Parameter Assumptions

| Parameter | Default | Campaign Science Assessment |
|-----------|---------|---------------------------|
| `max_turnout_lift_pct` | 0.08 (8%) | Reasonable — empirical range is 2-12% for intensive GOTV |
| `max_persuasion_lift_pct` | 0.06 (6%) | Slightly high — persuasion effect per contact closer to 1-4% per contact in RCT literature |
| `k_turnout` | 0.0008 | Low — implies ~8,600 contacts for 95% of max lift; fine for large precincts |
| `k_persuasion` | 0.0010 | Reasonable |

### 🔴 Math Issue M-01: Historical Trend Double-Counting

`to_new = (to_base + t_lift + t_trend).clip(0, 1)` — File: `lift_models.py:122`

If `to_base` was already derived from historical trend by the calibrator, adding `t_trend` again constitutes double-counting. The trend adjustment should be applied only at the baseline level, not added on top of a lift that already reflects trend.

**Risk level: HIGH** — inflates projected turnout in trending precincts.

---

## 2. Vote Path Mathematics

### Formula (from `campaign_strategy_ai.py:98-200`)

```
expected_voters       = registered * turnout_rate
win_number            = ceil(expected_voters * target_vote_share)
base_votes            = sum(precinct_yes_votes) or fallback estimate
persuasion_gap        = win_number - base_votes
persuasion_votes_needed = persuasion_gap * persuasion_split (default 0.65)
gotv_votes_needed       = persuasion_gap * (1 - persuasion_split) (default 0.35)
```

### Validation

| Check | Result | Notes |
|-------|--------|-------|
| Win number formula | ✅ PASS | `ceil(expected * share)` is standard |
| 65/35 split heuristic | ⚠️ ASSUMPTION | Fixed 65% persuasion / 35% GOTV split — not derived from data; should be configurable per contest type |
| `base_votes` fallback | ⚠️ WEAK | Falls back to `expected_voters * 0.48` if no precinct data — arbitrary constant |
| Gap calculation | ✅ PASS | `gap = win_number - base_votes` is correct |
| Doors calculation | ✅ PASS | `doors = votes / (persuasion_rate * contact_rate)` is algebraically correct |

### 🟡 Math Issue M-02: Fixed 65/35 Persuasion/GOTV Split

The strategy engine hardcodes a 65% persuasion / 35% GOTV allocation of the vote gap. This is reasonable for competitive general elections but may be wrong for:
- Low-turnout primaries (GOTV should dominate)
- Ballot measures (persuasion dominates)
- Safe-seat contests (neither applicable)

**Recommendation:** Read split ratio from `campaign_config.yaml` or derive from modeling scores.

---

## 3. Monte Carlo Simulation Mathematics

### Method (`lift_models.py:148-197`)

The Monte Carlo samples `max_lift` from a normal prior:
```
sampled_max_turnout    ~ Normal(max_turnout_base,  to_mean * 3)
sampled_max_persuasion ~ Normal(max_persuasion_base, pe_mean * 3)
```

### Validation

| Check | Result | Notes |
|-------|--------|-------|
| Distribution type | ✅ PASS | Normal prior is reasonable for parameter uncertainty |
| SD scaling | ⚠️ WEAK | `to_mean * 3` uses the elasticity mean × 3 as SD — not independently calibrated |
| Negative clamp | ✅ PASS | `max(0, sampled_max)` prevents negative max_lift |
| Seed handling | ✅ PASS | Reproducible with fixed seed |
| Iteration count | ✅ PASS | Default 2,000 iterations is sufficient for stable percentiles |
| P10/P90 output | ✅ PASS | Standard 80% confidence interval |

### 🟡 Math Issue M-03: MC Only Samples lift Parameters — Not Turnout or Support Base

The Monte Carlo varies `max_lift` (the ceiling) but does NOT sample uncertainty on `turnout_base` or `support_base` (precincts' starting rates). In reality, baseline uncertainty is often larger than lift uncertainty. This underestimates total forecast variance.

---

## 4. Persuasion Scoring

The `persuasion_model.py` applies scores from the `support_model.pkl` (Gradient Boosting Regressor). No score calibration to probability space is documented.

### 🔴 Math Issue M-04: Uncalibrated Persuasion Scores

Gradient Boosting Regressors do not output calibrated probabilities. Scores from `support_model.pkl` need isotonic or Platt calibration before being used as `support_pct` in vote math. Without calibration, scores may be systematically biased (compressed toward the mean).

---

## 5. Field Effects Configuration

From `field_effects.yaml`:
- GOTV contact effect: configured
- Persuasion contact effect: configured

These are applied in `lift_models.py` via `k` parameters only — the `field_effects.yaml` values are not automatically read by `lift_models.py`. This creates a configuration drift risk where YAML parameters diverge from hardcoded defaults.

### 🔴 Math Issue M-05: field_effects.yaml Configuration Not Wired Into lift_models.py

File: `engine/advanced_modeling/lift_models.py:28-49` — `k` defaults are hardcoded; `field_effects.yaml` values are not loaded here. Changing YAML has no effect on lift calculations.

---

## Summary Table

| Issue | Severity | Impact |
|-------|---------|--------|
| M-01: Historical trend double-counting | HIGH | Inflated turnout projections in trending precincts |
| M-02: Fixed 65/35 GOTV/persuasion split | MEDIUM | Wrong resource allocation for non-general elections |
| M-03: MC doesn't sample baseline uncertainty | MEDIUM | Underestimates forecast variance |
| M-04: Uncalibrated persuasion scores | HIGH | Biased support_pct inputs into vote math |
| M-05: field_effects.yaml not wired to lift_models | HIGH | Configuration drift; YAML changes ignored |
