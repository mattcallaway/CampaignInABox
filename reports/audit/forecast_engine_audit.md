# Forecast Engine Audit
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

---

## 1. Precinct Aggregation Math

**File:** `engine/advanced_modeling/lift_models.py`, `engine/advanced_modeling/scenarios.py`

Precinct-level projections correctly aggregated:
```
total_net_gain = sum(precinct.net_margin_gain)
total_added_yes = sum(precinct.expected_added_votes_yes)
```

✅ No double-counting across precincts in summation.
✅ Voter counts properly bounded to [0, registered].

### Risk: Missing Precincts Not Flagged

When `_assign_contacts_to_precincts()` cannot join alloc_df to universe_df via `region_id`, it silently falls back to spreading contacts uniformly. Precincts that receive zero contacts contribute zero net gain — which is correct — but the lack of logging prevents auditors from knowing how many precincts were dropped from the join.

**Severity:** MEDIUM | `scenarios.py:164-190`

---

## 2. Turnout Weighting

Turnout weighting is implicit in the formula:
```
projected_yes = registered * turnout_new * support_new
```

Each precinct's weight is its registered voter count × projected turnout. This is correct — larger precincts contribute proportionally more votes. No explicit turnout weight column is needed.

✅ PASS — weighting is mathematically embedded.

---

## 3. Swing Modeling

Swing is not explicitly modeled as a variable in the current system. The system uses:
- Historical trend (`t_trend`, `s_trend`) — linear extrapolation per precinct
- Lift from field contacts — applied on top of baseline

There is no macro-environment swing factor (e.g., national environment shift, top-of-ticket effect). This is a **modeling gap**, not a math error.

**Gap FE-01:** No partisan swing variable incorporated. National/statewide environment shifts that affect all precincts uniformly are not modeled. This is appropriate for local ballot measures but is a weakness for partisan general elections.

---

## 4. Scenario Logic

Standard scenarios defined in `config/forecast_scenarios.yaml`:
- baseline (0 shifts)
- lite (20 shifts)
- medium (50 shifts)
- heavy (100 shifts)
- user_budget (optional)

**Evaluation:**

| Check | Result |
|-------|--------|
| Scenarios cover low/high range | ✅ PASS |
| Baseline explicitly modeled | ✅ PASS |
| User budget scenario supported | ✅ PASS |
| Scenarios saved as separate rows | ✅ PASS |
| Monte Carlo run for each scenario | ✅ PASS |

**Gap FE-02:** `scenario_rows[-2]` in the log statement at `scenarios.py:147` is a fragile index — if scenarios are fewer than 2, this throws an IndexError. Minor bug.

---

## 5. Confidence Interval Logic

P10/P90 intervals are computed from 2,000 Monte Carlo iterations sampling `max_lift` priors:

```python
arr = np.array(results)
return {
    "net_gain_p10": float(np.percentile(arr, 10)),
    "net_gain_p90": float(np.percentile(arr, 90)),
}
```

✅ Correct — percentile computation is appropriate for non-parametric CI.
✅ 2,000 iterations is sufficient for stable P10/P90.

**Gap FE-03:** Only `net_margin_gain` is Monte Carlo'd. `expected_added_votes_yes` (absolute votes) is not. Users only see MC uncertainty on net margin, not on absolute vote projection.

---

## 6. Historical Similarity Weighting

`engine/archive/election_similarity.py` produces `similar_elections.csv` but the results are **displayed in the UI only** — they are not incorporated as prior weights into the forecast. This is a missed modeling opportunity.

**Gap FE-04:** Similar historical elections are identified but not used to calibrate priors. The historical similarity engine is currently informational only.

---

## Synthetic Test

A synthetic validation was performed by reasoning through the formula chain with sample inputs:

| Input | Value |
|-------|-------|
| Precinct registered | 5,000 |
| Baseline turnout | 0.55 |
| Baseline support | 0.51 |
| Contacts | 500 |

Expected Math:
```
t_lift = 0.08 * (1 - exp(-0.0008 * 500)) = 0.08 * 0.329 = 0.026
p_lift = 0.06 * (1 - exp(-0.0010 * 500)) = 0.06 * 0.394 = 0.024
turnout_new = 0.55 + 0.026 = 0.576
support_new = 0.51 + 0.024 = 0.534
projected_yes = 5000 * 0.576 * 0.534 = 1,538 votes
baseline_yes  = 5000 * 0.55 * 0.51  = 1,403 votes
added_yes     = 135 votes
```

✅ Formula chain produces sensible results for this input set.
