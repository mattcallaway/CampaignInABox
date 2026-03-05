# Post-Prompt-7 Full System Audit

**Audit ID:** `2026-03-05__023308__post_prompt7_full_audit`  
**Run ID:** `2026-03-05__011400__audit`  
**System Status:** ⚠️ **WARN**  
**Timestamp:** 2026-03-05 02:33:08

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| Contests Detected | 2 |
| Precincts Modeled | 5 |
| Turfs Generated | 1 |
| Strategic Regions | 1 |
| Scenarios Simulated | 4 |
| Strategy Packs | 4 |
| Constraint Violations | 0 |
| Code Issues | 1 |

**Verdict:** ⚠️ `WARN`

---

## 2. Pipeline Health

| Step | Status |
|---|---|
| Ingestion | ✅ |
| Features | ✅ |
| Targets | ✅ |
| Turfs | ✅ |
| Forecasts | ✅ |
| Ops | ✅ |
| Simulation | ❌ |
| Strategy Generator | ✅ |

---

## 3. Required Directories

| Directory | Exists |
|---|---|
| `data` | ✅ |
| `votes` | ✅ |
| `derived/features` | ✅ |
| `derived/universes` | ✅ |
| `derived/campaign_targets` | ✅ |
| `derived/turfs` | ✅ |
| `derived/forecasts` | ✅ |
| `derived/ops` | ✅ |
| `derived/diagnostics` | ✅ |
| `derived/strategy_packs` | ✅ |
| `logs` | ✅ |
| `needs` | ✅ |
| `config` | ✅ |
| `scripts` | ✅ |

---

## 4. Data Ingestion

Contests found: **2**

- `votes\2024\CA\Sonoma\nov2024_general\contest.json` —  (0 precincts, 0 registered)
- `votes\2024\CA\SAMPLE_COUNTY\MEASURE_A\contest.json` —  (0 precincts, 0 registered)


---

## 5. Geography System

| Check | Result |
|---|---|
| geopandas installed | ❌ |
| MPREC geojson | ✅ |
| SRPREC geojson | ✅ |
| Boundary index | ❌ |
| Geometry parsed | ❌ |
| MPREC precinct count | N/A |

Issues: None

---

## 6. Crosswalk System

| Crosswalk | Status |
|---|---|
| SRPREC_TO_2020_BLK | ✅ |
| RGPREC_TO_2020_BLK | ✅ |
| 2020_BLK_TO_MPREC | ✅ |
| MPREC_to_SRPREC | ✅ |
| SRPREC_to_CITY | ✅ |
| RG_to_RR_to_SR_to_SVPREC | ✅ |


---

## 7. Feature Engineering

| Check | Value |
|---|---|
| File found | ✅ |
| Row count | 5 |
| Missing cols | canonical_precinct_id, registered, ballots_cast, turnout_pct, support_pct |
| Violations | None |

---

## 8. Universe Generation

| Check | Value |
|---|---|
| File found | ✅ |
| Row count | 10 |
| Universe names | Turnout Opportunity |

---

## 9. Target Scoring

| Check | Value |
|---|---|
| File found | ✅ |
| Row count | 5 |
| Missing cols | target_score, persuasion_potential, turnout_opportunity, tier, walk_priority_rank, confidence_level |
| Tier distribution | {} |

---

## 10. Turf Generation

| Check | Value |
|---|---|
| File found | ✅ |
| Turf count | 1 |
| Missing cols | expected_contacts |

---

## 11. Forecast Engine

Forecast files found: 2  
Scenarios found: None  
Scenarios missing: baseline, field_program_light, field_program_medium, field_program_heavy

---

## 12. Operations Planning

| Check | Result |
|---|---|
| derived/ops/ exists | ✅ |
| regions.csv | ✅ |
| field_plan.csv | ✅ |
| net_gain_by_entity.csv | ❌ |
| Region count | 1 |
| Field plan rows | 1 |

---

## 13. Simulation Engine

| Check | Result |
|---|---|
| File found | ❌ |
| Scenarios | None |
| Row count | 0 |
| Missing cols | None |

---

## 14. Strategy Generator

| File | Present |
|---|---|
| `STRATEGY_SUMMARY.md` | ✅ |
| `STRATEGY_META.json` | ✅ |
| `TOP_TARGETS.csv` | ✅ |
| `TOP_TURFS.csv` | ❌ |
| `FIELD_PACE.csv` | ✅ |

**STRATEGY_META.json summary:**

| Field | Value |
|---|---|
| contest_id | 2024_CA_sonoma_Sonoma_2024_nov2024_general |
| contest_mode | measure |
| derived_mode | degraded |
| baseline_support | 0.6 |
| baseline_turnout | None |
| baseline_margin | 1000.0 |
| win_number | 2501.0 |
| precinct_count | 10 |
| turf_count | 0 |
| region_count | 0 |
| inputs_missing | target_ranking, walk_turfs, scenario_forecasts, precinct_universes |

---

## 15. Strategy Decision Quality

| Decision | Produced |
|---|---|
| Top precinct targets | ✅ |
| Top turfs | ❌ |
| Field pace plan | ✅ |
| Win path summary | ✅ |

Notes: TOP_TURFS.csv empty or missing

---

## 16. UI Integration

| Check | Pass |
|---|---|
| strategy generator panel | ✅ |
| contest selector | ✅ |
| contest mode toggle | ✅ |
| generate button | ✅ |
| download buttons | ✅ |
| strategy fn import | ✅ |
| completeness badge | ✅ |

Score: **7/7**

---

## 17. NEEDS System

File found: ✅  
Entries: jurisdictions, meta, runs, strategy_generator  
strategy_generator status: `degraded`

---

## 18. Code Quality


| Severity | File | Line | Description |
|---|---|---|---|
| LOW | `scripts\loaders\contest_parser.py` | 214 | BARE_EXCEPT: except: |
*Top 1 of 1 total (all medium/low)*


---

## 19. Repository Health

| Metric | Count |
|---|---|
| Total files | 307 |
| Python files | 66 |
| Geo files | 12 |
| Vote files | 2 |
| Derived outputs | 61 |
| Strategy pack files | 22 |
| Missing configs | None |

---

## 20. Recommended Fixes

1. No simulation_results.csv — confirm simulate_scenarios() is called in pipeline.
2. geopandas not installed — run `pip install geopandas` or `uv add geopandas`.
3. Scenario engine missing scenarios: ['baseline', 'field_program_light', 'field_program_medium', 'field_program_heavy']

---

*Generated by `scripts/tools/audit_post_prompt7.py` at 2026-03-05 02:33:08*
