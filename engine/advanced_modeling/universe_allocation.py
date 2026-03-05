"""
engine/advanced_modeling/universe_allocation.py — Prompt 10

Estimates persuasion and turnout universe sizes at the precinct level
using only aggregate data (no voter file required).

Formula (from spec):
  persuasion_universe = ballots_cast * (1 - |0.5 - support_pct|*2) * 0.6
  turnout_universe    = max(0, registered - ballots_cast)

Both are clamped to [0, registered].
"""
from __future__ import annotations

import datetime
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def estimate_universes(
    precinct_model: pd.DataFrame,
    run_id: str,
    contest_id: str,
    out_dir: Path | None = None,
) -> pd.DataFrame:
    """
    Estimate persuasion + turnout universe sizes per precinct.

    Parameters
    ----------
    precinct_model : DataFrame with canonical columns
    run_id         : run identifier
    contest_id     : contest identifier (used for output path)
    out_dir        : override output directory

    Returns
    -------
    DataFrame with precinct_id + universe columns
    """
    if precinct_model.empty:
        log.warning("[UNIVERSE_ALLOC] precinct_model is empty — returning stub")
        return pd.DataFrame(columns=[
            "canonical_precinct_id",
            "registered", "ballots_cast",
            "persuasion_universe_size", "turnout_universe_size",
        ])

    df = precinct_model.copy()

    # Resolve column names gracefully
    def _col(name: str, *alts: str) -> str | None:
        for c in (name, *alts):
            if c in df.columns:
                return c
        return None

    reg_col     = _col("registered")
    ballots_col = _col("ballots_cast", "BallotsCast")
    sup_col     = _col("support_pct", "SupportPct")

    # Fill missing columns with zeros
    reg     = df[reg_col].fillna(0).clip(lower=0)     if reg_col     else pd.Series(0, index=df.index)
    ballots = df[ballots_col].fillna(0).clip(lower=0) if ballots_col else pd.Series(0, index=df.index)
    support = df[sup_col].fillna(0.5).clip(0, 1)      if sup_col     else pd.Series(0.5, index=df.index)

    # Persuasion universe: highest near 50/50 splits, near zero at 0% or 100%
    swing_factor = 1.0 - (support - 0.5).abs() * 2.0
    persuasion_universe = (ballots * swing_factor * 0.6).clip(lower=0)
    persuasion_universe = persuasion_universe.where(persuasion_universe <= reg, reg)

    # Turnout universe: unregistered-equivalent (people who didn't vote)
    turnout_universe = (reg - ballots).clip(lower=0)

    pid_col = _col("canonical_precinct_id", "precinct_id") or df.columns[0]

    result = pd.DataFrame({
        "canonical_precinct_id":   df[pid_col],
        "registered":              reg,
        "ballots_cast":            ballots,
        "support_pct":             support,
        "persuasion_universe_size": persuasion_universe.round(1),
        "turnout_universe_size":    turnout_universe.round(1),
        "swing_factor":             swing_factor.round(4),
    })

    # Write artifact
    if out_dir is None:
        out_dir = BASE_DIR / "derived" / "advanced_modeling" / contest_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}__precinct_universe_estimates.csv"
    result.to_csv(out_path, index=False)
    log.info(f"[UNIVERSE_ALLOC] Written {len(result)} rows → {out_path.name}")

    return result
