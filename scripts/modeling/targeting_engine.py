"""
scripts/modeling/targeting_engine.py

Core targeting calculations for Campaign In A Box.
Computes TurnoutOpportunity, PersuasionPotential, and TargetScore based on weights.

Prompt 8.6: dual-name compatible — works with both canonical lowercase column names
(registered, ballots_cast, yes_votes, no_votes) and legacy CamelCase names
(Registered, BallotsCast, YES, NO) without renaming or duplicating columns.
"""

import pandas as pd
import numpy as np


def _col(df: pd.DataFrame, *candidates) -> str | None:
    """Return the first column name from candidates that exists in df."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _series(df: pd.DataFrame, *candidates) -> pd.Series:
    """Return the Series for the first matching candidate column, or zeros."""
    c = _col(df, *candidates)
    if c is None:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[c], errors="coerce").fillna(0)


def compute_targeting_metrics(
    df: pd.DataFrame,
    weights: dict,
    thresholds: dict,
    contest_type: str = "ballot_measure",
    target_candidate: str = None
) -> pd.DataFrame:
    """
    Compute targeting dimensions and final composite TargetScore.

    Dimensions:
    - TurnoutOpportunity: Scale of 0-1 (High Registered, Low TurnoutPct)
    - PersuasionPotential: Scale of 0-1 (High SwingIndex or mid-range SupportPct)
    - ExpectedSupportVotes: Raw number estimate.

    Works with both canonical lowercase and legacy CamelCase column names.
    DOES NOT rename any input columns — output df preserves all input columns.
    """
    res = df.copy()

    # 1. Base Metrics — resolve column names, never rename
    reg_s   = _series(res, "registered",  "Registered",  "REG")
    balls_s = _series(res, "ballots_cast", "BallotsCast", "ballots")

    # Turnout
    turnout_s = pd.Series(0.0, index=res.index)
    mask = reg_s > 0
    turnout_s[mask] = (balls_s[mask] / reg_s[mask]).clip(0, 1)

    # Support
    yes_col = _col(res, "yes_votes", "YES", "Yes", "votes_yes")
    no_col  = _col(res, "no_votes",  "NO",  "No",  "votes_no")

    if contest_type == "ballot_measure":
        if yes_col and no_col:
            yes_s = _series(res, yes_col)
            no_s  = _series(res, no_col)
            denom = (yes_s + no_s).replace(0, 1)
            support_s = (yes_s / denom).clip(0, 1)
        else:
            support_s = pd.Series(0.5, index=res.index)
    elif target_candidate and target_candidate in res.columns:
        cand_s = _series(res, target_candidate)
        support_s = (cand_s / balls_s.replace(0, 1)).clip(0, 1)
    else:
        support_s = pd.Series(0.5, index=res.index)

    # 2. Targeting Dimensions
    reg_max = reg_s.max()
    reg_norm = (reg_s / reg_max).fillna(0) if reg_max > 0 else pd.Series(0.0, index=res.index)

    turnout_opp  = (1.0 - turnout_s) * reg_norm
    persuasion   = (1.0 - 4 * (support_s - 0.5) ** 2).clip(0, 1)
    expected_sup = (support_s * reg_s).round(1)

    # 3. TargetScore (Composite)
    w_opp  = weights.get("turnout_opportunity",  weights.get("turnout_pct", 0.33))
    w_per  = weights.get("persuasion_potential",  weights.get("yes_pct",    0.34))
    w_size = weights.get("voter_pool_size",        weights.get("registered", 0.33))

    target_score = (
        w_opp  * turnout_opp +
        w_per  * persuasion  +
        w_size * reg_norm
    ).round(6)

    # 4. Tiers
    def assign_tier(val):
        if val >= thresholds.get("tier_1_cutoff", 0.75): return 1
        if val >= thresholds.get("tier_2_cutoff", 0.50): return 2
        if val >= thresholds.get("tier_3_cutoff", 0.25): return 3
        return 4

    support_tier = support_s.apply(assign_tier)
    turnout_tier = turnout_s.apply(assign_tier)
    target_tier  = target_score.apply(assign_tier)

    walk_priority = pd.Series("Low", index=res.index)
    walk_priority[target_tier == 1] = "High"
    walk_priority[target_tier == 2] = "Medium"

    # Write results back using canonical lowercase names
    res["turnout_opportunity"]   = turnout_opp
    res["persuasion_potential"]  = persuasion
    res["ExpectedSupportVotes"]  = expected_sup   # keep legacy name, used downstream
    res["TargetScore"]           = target_score
    res["SupportTier"]           = support_tier
    res["TurnoutTier"]           = turnout_tier
    res["TargetTier"]            = target_tier
    res["WalkPriority"]          = walk_priority

    return res
