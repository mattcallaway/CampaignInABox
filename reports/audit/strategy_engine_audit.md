# Strategy Engine Audit
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

---

## 1. Target Universe Selection

**File:** `engine/strategy/campaign_strategy_ai.py:67-85` — `load_campaign_inputs()`

The strategy engine loads:
- `precinct_model` from `derived/precinct_models/`
- `voter_universes` from `derived/voter_universes/`
- `targeting_quadrants` from `derived/voter_segments/`
- `tps_precinct` (turnout propensity scores) from `derived/voter_models/`
- `ps_precinct` (persuasion scores) from `derived/voter_models/`

**Findings:**

| Check | Result | Notes |
|-------|--------|-------|
| Universe data loaded | ✅ | If present |
| Prioritization uses both turnout and persuasion scores | ✅ | Quadrant-based targeting |
| Missing data fallback | ✅ | Graceful with None check |
| `simulations` search path | ❌ BROKEN | Searches `derived/scenario_forecasts/` — does not exist |

**SE-01 (HIGH):** `load_campaign_inputs()` line 80 searches `derived/scenario_forecasts/**/*.csv` — this directory does not appear in the derived inventory. The strategy engine never loads simulation data, silently ignoring it.

---

## 2. Precinct Prioritization

The targeting quadrant system assigns each precinct to:
- High Turnout + High Support → PROTECT
- Low Turnout + High Support → GOTV
- High Turnout + Low Support → PERSUADE
- Low Turnout + Low Support → DEPRIORITIZE

This is standard campaign targeting methodology.

✅ Quadrant assignment logic is correct.
⚠️ **SE-02:** Quadrant thresholds (high/low splits for turnout and support) are hardcoded or config-driven, not dynamically calibrated to the actual distribution. In low-information races, fixed thresholds may over-prioritize or under-prioritize large shares of precincts.

---

## 3. Budget Allocation Logic

Budget is allocated rule-based across field / digital / mail channels.

**SE-03 (MEDIUM):** The budget allocator in `campaign_strategy_ai.py` uses proportional rules from `config/allocation.yaml`. There is no optimization (e.g., ROI maximization). The advanced `optimizer.py` in `engine/advanced_modeling/` exists but strategy_ai.py does not call it — it has its own simpler rule-based allocator.

This means the optimizer and the strategy engine run in parallel with different answers, which can show inconsistent budget recommendations in UI.

---

## 4. Field Strategy Math

```
doors_per_week = (shifts_per_week * doors_per_shift)
contacts_per_week = doors_per_week * contact_rate
weeks_to_complete = total_doors / doors_per_week
```

✅ Math is algebraically correct.
✅ Weeks are computed from election date delta.
⚠️ **SE-04:** `election_date` parsed from config at runtime — if config has wrong date, weeks calculation may be negative or zero, causing division errors (guarded by `max(..., 1)` but produces wrong output).

---

## 5. Risk Analysis

Risk flags generated from:
- Turnout gap vs. target
- Persuasion universe size vs. needed
- Volunteer capacity vs. doors needed

✅ Risk logic is internally consistent.
✅ Risk levels (HIGH/MEDIUM/LOW) are generated.

**SE-05 (LOW):** Risk flags are narrative text strings, not structured data. Cannot be aggregated or filtered programmatically downstream.

---

## 6. Internal Consistency Check

| Metric | Vote Path | Field Strategy | Consistent? |
|--------|-----------|----------------|-------------|
| Win Number | Computed from registered × turnout × share | Referenced in field calc | ✅ Same source |
| Persuasion Votes Needed | `gap × 0.65` | Used in doors formula | ✅ Consistent |
| GOTV Votes Needed | `gap × 0.35` | Used in GOTV doors | ✅ Consistent |
| Volunteer contacts | `vols × shifts × hours × cph` | Compared to doors needed | ✅ Consistent |

Strategy recommendations are internally consistent. The main risk is the 65/35 hardcoded split (per M-02 in modeling audit).
