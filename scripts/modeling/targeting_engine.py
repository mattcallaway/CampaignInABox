"""
scripts/modeling/targeting_engine.py

Core targeting calculations for Campaign In A Box.
Computes TurnoutOpportunity, PersuasionPotential, and TargetScore based on weights.
"""

import pandas as pd
import numpy as np

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
    """
    res = df.copy()

    # 1. Base Metrics
    res["Registered"] = pd.to_numeric(res["Registered"], errors="coerce").fillna(0)
    res["BallotsCast"] = pd.to_numeric(res["BallotsCast"], errors="coerce").fillna(0)
    
    res["TurnoutPct"] = 0.0
    mask = res["Registered"] > 0
    res.loc[mask, "TurnoutPct"] = (res.loc[mask, "BallotsCast"] / res.loc[mask, "Registered"]).clip(0, 1)

    # Support Calculation
    if contest_type == "ballot_measure":
        yes_col = next((c for c in res.columns if c.upper() in ("YES", "YES VOTES")), None)
        no_col = next((c for c in res.columns if c.upper() in ("NO", "NO VOTES")), None)
        if yes_col and no_col:
            res["SupportPct"] = (res[yes_col] / (res[yes_col] + res[no_col]).replace(0, 1)).clip(0, 1)
        else:
            res["SupportPct"] = 0.5 # Neutral
    elif target_candidate and target_candidate in res.columns:
        res["SupportPct"] = (res[target_candidate] / res["BallotsCast"].replace(0, 1)).clip(0, 1)
    else:
        res["SupportPct"] = 0.5 # Neutral mode

    # 2. Targeting Dimensions
    # TurnoutOpportunity: High Registered but low turnout = high opportunity to gain votes by increasing turnout.
    # Inverse TurnoutPct * Relative Registration Size
    reg_norm = (res["Registered"] / res["Registered"].max()).fillna(0) if res["Registered"].max() > 0 else 0
    res["TurnoutOpportunity"] = (1.0 - res["TurnoutPct"]) * reg_norm

    # PersuasionPotential: High in "swing" areas.
    # Simple heuristic: parabala peaked at 0.5 support. 1 - 4*(Support - 0.5)^2
    res["PersuasionPotential"] = (1.0 - 4 * (res["SupportPct"] - 0.5)**2).clip(0, 1)

    # ExpectedSupportVotes: SupportPct * Registered (potential pool if 100% turnout)
    # or SupportPct * BallotsCast (actual current support)
    # We'll use potential pool for "ground game" sizing.
    res["ExpectedSupportVotes"] = (res["SupportPct"] * res["Registered"]).round(1)

    # 3. TargetScore (Composite)
    # Formula: w1*TurnoutOpp + w2*PersuasionPot + w3*RegNorm
    w_opp = weights.get("turnout_opportunity", weights.get("turnout_pct", 0.33))
    w_per = weights.get("persuasion_potential", weights.get("yes_pct", 0.34))
    w_size = weights.get("voter_pool_size", weights.get("registered", 0.33))

    res["TargetScore"] = (
        w_opp * res["TurnoutOpportunity"] +
        w_per * res["PersuasionPotential"] +
        w_size * reg_norm
    ).round(6)

    # 4. Tiers
    def assign_tier(val, category="TargetScore"):
        if val >= thresholds.get(f"tier_1_cutoff", 0.75): return 1
        if val >= thresholds.get(f"tier_2_cutoff", 0.50): return 2
        if val >= thresholds.get(f"tier_3_cutoff", 0.25): return 3
        return 4

    res["SupportTier"] = res["SupportPct"].apply(lambda x: assign_tier(x))
    res["TurnoutTier"] = res["TurnoutPct"].apply(lambda x: assign_tier(x))
    res["TargetTier"]  = res["TargetScore"].apply(lambda x: assign_tier(x))
    
    # WalkPriority: High Score, Tier 1
    res["WalkPriority"] = "Low"
    res.loc[res["TargetTier"] == 1, "WalkPriority"] = "High"
    res.loc[res["TargetTier"] == 2, "WalkPriority"] = "Medium"

    return res
