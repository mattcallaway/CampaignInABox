"""
scripts/modeling/scoring_engine_v2.py

Upgraded Scoring + Targeting Engine for Campaign In A Box v2.
Uses model_weights.yaml and produces tiered target rankings.
"""

import pandas as pd
import numpy as np
import yaml
import sys
from pathlib import Path

# Bootstrap
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.lib.schema import canonicalize_df, validate_schema

def run_scoring_v2(features_df: pd.DataFrame, logger=None) -> pd.DataFrame:
    """
    Computes TargetScore and Tiers based on weights and thresholds in config.
    """
    config_path = BASE_DIR / "config" / "model_weights.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    df = canonicalize_df(features_df.copy())
    weights = config.get("scoring_weights", {})
    thresholds = config.get("thresholds", {})
    
    if logger: logger.info("[Scoring] Computing v2 scores...")
    
    # 1. Basic Component Calculations (if already provided in features, use them; otherwise re-derive)
    # Ensure support_pct exists
    if "support_pct" not in df.columns:
        df["support_pct"] = 0.5
        
    # 2. Apply Weight Logic
    final_score = pd.Series(0.0, index=df.index)
    
    for dim, cfg in weights.items():
        weight = cfg.get("weight", 0)
        formula = cfg.get("formula", "")
        
        # Safe eval or manual map
        val = 0.0
        if dim == "persuasion_potential" and "persuasion_potential" in df.columns:
            # Formula context: persuasion_potential * support_density
            sd_norm = (df["support_density"] / df["support_density"].max()).fillna(0) if df["support_density"].max() > 0 else 0
            val = df["persuasion_potential"] * sd_norm
        elif dim == "turnout_opportunity" and "turnout_opportunity" in df.columns:
            # Formula context: turnout_opportunity * registered
            reg_norm = (df["registered"] / df["registered"].max()).fillna(0) if df["registered"].max() > 0 else 0
            val = df["turnout_opportunity"] * reg_norm
        elif dim == "expected_support_votes":
            val = (df["support_pct"] * (df["registered"] / df["registered"].max()).fillna(0)).fillna(0)
            
        final_score += weight * val

    # Normalize final score to 0-1
    if final_score.max() > final_score.min():
        df["target_score"] = (final_score - final_score.min()) / (final_score.max() - final_score.min())
    else:
        df["target_score"] = final_score
        
    # 3. Assign Tiers
    def get_tier(score):
        if score >= thresholds.get("tier_1", 0.85): return 1
        if score >= thresholds.get("tier_2", 0.70): return 2
        if score >= thresholds.get("tier_3", 0.45): return 3
        return 4
        
    df["target_tier"] = df["target_score"].apply(get_tier)
    
    # 4. Rank and Confidence
    df["walk_priority_rank"] = df["target_score"].rank(ascending=False, method="min").astype(int)
    
    # Confidence Scoring
    # High if voter-file present (check for party columns), Medium if not.
    has_voter_data = "dem_pct_reg" in df.columns
    df["confidence_level"] = "high" if has_voter_data else "medium"
    
    # 5. Metadata columns
    df["walk_priority"] = "Low"
    df.loc[df["target_tier"] == 1, "walk_priority"] = "High"
    df.loc[df["target_tier"] == 2, "walk_priority"] = "Medium"
    
    return df

if __name__ == "__main__":
    pass
