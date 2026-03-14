# System Fix Plan
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

All fixes are read-only analysis recommendations. No code was modified during this audit.

---

## CRITICAL FIXES

### FIX-C01: Wire `field_effects.yaml` into `lift_models.py`
- **Issue:** M-05 — `k_turnout` and `k_persuasion` are hardcoded defaults; `field_effects.yaml` changes have no effect.
- **Files:** `engine/advanced_modeling/lift_models.py:28-49`, `config/field_effects.yaml`
- **Action:** Load `field_effects.yaml` inside `apply_lifts()`. Map YAML keys to `k` parameters.

### FIX-C02: Calibrate Persuasion Scores Before Use in Vote Math
- **Issue:** M-04 — `support_model.pkl` (Gradient Boosting) outputs raw regression scores, not probabilities.
- **Files:** `engine/voters/persuasion_model.py`, `engine/archive/train_support_model.py`
- **Action:** Apply isotonic regression calibration wrapper after `support_model.predict()`. Save calibrated scorer.

### FIX-C03: Fix Historical Trend Double-Counting in `lift_models.py`
- **Issue:** M-01 — `t_trend` is added on top of lift, but baseline may already reflect the trend.
- **Files:** `engine/advanced_modeling/lift_models.py:122`
- **Action:** Apply `t_trend` only to baseline before lift, not additively with lift. Or add a flag to disable trend additive mode.

### FIX-C04: Wire `github_safety.py` as Pre-Commit Hook
- **Issue:** SEC-03 — `github_safety.py` is callable but not enforced.
- **Files:** `engine/data_intake/github_safety.py`, new `.pre-commit-config.yaml`
- **Action:** Create `.pre-commit-config.yaml` with hook pointing to `github_safety.py`.

---

## HIGH-PRIORITY IMPROVEMENTS

### FIX-H01: Fix Broken `scenario_forecasts/` Path in Strategy Engine
- **Issue:** SE-01 / P-02 — `load_campaign_inputs()` searches non-existent `derived/scenario_forecasts/`.
- **Files:** `engine/strategy/campaign_strategy_ai.py:80`
- **Action:** Update path to `derived/advanced_modeling/*/advanced_scenarios.csv` or `derived/simulation/`.

### FIX-H02: Populate `county` and `state` in Campaign State
- **Issue:** P-03 — State snapshot shows empty county and state.
- **Files:** `engine/state/state_builder.py`, `config/campaign_config.yaml`
- **Action:** Verify `campaign_config.yaml` has `campaign.state` and `campaign.county` populated; add explicit extraction in `state_builder.py`.

### FIX-H03: Add Chunked Reading for Large Voter Files
- **Issue:** PERF-01 — Voter parser reads full file into memory.
- **Files:** `engine/voters/voter_parser.py`
- **Action:** Add `dtype` spec and `chunksize` argument; process in chunks with aggregation.

### FIX-H04: Add Arrow-Compatible Index Reset to DataFrames
- **Issue:** PERF-05 — `Unnamed: 0` columns cause Arrow serialization failures in Streamlit.
- **Files:** All views calling `st.dataframe()` on derived CSVs
- **Action:** Add `df = df.reset_index(drop=True)` or use `pd.read_csv(..., index_col=0)` at load time.

### FIX-H05: Verify/Remove Passwords from `users_registry.json`
- **Issue:** SEC-04 — User registry is in Git.
- **Files:** `config/users_registry.json`
- **Action:** Audit file for plaintext credentials; move secrets to environment variables or a `.env` file (gitignored).

---

## RECOMMENDED REFACTORS

### FIX-R01: Create Shared `engine/utils/helpers.py`
- Consolidate `_g()`, `_find_latest()`, `BASE_DIR`, config loaders
- All engine modules import from this single utility module

### FIX-R02: Split `campaign_strategy_ai.py` (548 lines)
- `engine/strategy/vote_path.py`
- `engine/strategy/budget_allocator.py`
- `engine/strategy/field_strategy.py`
- `engine/strategy/risk_analyzer.py`

### FIX-R03: Split `state_builder.py` (~614 lines)
- Separate reader per domain (archive, strategy, performance, war_room)
- Thin orchestrator that calls all readers and assembles state

### FIX-R04: Delete 18 `tmp_patch_*.py` Files
- Files: all `tmp_*.py` at root
- Action: Commit deletion in single cleanup commit

### FIX-R05: Add `n_jobs=-1` to All scikit-learn Estimators
- Files: `train_turnout_model.py`, `train_support_model.py`, `persuasion_model.py`, `turnout_propensity.py`
- Action: Enables parallel training on all CPU cores

---

## MODEL IMPROVEMENTS

### FIX-M01: Make 65/35 Persuasion/GOTV Split Configurable
- **Files:** `engine/strategy/campaign_strategy_ai.py`, `config/campaign_config.yaml`
- Add `strategy.persuasion_gotv_split` key to campaign_config

### FIX-M02: Add Baseline Uncertainty to Monte Carlo
- **Files:** `engine/advanced_modeling/lift_models.py:176-186`
- Sample `turnout_base` and `support_base` from historical variance distribution per precinct

### FIX-M03: Wire Historical Similarity into Calibration Priors
- **Files:** `engine/archive/election_similarity.py`, `engine/calibration/model_calibrator.py`
- Use top-3 similar historical elections as prior weights
