# Campaign In A Box — Living Technical System Map
**Version:** 1.2 (Prompt 25A — Contest & Geometry Source Registry) | **Maintained:** Update per Change Protocol (Section K)

> **Prompt 25A Changelog (2026-03-13):**
> - `engine/source_registry/` added: canonical source registry for election result and geometry sources
>   - `source_registry.py`: loader with override merging, multi-factor match scoring
>   - `source_resolver.py`: registry-first resolver with high/medium/low confidence tiers
>   - `source_registry_updates.py`: user approval writeback to `local_overrides.yaml`
>   - `source_registry_report.py`: diagnostics report + JSON snapshots
> - `config/source_registry/` added: schema YAML, seeded contest sources (16 entries), seeded geometry sources (10 entries), local_overrides.yaml, notes
> - Seeded: Sonoma County Registrar 2016-2024, CA SOS statewide, ElectionStats, Clarity ENR
> - Seeded: CA MPREC (SWDB), Sonoma SRPREC, MPREC<->SRPREC crosswalks, city/supervisorial/school boundaries
> - `ui/dashboard/source_registry_view.py` added: Source Registry page with approve/reject/prefer/alias/notes/add-manual UI
> - `ui_pages.yaml` updated: Source Registry added to Data section
> - `campaign_state.json` updated with `source_registry_summary` block

> **Prompt 24 Changelog (2026-03-12):**
> - `archive_ingest.py` rebuilt: real file support (CSV/XLS/XLSX/TSV), MPREC normalization, provenance tagging, multi-format, coverage report
> - `precinct_profiles.py` rebuilt: avg turnout, variance, SD, partisan tilt, OLS trend slopes, special election penalty
> - `trend_analysis.py` added: OLS slopes + R² + p-values + direction labels per precinct
> - `election_similarity.py` added: multi-factor similarity scoring against active contest config
> - `train_support_model.py` upgraded: Isotonic Regression calibration wrapper; graceful fallback with insufficient-data report
> - `file_registry_pipeline.py` added: File registry as active pipeline step; updates `campaign_state.json`
> - `voter_parser.py` patched: chunked reads (50k rows) for files >50MB, VAN dtype map, elapsed time logging

---

## A. System Purpose

**Campaign In A Box** is a self-contained campaign analytics and operations platform for local, state, and federal election campaigns. It runs on a campaign laptop or local server, with optional cloud deployment.

### What It Does Operationally
1. Ingests voter files, election results, field data, polling, and intelligence
2. Models precinct-level voter behavior (turnout propensity + persuasion scoring)
3. Forecasts election outcomes under multiple field effort scenarios
4. Generates a full campaign strategy with vote path, budget allocation, and field plan
5. Tracks real-time field operations via War Room (contacts, volunteer output, pace vs. goal)
6. Provides an audit-ready provenance trail for all data and model outputs

### Major User Types
| Role | Primary Use |
|------|-------------|
| Campaign Manager | Strategy overview, risk flagging, scenario comparison |
| Data Director | Voter model outputs, pipeline management, data quality |
| Field Director | War Room pace tracking, precinct priorities, turf building |
| Analyst | Advanced modeling, simulation, calibration, diagnostics |
| Finance Director | Budget allocation view |
| Viewer | Read-only access to dashboards |

---

## B. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  UI LAYER — Streamlit (18 pages across 7 sidebar sections)          │
│  ui/dashboard/app.py → *_view.py → ui/components/                  │
│  Cache: @st.cache_data(ttl=120) via ui/dashboard/data_loader.py     │
└────────────────────────┬────────────────────────────────────────────┘
                         │ reads
┌────────────────────────▼────────────────────────────────────────────┐
│  STATE LAYER                                                        │
│  engine/state/state_builder.py → derived/state/latest/campaign_state│
│  engine/state/state_schema.py — schema definition & validation      │
│  engine/state/state_validator.py — validates before write           │
│  engine/state/state_diff.py — detects state changes between runs    │
└────────────────────────┬────────────────────────────────────────────┘
                         │ reads derived/ outputs
┌────────────────────────▼────────────────────────────────────────────┐
│  ENGINE LAYER — 19 subsystems in engine/                            │
│  See Section D for full subsystem map                               │
│  Shared utils: engine/utils/helpers.py                              │
│                engine/utils/derived_data_reader.py                  │
└────────────────────────┬────────────────────────────────────────────┘
                         │ writes to
┌────────────────────────▼────────────────────────────────────────────┐
│  DERIVED OUTPUTS (derived/) — all safe for Git                      │
│  derived/state/  advanced_modeling/  archive/  calibration/         │
│  derived/forecasts/  models/  performance/  simulation/             │
│  derived/strategy/  war_room/  file_registry/  repair/             │
└────────────────────────┬────────────────────────────────────────────┘
                         │ sourced from
┌────────────────────────▼────────────────────────────────────────────┐
│  RAW DATA LAYER (data/) — gitignored where PII                      │
│  data/elections/  data/voters/ (gitignored)                         │
│  data/intelligence/  data/campaign_runtime/  data/election_archive/ │
└────────────────────────┬────────────────────────────────────────────┘
                         │ deployed via
┌────────────────────────▼────────────────────────────────────────────┐
│  DEPLOYMENT LAYER                                                   │
│  deployment/install/  deployment/docker/  deployment/scripts/       │
│  run_campaign_box.ps1 / run_campaign_box.sh                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## C. Data Model

### Canonical Folder Structure

