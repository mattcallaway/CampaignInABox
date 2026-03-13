# Fix Prompt: Data Pipeline Repairs
**Campaign In A Box | Prompt 23 Audit Fix Prompts**

---

## Objective
Fix the critical data pipeline bugs identified in the Prompt 23 audit. These are the highest-impact data integrity issues that affect modeling accuracy.

---

## Issue 1: `scenario_forecasts/` Path Does Not Exist

**File to modify:** `engine/strategy/campaign_strategy_ai.py`
**Line:** 80

**Current code:**
```python
"simulations": _find_latest(BASE_DIR / "derived" / "scenario_forecasts", "**/*.csv"),
```

**Fix:**
```python
"simulations": (
    _find_latest(BASE_DIR / "derived" / "advanced_modeling", "**/*advanced_scenarios*.csv")
    or _find_latest(BASE_DIR / "derived" / "simulation", "**/*.csv")
),
```

**Expected output:** Strategy engine now correctly loads simulation outputs from `advanced_modeling/` or `simulation/` directories.

---

## Issue 2: Add Warning When Critical Columns Missing

**File to modify:** `engine/advanced_modeling/lift_models.py`
**Lines:** 101-111

**Current code:**
```python
def _c(*names):
    for n in names:
        if n in df.columns:
            return df[n].fillna(0)
    return pd.Series(0.0, index=df.index)
```

**Fix:**
```python
def _c(*names, warn_if_missing=False):
    for n in names:
        if n in df.columns:
            return df[n].fillna(0)
    if warn_if_missing:
        log.warning(f"[LIFT_MODELS] Column(s) {names} not found — defaulting to 0.0. Check precinct model input.")
    return pd.Series(0.0, index=df.index)
```

Then update callers:
```python
reg      = _c("registered", warn_if_missing=True).clip(lower=0)
to_base  = _c("turnout_pct", "turnout_rate", warn_if_missing=True).clip(0, 1)
sup_base = _c("support_pct", "yes_rate", warn_if_missing=True).clip(0, 1)
```

---

## Issue 3: Add `index_col=0` to CSV Reads to Fix Arrow Serialization

**Files to modify:** `ui/dashboard/data_loader.py` and all `*_view.py` files calling `st.dataframe()`

Scan for all `pd.read_csv(...)` calls that produce DataFrames shown to `st.dataframe()`. Add `index_col=False` or call `df.reset_index(drop=True)` before display:

```python
df = pd.read_csv(path, index_col=False)
# or before display:
st.dataframe(df.reset_index(drop=True), use_container_width=True)
```

**Expected output:** Eliminates `ArrowTypeError` warnings from server logs.
