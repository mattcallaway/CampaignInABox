# Campaign In A Box — Rollback Points

This file documents all official rollback points for Campaign In A Box.
When something breaks during a major repair or feature pass, use these points to restore the last good state.

---

## How to Restore a Rollback Point

```bash
# Option A: Restore to branch
git checkout rollback/prompt23_pre_stabilization

# Option B: Restore to tagged commit
git checkout tags/v_pre_prompt23_stable

# Then verify:
python deployment/scripts/system_check.py
streamlit run ui/dashboard/app.py
```

---

## Rollback Entries

---

### Entry 1 — Pre Prompt 23 Stabilization

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-12T22:04:00-07:00 |
| **Branch** | `rollback/prompt23_pre_stabilization` |
| **Tag** | `v_pre_prompt23_stable` |
| **Overall Health Score** | 5.8 / 10 (from Prompt 23 full audit) |
| **Created By** | Prompt 23 pre-repair protocol |

#### What Was Working
- 18 dashboard pages fully routed and rendering
- Streamlit app launching cleanly on port 8502
- Historical Archive page (Prompt 22) — UI and engine complete
- Strategy, simulation, advanced modeling pages functional
- War room runtime tracking operational
- Deployment installer scripts present (Docker, bash, PS1)
- Voter file security protection via .gitignore (42 rules)
- Monte Carlo simulation with P10/P90 outputs
- Campaign state store persisting to `derived/state/latest/`
- All bugs from session fixed: `_DESTINATION_RULES`, `metric_card` import, `rec.get()` str error

#### Known Issues at This Point (Motivating the Repair)
- `field_effects.yaml` not wired to `lift_models.py` — YAML changes silently ignored
- Strategy engine searches `derived/scenario_forecasts/` (does not exist)
- `github_safety.py` not enforced as pre-commit hook
- Historical trend double-counting in lift math
- `county` and `state` empty in campaign state snapshot
- File registry not generated in pipeline
- 18 `tmp_patch_*.py` files at repository root
- Persuasion model scores uncalibrated (raw regressor output)
- Arrow serialization warnings on every page load

#### Why This Rollback Point Matters
This is the last validated point before the systematic critical stabilization from the Prompt 23 audit. If the repair pass introduces regressions, restore to this point and re-approach the specific repair that broke things.

---

### Entry 2 — Post Prompt 23 Repair

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-12T22:35:00-07:00 |
| **Branch** | `rollback/prompt23_post_repair` |
| **Tag** | `v_post_prompt23_repaired` |
| **Overall Health Score** | ~7.0 / 10 (expected improvement from 5.8) |
| **Created By** | Prompt 23 post-repair protocol |

#### What Was Fixed
- **C01:** `field_effects.yaml` wired into `lift_models.py` via priority chain
- **C02:** Broken `scenario_forecasts/` path replaced with `DerivedDataReader` canonical resolver
- **C03:** `.pre-commit-config.yaml` created — GitHub safety now enforced on every commit
- **M-01:** Historical trend double-counting fixed (`apply_historical_trends` flag)
- **M-02:** 65/35 GOTV/persuasion split is now configurable via `strategy.persuasion_gotv_split`
- **Phase 7:** `state` and `county` populated in `campaign_config.yaml`
- **Phase 9:** 20 `tmp_patch_*.py` files deleted from repository root
- **New utilities:** `engine/utils/helpers.py`, `engine/utils/derived_data_reader.py`
- **Docs:** `docs/SYSTEM_TECHNICAL_MAP.md` (11 sections), `docs/ROLLBACK_POINTS.md`

#### Why This Rollback Point Matters
This is the first validated post-repair snapshot. Use this point if a future feature prompt breaks any of the C01/C02/C03 fixes.

---

### Entry 3 — Pre Prompt 24 Archive & Calibration

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-12T22:45:00-07:00 |
| **Branch** | `rollback/prompt24_pre_archive_calibration` |
| **Tag** | `v_pre_prompt24_archive_calibration` |
| **Overall Health Score** | ~7.0 / 10 (post Prompt 23 stabilization baseline) |
| **Created By** | Prompt 24 pre-work protocol |

#### What Was Working (Prompt 23 baseline)
All Prompt 23 fixes are active and verified. GitHub safety pre-commit hook live. Strategy engine path fixed. Field effects wired. Technical map written.

