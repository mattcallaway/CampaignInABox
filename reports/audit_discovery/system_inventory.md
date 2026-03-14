# Campaign In A Box — System Inventory
**Export Time:** 2026-03-13T04:12:40Z  
**Export By:** Audit Discovery Script v1.0

---

## Repository Structure

**Root directories:** Campaign In A Box Data, app, archive, config, data, deployment, derived, docs, engine, logs, needs, reports, scripts, staging, ui, voters, votes

**File counts by type:**

- `other`: 273
- `yaml`: 61
- `text`: 2584
- `python`: 208
- `json`: 158
- `excel`: 9
- `csv`: 2682
- `geo`: 18
- `pkl`: 2

**Key root files:** README.md, _git_init.ps1, _scaffold.ps1, environment.yml, requirements.txt, run_campaign_box.ps1, run_campaign_box.sh, test_city_registry.py, test_naming.py, test_registry.py, tmp_fix_pipeline.py, tmp_gen_ca.py, tmp_patch_app.py, tmp_patch_app_login.py, tmp_patch_app_v.py, tmp_patch_diag.py, tmp_patch_dm.py, tmp_patch_footer.py, tmp_patch_lift_models.py, tmp_patch_map.py, tmp_patch_nav.py, tmp_patch_readme.py, tmp_patch_strat.py, tmp_patch_strategy.py, tmp_patch_ui.py, tmp_patch_wr.py, tmp_refactor.py, tmp_update_collab.py, tmp_update_sim.py, tmp_update_state_builder.py

## Engine Module Inventory

### advanced_modeling

- **__init__** — `engine\advanced_modeling\__init__.py`
  - *Campaign engine module*
- **lift_models** — `engine\advanced_modeling\lift_models.py`
  - *Applies turnout/persuasion lift curves to precincts*
- **model_card** — `engine\advanced_modeling\model_card.py`
  - *Campaign engine module*
- **optimizer** — `engine\advanced_modeling\optimizer.py`
  - *Campaign engine module*
- **qa_checks** — `engine\advanced_modeling\qa_checks.py`
  - *Campaign engine module*
- **scenarios** — `engine\advanced_modeling\scenarios.py`
  - *Runs deterministic and Monte Carlo scenario projections*
- **universe_allocation** — `engine\advanced_modeling\universe_allocation.py`
  - *Campaign engine module*
### archive

- **archive_ingest** — `engine\archive\archive_ingest.py`
  - *Ingests historical election data into normalized archive*
- **election_similarity** — `engine\archive\election_similarity.py`
  - *Identifies similar historical elections for calibration*
- **generate_archive_summary** — `engine\archive\generate_archive_summary.py`
  - *Produces archive_summary.json for state integration*
- **precinct_profiles** — `engine\archive\precinct_profiles.py`
  - *Builds precinct behavioral profiles from historical data*
- **train_support_model** — `engine\archive\train_support_model.py`
  - *Trains Gradient Boosting support/persuasion model*
- **train_turnout_model** — `engine\archive\train_turnout_model.py`
  - *Trains Random Forest turnout prediction model*
- **trend_analysis** — `engine\archive\trend_analysis.py`
  - *Computes long-term turnout/support trends per precinct*
### audit

- **__init__** — `engine\audit\__init__.py`
  - *Campaign engine module*
- **artifact_validator** — `engine\audit\artifact_validator.py`
  - *Validates pipeline output artifacts for integrity*
- **post_prompt86_audit** — `engine\audit\post_prompt86_audit.py`
  - *Campaign engine module*
### auth

- **auth_manager** — `engine\auth\auth_manager.py`
  - *Manages user authentication and role-based permissions*
### calibration

- **__init__** — `engine\calibration\__init__.py`
  - *Campaign engine module*
- **calibration_engine** — `engine\calibration\calibration_engine.py`
  - *Campaign engine module*
- **election_downloader** — `engine\calibration\election_downloader.py`
  - *Campaign engine module*
- **forecast_accuracy** — `engine\calibration\forecast_accuracy.py`
  - *Campaign engine module*
- **historical_parser** — `engine\calibration\historical_parser.py`
  - *Campaign engine module*
- **model_calibrator** — `engine\calibration\model_calibrator.py`
  - *Calibrates model outputs against observed results*
