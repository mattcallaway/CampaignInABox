# UI ↔ Engine Integration Audit
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

---

## 1. Page-to-Engine Mapping

| UI Page | Expected Engine Source | Integration Status | Issues |
|---------|----------------------|--------------------|--------|
| Overview | `state_snapshot`, `strategy_meta` | ✅ Correct | `recommended_strategy` type mismatch (str vs dict) — fixed |
| War Room | `war_room/forecast_updater.py` | ✅ Correct | N/A |
| Jurisdiction Summary | `state` → campaign_setup | ✅ Correct | county/state fields empty |
| Team Activity | `workflow/task_manager.py` | ✅ Correct | N/A |
| Campaign Setup | `config/campaign_config.yaml` | ✅ Correct | N/A |
| Upload Contest Data | `data_intake_manager.py` | ⚠️ Fixed | `_DESTINATION_RULES` was not a class attr — fixed this session |
| Political Intelligence | `intelligence/` modules | ✅ Correct | N/A |
| Voter Intelligence | `voters/persuasion_model.py`, `voters/turnout_propensity.py` | ✅ Correct | N/A |
| Data Manager | `data_intake_manager.py` | ✅ Fixed | Import fixed this session |
| Data Explorer | `data_loader.py` | ✅ Correct | N/A |
| Precinct Map | `geo/` + derived boundary | ✅ Correct | N/A |
| Targeting | `voters/targeting_quadrants.py` | ✅ Correct | N/A |
| Strategy | `strategy/campaign_strategy_ai.py` | ✅ Correct | N/A |
| Simulations | `advanced_modeling/scenarios.py` | ✅ Correct | N/A |
| Historical Archive | `archive/` + state.archive_summary | ✅ Correct | New page added this session |
| Advanced Modeling | `advanced_modeling/` | ✅ Correct | N/A |
| Calibration | `calibration/model_calibrator.py` | ✅ Correct | N/A |
| Diagnostics | Various engine status | ✅ Correct | N/A |

---

## 2. Data Refresh Cycle

The dashboard uses `@st.cache_data(ttl=120)` — 2-minute cache on the data loader.

```python
@st.cache_data(ttl=120, show_spinner="Loading campaign data…")
def get_data() -> dict:
    return load_all()
```

✅ Cache invalidation via "Refresh Data" button (`st.cache_data.clear()`).
⚠️ **UI-01:** The 2-minute TTL means live pipeline updates won't show in the dashboard for up to 2 minutes. For war room use, this lag could be operationally significant.

---

## 3. State Persistence

State written to `derived/state/latest/` by `state_builder.py`. UI reads via `data_loader.py`. This pattern correctly decouples the engine from the UI.

✅ State persists across browser refreshes.
✅ Multiple users see consistent state (same file).

**UI-02 (LOW):** No per-user state isolation. If two users change settings simultaneously, one can overwrite the other's session state.

---

## 4. Broken Buttons / Dead Panels

| Issue | Location | Evidence |
|-------|---------|----------|
| Strategy `recommended_strategy` type error (str vs dict) | `layout.py:99` | Fixed this session; was causing Overview crash |
| `_DESTINATION_RULES` AttributeError | `data_manager_view.py:106` | Fixed this session |
| `archive_view.py` used non-existent `ui.components.cards` | `archive_view.py:8` | Fixed this session |
| Sidebar footer HTML renders inside error block | `app.py:249-259` | Code in unreachable block inside `except` after `st.stop()` |

**UI-03 (MEDIUM) — Dead Code Block:**
`app.py:249-259` — The sidebar footer markdown rendering is inside the data loading `except` block, after `st.stop()`. This code is **unreachable** and the footer never renders.

---

## 5. Deprecated Streamlit APIs

```
Please replace `use_container_width` with `width`
`use_container_width` will be removed after 2025-12-31
```

Several views use `use_container_width=True` on `st.dataframe()` calls. This produces deprecation warnings throughout the server logs.

**UI-04 (LOW):** `use_container_width=True` deprecated in installed Streamlit version. Replace with `width='stretch'` across all dashboard views.

---

## 6. Summary

| Area | Status |
|------|--------|
| Page routing | ✅ All 18 pages routed |
| Engine ↔ UI data flow | ✅ Via `data_loader` + `state_builder` |
| Cache refresh | ✅ Works, 2-min lag |
| Active bugs | 3 fixed this session; 2 remain (dead code block, deprecated API) |
| REAL/ESTIMATED indicator | ⚠️ Incomplete in war room |