#### Why This Rollback Point Matters
Last validated state before the archive population, calibration, and voter parser changes of Prompt 24.

---

### Entry 4 — Post Prompt 24 Archive & Calibration

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-12T23:00:00-07:00 |
| **Branch** | `rollback/prompt24_post_archive_calibration` |
| **Tag** | `v_post_prompt24_archive_calibration` |
| **Overall Health Score** | ~7.5 / 10 (expected after Prompt 24; ~8.5/10 with real election data) |
| **Created By** | Prompt 24 post-work protocol |

#### What Was Completed
- **Archive Ingest:** Real file parsing from `data/election_archive/` — multi-format, MPREC normalization, provenance tagging
- **Precinct Profiles:** avg_turnout, variance, SD, tilt, special election penalty, OLS trend slopes — from archive data
- **Trend Analysis:** OLS slopes + R² + p-values + direction labels per precinct
- **Election Similarity:** Multi-factor scoring (type, jurisdiction, turnout, support) — machine-usable ranking
- **Calibration Framework:** Isotonic regression wrapper fully implemented; awaiting election result data to activate
- **File Registry:** Active as normal pipeline step; updates `campaign_state.json` on every run
- **Voter Parser:** Chunked reads (50k rows) for files >50MB; VAN dtype maps; elapsed time logging
- **SYSTEM_TECHNICAL_MAP:** Updated with Prompt 24 changelog

#### Remaining Deferred Items
- Real election result files needed in `data/election_archive/<YEAR>/` for model training to activate
- Monte Carlo parallelization (optional)
- Persuasion score calibration (requires election result data)

#### Why This Rollback Point Matters
First post-calibration-framework snapshot. If Prompt 25 breaks precinct profiles or file registry behavior, restore to this point.

---

### Entry 5 — Pre Prompt 25A Source Registry

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-13T00:00:00-07:00 |
| **Branch** | `rollback/prompt25a_pre_source_registry` |
| **Tag** | `v_pre_prompt25a_source_registry` |
| **Overall Health Score** | ~7.5 / 10 (post Prompt 24 baseline) |

#### What Was Working
All Prompt 23 and 24 fixes active. Archive ingest live. Registry active. Precinct profiles built. Technical map v1.1.

#### Why This Rollback Point Matters
Last validated state before source registry system was added. If source registry causes import errors or UI crashes, restore here.

---

### Entry 6 — Post Prompt 25A Source Registry

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-13T00:45:00-07:00 |
| **Branch** | `rollback/prompt25a_post_source_registry` |
| **Tag** | `v_post_prompt25a_source_registry` |
| **Overall Health Score** | ~8.0 / 10 |

#### What Was Completed
- Source Registry: 16 seeded contest sources (Sonoma 2016-2024, CA SOS statewide, ElectionStats, Clarity ENR)
- Geometry Registry: 10 seeded sources (MPREC, SRPREC, 3 crosswalk types, city/supervisorial/school boundaries)
- Resolver: Registry-first lookup with high/medium/low confidence tiers, official-status prioritization
- User Approval Writeback: Persists to `config/source_registry/local_overrides.yaml`
- Source Registry UI Page: Approve/reject/prefer/alias/notes/add-manual actions; diagnostics runner
- Diagnostics: Reports and JSON snapshots with coverage analysis, gap detection, year coverage
- campaign_state.json updated with `source_registry_summary`
- SYSTEM_TECHNICAL_MAP.md updated to v1.2 with source_registry subsystem

#### Validation Results
- Contest sources: 16 | Geometry sources: 10
- Best match for CA/Sonoma/2024/general: `ca_sonoma_registrar_2024_general` (score=1.805)
- Best crosswalk: `ca_sonoma_mprec_srprec_crosswalk_local`
- Coverage rating: **strong** | Years covered: 2016, 2018, 2020, 2022, 2024

#### Why This Rollback Point Matters
First post-source-registry snapshot. If Prompt 25B or later breaks registry-first discovery logic, restore here.

---

### Entry 7 — Pre Prompt 25A.1 Registry Validation

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-13T00:24:00-07:00 |
| **Branch** | `rollback/prompt25a1_pre_registry_validation` |
| **Tag** | `v_pre_prompt25a1_registry_validation` |
| **Overall Health Score** | ~8.0 / 10 |
| **Reason** | Source registry confidence system before validation repair |

