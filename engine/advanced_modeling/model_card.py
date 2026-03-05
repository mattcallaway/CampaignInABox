"""
engine/advanced_modeling/model_card.py — Prompt 10

Generates the model card for the advanced modeling engine.
Written as a markdown document explaining assumptions, limitations, and interpretation.
"""
from __future__ import annotations

import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def write_model_card(
    run_id:      str,
    contest_id:  str,
    cfg:         dict,
    scenarios_summary: dict | None = None,
    out_dir:     Path | None = None,
) -> Path:
    """
    Write the advanced modeling model card.

    Returns the path to the written model card.
    """
    curves  = cfg.get("curves",      {})
    elast   = cfg.get("elasticity",  {})
    eff     = cfg.get("effort",      {})
    sim_cfg = cfg.get("simulation",  {})
    opt     = cfg.get("optimizer",   {})

    if out_dir is None:
        out_dir = BASE_DIR / "reports" / "model_cards"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}__advanced_modeling_model_card.md"

    net_gain_str = "—"
    if scenarios_summary:
        heavy = scenarios_summary.get("heavy", {})
        net_gain_str = f"{heavy.get('mc_net_gain_mean', 0):.1f} (p10–p90: {heavy.get('risk_band','—')})"

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = f"""# Advanced Modeling Model Card
**Run ID:** `{run_id}`  
**Contest:** `{contest_id}`  
**Generated:** {ts}  
**Prompt:** 10 — Advanced Modeling Engine  

---

> ⚠️ **This is a prior-driven proof-of-concept unless calibrated with historical contests.**
> Results describe expected outcomes under assumed elasticity priors, not empirically validated coefficients.

---

## 1 — What This Model Does

The advanced modeling engine extends Campaign In A Box beyond rank-and-simulate
by modeling **how field effort translates into vote lift**.

Given:
- A precinct population (registered voters, baseline turnout, baseline support)
- A shift budget (number of canvasser shifts)
- Contact + elasticity assumptions

It produces:
- **Universe estimates** — persuasion and turnout universe sizes per precinct
- **Lift projections** — expected vote gain from field contacts
- **Optimal allocation** — greedy assignment of shifts to maximize net margin gain
- **Scenario comparisons** — baseline / lite / medium / heavy / user budget

---

## 2 — What Data It Uses

| Source | Used For |
|---|---|
| `derived/precinct_models/` | Baseline registered, turnout_pct, support_pct |
| `derived/ops/.../regions.csv` | Region aggregates for allocation |
| `derived/turfs/.../top_N_walk_turfs.csv` | Turf aggregates |
| `config/advanced_modeling.yaml` | All priors and assumptions |

**No voter file is required.** All estimates are aggregate-level.

---

## 3 — Assumptions

### Contact Assumptions
| Parameter | Value | Source |
|---|---|---|
| Doors per shift | {eff.get('doors_per_shift', 100)} | Assumed |
| Contact rate | {eff.get('contact_rate', 0.18):.0%} | Green & Gerber (2015), adjusted |
| Persuasion contact rate | {eff.get('persuasion_contact_rate', 0.55):.0%} | Assumed |
| Turnout contact rate | {eff.get('turnout_contact_rate', 0.45):.0%} | Assumed |

### Elasticity Priors
| Parameter | Mean | SD |
|---|---|---|
| Persuasion lift / contact | {elast.get('persuasion_lift_per_contact_mean', 0.006)} | {elast.get('persuasion_lift_per_contact_sd', 0.003)} |
| Turnout lift / contact | {elast.get('turnout_lift_per_contact_mean', 0.004)} | {elast.get('turnout_lift_per_contact_sd', 0.002)} |

These are **priors from academic literature**. They have not been calibrated to this contest.

### Diminishing Returns Curve
```
lift(contacts) = max_lift × (1 − exp(−k × contacts))
```
| Parameter | Turnout | Persuasion |
|---|---|---|
| max_lift | {curves.get('max_turnout_lift_pct', 0.08):.0%} | {curves.get('max_persuasion_lift_pct', 0.06):.0%} |
| k | {curves.get('k_turnout', 0.0008)} | {curves.get('k_persuasion', 0.0010)} |

Monte Carlo: {sim_cfg.get('monte_carlo_iterations', 2000)} iterations, seed={sim_cfg.get('seed', 1337)}

---

## 4 — What This Model Cannot Do

- ❌ Target individual voters (no voter file integration)
- ❌ Account for opponent field programs
- ❌ Model media or digital advertising effects
- ❌ Account for weather, ballot access, or GOTV timing
- ❌ Capture geographic clustering of voter behavior

---

## 5 — Validation Status

**Status: PRIORS ONLY (uncalibrated)**

To calibrate this model, provide historical field experiment results or
matched contest results from similar contests. See `config/advanced_modeling.yaml`
for the parameters that should be updated with calibrated values.

---

## 6 — Known Risks

| Risk | Description | Mitigation |
|---|---|---|
| Overconfidence | Point estimates look precise but uncertainty is high | Use p10–p90 band, not the mean |
| Contact rate uncertainty | 18% contact rate is an average; varies enormously by neighborhood | Treat all outputs as ordinal, not cardinal |
| Baseline data quality | Registered=0 in 10 precincts (data quality issue in source) | Those precincts produce 0 lift and are correct to exclude |
| Prior mismatch | Literature priors may not reflect local conditions | Recalibrate with local data before use in resource decisions |

---

## 7 — How to Interpret Results

| Output | Meaning |
|---|---|
| `expected_net_gain_votes` | Deterministic estimate of incremental net votes from field program |
| `mc_net_gain_p10` | Pessimistic (10th percentile) outcome under prior uncertainty |
| `mc_net_gain_p90` | Optimistic (90th percentile) outcome under prior uncertainty |
| `risk_band` | The range within which 80% of Monte Carlo outcomes fall |
| `shifts_assigned` | Optimal canvasser shifts per region under given budget |

**Do not use absolute numbers for public commitments.** Use the relative ordering
of precincts/regions (which are more robust than absolute estimates).

---

## 8 — Heavy Scenario Expected Outcome

Under the heavy scenario ({opt.get('max_total_shifts', 100)} shifts):  
**Expected net gain: {net_gain_str}**

---

*Model card auto-generated by Campaign In A Box — engine/advanced_modeling/model_card.py*
"""

    out_path.write_text(md, encoding="utf-8")
    return out_path
