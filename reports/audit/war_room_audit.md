# War Room System Audit
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

---

## 1. Runtime Data Ingestion

**File:** `engine/war_room/runtime_loader.py`

The war room loads live field/volunteer data from `data/campaign_runtime/`. The system inventory shows 4 files present, which means runtime data flow has been exercised.

| Component | Status |
|-----------|--------|
| Field results loader | ✅ Present |
| Volunteer log loader | ✅ Present |
| Contact results loader | ✅ Present |
| `derived/war_room/` output | ✅ 3 files present |

---

## 2. Forecast Update Logic

**File:** `engine/war_room/forecast_updater.py:43-190`

The forecast update computes runtime-adjusted contact rates and volunteer capacity:

```python
contact_rate_current = rt.get("observed_contact_rate", contact_rate_base)
doors_pers_current   = doors_needed(pers_votes_base, persuasion_rate_current, contact_rate_current)
```

### Findings

| Check | Result | Notes |
|-------|--------|-------|
| Runtime overrides model assumptions | ✅ | REAL data preferred over ESTIMATED |
| `turnout_lift_current` hardcoded to base | ⚠️ WR-01 | Line 74: `turnout_lift_current = turnout_lift_base` — never updated from runtime |
| Weeks computed from election date | ✅ | Falls back to 12 weeks if date parse fails |
| Division-by-zero protection | ✅ | `if pers_rate * contact_rate > 0` guard |
| Missing runtime graceful fallback | ✅ | Uses config baseline when runtime field missing |

**WR-01 (MEDIUM):** `turnout_lift_current` is never updated from runtime observations — it always equals the baseline. If the campaign observes a different GOTV conversion rate in the field, that is not reflected in forecast updates.

---

## 3. Data Request System

**File:** `engine/war_room/data_requests.py`

The data request system tracks what data is needed vs. present. No critical bugs identified in the system structure. Data presence flags drive the `presence` dict used in forecast_updater.

---

## 4. Status Engine

**File:** `engine/war_room/status_engine.py`

Status engine generates war room health status based on runtime data presence and forecast comparison. Output written to `derived/war_room/`.

**WR-02 (LOW):** Status outputs are written to `derived/war_room/` — only 3 files present. Status engine likely runs in full pipeline mode only; not continuously updated unless pipeline is re-run.

---

## 5. Resilience to Missing Data

The war room is designed to run with ESTIMATED data when REAL data is unavailable:

```python
contact_rate_current = rt.get("observed_contact_rate", contact_rate_base)
volunteers_current   = rt.get("avg_volunteers_per_week", volunteers_base)
```

✅ All runtime lookups use `.get(key, default)` pattern — safe for missing keys.
✅ `presence` dict flags which data sources are real vs. estimated.

**WR-03 (LOW):** The war room view in the UI renders the same way regardless of whether REAL or ESTIMATED data is being shown. A stronger visual indicator when operating in ESTIMATED-only mode would reduce analyst confusion.

---

## Summary

| Area | Status |
|------|--------|
| Runtime data ingestion | ✅ Functioning |
| Forecast update math | ⚠️ GOTV lift not runtime-updated |
| Data request tracking | ✅ Functioning |
| Missing data resilience | ✅ Good fallback patterns |
| UI integration | ⚠️ Insufficient ESTIMATED mode indicator |
