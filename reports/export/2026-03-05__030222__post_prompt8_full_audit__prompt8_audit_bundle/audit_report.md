# Post-Prompt-8 Full System Audit
**Audit ID:** `2026-03-05__030222__post_prompt8_full_audit`
**Run ID:** `unknown`
**System Status:** **WARN**
**Generated:** 2026-03-05 03:02:22

---

## Executive Summary

| Metric | Value |
|---|---|
| Precincts Modeled | 10 |
| Turfs Generated | 10 |
| Regions Generated | 10 |
| Scenarios Simulated | 4 |
| Strategy Packs | 4 |
| Constraint Violations | 1 |
| Code Issues | 14 |
| UI Checks Passed | 10/10 |

---

## Pipeline Health

| Directory | Status |
|---|---|
| `data` | ✅ |
| `votes` | ✅ |
| `derived/features` | ✅ |
| `derived/universes` | ✅ |
| `derived/campaign_targets` | ✅ |
| `derived/turfs` | ✅ |
| `derived/forecasts` | ✅ |
| `derived/simulation` | ✅ |
| `derived/ops` | ✅ |
| `derived/strategy_packs` | ✅ |
| `derived/diagnostics` | ✅ |
| `logs` | ✅ |
| `needs` | ✅ |
| `config` | ✅ |
| `scripts` | ✅ |

---

## Simulation Engine Validation

### Deterministic Forecast
- **File found:** ✅ `derived\simulation\CA\Sonoma\Sonoma_2024_nov2024_general\2026-03-05__023047__prompt8__deterministic_forecast.csv`
- **Row count:** 10
- **Missing columns:** None ✅

### Monte Carlo
- **File found:** ✅ `derived\simulation\CA\Sonoma\Sonoma_2024_nov2024_general\2026-03-05__023047__prompt8__simulation_results.csv`
- **Rows:** 4,000 (1000 iterations per scenario)
- **Scenarios:** ['baseline', 'field_program_light', 'field_program_medium', 'field_program_heavy']
- **Missing columns:** None ✅

### Scenario Summary
- **File found:** ✅
- **Scenarios:** ['baseline', 'field_program_light', 'field_program_medium', 'field_program_heavy']
- **Probability violations:** None ✅

---

## Operations Planner Validation

- **derived/ops/ exists:** ✅
- **Regions file:** ✅ — 10 regions
- **Field plan:** ✅ — 10 rows
- **Regions missing cols:** ['region_name', 'precinct_count', 'registered_total', 'avg_target_score']
- **Field plan missing cols:** ['doors_to_knock', 'volunteers_needed', 'weeks_required']

---

## Strategy Generator Validation

- **Pack exists:** ✅
- **Latest pack:** `derived\strategy_packs\2024_CA_sonoma_nov2024_general\2026-03-05__030049__521cfe43__msi`
- **Simulation results size:** 291 bytes

### File Presence
| File | Present |
|---|---|
| `STRATEGY_META.json` | ✅ |
| `STRATEGY_SUMMARY.md` | ✅ |
| `TOP_TARGETS.csv` | ✅ |
| `FIELD_PLAN.csv` | ✅ |
| `SIMULATION_RESULTS.csv` | ✅ |
| `TOP_TURFS.csv` | ✅ |
| `FIELD_PACE.csv` | ✅ |

### Strategy Decisions
| Check | Status |
|---|---|
| has_recommended_strategy | ✅ |
| has_win_probability | ❌ |
| has_precinct_count | ✅ |
| has_scenario_count | ✅ |
| has_forecast_mode | ✅ |
| top_targets_present | ✅ |
| field_plan_present | ✅ |
| simulation_results_present | ✅ |
| strategy_summary_present | ✅ |

### Meta Summary
- **win_probability:** None
- **recommended_strategy:** Tight race. Balanced approach: persuasion for undecideds, turnout for supporters.
- **scenario_count:** 4
- **forecast_mode:** both

---

## UI Integration Validation

✅ app.py found | **10/10 checks passed**

| Check | Status |
|---|---|
| strategy_generator_panel | ✅ |
| contest_selector | ✅ |
| forecast_mode_toggle | ✅ |
| deterministic_option | ✅ |
| monte_carlo_option | ✅ |
| both_option | ✅ |
| generate_button | ✅ |
| download_buttons | ✅ |
| strategy_fn_import | ✅ |
| completeness_badge | ✅ |

---

## NEEDS System Validation

| Key | Status |
|---|---|
| `simulation_engine` | `None` |
| `operations_planner` | `None` |
| `strategy_generator` | `complete` |

---

## Issues Detected (14)

- [LOW] `scripts\run_pipeline.py` L12: HARD_CODED_PATH
- [LOW] `scripts\loaders\contest_parser.py` L214: BARE_EXCEPT: except:
- [INFO] `scripts\loaders\contest_parser.py` L218: MARKER: "contest_id": meta.get("contest_id", "FIXME"),
- [INFO] `scripts\tools\audit_post_prompt6.py` L401: MARKER: "fixme":       re.compile(r"#\s*FIXME", re.IGNORECASE),
- [INFO] `scripts\tools\audit_post_prompt6.py` L404: MARKER: "todo":        re.compile(r"#\s*TODO", re.IGNORECASE),
- [INFO] `scripts\tools\audit_post_prompt6.py` L601: MARKER: fixme_issues = [i for i in code_issues if "FIXME" in i["description"]]
- [INFO] `scripts\tools\audit_post_prompt6.py` L603: MARKER: recs.append(f"{len(fixme_issues)} FIXME marker(s) in code â€” resolve before pro
- [INFO] `scripts\tools\audit_post_prompt7.py` L523: MARKER: "FIXME":        re.compile(r"#\s*FIXME", re.I),
- [INFO] `scripts\tools\audit_post_prompt7.py` L526: MARKER: "TODO":         re.compile(r"#\s*TODO", re.I),
- [INFO] `scripts\tools\audit_post_prompt7.py` L542: MARKER: "severity": "high" if label == "HARD_PATH" else "medium" if label == "FIXME" els
- [LOW] `scripts\tools\audit_post_prompt8.py` L59: BARE_EXCEPT: except: return 0
- [INFO] `scripts\tools\audit_post_prompt8.py` L536: MARKER: # TODO
- [INFO] `scripts\tools\audit_post_prompt8.py` L537: MARKER: if "TODO" in line or "FIXME" in line or "HACK" in line:
- [LOW] `scripts\tools\audit_post_prompt8.py` L566: BARE_EXCEPT: except: pass

---

## Recommendations

- geopandas not installed — run `pip install geopandas`.
- Missing crosswalks: ['SRPREC_TO_2020_BLK', 'RGPREC_TO_2020_BLK', '2020_BLK_TO_MPREC', 'MPREC_to_SRPREC', 'RG_to_RR_to_SR_to_SVPREC']

---

*Generated by `audit_post_prompt8.py`*
