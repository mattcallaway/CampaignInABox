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
