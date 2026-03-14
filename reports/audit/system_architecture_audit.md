# System Architecture Audit
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

---

## 1. Architecture Overview

Campaign In A Box follows a **layered, file-mediated pipeline architecture**:

```
┌─────────────────────────────────────────────────────────────────┐
│  UI Layer (Streamlit)                                           │
│  ui/dashboard/app.py  →  *_view.py pages                       │
└──────────────────┬──────────────────────────────────────────────┘
                   │ reads derived/ + passes data dict
┌──────────────────▼──────────────────────────────────────────────┐
│  Data Loader / State Layer                                      │
│  ui/dashboard/data_loader.py                                    │
│  engine/state/state_builder.py                                  │
└──────────────────┬──────────────────────────────────────────────┘
                   │ reads derived/ CSV + JSON outputs
┌──────────────────▼──────────────────────────────────────────────┐
│  Engine Layer (20 subsystems)                                   │
│  archive │ calibration │ strategy │ advanced_modeling           │
│  state   │ voters      │ war_room │ intelligence │ geo          │
│  integrity │ performance │ provenance │ audit                   │
└──────────────────┬──────────────────────────────────────────────┘
                   │ writes to
┌──────────────────▼──────────────────────────────────────────────┐
│  Derived Outputs (derived/)                                     │
│  models/ │ state/ │ archive/ │ strategy/ │ simulation/         │
│  forecasts/ │ war_room/ │ advanced_modeling/ │ calibration/     │
└──────────────────┬──────────────────────────────────────────────┘
                   │ sources from
┌──────────────────▼──────────────────────────────────────────────┐
│  Data Layer (data/)                                             │
│  elections/ │ voters/ │ intelligence/ │ campaign_runtime/       │
│  election_archive/ (MISSING — no raw historical files)          │
└─────────────────────────────────────────────────────────────────┘
```

**Configuration System:** `config/` — 20 YAML/JSON files. All modules load config at startup; no hot-reload.

**Deployment:** `deployment/` — Docker, bash/PS1 installers, run scripts.

---

## 2. Module Dependency Tree

| Subsystem | Depends On | Consumers |
|-----------|-----------|-----------|
| `engine/archive` | pandas, scikit-learn, joblib, numpy | `state_builder`, `lift_models` |
| `engine/advanced_modeling` | numpy, pandas, scipy | `scenarios.py` calls `lift_models`, `optimizer` |
| `engine/strategy` | pandas, yaml, engine/advanced_modeling | UI strategy_view |
| `engine/calibration` | pandas, yaml, sklearn | state_builder, strategy_ai |
| `engine/state` | pandas, yaml, json, all engine outputs | UI data_loader |
| `engine/voters` | pandas, numpy, sklearn | strategy_ai, state_builder |
| `engine/war_room` | pandas, engine/strategy (vote_path) | UI war_room_view |
| `engine/intelligence` | pandas, requests (optional) | state_builder |
| `engine/integrity` | pandas | data_intake |
| `engine/auth` | json | app.py |
| `engine/geo` | geopandas, shapely | map_view |
| `engine/data_intake` | pandas, shutil | data_manager_view |
| `engine/performance` | pandas | state_builder |
| `engine/provenance` | json | state_builder |
| `engine/workflow` | json | team_view |

---

## 3. Structural Risk Flags

### 🔴 CRITICAL

| ID | Finding | Location | Evidence |
|----|---------|----------|----------|
| A-01 | `_g()` helper duplicated in 3+ engine files — divergent behavior risk | `campaign_strategy_ai.py:44`, `forecast_updater.py:27` | Nested dict accessor reinvented in each file |
| A-02 | `_find_latest()` / `_find_latest_csv()` pattern duplicated across 5+ files | `strategy_ai.py:56`, `forecast_updater.py:35` | Each caller reads "latest" file by mtime; no canonical accessor |
| A-03 | `engine/archive/lift_models.py` does not exist — import would fail if referenced | Scanned repo | No such file found |

### 🟡 HIGH

| ID | Finding | Location | Evidence |
|----|---------|----------|----------|
| A-04 | State builder (~614 lines) is monolithic — handles ingestion, validation, aggregation, write in one `build_campaign_state()` function | `engine/state/state_builder.py` | Single function, no separation of concerns |
| A-05 | `campaign_strategy_ai.py` is 548 lines doing vote path, budget alloc, field strategy, risk analysis — should be 4 modules | `engine/strategy/campaign_strategy_ai.py` | All strategy concerns in one file |
| A-06 | 18 `tmp_patch_*.py` files at root — leftover from development; create confusion and cannot be run safely in prod | Root directory | `tmp_patch_app.py`, `tmp_patch_dm.py`, etc. |
| A-07 | `data/election_archive/` path exists per config but contains 0 files — historical archive is mock-only | `system_inventory.md:275` | `data/election_archive: MISSING — 0 files` |

### 🟢 LOW

| ID | Finding | Location | Evidence |
|----|---------|----------|----------|
| A-08 | No formal inter-module API — all integration via CSV/JSON files on disk | All engine modules | Derived/ directories as the "bus" |
| A-09 | `BASE_DIR` computed from `Path(__file__)` in every file — fragile if run from unexpected cwd | Multiple `__init__`-style headers | `scenarios.py:31`, `strategy_ai.py:24` |
| A-10 | `archive/` top-level directory at root (not under `engine/` or `data/`) — ambiguous purpose | Root listing | Listed alongside `data/`, `engine/`, `scripts/` |

---

## 4. Layer Separation Evaluation

| Concern | Status | Notes |
|---------|--------|-------|
| UI/Engine boundary | ✅ Mostly clean | Views call engine only via `data_loader`; a few views import engine directly |
| Engine/Data boundary | ✅ Clean | Engine writes to `derived/`; UI reads from same |
| Config isolation | ✅ Clean | All config in `config/` dir |
| Secrets isolation | ✅ Clean | No secrets in codebase; .gitignore protects data |
| ML model boundary | ⚠️ Partial | `train_*` scripts in `engine/archive/` — training and inference in same package |

---

## 5. Refactor Recommendations

1. **Extract shared utilities:** Create `engine/utils/helpers.py` with `_g()`, `_find_latest()`, `_clamp()` shared by all subsystems.
2. **Split `campaign_strategy_ai.py`** into `vote_path.py`, `budget_allocator.py`, `field_strategy.py`, `risk_analyzer.py`.
3. **Split `state_builder.py`** into reader modules (one per data domain) aggregated by a thin orchestration layer.
4. **Delete `tmp_patch_*.py` files** from root — move any reusable logic into proper modules.
5. **Introduce a DataLoader abstraction** — replace repeated `_find_latest()` with a canonical `DerivedDataReader` class.