| Folder | Purpose | Git-Safe? |
|--------|---------|----------|
| `data/elections/` | Raw election result files | ✅ |
| `data/voters/` | Raw voter files (PII) | ❌ gitignored |
| `data/intelligence/` | Polling, demographics, registration | ✅ |
| `data/campaign_runtime/` | Live field/volunteer data | ❌ gitignored |
| `data/election_archive/` | Historical election files | ✅ (results only) |
| `derived/` | All pipeline outputs | ✅ |
| `config/source_registry/` | Election/geometry source registry | ✅ |
| `config/` | All configuration files | ✅ |
| `engine/` | All pipeline code | ✅ |
| `ui/` | All dashboard code | ✅ |

### Major File Types

| Extension | Purpose |
|-----------|---------|
| `.csv` | Derived data tables (precinct models, voter scores, scenarios) |
| `.json` | State store, config registries, provenance records |
| `.pkl` | Trained ML models (turnout_model, support_model) |
| `.yaml` | Configuration files |
| `.geojson/.shp` | Precinct boundary geometry |
| `.md` | Audit reports, rollback docs, system documentation |
| `.log` | Run logs (logs/ directory) |

### Provenance Types

| Value | Meaning |
|-------|---------|
| `REAL` | Actual campaign or voter file data |
| `SIMULATED` | Model-generated or scenario-based |
| `ESTIMATED` | Derived from comparable data |
| `EXTERNAL` | Data from third-party sources |
| `MISSING` | Data not yet available |

### Run ID Logic

Every pipeline run is stamped with a `run_id`:
```
<YYYYMMDD>__<HHMMSS>__<8-char-hash>__<machine>__<contest_id>
```
All derived outputs are prefixed with the `run_id`:
```
derived/strategy/<run_id>__vote_path.csv
derived/advanced_modeling/<contest_id>/<run_id>__advanced_scenarios.csv
```
This enables full reproducibility — any run can be traced to its exact inputs.

### State Store Structure

```json
{
  "run_id": "...",
  "contest_id": "...",
  "state": "CA",
  "county": "Sonoma",
  "generated_at": "...",
  "campaign_setup": {},
  "model_summary": {},
  "strategy_summary": {},
  "war_room_summary": {},
  "archive_summary": {},
  "historical_models_active": "true/false",
  "calibration_status": {},
  "source_registry_summary": {
    "contest_sources": 16,
    "geometry_sources": 10,
    "approved_sources": 0,
    "registry_coverage": "partial|good|strong"
  },
  "risks": [],
  "recommendations": []
}
```

---

## D. Engine Subsystem Map

### source_registry
- **Purpose:** Canonical lookup layer for known election result and geometry sources. Called first by archive discovery and file registry before any web search or user prompt.
- **Key files:** `source_registry.py`, `source_resolver.py`, `source_registry_updates.py`, `source_registry_report.py`
- **Config:** `config/source_registry/contest_sources.yaml` (16 seeded), `geometry_sources.yaml` (10 seeded), `local_overrides.yaml` (user approvals)
- **Resolver flow:** lookup → score by state/county/year/election_type/alias → tier as high/medium/low confidence → return best; fallback_required=True only if no high/medium match
- **Scoring:** base × county_match × year_match × election_type × contest_alias × confidence_default
- **High confidence threshold:** ≥0.80 (use directly); Medium: 0.55–0.80 (present for confirmation); Low: <0.55 (fallback only)
- **User approval writeback:** UI calls `source_registry_updates.py` → persists to `local_overrides.yaml`
- **Outputs:** `derived/source_registry/<RUN_ID>__contest_registry_snapshot.json`, `geometry_registry_snapshot.json`, `reports/source_registry/<RUN_ID>__source_registry_report.md`; updates `campaign_state.json → source_registry_summary`
- **Failure modes:** Falls back gracefully if YAML missing; never blocks pipeline
- **UI:** Source Registry page — approve/reject/preferred/alias/notes/add-manual actions

### archive
- **Purpose:** Ingests historical election data and trains baseline ML models
- **Key files:** `archive_ingest.py`, `precinct_profiles.py`, `trend_analysis.py`, `election_similarity.py`, `train_turnout_model.py`, `train_support_model.py`, `generate_archive_summary.py`
- **Inputs:** `data/election_archive/<state>/<county>/<year>/` (CSV, XLS, XLSX, TSV)
- **Outputs:** `derived/archive/normalized_elections.csv`, `precinct_profiles.csv`, `precinct_trends.csv`, `similar_elections.csv`, `derived/models/turnout_model.pkl`, `derived/models/support_model.pkl`
- **Precinct profiles:** avg_turnout, turnout_variance, support_mean, support_sd, partisan_tilt, special_election_penalty, OLS trend slopes, R², p-values
- **Election similarity:** scores historical elections against active contest by type, jurisdiction, turnout proximity, support proximity
- **Calibration status:** Isotonic Regression wrapper implemented. Requires real election result data (precinct-level totals with support_rate) to activate.
- **Dependencies:** pandas, numpy, scikit-learn, scipy, joblib
- **Failure modes:** Falls back to synthetic mock data if real archive is absent. Calibration skipped if <50 clean training rows. Both produce explicit reports.