- **persuasion_calibrator** — `engine\calibration\persuasion_calibrator.py`
  - *Campaign engine module*
- **turnout_calibrator** — `engine\calibration\turnout_calibrator.py`
  - *Campaign engine module*
- **turnout_lift_calibrator** — `engine\calibration\turnout_lift_calibrator.py`
  - *Campaign engine module*
### data_intake

- **__init__** — `engine\data_intake\__init__.py`
  - *Campaign engine module*
- **data_intake_manager** — `engine\data_intake\data_intake_manager.py`
  - *Campaign engine module*
- **github_safety** — `engine\data_intake\github_safety.py`
  - *Campaign engine module*
- **missing_data_assistant** — `engine\data_intake\missing_data_assistant.py`
  - *Campaign engine module*
- **source_finder** — `engine\data_intake\source_finder.py`
  - *Campaign engine module*
### geo

- **__init__** — `engine\geo\__init__.py`
  - *Campaign engine module*
- **geometry_validation** — `engine\geo\geometry_validation.py`
  - *Campaign engine module*
- **master_index_builder** — `engine\geo\master_index_builder.py`
  - *Campaign engine module*
### integrity

- **__init__** — `engine\integrity\__init__.py`
  - *Campaign engine module*
- **integrity_repairs** — `engine\integrity\integrity_repairs.py`
  - *Auto-repairs common data integrity issues*
- **join_guard** — `engine\integrity\join_guard.py`
  - *Campaign engine module*
### intelligence

- **__init__** — `engine\intelligence\__init__.py`
  - *Campaign engine module*
- **ballot_returns** — `engine\intelligence\ballot_returns.py`
  - *Campaign engine module*
- **demographics** — `engine\intelligence\demographics.py`
  - *Campaign engine module*
- **intelligence_fusion** — `engine\intelligence\intelligence_fusion.py`
  - *Campaign engine module*
- **macro_environment** — `engine\intelligence\macro_environment.py`
  - *Campaign engine module*
- **poll_aggregation** — `engine\intelligence\poll_aggregation.py`
  - *Campaign engine module*
- **polling_ingest** — `engine\intelligence\polling_ingest.py`
  - *Campaign engine module*
- **registration_trends** — `engine\intelligence\registration_trends.py`
  - *Campaign engine module*
### jurisdictions

- **jurisdiction_resolver** — `engine\jurisdictions\jurisdiction_resolver.py`
  - *Campaign engine module*
### notifications

- **notification_engine** — `engine\notifications\notification_engine.py`
  - *Campaign engine module*
### performance

- **assumption_monitor** — `engine\performance\assumption_monitor.py`
  - *Campaign engine module*
- **campaign_scorecard** — `engine\performance\campaign_scorecard.py`
  - *Campaign engine module*
- **forecast_drift** — `engine\performance\forecast_drift.py`
  - *Campaign engine module*
- **leverage_analysis** — `engine\performance\leverage_analysis.py`
  - *Campaign engine module*
- **performance_ingest** — `engine\performance\performance_ingest.py`
  - *Campaign engine module*
### provenance

- **__init__** — `engine\provenance\__init__.py`
  - *Campaign engine module*
- **data_provenance** — `engine\provenance\data_provenance.py`
  - *Campaign engine module*
### setup

- **setup_wizard** — `engine\setup\setup_wizard.py`
  - *Campaign engine module*
### state

- **__init__** — `engine\state\__init__.py`
  - *Campaign engine module*
- **state_builder** — `engine\state\state_builder.py`
  - *Builds and persists the canonical campaign state store*
- **state_diff** — `engine\state\state_diff.py`
  - *Campaign engine module*
- **state_schema** — `engine\state\state_schema.py`
  - *Defines and validates campaign state schema*
- **state_validator** — `engine\state\state_validator.py`
  - *Campaign engine module*
### strategy

- **__init__** — `engine\strategy\__init__.py`
  - *Campaign engine module*
- **campaign_strategy_ai** — `engine\strategy\campaign_strategy_ai.py`
  - *Generates full strategy recommendations and targeting*
- **strategy_exporter** — `engine\strategy\strategy_exporter.py`
  - *Campaign engine module*
