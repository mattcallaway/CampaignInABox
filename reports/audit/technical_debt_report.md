# Technical Debt Report
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

---

## 1. Temporary Patch Files

**18 `tmp_patch_*.py` files at repository root.** These are development artifacts from iterative Prompt-based patching sessions and should be cleaned up.

| File | Purpose | Action |
|------|---------|--------|
| `tmp_patch_app.py` | App routing patch | Delete or move logic to `app.py` |
| `tmp_patch_app_login.py` | Login flow patch | Delete |
| `tmp_patch_dm.py` | Data manager patch | Already superseded by `data_manager_view.py` |
| `tmp_patch_nav.py` | Navigation patch | Superseded by `ui_pages.yaml` + sidebar |
| `tmp_patch_strat.py` | Strategy view patch | Delete |
| `tmp_patch_wr.py` | War room patch | Delete |
| `tmp_patch_lift_models.py` | Lift model patch | Delete — changes merged in |
| `tmp_fix_pipeline.py` | Pipeline fix | Delete |
| `tmp_gen_ca.py` | CA data generator | Delete or move to `scripts/tools/` |
| `tmp_patch_map.py` | Map patch | Delete |
| `tmp_patch_diag.py` | Diagnostics patch | Delete |
| `tmp_refactor.py` | Refactor helper | Delete |
| (8 more) | Various | All delete |

**Risk:** These files confuse onboarding developers and create maintenance overhead. Some may contain conflicting code paths.

---

## 2. Duplicate Logic

| Pattern | Found In | Redundancy |
|---------|---------|-----------|
| `_g()` nested dict accessor | `campaign_strategy_ai.py:44`, `forecast_updater.py:27`, `war_room/status_engine.py` | 3+ identical implementations |
| `_find_latest()` CSV finder | `strategy_ai.py:56`, `forecast_updater.py:35`, more | 4+ implementations |
| `BASE_DIR = Path(__file__).resolve().parent.parent.parent` | Every engine file | 20+ copies |
| `yaml.safe_load(open(path).read())` pattern | Multiple config loaders | No shared config reader |

---

## 3. Orphan / Unused Modules

| Module | Evidence of Orphan Status |
|--------|--------------------------|
| `engine/audit/post_prompt86_audit.py` | Named after "prompt 86" — not referenced by any other module (likely scaffolding artifact) |
| `engine/advanced_modeling/model_card.py` | Not called from any UI or pipeline; likely informational only |
| `engine/advanced_modeling/qa_checks.py` | Not called in any pipeline invocation found |
| `engine/advanced_modeling/universe_allocation.py` | `scenarios.py` uses `optimizer.py` not this file |
| `engine/data_intake/source_finder.py` | Not referenced in data_intake pipeline |
| `engine/data_intake/missing_data_assistant.py` | Not wired into any UI or engine call |

---

## 4. Incomplete Features

| Feature | Status | Evidence |
|---------|--------|---------|
| Historical Election Archive | Partial | `data/election_archive/` has 0 real files; training on mock data |
| File Registry | Not Running | Registry snapshot shows "not yet generated" |
| Provenance System | Partial | 0 datasets with any provenance tag in file registry |
| Pre-commit Safety Hooks | Missing | `github_safety.py` exists but not enforced |
| Multi-contest support | Partial | State store `contest_id` hardcoded to `2026_CA_sonoma_prop_50_special` |

---

## 5. Configuration Drift

| Setting | Defined In | Consumer | Synchronized? |
|---------|-----------|---------|--------------|
| `k_turnout` | `advanced_modeling.yaml` + `lift_models.py` default | `lift_models.py` | ⚠️ YAML not loaded by lift_models |
| `k_persuasion` | Same | Same | ⚠️ Same |
| `max_turnout_lift_pct` | `advanced_modeling.yaml:curves` | `lift_models.py` | ✅ Via `cfg` param if passed |
| Persuasion/GOTV split (65/35) | `campaign_strategy_ai.py` hardcoded | Strategy engine | ❌ Not in any YAML |
| Field effects (turnout per contact) | `field_effects.yaml` | Not wired | ❌ Dead config |

---

## 6. Test Coverage

3 test files found at root: `test_city_registry.py`, `test_naming.py`, `test_registry.py`.
No test suite is present for:
- Engine modeling math
- State builder
- Strategy engine
- War room forecast updater
- Archive ingestion

**No automated test runner (pytest) is configured.** No `tests/` directory exists.

---

## Summary

| Debt Category | Count | Priority |
|--------------|-------|---------|
| Temp patch files (to delete) | 18 | High |
| Duplicate utility functions | 4+ patterns | Medium |
| Orphan/unreferenced modules | 6 | Low |
| Incomplete features | 5 | High |
| Configuration drift | 3 critical | High |
| Missing test suite | Entire engine | Medium |
