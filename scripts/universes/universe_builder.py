"""
scripts/universes/universe_builder.py

Categorizes precincts into strategic universes (Persuasion, Mobilization, etc.)
based on deterministic rules from config/universe_rules.yaml.
"""

import pandas as pd
import yaml
import sys
import json
from pathlib import Path

# Bootstrap
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.lib.schema import canonicalize_df

def apply_universe_rules(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: Merged model features DataFrame.
    Output: DataFrame with 'universe_name', 'universe_reason', and 'key_metrics_snapshot'.
    """
    config_path = BASE_DIR / "config" / "universe_rules.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    df = canonicalize_df(features_df.copy())
    
    # Initialize output columns
    df["universe_name"] = "Other / Unassigned"
    df["universe_reason"] = "Does not meet specific targeting criteria"
    
    for uni in config.get("universes", []):
        name = uni["name"]
        reason = uni["reason"]
        rules = uni["rules"]
        
        # Build mask
        mask = pd.Series([True] * len(df))
        for r in rules:
            field = r["field"]
            if field not in df.columns:
                print(f"[Universes] [WARN] Column '{field}' missing for rule in {name}. Skipping rule.")
                continue
                
            op = r["op"]
            val = r["value"]
            
            if op == "gt": mask &= (df[field] > val)
            elif op == "lt": mask &= (df[field] < val)
            elif op == "between": mask &= (df[field] >= val[0]) & (df[field] <= val[1])
            elif op == "eq": mask &= (df[field] == val)

        # Apply universe to matched rows (priority: first match wins in config or can be cumulative)
        # For this system, we'll allow the last match in the list to overwrite (or we could only match unassigned)
        df.loc[mask, "universe_name"] = name
        df.loc[mask, "universe_reason"] = reason

    # Create metrics snapshot
    def make_snapshot(row):
        return json.dumps({
            "registered": int(row.get("registered", 0)),
            "turnout_pct": round(float(row.get("turnout_pct", 0)), 3),
            "support_pct": round(float(row.get("support_pct", 0)), 3)
        })
    
    df["key_metrics_snapshot"] = df.apply(make_snapshot, axis=1)
    
    return df[["canonical_precinct_id", "universe_name", "universe_reason", "key_metrics_snapshot"]]

if __name__ == "__main__":
    pass