### advanced_modeling
- **Purpose:** Applies lift curves, runs scenarios, optimizes resource allocation
- **Key files:** `lift_models.py`, `scenarios.py`, `optimizer.py`, `universe_allocation.py`
- **Inputs:** `derived/voter_universes/`, `config/advanced_modeling.yaml`, `config/field_effects.yaml`
- **Outputs:** `derived/advanced_modeling/<contest_id>/<run_id>__advanced_scenarios.csv`
- **Lift formula:** `lift(contacts) = max_lift * (1 - exp(-k * contacts))` (saturating exponential)
- **Config source of truth:** `config/advanced_modeling.yaml` (curves section). `field_effects.yaml` provides supplementary overrides — see lift parameter priority below.
- **Lift parameter priority:** `advanced_modeling.yaml` curves → `field_effects.yaml` keys → hardcoded defaults
- **Failure modes:** Silent zero fallback if required columns missing (guarded post-Prompt23)

### calibration
- **Purpose:** Calibrates model outputs against observed historical results
- **Key files:** `model_calibrator.py`, `calibration_engine.py`, `turnout_calibrator.py`, `persuasion_calibrator.py`
- **Inputs:** `derived/archive/`, `config/model_parameters.yaml`
- **Outputs:** `derived/calibration/model_parameters.json`
- **Failure modes:** Falls back to default parameters if calibration data absent

### data_intake
- **Purpose:** Classifies, validates, and routes uploaded data files
- **Key files:** `data_intake_manager.py`, `file_registry_pipeline.py`, `github_safety.py`, `missing_data_assistant.py`
- **Inputs:** Uploaded files via UI, pipeline run completion hook
- **Outputs:** `derived/file_registry/latest/file_registry.json`, `missing_data_requests.json`, `source_finder_recommendations.json`; updates `campaign_state.json`
- **Registry pipeline:** Scans all known pipeline output paths, classifies active vs missing, writes recommendations for missing files
- **Security note:** `github_safety.py` enforced via `.pre-commit-config.yaml`
- **Failure modes:** Miscategorized files may land in wrong canonical directory

### geo
- **Purpose:** Validates and normalizes precinct geometry
- **Key files:** `geometry_validation.py`, `master_index_builder.py`
- **Inputs:** `data/geography/`, `.geojson`/`.shp` files
- **Outputs:** `derived/normalized_boundaries/`, `derived/geography/`
- **Failure modes:** Missing shapefiles degrade map view; app degrades gracefully

### integrity
- **Purpose:** Detects and auto-repairs data integrity issues
- **Key files:** `integrity_repairs.py`, `join_guard.py`
- **Inputs:** Any derived CSV
- **Outputs:** Repaired CSVs with repair log
- **Failure modes:** Cannot repair schema mutations; flags and skips

### intelligence
- **Purpose:** Ingests external political intelligence data
- **Key files:** `intelligence_fusion.py`, `poll_aggregation.py`, `polling_ingest.py`, `ballot_returns.py`, `demographics.py`, `registration_trends.py`
- **Inputs:** `data/intelligence/`
- **Outputs:** `derived/intelligence/`
- **Failure modes:** Falls back to empty if no intelligence data uploaded

### jurisdictions
- **Purpose:** Resolves jurisdiction names to canonical IDs
- **Key files:** `jurisdiction_resolver.py`
- **Inputs:** `config/jurisdictions_registry.json`, `config/counties_ca.json`
- **Outputs:** Canonical jurisdiction ID strings
- **Failure modes:** Unknown jurisdiction → `UNKNOWN_*` placeholder

### performance
- **Purpose:** Tracks forecast drift, assumption changes, scorecard metrics
- **Key files:** `campaign_scorecard.py`, `forecast_drift.py`, `assumption_monitor.py`, `leverage_analysis.py`, `performance_ingest.py`
- **Inputs:** Sequential state snapshots, runtime data
- **Outputs:** `derived/performance/`
- **Failure modes:** Requires 2+ runs to produce drift metrics

### provenance
- **Purpose:** Records data lineage for all pipeline inputs/outputs
- **Key files:** `data_provenance.py`
- **Inputs:** All derived file writes
- **Outputs:** `derived/provenance/`
- **Failure modes:** Missing provenance — audit trail incomplete but pipeline continues

### state
- **Purpose:** Assembles and persists the canonical campaign state store
- **Key files:** `state_builder.py`, `state_schema.py`, `state_validator.py`, `state_diff.py`
- **Inputs:** All `derived/` subdirectories
- **Outputs:** `derived/state/latest/campaign_state.json`, `derived/state/history/`
- **Failure modes:** Missing derived inputs produce partial state; schema validator flags missing required keys

### strategy
- **Purpose:** Generates full campaign strategy from pipeline outputs
- **Key files:** `campaign_strategy_ai.py`, `strategy_exporter.py`, `strategy_report_writer.py`
- **Inputs:** Via `derived_data_reader.py` from `derived/advanced_modeling/`, `derived/voter_models/`, `derived/voter_universes/`
- **Outputs:** `derived/strategy/<run_id>__vote_path.csv`, `__field_strategy.csv`, `__budget_allocation.csv`, `__risk_analysis.csv`
- **Failure modes:** If simulation inputs not found, strategy runs without scenario comparison

### voters
- **Purpose:** Parses voter files and computes individual voter scores
- **Key files:** `voter_parser.py`, `persuasion_model.py`, `turnout_propensity.py`, `universe_builder.py`, `targeting_quadrants.py`, `precinct_voter_metrics.py`
- **Inputs:** `data/voters/` (gitignored)
- **Outputs:** `derived/voter_models/`, `derived/voter_segments/`, `derived/voter_universes/`
- **Performance:** Files >50MB (default threshold) are read in 50k-row chunks for memory safety. Elapsed time logged per file.
- **Failure modes:** Missing voter file → model runs on synthetic data only

