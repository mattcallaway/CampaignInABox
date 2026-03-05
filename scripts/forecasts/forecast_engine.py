"""
scripts/forecasts/forecast_engine.py

Scenario-based forecasting for Campaign In A Box v2.
Uses forecast_scenarios.yaml to compute "What If" outcomes.
"""

import pandas as pd
import yaml
import sys
from pathlib import Path

# Bootstrap
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.lib.schema import canonicalize_df

def run_forecasts(features_df: pd.DataFrame, logger=None) -> pd.DataFrame:
    """
    Computes forecasted ballots and support for each scenario.
    """
    config_path = BASE_DIR / "config" / "forecast_scenarios.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    df = canonicalize_df(features_df.copy())
    scenarios = config.get("scenarios", [])
    
    forecast_results = []
    
    for scn in scenarios:
        s_id = scn["id"]
        s_name = scn["name"]
        to_mult = scn.get("turnout_multiplier", 1.0)
        sup_lift = scn.get("support_lift", 0.0)
        
        # Apply to entire set
        # Forecast turnout
        to_base = df["turnout_pct"].fillna(0)
        to_f = (to_base * to_mult).clip(0, 1)
        
        # Forecast support
        sup_base = df["support_pct"].fillna(0.5)
        sup_f = (sup_base + sup_lift).clip(0.1, 0.9) # Don't allow absolute 0/1 for stability
        
        # Totals
        ballots_f = (df["registered"] * to_f).sum()
        yes_votes_f = (df["registered"] * to_f * sup_f).sum()
        no_votes_f = ballots_f - yes_votes_f
        
        forecast_results.append({
            "scenario_id": s_id,
            "scenario_name": s_name,
            "expected_turnout_pct": round(to_f.mean(), 3),
            "total_expected_ballots": int(ballots_f),
            "expected_support_pct": round(yes_votes_f / ballots_f if ballots_f > 0 else 0, 3),
            "expected_yes_votes": int(yes_votes_f),
            "expected_no_votes": int(no_votes_f),
            "margin_votes": int(yes_votes_f - no_votes_f)
        })
        
    return pd.DataFrame(forecast_results)

if __name__ == "__main__":
    pass
