"""
scripts/ops/field_plan_engine.py

Computes campaign operations estimates (doors, shifts, volunteers)
at precinct, turf, region, and campaign levels.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any

def compute_field_plan(
    df: pd.DataFrame, 
    ops_config: Dict[str, Any],
    voter_features: pd.DataFrame = None
) -> pd.DataFrame:
    """
    Compute operational metrics for each entity in the dataframe.
    df should be a combined feature/scored dataframe.
    """
    plan_df = df.copy()
    
    # Base parameters
    doors_per_hour = ops_config.get("doors_per_hour", 20)
    hours_per_shift = ops_config.get("hours_per_shift", 3)
    target_shift_count = ops_config.get("target_shift_count_per_weekend", 5)
    contact_rate = ops_config.get("contact_rate", 0.25)
    
    # 1. Door Math
    # If we have voter features with household counts, use those. 
    # Otherwise, heuristic: 1.5 voters per door.
    plan_df["doors_estimated"] = (plan_df.get("registered", pd.Series(0, index=plan_df.index)) / 1.5).fillna(0).astype(int)

    if voter_features is not None and "household_count" in voter_features.columns:
        if "household_count" not in plan_df.columns:
            plan_df = pd.merge(plan_df, voter_features[["canonical_precinct_id", "household_count"]],
                               on="canonical_precinct_id", how="left")
        plan_df["doors_estimated"] = plan_df["household_count"].fillna(plan_df["doors_estimated"]).astype(int)

    # 2. Shift & Volunteer Math
    plan_df["shifts_needed"]            = plan_df["doors_estimated"] / (doors_per_hour * hours_per_shift)
    plan_df["volunteers_needed_weekend"] = plan_df["shifts_needed"] / target_shift_count
    plan_df["expected_contacts"]         = plan_df["doors_estimated"] * contact_rate

    # Prompt 8.6: add spec-required alias columns
    plan_df["doors_to_knock"]      = plan_df["doors_estimated"]
    plan_df["volunteers_needed"]   = plan_df["volunteers_needed_weekend"].round(1)
    # weeks_required: rough estimate — doors_estimated at 1 weekend (4h) per week
    weekly_doors = doors_per_hour * hours_per_shift * 2  # two shifts/weekend
    plan_df["weeks_required"] = (
        plan_df["doors_estimated"] / weekly_doors.real
        if hasattr(weekly_doors, "real") else plan_df["doors_estimated"] / max(weekly_doors, 1)
    ).round(1) if weekly_doors > 0 else 0
    # expected_contacts already computed above

    return plan_df

def summarize_field_plan(plan_df: pd.DataFrame, level_name: str = "precinct") -> pd.DataFrame:
    """Aggregate plan to higher levels (turf, region, campaign)."""
    group_col = None
    if level_name == "turf": group_col = "turf_id"
    elif level_name == "region": group_col = "region_id"
    
    if group_col:
        agg = plan_df.groupby(group_col).agg({
            "registered": "sum",
            "doors_estimated": "sum",
            "shifts_needed": "sum",
            "volunteers_needed_weekend": "sum",
            "expected_contacts": "sum",
            "turnout_pct": "mean",
            "support_pct": "mean"
        }).reset_index()
        return agg
    else:
        # Campaign level
        total = plan_df[[
            "registered", "doors_estimated", "shifts_needed", 
            "volunteers_needed_weekend", "expected_contacts"
        ]].sum().to_frame().T
        total["avg_turnout"] = plan_df["turnout_pct"].mean()
        total["avg_support"] = plan_df["support_pct"].mean()
        return total
