# Post-Prompt-8.5 Full System Audit
**Audit ID:** `2026-03-05__030716__post_prompt85_full_audit`  **Prior:** `2026-03-05__030222__post_prompt8_full_audit`
**Generated:** 2026-03-05 03:07 — **Status: WARN**

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| Run ID | `2026-03-05__030049__521cfe43__msi__run` |
| State / County | unknown / unknown |
| Precincts Modeled | 10 |
| Turfs Generated | 10 |
| Regions | 10 |
| Scenarios Simulated | 4 |
| Strategy Packs | 4 |
| Strategy `derived_mode` | **full** |
| System Status | **WARN** |

---

## 2. Pipeline Health

| Step | Status |
|---|---|
| Data ingestion | ✅ |
| Geography loaded | ✅ |
| geopandas installed | ⚠️ |
| Crosswalks (4+ of 6) | ✅ |
| Features (0 violations) | ❌ |
| Universes | ✅ |
| Targets | ✅ |
| Turfs | ✅ |
| Deterministic forecast | ✅ |
| Monte Carlo simulation | ✅ |
| Operations planner | ✅ |
| Strategy pack (full mode) | ✅ |
| UI (10/10 checks) | ❌ |

---

## 3. Simulation Engine

| Metric | Value |
|---|---|
| Deterministic rows | 10 |
| Monte Carlo rows | 4000 |
| Scenarios | field_program_heavy, field_program_medium, field_program_light, baseline |
| Max iteration | 1000 |
| Simulation file size | 291 bytes |

---

## 4. Operations Planner

| Metric | Value |
|---|---|
| Regions found | 10 |
| Field plan rows | 10 |
| Regions missing cols | ['region_name', 'precinct_count', 'registered_total', 'avg_target_score'] |
| Field plan missing cols | ['doors_to_knock', 'volunteers_needed', 'weeks_required'] |

---

## 5. Strategy Generator

| Metric | Value |
|---|---|
| `derived_mode` | **full** |
| `forecast_mode` | both |
| `win_probability` | None |
| `recommended_strategy` | Tight race. Balanced approach: persuasion for undecideds, turnout for supporters |
| STRATEGY_META.json | ✅ |
| STRATEGY_SUMMARY.md | ✅ |
| TOP_TARGETS.csv | ✅ |
| FIELD_PLAN.csv | ✅ |
| SIMULATION_RESULTS.csv | ✅ |
| TOP_TURFS.csv | ✅ |

---

## 6. UI Integration

| Check | Status |
|---|---|
| Strategy Generator Panel | ✅ |
| Contest Selector | ❌ |
| Forecast Mode Toggle | ✅ |
| Deterministic Option | ✅ |
| Monte Carlo Option | ✅ |
| Both Option | ✅ |
| Generate Button | ✅ |
| Download Buttons | ✅ |
| Strategy Fn Import | ✅ |
| Completeness Badge | ✅ |

**UI Pass Rate:** 9/10

---

## 7. NEEDS System

| Key | Status |
|---|---|
| `simulation_engine` | (no entry) |
| `operations_planner` | (no entry) |
| `strategy_generator` | (no entry) |

---

## 8. Repository Health

| Metric | Value |
|---|---|
| Total Files | 1008 |
| Python Files | 73 |
| Geo Files | 12 |
| Vote Files | 2 |
| Derived Outputs | 115 |
| Strategy Packs | 23 |

---

## 9. Issues Detected

| Severity | File | Line | Description |
|---|---|---|---|
| low | `scripts\loaders\contest_parser.py` | 214 | BARE_EXCEPT: except: |

---

## 10. Recommended Fixes

- geopandas not installed — run `pip install geopandas`.
- Missing crosswalks: ['SRPREC_TO_2020_BLK', 'RGPREC_TO_2020_BLK']
- Constraint violations in features: ['ballots_cast > registered: 10 rows']
- 1 BARE_EXCEPT(s) in production code — add specific exception types