### war_room
- **Purpose:** Real-time field operations tracking and forecast updating
- **Key files:** `runtime_loader.py`, `forecast_updater.py`, `status_engine.py`, `data_requests.py`
- **Inputs:** `data/campaign_runtime/`, `derived/strategy/*__vote_path.csv`
- **Outputs:** `derived/war_room/<run_id>__forecast_update_comparison.csv`
- **Failure modes:** Falls back to ESTIMATED mode when REAL data absent; always shows a comparison table

### workflow
- **Purpose:** Task management and strategy approval workflows
- **Key files:** `task_manager.py`, `strategy_approval.py`
- **Inputs:** User actions via UI
- **Outputs:** Task records in `derived/workflow/`

### auth
- **Purpose:** User authentication and RBAC
- **Key files:** `auth_manager.py`
- **Inputs:** `config/users_registry.json`, `config/roles_permissions.yaml`
- **Security:** Credentials must use environment variables — no plaintext in YAML
- **Failure modes:** If registry missing, login is blocked

### notifications
- **Purpose:** Generates alerts and notifications for key events
- **Key files:** `notification_engine.py`
- **Inputs:** State store, performance metrics
- **Failure modes:** Non-critical; degraded gracefully

### audit
- **Purpose:** Validates pipeline artifact integrity
- **Key files:** `artifact_validator.py`
- **Inputs:** All derived outputs
- **Outputs:** Validation reports to `reports/audit/`

---

## E. Mathematical Framework

### Vote Path
```
expected_voters = registered_total × avg_turnout_rate
win_number      = ceil(expected_voters × target_vote_share)
gap             = win_number - base_votes
persuasion_votes_needed = gap × persuasion_share  [configurable, default 0.65]
gotv_votes_needed       = gap × (1 - persuasion_share)  [default 0.35]
```
**Config:** `campaign_config.yaml → targets.target_vote_share`, `strategy.persuasion_gotv_split`

### Turnout Model
Trained: RandomForestRegressor on historical precinct data
Input features: prior election turnout rates, registration density, demographic indices
Output: `turnout_propensity_score` ∈ [0, 1]
**Note:** Scores require no calibration (regressor output is already [0,1] bounded for rate prediction)

### Persuasion Model
Trained: GradientBoostingRegressor on historical support rates
Output: raw regression score → **must be calibrated** to [0,1] probability space via isotonic regression
**Status:** Calibration wrapper added (Prompt 23)

### Lift Curves (Saturating Exponential)
```
turnout_lift(contacts) = max_turnout_lift × (1 - exp(-k_turnout × contacts))
persuasion_lift(contacts) = max_persuasion_lift × (1 - exp(-k_persuasion × contacts))

turnout_new = clamp(turnout_base + turnout_lift, 0, 1)
support_new = clamp(support_base + persuasion_lift × direction, 0, 1)
```
**Config source of truth:** `config/advanced_modeling.yaml → curves`
**k parameter override:** `config/field_effects.yaml` (post-Prompt23 wiring)
**Historical trend:** Applied to baseline only — NOT additive with lift (see Prompt 23 fix)

### Monte Carlo Simulation
- 2,000 iterations by default (configurable)
- Samples `max_lift` from Normal prior each iteration
- Returns `net_gain_mean`, `net_gain_p10`, `net_gain_p90`, `net_gain_sd`
- Parallelizable via joblib (recommended for contests > 500 precincts)

### Scenario Comparison
Standard scenarios: baseline (0 shifts), lite (20), medium (50), heavy (100), user_budget (N)
Each scenario: optimizer allocates shifts → contacts per precinct → lift curves → vote projection

### Calibration Logic
Calibrator reads `derived/archive/` historical results and adjusts model priors.
Output: `derived/calibration/model_parameters.json` — consumed by state builder.

### Performance Drift Logic
Compares sequential state snapshots to detect forecast movement.
Flags if win probability changes by > threshold between runs.

---

## F. Configuration Map

| Config File | Controls | Consumed By | If Missing |
|-------------|---------|-------------|-----------|
| `campaign_config.yaml` | Contest params, budget, field plan, volunteer targets | strategy AI, state builder, war room | Strategy engine uses hardcoded defaults |
| `advanced_modeling.yaml` | Lift curve parameters, MC iterations, scenario budgets | lift_models.py, scenarios.py, optimizer.py | Hardcoded defaults used |
| `field_effects.yaml` | Field tactic lift values (door, phone, mail, sms) | lift_models.py (k parameter override) | Hardcoded defaults used |
| `model_parameters.yaml` | Scoring thresholds, allocation rules | calibration, allocation | Hardcoded defaults |
| `model_weights.yaml` | Scoring feature weights | persuasion/turnout models | Model scores unweighted |
| `allocation.yaml` | Budget allocation rules, cardinality limits | optimizer.py | Optimizer may over-allocate |
| `forecasting.yaml` | Turnout and swing model configs | calibration engine | Defaults used |
| `universe_rules.yaml` | Voter universe targeting rules | universe_builder.py | All voters included |
| `field_ops.yaml` | Doors/hour, contact rates, shift structure | scenarios.py, forecast_updater.py | Defaults used |
| `roles_permissions.yaml` | RBAC definitions | auth_manager.py | All users get viewer access |
| `ui_pages.yaml` | Sidebar navigation pages | app.py | App crashes — required |
| `voter_schema.yaml` | Voter file column name aliases | voter_parser.py | Parse fails on non-standard files |

---