- **strategy_report_writer** — `engine\strategy\strategy_report_writer.py`
  - *Campaign engine module*
### voters

- **__init__** — `engine\voters\__init__.py`
  - *Campaign engine module*
- **persuasion_model** — `engine\voters\persuasion_model.py`
  - *Scores voter persuadability using modeled features*
- **precinct_voter_metrics** — `engine\voters\precinct_voter_metrics.py`
  - *Campaign engine module*
- **targeting_quadrants** — `engine\voters\targeting_quadrants.py`
  - *Campaign engine module*
- **turnout_propensity** — `engine\voters\turnout_propensity.py`
  - *Scores voter likelihood to turn out*
- **universe_builder** — `engine\voters\universe_builder.py`
  - *Campaign engine module*
- **voter_parser** — `engine\voters\voter_parser.py`
  - *Parses and normalizes raw voter file data*
### war_room

- **__init__** — `engine\war_room\__init__.py`
  - *Campaign engine module*
- **data_requests** — `engine\war_room\data_requests.py`
  - *Campaign engine module*
- **forecast_updater** — `engine\war_room\forecast_updater.py`
  - *Campaign engine module*
- **runtime_loader** — `engine\war_room\runtime_loader.py`
  - *Loads live field/volunteer runtime data for war room*
- **status_engine** — `engine\war_room\status_engine.py`
  - *Campaign engine module*
### workflow

- **strategy_approval** — `engine\workflow\strategy_approval.py`
  - *Campaign engine module*
- **task_manager** — `engine\workflow\task_manager.py`
  - *Campaign engine module*

## UI Pages

| Page | Sidebar Section |
|------|----------------|
| 🏠 Overview | 🏠 Campaign Command |
| 🪖 War Room | 🏠 Campaign Command |
| 🌐 Jurisdiction Summary | 🏠 Campaign Command |
| 📋 Team Activity | 🏠 Campaign Command |
| 🗳️ Campaign Setup | 🗳️ Campaign Setup |
| 📂 Upload Contest Data | 🗳️ Campaign Setup |
| 🧭 Political Intelligence | 📊 Intelligence |
| 🧠 Voter Intelligence | 📊 Intelligence |
| 📂 Data Manager | 📂 Data |
| 🗄️ Data Explorer | 📂 Data |
| 🗺️ Precinct Map | 🗺️ Geography |
| 🎯 Targeting | 🗺️ Geography |
| 📋 Strategy | 📈 Strategy & Modeling |
| 🔬 Simulations | 📈 Strategy & Modeling |
| 🏛️ Historical Archive | 📈 Strategy & Modeling |
| ⚡ Advanced Modeling | 📈 Strategy & Modeling |
| 📐 Calibration | 📈 Strategy & Modeling |
| 🩺 Diagnostics | 🛠 System |

## Configuration Files

| File | Size (bytes) | Keys |
|------|-------------|------|
| .gitkeep | 0 |  |
| advanced_modeling.yaml | 3090 | effort, elasticity, curves, persuasion_direction, simulation, optimizer, scenarios |
| allocation.yaml | 2262 | allocation_method, fallback_chain, cardinality_max_multiplier, registration_discrepancy_threshold, auto_repair_violations, repair_log_level |
| campaign_config.yaml | 1965 | campaign, targets, budget, field_program, volunteers, strategy |
| cities_by_county_ca.json | 2592 | state, version, generated_at, counties |
| counties_ca.json | 13537 | state, version, generated_at, counties |
| field_effects.yaml | 800 | gotv, persuasion, targeting, notes |
| field_ops.yaml | 547 | doors_per_hour, hours_per_shift, contact_rate, persuasion_effect_per_contact, turnout_effect_per_contact, volunteers_per_turf_per_weekend, max_precincts_per_turf, min_registered_per_turf |
| forecast_scenarios.yaml | 1109 | scenarios |
| forecasting.yaml | 642 | turnout_model, swing_model, confidence_intervals |
| jurisdictions_registry.json | 339 | CA |
| model_parameters.yaml | 782 | scoring, turnout, allocation, sanity, calibration |
| model_weights.yaml | 514 | scoring_weights, thresholds, parameters |
| roles_permissions.yaml | 1750 | campaign_manager, data_director, field_director, finance_director, communications_director, analyst, viewer |
| schema_registry.yaml | 1434 | mappings, rules |
| ui_pages.yaml | 1477 | campaign_command, campaign_setup, intelligence, data, geography, strategy_modeling, system |
| universe_rules.yaml | 1149 | universes |
| users_registry.json | 764 | users |
| version.json | 57 | version, release_date |
| voter_schema.yaml | 3069 | voter_id_aliases, precinct_aliases, party_aliases, party_map, vote_history_prefixes, age_aliases, gender_aliases, ethnicity_aliases |

