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