## G. UI Map

| Page | Depends On | Engine Sources |
|------|-----------|---------------|
| Overview | state.strategy_summary, state.risks | strategy_ai.py → derived/strategy/ |
| War Room | state.war_room_summary | runtime_loader.py, forecast_updater.py |
| Jurisdiction Summary | state.campaign_setup | config/campaign_config.yaml |
| Team Activity | derived/workflow/ | task_manager.py |
| Campaign Setup | config/campaign_config.yaml | direct config read |
| Upload Contest Data | data_intake_manager.py | FileRegistryManager |
| Political Intelligence | derived/intelligence/ | intelligence_fusion.py |
| Voter Intelligence | derived/voter_models/ | persuasion_model.py, turnout_propensity.py |
| Data Manager | file_registry.json | data_intake_manager.py |
| Data Explorer | derived/ (multiple) | data_loader.py |
| Precinct Map | derived/normalized_boundaries/ | geo/master_index_builder.py |
| Targeting | derived/voter_segments/ | targeting_quadrants.py |
| Strategy | derived/strategy/ | campaign_strategy_ai.py |
| Simulations | derived/advanced_modeling/ | scenarios.py |
| Historical Archive | state.archive_summary, derived/archive/ | archive/ modules |
| Advanced Modeling | derived/advanced_modeling/ | lift_models.py, optimizer.py |
| Calibration | derived/calibration/ | model_calibrator.py |
| Diagnostics | All derived/ + logs/ | artifact_validator.py |

---

## H. Security Model

### Git-Safe (✅ can commit)
- All code (`engine/`, `ui/`, `scripts/`)
- Config files (`config/`)
- Derived aggregate data (`derived/`)
- Documentation (`docs/`, `reports/`)
- Deployment files (`deployment/`)

### Not Git-Safe (❌ gitignored)
- `data/voters/` — raw voter PII
- `data/voter_files/` — voter file exports
- `data/campaign_runtime/` — live field data
- `derived/voter_models/` — individual voter scores
- `derived/voter_segments/` — voter universe lists
- `derived/voter_universes/` — universe tables

### Enforcement
`.gitignore` has 42 rules protecting all PII directories.
`engine/data_intake/github_safety.py` is enforced as a mandatory pre-commit hook via `.pre-commit-config.yaml`.
Any commit containing voter data will be **blocked automatically**.

### Pre-Commit Installation
```bash
pip install pre-commit
pre-commit install
```

---

## I. Deployment Model

### Install Flow
```
deployment/install/install_campaign_in_a_box.ps1   # Windows
deployment/install/install_campaign_in_a_box.sh    # macOS/Linux
```
- Creates Python venv
- Installs dependencies from `requirements.txt` / `environment.yml`
- Creates required directories

### Run Flow
```
run_campaign_box.ps1   # Windows
run_campaign_box.sh    # Linux/macOS
```
Activates venv, launches `streamlit run ui/dashboard/app.py`

### Backup/Restore Flow
```bash
# Backup current derived outputs
cp -r derived/ ../campaign_backup_$(date +%Y%m%d)/

# Restore
cp -r ../campaign_backup_YYYYMMDD/ derived/

# Git rollback:
git checkout rollback/<branch_name>
```

### Docker/Cloud
`deployment/docker/Dockerfile` available. Mounts `data/` and `derived/` as volumes.
Cloud: generic Linux server supported. See `deployment/cloud/`.

---

## J. Known Risks & Limitations

| Risk | Severity | Status |
|------|---------|--------|
| Historical archive has voter list only (no election result totals) | HIGH | Place real election result files in `data/election_archive/<YEAR>/` |
| MC underestimates variance (samples lift only, not baseline) | MEDIUM | Known limitation — improves with multi-year precinct profiles |
| Large voter files (>200K rows) may be slow | MEDIUM | Chunked reading now active (>50MB triggers 50k-row chunks) |
| Single-user Streamlit session (no multi-user state isolation) | MEDIUM | Not intended for concurrent editing |
| Persuasion model requires calibration for probability output | HIGH | Calibration wrapper added; awaiting election result data to train |

---

## K. Change Protocol

**When to update this document:**

| Change Type | Required Updates |
|-------------|-----------------|
| New engine subsystem added | Section D: add new subsystem block |
| New config file added | Section F: add row to config map |
| New pipeline stage added | Section B: update architecture diagram if layer changes; Section D: update consuming subsystem |
| New derived directory added | Section C: add to canonical folders table |
| Model math changed | Section E: update formula + note in relevant subsystem (Section D) |
| New UI page added | Section G: add row to UI map |
| Security boundary changed | Section H: update |

**Who updates it:** The prompt engineer or developer completing the change, as part of the commit that introduces the change.

**Format:** Keep all tables, keep all section headers. Use clear changelog notes at the top of the file when making updates.


---

## v1.8 � Prompt 28: Canonical Contest Data Architecture (2026-03-14)

### Problem Solved

The system had two independent operational paths for contest/election-result data:

- **UI/Data Manager uploads** ? `data/elections/{state}/{county}/{contest_id}/`
- **Modeling pipeline reads** ? `data/CA/counties/{county}/votes/{year}/{slug}/detail.xlsx`
- **Archive builder** ? saw yet another path

This caused: P28 pre-audit found **7 failure points** including 2020 data never reaching modeling and 2024 real data blocked by a slug mismatch.

### New Canonical Contest Data Architecture