#### What Was Working
All Prompt 25A source registry work complete. 16 contest sources, 10 geometry sources. UI page live.
Confidence enforcement not yet applied — domain allowlist did not exist yet.

#### Why This Rollback Point Matters
Last state before domain allowlist and confidence recalculation was added.

---

### Entry 8 — Post Prompt 25A.1 Registry Validation

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-13T00:45:00-07:00 |
| **Branch** | `rollback/prompt25a1_post_registry_validation` |
| **Tag** | `v_post_prompt25a1_registry_validation` |
| **Overall Health Score** | ~8.2 / 10 |

#### What Was Completed
- Domain allowlist: 3 tiers (gov=0.99, official=0.90, academic=0.85)
- source_origin field added to all 26 registry entries (schema_version 1.1)
- source_verifier.py: domain extraction, allowlist check, HTTP HEAD verification
- confidence_engine.py: 5-rule confidence recalculation with confidence_reason
- registry_repair.py: full repair scan, suspicious source flagging, registry_health.json
- UI updated: Domain, Verified badge, Source Origin, Confidence Reason, suspicious filter
- campaign_state.json updated with source_registry_health
- SYSTEM_TECHNICAL_MAP.md bumped to v1.3

#### Validation Results
- 26 sources validated: 22 verified, 0 suspicious, 0 invalid domains
- Academic tier capped at 0.85, gov tier preserved, all 26 assertions passed
- Coverage: **strong**

#### Why This Rollback Point Matters
First post-confidence-enforcement snapshot. Registry is now policy-enforced.

---

### Entry 13 — Pre Prompt 25A.4 Precinct ID Normalization Engine

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-13T01:32:45-07:00 |
| **Branch** | `rollback/prompt25a4_pre_precinct_id_engine` |
| **Tag** | `v_pre_prompt25a4_precinct_id_engine` |
| **Reason** | Adding jurisdiction-scoped precinct ID normalization safety engine |
| **System Health** | Post-25A.3 (fingerprinting engine complete) |

#### What This Protects Against
- Introduction of cross-jurisdiction join bugs
- False positive precinct ID matches across counties
- SRPREC-to-MPREC mapping without explicit crosswalk
- Ambiguous short IDs being auto-promoted to canonical keys

---

### Entry 14 — Post Prompt 25A.4 Precinct ID Normalization Engine

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-13T01:32:45-07:00 |
| **Branch** | `rollback/prompt25a4_post_precinct_id_engine` |
| **Tag** | `v_post_prompt25a4_precinct_id_engine` |
| **Reason** | Jurisdiction-scoped precinct ID engine complete and validated |

#### What Was Added
- `engine/precinct_ids/` module: id_rules.yaml (7 schema families), id_schema_detector.py, id_normalizer.py, id_crosswalk_resolver.py, safe_join_engine.py
- Canonical scoped key: `CA|Sonoma|MPREC|0400127`
- Confidence tiers: 0.99 exact → 0.95 crosswalk → 0.90 normalized → ≤0.50 ambiguous → 0.00 blocked
- Ambiguity review queue: `derived/precinct_id_review/`
- Audit reports: `reports/precinct_ids/`
- UI: Precinct ID Review tab in Data Manager

#### Validation Results
- 28/28 assertions passed
- Cross-jurisdiction blocking confirmed (confidence=0.00)
- Ambiguous IDs fail closed (no auto-join)
- SRPREC cannot become MPREC without crosswalk
- Coverage: **strong**

---

### Entry 12 — Pre Prompt 26 Swing Modeling

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-13T02:00:00-07:00 |
| **Branch** | `rollback/prompt26_pre_swing_modeling` |
| **Tag** | `v_pre_prompt26_swing_modeling` |
| **Reason** | Backtested swing precinct modeling |
| **Note** | Prompt 25 archive builder is baseline. Before adding swing_detector, persuasion_target_model, turnout_opportunity_model, backtester, metrics, and UI swing modeling view. |

#### Scope
- `engine/swing_modeling/*` — new module (7 files)
- `engine/strategy/swing_strategy_adapter.py` — validation-aware strategy integration
- `ui/dashboard/swing_model_view.py` — swing modeling dashboard view
- `derived/swing_modeling/` and `reports/swing_modeling/` — output directories
- `derived/state/latest/campaign_state.json` — swing_model_summary block added

