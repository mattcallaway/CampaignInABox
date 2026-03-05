"""
scripts/turfs/turf_generator.py

Groups ranked precincts into "Walk Turfs" for field programs.
Deterministic grouping based on registration capacity.
"""

import pandas as pd
import sys
from pathlib import Path

# Bootstrap
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.lib.schema import canonicalize_df

def generate_turfs(ranked_df: pd.DataFrame, capacity: int = 300) -> pd.DataFrame:
    """
    Groups precincts into bundles.
    """
    df = canonicalize_df(ranked_df.copy())
    
    if "walk_priority_rank" not in df.columns:
        df["walk_priority_rank"] = df["target_score"].rank(ascending=False, method="min")
        
    # Sort by rank
    df = df.sort_values("walk_priority_rank")
    
    turfs = []
    current_turf_ids = []
    current_reg = 0
    turf_counter = 1
    
    for _, row in df.iterrows():
        p_id = row["canonical_precinct_id"]
        reg = row.get("registered", 0)
        
        current_turf_ids.append(p_id)
        current_reg += reg
        
        if current_reg >= capacity:
            # Close turf
            turfs.append({
                "turf_id": f"TURF_{turf_counter:03d}",
                "precinct_ids": ",".join(current_turf_ids),
                "precinct_count": len(current_turf_ids),
                "sum_registered": int(current_reg),
                "avg_target_score": round(df.loc[df["canonical_precinct_id"].isin(current_turf_ids), "target_score"].mean(), 3)
            })
            # Reset
            current_turf_ids = []
            current_reg = 0
            turf_counter += 1
            
    # Add trailing turf if any
    if current_turf_ids:
        turfs.append({
            "turf_id": f"TURF_{turf_counter:03d}",
            "precinct_ids": ",".join(current_turf_ids),
            "precinct_count": len(current_turf_ids),
            "sum_registered": int(current_reg),
            "avg_target_score": round(df.loc[df["canonical_precinct_id"].isin(current_turf_ids), "target_score"].mean(), 3)
        })
        
    return pd.DataFrame(turfs)

if __name__ == "__main__":
    pass