```
data/contests/
  {state}/
    {county}/
      {year}/
        {contest_slug}/
          raw/          <- original uploaded files
          normalized/   <- cleaned result tables
          manifests/    <- contest_metadata.json, ingest_manifest.json, primary_result_file.json
```

### New Engine Modules

| Module | Location | Purpose |
|---|---|---|
| `ContestResolver` | `engine/contest_data/contest_resolver.py` | Canonical path resolver; replaces all hardcoded legacy paths |
| `ContestIntake` | `engine/contest_data/contest_intake.py` | Unified intake workflow (hash, dedup, fingerprint, manifest, register) |
| `ContestHealthChecker` | `engine/contest_data/contest_health.py` | Detects legacy files, registry dupes, broken manifests, legacy code refs |

### Invariants Enforced

- **One canonical path:** all contest result files live at `data/contests/{state}/{county}/{year}/{slug}/raw/`
- **One registry entry per unique file** (SHA-256 dedup in ContestIntake)
- **One primary result file per contest** (`primary_result_file.json` manifest)
- **No new writes** to `data/elections/`, `votes/`, `data/CA/counties/*/votes/`
- **Data Manager** routes `election_results` type through `ContestIntake`
- **Pipeline Runner** uses `ContestResolver` as primary contest discovery source

### Purge Executed (P28 Contest Data Reset)

- 31 contest/result files deleted from legacy paths
- Geography, crosswalk, source registry, campaign config, users � **all preserved**
- `file_registry.json` rebuilt (5 contest entries removed)
- Reports: `reports/contest_reset/2026-03-14__011318__p28/`

### Re-Upload Procedure

1. Open Data Manager ? Upload tab
2. Select file ? set **Campaign Data Type = election_results**
3. Fill in **State**, **County**, **Contest Slug**, **Year**
4. Click Confirm & Save ? file lands in `data/contests/{state}/{county}/{year}/{slug}/raw/`
5. Run pipeline from Pipeline Runner ? contest appears in dropdown from canonical path

---

## v1.9 � Prompt 29: Precinct Normalization & Crosswalk Repair (2026-03-14)

### Changelog

| Change | File(s) |
|---|---|
| `detect_crosswalk_columns()` upgraded to 3-tier resolution (config ? alias ? heuristic) | `scripts/geography/crosswalk_resolver.py` |
| `CROSSWALK_REGISTRY` required_cols fixed to match actual lowercase Sonoma column names | `scripts/lib/crosswalks.py` |
| `load_crosswalk_from_category()` now emits explicit `IDENTITY_FALLBACK_USED` diagnostic | `scripts/geography/crosswalk_resolver.py` |
| New per-file column hint config created for all 5 Sonoma crosswalk files | `config/precinct_id/crosswalk_column_hints.yaml` |
| Manual override config skeleton created | `config/precinct_id/manual_mapping_overrides.yaml` |
| Join outcome taxonomy (10 standardized constants) | `engine/precinct_ids/join_outcomes.py` |
| Deep crosswalk introspector | `engine/precinct_ids/crosswalk_introspector.py` |
| Per-row ID trace logger | `engine/precinct_ids/id_trace.py` |
| Join quality metrics module | `engine/precinct_ids/join_quality.py` |
| Human review queue writer | `engine/precinct_ids/review_queue.py` |
| 5-file diagnostic bundle writer | `engine/precinct_ids/diagnostic_bundle.py` |
| LOAD_CROSSWALKS pipeline step wired to P29 introspection + review queue | `scripts/run_pipeline.py` |

---

## P. Contest ? Crosswalk ? Geometry ? UI: Full Data Flow (Prompt 29)

### P.1 How a Contest File Is Uploaded and Registered

1. **User uploads** via UI: `ui/dashboard/data_manager_view.py` ? Data Manager tab
2. File is written to `data/contests/{state}/{county}/{year}/{contest_slug}/raw/`
3. `engine/contest_data/contest_intake.py` ? `ContestIntake.register_file()` writes metadata to `data/contests/{state}/{county}/{year}/{contest_slug}/registry.json`
4. `engine/contest_data/contest_resolver.py` ? `ContestResolver.resolve_primary_result_file()` � the canonical path lookup used by the pipeline

### P.2 How the Pipeline Selects a Contest File

**Step: VALIDATE_VOTES** in `scripts/run_pipeline.py`:

1. `ContestResolver.resolve_primary_result_file(state, county, year, contest_slug)` is tried first
2. If found in canonical path ? logs `[VALIDATE_VOTES] Found votes via canonical path`
3. If not found ? falls back to legacy path check under `votes/raw/`
4. If still not found ? step SKIPS with reason logged

The contest file path is passed downstream to PARSE_CONTEST_SHEETS.

### P.3 How Sheets Are Parsed and Precinct Columns Identified

**Step: PARSE_CONTEST_SHEETS**:

1. File opened by `scripts/loaders/contest_registry.py`
2. For XLS/XLSX: `engine/contest_data/contest_intake.py` parses sheets
3. Precinct column detection: looks for columns matching `precinct`, `pct`, `Precinct`, `PCT Number` etc.
4. Each row's precinct value becomes `raw_precinct_value`
5. `engine/precinct_ids/id_schema_detector.py` ? `detect_schema()` classifies: `mprec` | `mprec_unpadded` | `short_precinct` | `srprec` | etc.

### P.4 How Crosswalks Are Chosen and Loaded

**Step: LOAD_CROSSWALKS** in `scripts/run_pipeline.py`:

