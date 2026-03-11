"""
engine/archive/precinct_profiles.py

Analyzes historical results to create a long-term behavioral fingerprint
for each precinct (turnout, support variance, tilt).
Outputs derived/archive/precinct_profiles.csv
"""
import pandas as pd
import numpy as np
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DERIVED_DIR = BASE_DIR / "derived" / "archive"
LOG_DIR = BASE_DIR / "logs" / "archive"

logger = logging.getLogger("precinct_profiles")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(LOG_DIR / "archive_ingest.log")
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(fh)

def build_profiles():
    infile = DERIVED_DIR / "normalized_elections.csv"
    if not infile.exists():
        logger.error("normalized_elections.csv not found. Run archive_ingest first.")
        return

    df = pd.read_csv(infile)
    if df.empty:
        logger.warning("normalized_elections.csv is empty.")
        return

    # Compute precinct-level aggregations
    profiles = df.groupby(["state", "county", "precinct"]).agg(
        avg_turnout=("turnout_rate", "mean"),
        turnout_variance=("turnout_rate", "var"),
        avg_support=("support_rate", "mean"),
        support_variance=("support_rate", "var"),
        elections_counted=("year", "count")
    ).reset_index()

    # Fill NaN variances with 0 (if only 1 election)
    profiles["turnout_variance"] = profiles["turnout_variance"].fillna(0)
    profiles["support_variance"] = profiles["support_variance"].fillna(0)

    # Compute "tilt" (partisan or issue tilt). Assume support > 0.5 is lean Yes/D
    profiles["partisan_tilt"] = profiles["avg_support"] - 0.5
    profiles["ballot_measure_tilt"] = profiles["partisan_tilt"] * 0.8 # generic proxy
    
    # Clean up floats
    for c in ["avg_turnout", "turnout_variance", "avg_support", "support_variance", "partisan_tilt", "ballot_measure_tilt"]:
        profiles[c] = profiles[c].round(4)

    outfile = DERIVED_DIR / "precinct_profiles.csv"
    profiles.to_csv(outfile, index=False)
    logger.info(f"Built behavior profiles for {len(profiles)} precincts.")
    return profiles

if __name__ == "__main__":
    build_profiles()
    print("Precinct profiles generated.")