#### Validation Results
- 26/26 assertions passed
- Backtest: 2 folds on synthetic data, avg F1=0.594, status=ACTIVE_VALIDATED
- IQR anomaly detection confirmed
- Sparse data → confidence floor correctly applied
- Cross-county isolation enforced (state + county filter)

---

### Entry 13 — Pre Prompt 20.8 User & Campaign Administration Layer

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-13T09:15:00-07:00 |
| **Branch** | `rollback/prompt208_pre_admin_layer` |
| **Tag** | `v_pre_prompt208_admin_layer` |
| **Reason** | User management, persistent sessions, campaign admin layer |
| **Note** | Before adding user admin UI, session manager, campaign registry, campaign admin UI, and enhanced command bar. |

#### Scope
- `engine/auth/auth_manager.py` — extended with create_user, update_user_role, disable_user, enable_user
- `engine/auth/session_manager.py` — new: persistent remembered sessions (gitignored store)
- `engine/admin/campaign_manager.py` — new: campaign registry CRUD
- `config/users_registry.json` — expanded with is_active, remember_login_allowed, full_name, timestamps
- `config/roles_permissions.yaml` — added manage_users + manage_campaigns to all 7 roles
- `config/campaign_registry.yaml` + `config/active_campaign.yaml` — new
- `ui/dashboard/user_admin_view.py` + `ui/dashboard/campaign_admin_view.py` — new admin views
- `ui/dashboard/app.py` — Remember Me login, session bootstrap, enhanced command bar
- `config/ui_pages.yaml` — added admin group (Users & Roles, Campaign Admin, Swing Modeling)
- `.gitignore` — added `data/local_sessions/`

#### Validation Results
- 41/41 assertions passed
- session_manager: create/validate/revoke/purge all correct
- auth_manager: create_user, role update, disable/enable, permissions all correct
- campaign_manager: create, set_active (single-active enforced), stage change, archive, audit log all correct
- Config file integrity: all fields present across all 4 config files

---

### Entry 14 — Pre Prompt 27: Campaign State Isolation & Archive Normalizer Integration

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-13T19:32:00-07:00 |
| **Branch** | `rollback/prompt27_pre_state_isolation` |
| **Tag** | `v_pre_prompt27_state_isolation` |
| **Reason** | Campaign state isolation + archive normalizer integration |
| **Note** | Motivated by platform audit (20260313__platform_audit): campaign_switching=0.33 (flat state path), archive normalizer MISSING flag. No new modeling features. |

#### Scope
- `engine/state/campaign_state_resolver.py` — new: central resolver for campaign-scoped state paths
- `engine/state/state_builder.py` — route writes to `derived/state/campaigns/<cid>/latest/` and history
- `engine/state/state_diff.py` + `state_validator.py` — read via resolver
- `engine/archive_builder/archive_ingestor.py` — add schema detection + hard acceptance gates + join metadata output
- `engine/archive_builder/archive_classifier.py` — add `archive_status` field (ARCHIVE_READY/REVIEW_REQUIRED/REJECTED)
- `ui/dashboard/app.py` — use resolver for state bootstrap + cache invalidation on campaign switch
- `docs/SYSTEM_TECHNICAL_MAP.md` — add campaign-scoped state + archive normalizer docs
- `data/historical_elections/archive_registry.yaml` — add normalization provenance fields

---

### Entry 15 — Pre Prompt 25C: Election Directory Predictor

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-13T18:43:00-07:00 |
| **Branch** | `rollback/prompt25C_pre_directory_predictor` |
| **Tag** | `v_pre_prompt25C_directory_predictor` |
| **Reason** | Adding deterministic election directory prediction engine |
| **Note** | Motivated by Prompt 25B discovering 0 candidate files in offline runs. Predictor generates URL path hypotheses (10 patterns × 5 years = 50 candidates), HTTP-tests them, and feeds confirmed directories to the existing page_explorer crawler. |