1. `scripts/geography/crosswalk_resolver.load_crosswalk_from_category()` searches `data/{state}/counties/{county}/geography/crosswalks/`
2. Calls `detect_crosswalk_columns(headers, filename=...)` � **3-tier resolution (P29)**:
   - Tier 1: `config/precinct_id/crosswalk_column_hints.yaml` per-file override
   - Tier 2: Expanded alias table (lowercase + uppercase column names)
   - Tier 3: Filename heuristic (e.g. file contains `blk_mprec` ? prefer `block`,`mprec`)
3. If detection fails ? `IDENTITY_FALLBACK_USED` logged explicitly; `return {}, False`
4. `engine/precinct_ids/crosswalk_introspector.py` runs deep inspection of all crosswalk files
5. Any failures written to `derived/precinct_id_review/{run_id}__crosswalk_review.csv`

**Sonoma crosswalk files and their columns:**

| File | Source col | Target col | Weight col | Purpose |
|---|---|---|---|---|
| `blk_mprec_097_g24_v01.csv` | `block` | `mprec` | `pct_block` | Census block ? MPREC |
| `mprec_srprec_097_g24.csv` | `mprec` | `srprec` | none | MPREC ? SRPREC |
| `c097_g24_srprec_to_city.csv` | `srprec` | `city` | none | SRPREC ? City |
| `c097_g24_sr_blk_map.csv` | `srprec` | `block` | `pctsrprec` | SRPREC ? Block |
| `c097_rg_rr_sr_svprec_g24.csv` | `rgprec` | `svprec` | none | RG?RR?SR?SVPREC chain |

### P.5 How Raw Precinct IDs Become Canonical IDs

1. `engine/precinct_ids/id_normalizer.py` ? `normalize_id(raw_id, schema_key, state, county, boundary_type)`
   - `mprec`: zero-pad to 7 digits
   - `mprec_unpadded`: left-pad to 7 digits
   - `short_precinct`, `srprec`, `city_precinct`: **fail closed** � require explicit crosswalk
   - `unknown_schema`: fail closed, review required
2. `engine/precinct_ids/id_crosswalk_resolver.py` ? `resolve_via_crosswalk()`: searches all crosswalk files for a match
3. Result: canonical key `{STATE}|{COUNTY}|{BOUNDARY_TYPE}|{CANONICAL_ID}`

### P.6 How Geometry Joins Happen

1. Geometry loaded from `data/{state}/counties/{county}/geography/precinct_shapes/`
2. Join key in geometry file identified (MPREC or SRPREC field)
3. Contest canonical keys matched against geometry IDs
4. Outcome recorded using join outcome taxonomy from `engine/precinct_ids/join_outcomes.py`:
   - `EXACT_GEOMETRY_MATCH` � raw ID matched directly
   - `EXACT_CROSSWALK_MATCH` � crosswalk resolved it
   - `NORMALIZED_MATCH` � zero-padding resolved it
   - `IDENTITY_FALLBACK_USED` � crosswalk failed; raw ID used as-is ??
   - `NO_MATCH_AFTER_NORMALIZATION` � ID couldn't be resolved
5. Join quality computed by `engine/precinct_ids/join_quality.py` ? `JoinQualityReport`

### P.7 How Map Data Is Produced

1. Joined GeoDataFrame emitted after geometry join step
2. Exported as GeoJSON to `derived/maps/{run_id}_{contest_slug}.geojson`
3. `scripts/geo/kepler_export.py` produces Kepler.gl config + data layer
4. Map page reads from `derived/maps/` � if join coverage poor, sparse map appears

### P.8 How Archive Outputs Are Produced

1. `engine/archive_builder/archive_ingestor.py` ingests normalized contest rows
2. Requires geometry join to have succeeded � empty join ? empty archive profiles
3. `engine/archive/precinct_profiles.py` builds per-precinct turnout/support statistics
4. `engine/archive/trend_analysis.py` adds OLS trend slopes
5. Archive outputs written to `derived/archive/{state}/{county}/{year}/{contest_slug}/`

---

## Q. File-by-File Subsystem Map: engine/precinct_ids/

| File | Purpose | Inputs | Outputs | Common failures |
|---|---|---|---|---|
| `id_schema_detector.py` | Classify raw precinct ID schema | raw string | schema key (`mprec`, `srprec`, ...) | `unknown_schema` if unexpected format |
| `id_normalizer.py` | Normalize to canonical 7-digit or scoped ID | raw_id, schema_key, state, county | `NormalizationResult` | Fails closed for `short_precinct`/`srprec` � requires crosswalk |
| `id_crosswalk_resolver.py` | Resolve via crosswalk files | raw_id, state, county, boundary | `CrosswalkResolutionResult` | `NO_MATCH` if crosswalk files missing/wrong columns |
| `id_rules.yaml` | Schema detection regex rules | � | loaded by `id_schema_detector.py` | � |
| `safe_join_engine.py` | Jurisdiction-safe join engine | normalized IDs, geometry index | joined GDF | `BLOCKED_CROSS_JURISDICTION` if county mismatch |
| **NEW: P29** | | | | |
| `join_outcomes.py` | Standardized outcome constants | � | 10 outcome strings | � |
| `crosswalk_introspector.py` | Deep per-file crosswalk inspection | crosswalk directory | list of `CrosswalkFileReport` | import error if pandas not installed |
| `id_trace.py` | Per-row join trace logger | PrecincIDTracer calls | `{run_id}__id_trace.csv`, `__id_trace_summary.json` | Large CSV if not sampled |
| `join_quality.py` | Join quality metrics | outcome_counts dict | `JoinQualityReport` | verdict FAILED if 0% joined |
| `review_queue.py` | Human review CSV writer | crosswalk/join issues | `derived/precinct_id_review/*.csv` | Empty CSVs if no failures |
| `diagnostic_bundle.py` | 5-file repairdiagnostic bundle | introspect reports + join quality + trace | `reports/crosswalk_repair/{run_id}/*.{md,json,csv}` | � |

