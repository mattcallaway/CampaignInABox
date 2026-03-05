"""
engine/advanced_modeling/optimizer.py — Prompt 10

Greedy shift allocator across regions or turfs.

Algorithm:
  1. For each entity, compute marginal_gain(next_shift) using the saturating curve
  2. Assign the next shift to the entity with the highest marginal gain
  3. Repeat until max_total_shifts exhausted

Deterministic given fixed curve params and entity list.

Outputs:
  <RUN_ID>__optimal_allocation.csv
  <RUN_ID>__allocation_curve.csv
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from engine.advanced_modeling.lift_models import turnout_lift, persuasion_lift

log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ── Marginal gain calculation ─────────────────────────────────────────────────

def _marginal_gain(
    current_contacts: float,
    additional_contacts: float,
    registered: float,
    to_base: float,
    sup_base: float,
    max_to: float, k_to: float,
    max_pe: float, k_pe: float,
    persuasion_direction: int = 1,
) -> float:
    """Net votes gained by adding additional_contacts beyond current_contacts."""
    # Before
    t_before = turnout_lift(current_contacts, max_to, k_to)
    p_before = persuasion_lift(current_contacts, max_pe, k_pe)
    to_before  = min(1.0, to_base + t_before)
    sup_before = min(1.0, max(0.0, sup_base + p_before * persuasion_direction))
    yes_before = registered * to_before * sup_before
    no_before  = registered * to_before * (1 - sup_before)

    # After
    t_after = turnout_lift(current_contacts + additional_contacts, max_to, k_to)
    p_after = persuasion_lift(current_contacts + additional_contacts, max_pe, k_pe)
    to_after  = min(1.0, to_base + t_after)
    sup_after = min(1.0, max(0.0, sup_base + p_after * persuasion_direction))
    yes_after = registered * to_after * sup_after
    no_after  = registered * to_after * (1 - sup_after)

    return (yes_after - yes_before) - (no_after - no_before)


def optimize_allocation(
    entities_df: pd.DataFrame,
    cfg: dict,
    run_id: str,
    contest_id: str,
    max_total_shifts: Optional[int] = None,
    entity_type: str = "region",
    out_dir: Optional[Path] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Greedy shift allocator.

    Parameters
    ----------
    entities_df : DataFrame with columns:
        entity_id, registered_total, avg_turnout_pct, avg_support_pct
    cfg         : advanced_modeling config dict
    max_total_shifts : override optimizer.max_total_shifts from cfg
    entity_type : 'region' | 'turf'
    out_dir     : output directory for CSV artifacts

    Returns
    -------
    (allocation_df, curve_df)
    """
    opt     = cfg.get("optimizer", {})
    eff     = cfg.get("effort",    {})
    curves  = cfg.get("curves",    {})

    max_shifts   = max_total_shifts if max_total_shifts is not None else int(opt.get("max_total_shifts", 100))
    min_per_ent  = int(opt.get("min_shifts_per_region", 0))
    max_per_ent  = int(opt.get("max_shifts_per_region", 999))
    doors_shift  = float(eff.get("doors_per_shift",     100))
    contact_rate = float(eff.get("contact_rate",         0.18))
    max_to       = float(curves.get("max_turnout_lift_pct",    0.08))
    k_to         = float(curves.get("k_turnout",                0.0008))
    max_pe       = float(curves.get("max_persuasion_lift_pct",  0.06))
    k_pe         = float(curves.get("k_persuasion",             0.0010))
    pd_dir       = int(cfg.get("persuasion_direction", 1))

    contacts_per_shift = doors_shift * contact_rate  # ~18

    if entities_df.empty:
        log.warning("[OPTIMIZER] entities_df is empty — returning stub allocation")
        empty = pd.DataFrame(columns=[
            "entity_type","entity_id","shifts_assigned","contacts_estimated",
            "turnout_lift","persuasion_lift","expected_net_gain_votes",
        ])
        return empty, pd.DataFrame(columns=["shift_number","entity_assigned","marginal_gain_votes"])

    # ── Build entity table ────────────────────────────────────────────────────
    df = entities_df.copy()

    id_col  = next((c for c in ["entity_id","region_id","turf_id"] if c in df.columns), df.columns[0])
    reg_col = next((c for c in ["registered_total","registered","sum_registered"] if c in df.columns), None)
    to_col  = next((c for c in ["avg_turnout_pct","turnout_pct","avg_support_pct"] if c in df.columns), None)
    sup_col = next((c for c in ["avg_support_pct","support_pct"] if c in df.columns), None)

    ids     = df[id_col].tolist()
    regs    = df[reg_col].fillna(0).clip(lower=0).tolist() if reg_col else [0.0]*len(df)
    to_bse  = df[to_col].fillna(0.5).clip(0,1).tolist()   if to_col  else [0.5]*len(df)
    sup_bse = df[sup_col].fillna(0.5).clip(0,1).tolist()  if sup_col else [0.5]*len(df)

    # State tracking
    n = len(ids)
    shift_counts = [min_per_ent] * n   # start at min
    used_shifts  = sum(shift_counts)
    remaining    = max_shifts - used_shifts

    curve_rows = []  # (shift_number, entity_id, marginal_gain)

    # ── Greedy loop ───────────────────────────────────────────────────────────
    for s in range(max(0, remaining)):
        # Compute marginal gain for each entity
        gains = []
        for i in range(n):
            current = shift_counts[i] * contacts_per_shift
            if shift_counts[i] >= max_per_ent:
                gains.append(-1e9)
                continue
            mg = _marginal_gain(
                current, contacts_per_shift,
                regs[i], to_bse[i], sup_bse[i],
                max_to, k_to, max_pe, k_pe, pd_dir,
            )
            gains.append(mg)

        best_idx = int(np.argmax(gains))
        shift_counts[best_idx] += 1
        curve_rows.append({
            "shift_number":      used_shifts + s + 1,
            "entity_assigned":   ids[best_idx],
            "marginal_gain_votes": round(gains[best_idx], 4),
        })

    # ── Build allocation output ───────────────────────────────────────────────
    alloc_rows = []
    for i, eid in enumerate(ids):
        shifts    = shift_counts[i]
        contacts  = shifts * contacts_per_shift
        t_lift    = turnout_lift(contacts, max_to, k_to)
        p_lift    = persuasion_lift(contacts, max_pe, k_pe)
        to_new    = min(1.0, to_bse[i] + t_lift)
        sup_new   = min(1.0, max(0.0, sup_bse[i] + p_lift * pd_dir))
        yes_old   = regs[i] * to_bse[i]  * sup_bse[i]
        yes_new   = regs[i] * to_new     * sup_new
        no_old    = regs[i] * to_bse[i]  * (1 - sup_bse[i])
        no_new    = regs[i] * to_new     * (1 - sup_new)
        net_gain  = (yes_new - yes_old) - (no_new - no_old)
        alloc_rows.append({
            "entity_type":            entity_type,
            "entity_id":              eid,
            "shifts_assigned":        shifts,
            "contacts_estimated":     round(contacts, 1),
            "turnout_lift":           round(t_lift, 6),
            "persuasion_lift":        round(p_lift, 6),
            "expected_net_gain_votes": round(max(0.0, net_gain), 2),
        })

    alloc_df = pd.DataFrame(alloc_rows)
    curve_df = pd.DataFrame(curve_rows)

    # ── Write artifacts ───────────────────────────────────────────────────────
    if out_dir is None:
        out_dir = BASE_DIR / "derived" / "advanced_modeling" / contest_id
    out_dir.mkdir(parents=True, exist_ok=True)

    alloc_df.to_csv(out_dir / f"{run_id}__optimal_allocation.csv", index=False)
    curve_df.to_csv(out_dir / f"{run_id}__allocation_curve.csv",   index=False)

    total_gain = alloc_df["expected_net_gain_votes"].sum()
    log.info(
        f"[OPTIMIZER] {sum(shift_counts)} shifts allocated across {n} {entity_type}s "
        f"| expected_net_gain={total_gain:.1f} votes | artifacts written"
    )
    return alloc_df, curve_df
