# Fix Prompt: Performance Improvements
**Campaign In A Box | Prompt 23 Audit Fix Prompts**

---

## Objective
Improve performance for large voter files, parallelized simulations, and model training.

---

## Fix 1: Chunked Voter File Reading

**File:** `engine/voters/voter_parser.py`

```python
# Replace single full read:
df = pd.read_csv(path)

# With optimized dtype + optional chunked read:
DTYPE_MAP = {
    "voter_id": str,
    "precinct_id": str,
    "party": str,
    "gender": str,
    "age_group": str,
}

def read_voter_file(path: Path, chunk_rows: int = 50_000) -> pd.DataFrame:
    """Read voter file with optional chunking for large files."""
    file_size = path.stat().st_size
    if file_size > 50_000_000:  # >50MB — use chunks
        chunks = []
        for chunk in pd.read_csv(path, dtype=DTYPE_MAP, chunksize=chunk_rows, low_memory=False):
            chunks.append(chunk)
        return pd.concat(chunks, ignore_index=True)
    return pd.read_csv(path, dtype=DTYPE_MAP, low_memory=False)
```

---

## Fix 2: Parallelize Monte Carlo with joblib

**File:** `engine/advanced_modeling/lift_models.py`
**Function:** `apply_lifts_mc()`

```python
from joblib import Parallel, delayed

def _single_mc_run(universe_df, contacts_col, cfg, seed, persuasion_direction):
    """Single MC iteration — used by parallel executor."""
    lifted = apply_lifts(universe_df, contacts_col, cfg, persuasion_direction)
    return lifted["net_margin_gain"].sum()

def apply_lifts_mc(universe_df, contacts_col="contacts_estimated",
                   cfg=None, n_iter=200, seed=1337, persuasion_direction=1):
    cfg    = cfg or {}
    curves = cfg.get("curves", {})
    elast  = cfg.get("elasticity", {})
    rng    = np.random.default_rng(seed)

    max_to_base = curves.get("max_turnout_lift_pct", 0.08)
    max_pe_base = curves.get("max_persuasion_lift_pct", 0.06)
    to_mean = elast.get("turnout_lift_per_contact_mean", 0.004)
    pe_mean = elast.get("persuasion_lift_per_contact_mean", 0.006)

    cfgs = []
    for _ in range(n_iter):
        cfg_i = dict(cfg)
        cfg_i["curves"] = {
            **curves,
            "max_turnout_lift_pct":   max(0.0, float(rng.normal(max_to_base, to_mean * 3))),
            "max_persuasion_lift_pct": max(0.0, float(rng.normal(max_pe_base, pe_mean * 3))),
        }
        cfgs.append(cfg_i)

    results = Parallel(n_jobs=-1)(
        delayed(_single_mc_run)(universe_df, contacts_col, c, seed + i, persuasion_direction)
        for i, c in enumerate(cfgs)
    )
    arr = np.array(results)
    return {
        "net_gain_mean": float(arr.mean()),
        "net_gain_p10":  float(np.percentile(arr, 10)),
        "net_gain_p90":  float(np.percentile(arr, 90)),
        "net_gain_sd":   float(arr.std()),
    }
```

---

## Fix 3: Add `n_jobs=-1` to scikit-learn Estimators

**Files:** `engine/archive/train_turnout_model.py`, `engine/archive/train_support_model.py`

```python
# Turnout model:
model = RandomForestRegressor(n_estimators=100, n_jobs=-1, random_state=42)

# Support model:
# GradientBoostingRegressor does not support n_jobs. Use HistGradientBoostingRegressor instead:
from sklearn.ensemble import HistGradientBoostingRegressor
model = HistGradientBoostingRegressor(max_iter=100, random_state=42)
# Note: HistGradientBoostingRegressor is fully parallelized and supports native NaN handling
```

---

## Fix 4: Lazy Data Loading by Page

**File:** `ui/dashboard/data_loader.py`

Refactor from `load_all()` to page-specific loaders:

```python
def load_overview_data() -> dict:
    """Load only state + strategy summary for Overview page."""
    return {
        "state": load_state(),
        "strategy_meta": load_strategy_summary(),
    }

def load_war_room_data() -> dict:
    """Load only war room + runtime data."""
    return {
        "state": load_state(),
        "war_room": load_war_room(),
        "runtime": load_runtime(),
    }
```

Use `st.query_params` or `st.session_state["page"]` to select the correct loader.