---

## R. Crosswalk & Geometry Data Inventory (Sonoma, CA, g24 vintage)

All files at: `data/CA/counties/Sonoma/geography/crosswalks/`

| File | Maps | Source col | Target col | Weight | Code that uses it |
|---|---|---|---|---|---|
| `blk_mprec_097_g24_v01.csv` | Census Block ? MPREC | `block` | `mprec` | `pct_block` | `scripts/geography/crosswalk_resolver.load_crosswalk_from_category()` |
| `mprec_srprec_097_g24.csv` | MPREC ? SRPREC | `mprec` | `srprec` | none | same |
| `c097_g24_srprec_to_city.csv` | SRPREC ? City | `srprec` | `city` | none | `scripts/aggregation/vote_allocator.py` |
| `c097_g24_sr_blk_map.csv` | SRPREC ? Block (weighted) | `srprec` | `block` | `pctsrprec` | block-level allocation |
| `c097_rg_rr_sr_svprec_g24.csv` | RG?RR?SR?SVPREC chain | `rgprec` | `svprec` | none | RG-prec analysis |

Geometry file: `data/CA/counties/Sonoma/geography/precinct_shapes/`
  - Contains MPREC geometry (primary) and SRPREC geometry (fallback)
  - Expected ID column: `MPREC` or `mprec` (case-insensitive match in join engine)

---

## S. Join Logic Narrative

### How raw precinct IDs become canonical IDs

1. Contest sheet parsed ? raw string extracted from precinct column (e.g. `"127"`, `"PCT 0127"`, `"0400127"`)
2. `id_schema_detector.py` classifies the string: `mprec` (7 digits), `mprec_unpadded` (6 digits), `short_precinct` (1-3 digits), `srprec`, etc.
3. For `mprec`/`mprec_unpadded`: `id_normalizer.py` zero-pads to 7 digits ? canonical ID `0400127`
4. For `short_precinct`/`srprec`: normalizer **fails closed** � crosswalk required
5. Crosswalk used: `engine/precinct_ids/id_crosswalk_resolver.py` searches `data/crosswalks/{state}/{county}/`
6. Cross-jurisdiction check: if state or county doesn't match the contest's scope ? `BLOCKED_CROSS_JURISDICTION`
7. Final output: canonical scoped key `CA|Sonoma|MPREC|0400127`

### When identity fallback is dangerous

Identity fallback (`IDENTITY_FALLBACK_USED`) means the crosswalk detector could not identify source and target columns, so the raw precinct string is used directly as the geometry join key. This produces:
- Map points only where the raw string accidentally matches a geometry ID
- "Scattered" or "sparse" map with no interpretable pattern
- Empty archive profiles
- **Fix**: add entry to `config/precinct_id/crosswalk_column_hints.yaml`

---

## T. UI Data Lineage

| Page | Files read | Derived outputs expected | If join poor |
|---|---|---|---|
| Precinct Map | `derived/maps/{run_id}*.geojson` | Geometry-joined GeoJSON | Blank or scattered points |
| Archive / Precinct Profiles | `derived/archive/{state}/{county}/{year}/{slug}/` | precinct_profiles.json | Empty profiles |
| Pipeline Runner | pipeline stdout + `reports/pipeline_logs/{run_id}.log` | � | Download buttons show raw log |
| Data Manager | `data/contests/{state}/{county}/{year}/{slug}/registry.json` | � | "No files" if registry missing |
| Source Registry | `config/source_registry/*.yaml` | � | Empty registry |

---

## U. How the System Can Fail (Known Failure Patterns)

| Failure | Symptom | Root cause | Fix |
|---|---|---|---|
| File uploaded but not selected by pipeline | VALIDATE_VOTES skips | `ContestResolver.resolve_primary_result_file()` returns None | Ensure file is in correct canonical path `data/contests/{state}/{county}/{year}/{slug}/raw/` |
| Crosswalk columns not detected | IDENTITY_FALLBACK_USED; map scattered | `detect_crosswalk_columns()` alias mismatch | Add `per_file_hints` to `config/precinct_id/crosswalk_column_hints.yaml` |
| Stub contest file used instead of real file | 0 votes found | Pipeline resolves placeholder file | Upload real result file via Data Manager ? canonical path |
| Archive outputs synthetic/empty | Profiles page blank | Geometry join had 0% coverage (identity fallback) | Fix crosswalk detection; re-run pipeline |
| Map join sparse (random precincts) | Only 2-5 precincts on map | Identity fallback: raw precinct strings randomly match geometry IDs | Fix crosswalk; run introspector; check `crosswalk_repair_summary.md` |
| Schema `short_precinct` fails closed | `requires_crosswalk` in trace | 1-3 digit raw IDs need crosswalk to map to 7-digit MPREC | Verify crosswalk file is present and columns detected |
| Archive ingest empty | Blank `precinct_profiles.json` | Archive ingest requires geometry join rows | Fix upstream join; geometry must match before archive runs |
| `KeyError: 'current_filename'` in UI | Data Manager crash | Old schema field in registry | Fixed by `_norm()` in `data_manager_view.py` |