## Data Directory

- `data/elections` ✅ — 2 files
- `data/election_archive` ❌ MISSING — 0 files
- `data/voters` ✅ — 2 files
- `data/intelligence` ✅ — 5 files
- `data/campaign_runtime` ✅ — 4 files

## Derived/Output Inventory

- `derived/models` ✅ — 5 files
- `derived/state` ✅ — 8 files
- `derived/archive` ✅ — 6 files
- `derived/performance` ✅ — 6 files
- `derived/strategy` ✅ — 10 files
- `derived/strategies` — — 0 files
- `derived/simulation` ✅ — 12 files
- `derived/forecasts` ✅ — 42 files
- `derived/file_registry` ✅ — 2 files
- `derived/advanced_modeling` ✅ — 22 files
- `derived/calibration` ✅ — 8 files
- `derived/war_room` ✅ — 3 files

## Trained Models

- **support_model** — `derived\models\support_model.pkl` (unknown)
- **turnout_model** — `derived\models\turnout_model.pkl` (unknown)
- **support_feature_importance** — `derived\models\support_feature_importance.csv` (feature_importance_table)

## Strategy & Simulation Engine

- `strategy_generator` ✅ — `engine/strategy/campaign_strategy_ai.py`
- `targeting_engine` ✅ — `engine/strategy/campaign_strategy_ai.py`
- `scenario_simulator` ✅ — `engine/advanced_modeling/scenarios.py`
- `monte_carlo` ✅ — `engine/advanced_modeling/scenarios.py`
- `resource_allocator` ✅ — `engine/strategy/campaign_strategy_ai.py`
- `lift_models` ✅ — `engine/advanced_modeling/lift_models.py`
- `calibration` ✅ — `engine/calibration/model_calibrator.py`

## Campaign State Store

**State keys present:** run_id, contest_id, state, county, generated_at, campaign_setup, model_summary, strategy_summary, war_room_summary, voter_intelligence_summary, provenance_summary, data_requests, risks, recommendations, artifact_index, calibration_status, calibration_sources

- `contest_id`: 2026_CA_sonoma_prop_50_special
- `county`: 
- `state`: 

## File Registry

File registry not yet generated.

## Deployment Configuration

| Component | Path | Status |
|-----------|------|--------|
| Dockerfile | `deployment/docker/Dockerfile` | ✅ |
| install_sh | `deployment/install/install_campaign_in_a_box.sh` | ✅ |
| install_ps1 | `deployment/install/install_campaign_in_a_box.ps1` | ✅ |
| run_sh | `run_campaign_box.sh` | ✅ |
| run_ps1 | `run_campaign_box.ps1` | ✅ |
| environment_yml | `environment.yml` | ✅ |
| requirements_txt | `requirements.txt` | ✅ |
| system_check | `deployment/scripts/system_check.py` | ✅ |

## Logging System

- `logs/archive` — 2 log files
- `logs/collaboration` — 0 log files
- `logs/latest` — 1 log files
- `logs/runs` — 59 log files
- `logs/ui` — 3 log files

## Security Snapshot

- `.gitignore` present: ✅ (42 rules)
- Voter file protection rules: 5
- Runtime data rules: 3
  - `data/voters/`
  - `data/voter_files/`
  - `derived/voter_models/`
  - `derived/voter_segments/`
  - `/data/voters/`

## Provenance System

**Possible values:** REAL, SIMULATED, ESTIMATED, EXTERNAL, MISSING

- **REAL:** 0 datasets
- **SIMULATED:** 0 datasets
- **ESTIMATED:** 0 datasets
- **EXTERNAL:** 0 datasets
- **MISSING:** 0 datasets

---
*Generated by Campaign In A Box Audit Discovery Script*