#### What Was Working at This Point
- `link_extractor.py` — 7-source link extraction (P25B, 58/58 validated)
- `viewer_resolver.py` — CivicEngage + ASP.NET viewer URL resolution (P25B)
- `page_explorer.py` — depth-3 recursive crawler with visited URL set (P25B)
- `page_discovery.py` — Prompt 25B scoring (SoV+0.30, Precinct+0.20, Detail+0.20, URL+0.30)
- `file_discovery.py` — 5-factor scoring (MIN_CANDIDATE_SCORE=0.50)
- `file_downloader.py` — SHA-256 dedup + page_depth + candidate_score in registry
- `archive_builder.py` — full 10-step orchestrator
- Source registry: 16 contest sources + 10 geometry sources, CA/Sonoma locked
- Platform: multi-campaign state isolation, session manager, admin layer (P27 + P20.8)

#### What This Rollback Protects Against
- `election_directory_predictor.py` introducing broken HTTP logic or cross-jurisdiction crawl
- `file_discovery.py` scoring change (0.50 → 0.60 threshold) blocking previously accepted files
- `archive_builder.py` Step 2.5 integration breaking existing Steps 3–11
- 4 new report files causing file write errors in the pipeline

#### To Restore
```bash
git checkout rollback/prompt25C_pre_directory_predictor
# or
git checkout tags/v_pre_prompt25C_directory_predictor
python scripts/tools/run_p25b_validation.py   # should still pass 58/58
```


### Entry 16 � Pre Prompt 28: Canonical Contest Data Intake Unification

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-14T08:13:18+00:00 |
| **Branch** | `rollback/prompt28_pre_contest_reset` |
| **Tag** | `v_pre_prompt28_contest_reset` |
| **Reason** | Canonical contest data intake unification + surgical purge of contest/result data |
| **Note** | This is a surgical purge of contest/result data ONLY. Geography, crosswalk, source registry, campaign config, user accounts, code, and all rollback history are preserved. The audit (P28 pre-audit) identified 7 failure points including FP-01 (2020 file not in pipeline votes/ tree), FP-03 (archive normalized with synthetic data), FP-06 (slug mismatch on 2024 real data). This repair creates one canonical contest data path: `data/contests/`. |

#### What Is Being Reset (contest/result data only)
- `data/elections/` � manually uploaded results dumped by Data Manager
- `data/CA/counties/Sonoma/votes/` � pipeline vote files (stubs and real)
- `data/election_archive/normalized/` and `data/election_archive/raw/`
- `derived/archive/normalized_elections.csv`, `precinct_profiles.csv`, `precinct_trends.csv`, `similar_elections.csv`
- Contest-result entries in `file_registry.json`

#### What Is Preserved
- All geometry/boundary data (MPREC/SRPREC GeoJSON, GeoPackage, Shapefile)
- All crosswalk files (6 crosswalk CSVs in `data/CA/counties/Sonoma/geography/crosswalks/`)
- Source registry (`config/source_registry/`)
- User and campaign configs (`config/users_registry.json`, `config/campaign_registry.yaml`)
- All rollback branches and tags
- All code, docs, UI

#### To Restore
```bash
git checkout rollback/prompt28_pre_contest_reset
# or
git checkout tags/v_pre_prompt28_contest_reset
```

## 2026-03-14T03:21 � pre-Prompt-29 Crosswalk Repair

- **Branch:** `rollback/prompt29_pre_crosswalk_repair`
- **Tag:** `v_pre_prompt29_crosswalk_repair`
- **Reason:** Precinct normalization and crosswalk repair (Prompt 29).
  `detect_crosswalk_columns()` was using uppercase aliases (BLOCK20, MPREC_ID)
  but all Sonoma crosswalk files use lowercase short names (block, mprec, srprec).
  Every crosswalk join was silently falling back to identity mapping.
- **Note:** This point precedes a verification audit (P29 validation run).

## 2026-03-14T04:05:38-07:00 � pre-Prompt-30 Live Verification
- **Branch:** `rollback/prompt30_pre_live_verification`
- **Tag:** `v_pre_prompt30_live_verification`
- **Reason:** Live end-to-end verification audit (Prompt 30).
- **Note:** This prompt may perform targeted debugging after observing live behavior.

## 2026-03-14T05:22:41-07:00 � pre-Prompt-31 User Guidance Layer
- **Branch:** `rollback/prompt31_pre_user_guidance`
- **Tag:** `v_pre_prompt31_user_guidance`
- **Reason:** User guidance layer, auto-pipeline detection, ops playbook, diagnostics.
- **Note:** No UI layout changes, no data deletion, observation/automation only.
