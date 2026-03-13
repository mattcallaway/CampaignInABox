# Fix Prompt: Modeling Math Corrections
**Campaign In A Box | Prompt 23 Audit Fix Prompts**

---

## Objective
Fix the modeling math issues identified in the Prompt 23 audit. Focus on: wiring `field_effects.yaml` into lift models, fixing the trend double-counting, and adding score calibration.

---

## Fix 1: Wire `field_effects.yaml` into `lift_models.py`

**File to modify:** `engine/advanced_modeling/lift_models.py`

**Current:** `k_turnout` and `k_persuasion` are hardcoded defaults; `field_effects.yaml` is never loaded.

**Fix:** Modify `apply_lifts()` to load `field_effects.yaml` at module level or pass via `cfg`:

```python
# Add at top of apply_lifts():
import yaml
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_FIELD_EFFECTS_PATH = _ROOT / "config" / "field_effects.yaml"

def _load_field_effects() -> dict:
    try:
        return yaml.safe_load(_FIELD_EFFECTS_PATH.read_text()) or {}
    except Exception:
        return {}
```

Then in `apply_lifts()`, read `k` values from config when not overridden by `cfg`:
```python
fe = _load_field_effects()
k_to  = curves.get("k_turnout",   fe.get("gotv", {}).get("k", 0.0008))
k_pe  = curves.get("k_persuasion", fe.get("persuasion", {}).get("k", 0.0010))
```

---

## Fix 2: Fix Historical Trend Double-Counting

**File to modify:** `engine/advanced_modeling/lift_models.py`
**Lines:** 122-123

**Current:**
```python
to_new  = (to_base  + t_lift + t_trend).clip(0, 1)
sup_new = (sup_base + p_lift * persuasion_direction + s_trend).clip(0, 1)
```

**Problem:** If `to_base` already encodes historical trend, `t_trend` is counted twice.

**Fix:** Gate the trend with a config flag:
```python
apply_historical_trends = cfg.get("apply_historical_trends", False)
to_new  = (to_base + t_lift + (t_trend if apply_historical_trends else 0)).clip(0, 1)
sup_new = (sup_base + p_lift * persuasion_direction + (s_trend if apply_historical_trends else 0)).clip(0, 1)
```

Set `apply_historical_trends: true` in `config/advanced_modeling.yaml` only when baselines are NOT trend-adjusted.

---

## Fix 3: Make 65/35 Persuasion/GOTV Split Configurable

**File to modify:** `engine/strategy/campaign_strategy_ai.py`
**File to modify:** `config/campaign_config.yaml`

**Step 1:** Add to `campaign_config.yaml`:
```yaml
strategy:
  persuasion_share_of_gap: 0.65   # 65% of vote gap comes from persuasion
  gotv_share_of_gap: 0.35         # 35% from GOTV
```

**Step 2:** In `compute_vote_path()`:
```python
persuasion_split = _g(cfg, "strategy", "persuasion_share_of_gap", default=0.65)
gotv_split       = 1.0 - persuasion_split
persuasion_votes_needed = int(gap * persuasion_split)
gotv_votes_needed       = int(gap * gotv_split)
```
