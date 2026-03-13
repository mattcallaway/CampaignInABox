# Data Pipeline Audit
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

---

## Pipeline Map

```
Raw data (data/)
  ├── voter_parser.py      →  derived/voter_models/
  ├── archive_ingest.py    →  derived/archive/
  ├── data_intake_manager  →  data/<canonical path>
  └── intelligence/        →  derived/intelligence/
          ↓
precinct_voter_metrics.py  →  derived/voter_models/
universe_builder.py        →  derived/voter_universes/
targeting_quadrants.py     →  derived/voter_segments/
          ↓
scenarios.py + lift_models →  derived/advanced_modeling/
campaign_strategy_ai.py    →  derived/strategy/
          ↓
state_builder.py           →  derived/state/latest/
          ↓
UI (data_loader.py reads state + derived CSVs)
```

---

## Findings

### 🔴 CRITICAL

| ID | Finding | File | Line | Evidence |
|----|---------|------|------|----------|
| P-01 | `data/election_archive/` has 0 real files — archive ingest falls back to mock data silently. Historical models trained on synthetic data | `archive_ingest.py:~45` | Mock generation path triggered when no real files found |
| P-02 | Strategy engine searches `derived/scenario_forecasts/` for simulation inputs — directory does not exist in derived inventory; uses path that may never resolve | `campaign_strategy_ai.py:80` | `_find_latest(BASE_DIR / "derived" / "scenario_forecasts", ...)` |
| P-03 | State builder expects `county` and `state` values from campaign_setup section but state snapshot shows these as empty strings | `state_builder.py`, `system_inventory.md:316-317` | `"county": ""`, `"state": ""` in state snapshot |
| P-04 | File registry snapshot shows `"File registry not yet generated"` — `data_intake_manager.py` registry not being run as part of normal pipeline | `system_inventory.md:321` | No registry data present |

### 🟡 HIGH

| ID | Finding | File | Line | Evidence |
|----|---------|------|------|----------|
| P-05 | `_assign_contacts_to_precincts()` falls back to spreading total contacts proportionally when `region_id`/`turf_id` join key missing — silently produces inaccurate contact allocation | `scenarios.py:179-190` | Fallback logic with no warning log |
| P-06 | `_find_latest()` pattern used to find newest CSV by `st.mtime` — in concurrent pipeline runs, the wrong run's data could be read | `campaign_strategy_ai.py:56-63`, `forecast_updater.py:35-40` | No run_id validation in mtime-based selection |
| P-07 | No schema validation before writing derived CSVs — a missing column silently propagates NaN through the pipeline | `state_builder.py:170-180` | `fillna(0)` used defensively but no mandatory column check |
| P-08 | `_c()` helper in `apply_lifts()` returns `pd.Series(0.0)` silently when column missing — turnout or support of 0 corrupts all downstream vote math | `lift_models.py:101-105` | `_c(\"registered\")` returns zeros with no warning |
| P-09 | Archive ingest produces `normalized_elections.csv` but there is no step that merges historical trend data into the current precinct model before lift calculation | `lift_models.py:118-123` | `t_trend = _c("historical_turnout_trend")` — column only present if manually joined |

### 🟢 LOW

| ID | Finding | File | Line | Evidence |
|----|---------|------|------|----------|
| P-10 | All file reads use `encoding="utf-8"` but no explicit BOM handling — Windows voter file exports often include BOM | `voter_parser.py` (pattern) | Potential silent column name corruption on BOM-encoded files |
| P-11 | `data/voters/` shows 2 files — likely mock/test data; voter parser would run against these, producing real-looking model outputs from fake data | `system_inventory.md:276` | 2 files in voters dir |
| P-12 | No checksums or content hashes on derived outputs — cannot audit whether a derived CSV was produced from the correct input version | Entire derived/ path | No manifest or hash file found |

---

## Schema Mismatch Risks

| Join | Left Key | Right Key | Risk |
|------|---------|---------|------|
| Precinct model → Voter universe | `precinct_id` | `precinct_id` | Medium — canonical PCT format must match |
| Allocation → Precinct universe | `entity_id` / `region_id` | `region_id` | High — fallback if no match |
| Archive trends → Precinct model | `precinct_id` | `precinct_id` | High — merge not done automatically |
| War room runtime → Strategy baseline | vote_path columns | static key names | Low — uses `vp_base.get()` with defaults |

---

## Recommendations

1. **Guard `_find_latest()` with run_id prefix filter** to prevent cross-run contamination.
2. **Add explicit schema validation** (required columns check) at derived CSV write time.
3. **Wire historical trends** from `derived/archive/precinct_trends.csv` into precinct model before lift calculation.
4. **Log a WARNING** in `_c()` and `_assign_contacts_to_precincts()` when key column is missing.
5. **Populate `county` and `state`** fields in campaign_config.yaml and propagate through state builder.
