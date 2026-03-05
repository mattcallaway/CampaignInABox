"""
engine/advanced_modeling/scenarios.py — Prompt 10

Generates standard scenarios + advanced Monte Carlo simulation.

Scenarios:
  baseline (0 shifts), lite (20), medium (50), heavy (100), user_budget (N)

For each scenario:
  - Deterministic projection using lift models
  - Monte Carlo projection with uncertainty on priors

Outputs:
  <RUN_ID>__advanced_scenarios.csv
  <RUN_ID>__advanced_simulation_summary.csv
"""
from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from engine.advanced_modeling.lift_models import apply_lifts, apply_lifts_mc
from engine.advanced_modeling.optimizer import optimize_allocation

log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def run_advanced_scenarios(
    universe_df: pd.DataFrame,
    entities_df: pd.DataFrame,
    cfg: dict,
    run_id: str,
    contest_id: str,
    user_budget: Optional[int] = None,
    out_dir: Optional[Path] = None,
    entity_type: str = "region",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run all standard scenarios + Monte Carlo projected outcomes.

    Parameters
    ----------
    universe_df  : precinct-level DataFrame with universe estimates
    entities_df  : region/turf-level aggregate DataFrame
    cfg          : advanced_modeling config dict
    run_id       : run identifier
    contest_id   : contest identifier (used for output paths)
    user_budget  : override max_total_shifts for 'user_budget' scenario

    Returns
    -------
    (scenarios_df, simulation_summary_df)
    """
    eff    = cfg.get("effort",    {})
    sim    = cfg.get("simulation",{})
    scen   = cfg.get("scenarios", {})

    doors_shift  = float(eff.get("doors_per_shift",   100))
    contact_rate = float(eff.get("contact_rate",       0.18))
    contacts_per_shift = doors_shift * contact_rate

    n_mc   = int(sim.get("monte_carlo_iterations", 2000))
    seed   = int(sim.get("seed",                   1337))
    pd_dir = int(cfg.get("persuasion_direction",   1))

    # Standard scenario shift budgets
    scenario_budgets: dict[str, int] = {
        "baseline":    int(scen.get("baseline", 0)),
        "lite":        int(scen.get("lite",     20)),
        "medium":      int(scen.get("medium",   50)),
        "heavy":       int(scen.get("heavy",    100)),
    }
    if user_budget is not None:
        scenario_budgets["user_budget"] = int(user_budget)

    if out_dir is None:
        out_dir = BASE_DIR / "derived" / "advanced_modeling" / contest_id
    out_dir.mkdir(parents=True, exist_ok=True)

    scenario_rows = []
    mc_rows       = []

    for scen_name, max_shifts in scenario_budgets.items():
        log.info(f"[SCENARIOS] Running scenario={scen_name} max_shifts={max_shifts}")

        # ── Run optimizer for this budget ─────────────────────────────────────
        alloc_df, _ = optimize_allocation(
            entities_df, cfg, run_id, contest_id,
            max_total_shifts=max_shifts,
            entity_type=entity_type,
            out_dir=None,   # don't double-write from in optimizer
        )

        # Build contacts column: precinct → entity lookup
        uni_with_contacts = _assign_contacts_to_precincts(
            universe_df, alloc_df, entity_type, contacts_per_shift,
        )

        # ── Deterministic projection ──────────────────────────────────────────
        lifted = apply_lifts(uni_with_contacts, "contacts_estimated", cfg, pd_dir)

        total_shifts = alloc_df["shifts_assigned"].sum()
        total_contacts = alloc_df["contacts_estimated"].sum()
        net_gain_det  = lifted["net_margin_gain"].sum()
        added_yes_det = lifted["expected_added_votes_yes"].sum()

        scenario_rows.append({
            "scenario":               scen_name,
            "max_shifts_budget":      max_shifts,
            "shifts_assigned":        int(total_shifts),
            "contacts_estimated":     round(total_contacts, 1),
            "expected_net_gain_votes": round(max(0.0, net_gain_det), 2),
            "expected_added_yes_votes": round(max(0.0, added_yes_det), 2),
            "generated_at":           datetime.datetime.now().isoformat(),
        })

        # ── Monte Carlo ───────────────────────────────────────────────────────
        mc_stats = apply_lifts_mc(
            uni_with_contacts, "contacts_estimated",
            cfg, n_mc, seed + hash(scen_name) % 9999, pd_dir,
        )
        mc_rows.append({
            "scenario":       scen_name,
            "max_shifts_budget": max_shifts,
            "det_net_gain":   round(max(0.0, net_gain_det), 2),
            "mc_net_gain_mean": round(max(0.0, mc_stats["net_gain_mean"]), 2),
            "mc_net_gain_p10":  round(max(0.0, mc_stats["net_gain_p10"]),  2),
            "mc_net_gain_p90":  round(mc_stats["net_gain_p90"],            2),
            "mc_net_gain_sd":   round(mc_stats["net_gain_sd"],             4),
            "risk_band":        f"{mc_stats['net_gain_p10']:.1f}–{mc_stats['net_gain_p90']:.1f}",
        })

    scenarios_df = pd.DataFrame(scenario_rows)
    mc_df        = pd.DataFrame(mc_rows)

    scenarios_df.to_csv(out_dir / f"{run_id}__advanced_scenarios.csv",          index=False)
    mc_df.to_csv(out_dir        / f"{run_id}__advanced_simulation_summary.csv",  index=False)

    log.info(
        f"[SCENARIOS] {len(scenario_budgets)} scenarios run | "
        f"heavy net_gain={scenario_rows[-2]['expected_net_gain_votes'] if len(scenario_rows)>=2 else '?'}"
    )
    return scenarios_df, mc_df


def _assign_contacts_to_precincts(
    universe_df: pd.DataFrame,
    alloc_df: pd.DataFrame,
    entity_type: str,
    contacts_per_shift: float,
) -> pd.DataFrame:
    """
    Join allocation back to precinct universe to get per-precinct contacts.
    Falls back to spreading contacts evenly if no join key found.
    """
    df = universe_df.copy()

    if alloc_df.empty or "entity_id" not in alloc_df.columns:
        # No allocation — zero contacts everywhere
        df["contacts_estimated"] = 0.0
        return df

    # Try to join via region_id or turf_id
    join_col = "region_id" if entity_type == "region" else "turf_id"

    if join_col in df.columns:
        contact_map = alloc_df.set_index("entity_id")["contacts_estimated"].to_dict()
        # Divide contacts evenly across precincts within entity
        entity_sizes = df.groupby(join_col)[join_col].transform("count").clip(lower=1)
        df["contacts_estimated"] = (
            df[join_col].map(contact_map).fillna(0) / entity_sizes
        )
    else:
        # Fallback: spread total contacts proportional to registered voters
        total_contacts = alloc_df["contacts_estimated"].sum()
        reg_col = next((c for c in ["registered", "registered_total"] if c in df.columns), None)
        if reg_col:
            total_reg = df[reg_col].sum()
            if total_reg > 0:
                df["contacts_estimated"] = total_contacts * df[reg_col] / total_reg
            else:
                df["contacts_estimated"] = total_contacts / max(1, len(df))
        else:
            df["contacts_estimated"] = total_contacts / max(1, len(df))

    return df
