"""
engine/archive/election_similarity.py

Compares current contest against historical archive to find most similar elections.
Outputs derived/archive/similar_elections.csv
"""
import pandas as pd
import numpy as np
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = BASE_DIR / "derived" / "archive"
CONFIG_FILE = BASE_DIR / "config" / "campaign_config.yaml"

def get_current_setup():
    if not CONFIG_FILE.exists():
        return {"contest_type": "local_general", "state": "CA", "county": "Sonoma", "expected_turnout": 0.5}
    with open(CONFIG_FILE, "r") as f:
        cfg = yaml.safe_load(f)
    camp = cfg.get("campaign", {})
    return {
        "contest_type": camp.get("contest_type", "local_general"),
        "state": camp.get("state", "CA"),
        "county": camp.get("county", "Sonoma"),
        "expected_turnout": 0.5 # placeholder logic
    }

def calculate_similarity(row, current):
    score = 100
    if row["contest_type"] != current["contest_type"]:
        score -= 30
    if row["county"] != current["county"]:
        score -= 20
    if row["state"] != current["state"]:
        score -= 10
    
    # Penalty for extreme turnout delta
    t_delta = abs(row["avg_turnout"] - current["expected_turnout"])
    score -= (t_delta * 100) # e.g. 10% diff = -10 pts
    
    # Recency bonus
    years_ago = (2026 - row["year"])
    score -= (years_ago * 0.5)
    
    return max(0, score)

def find_similar():
    infile = ARCHIVE_DIR / "normalized_elections.csv"
    if not infile.exists():
        return
        
    df = pd.read_csv(infile)
    if df.empty: return
    
    current = get_current_setup()
    
    # Agg to contest level
    contests = df.groupby(["year", "state", "county", "contest", "contest_type"]).agg(
        avg_turnout=("turnout_rate", "mean")
    ).reset_index()
    
    contests["similarity_score"] = contests.apply(lambda r: calculate_similarity(r, current), axis=1)
    
    top_matches = contests.sort_values("similarity_score", ascending=False).head(5)
    
    outfile = ARCHIVE_DIR / "similar_elections.csv"
    top_matches.to_csv(outfile, index=False)
    print(f"Computed top 5 similar elections. Output to {outfile}")

if __name__ == "__main__":
    find_similar()
