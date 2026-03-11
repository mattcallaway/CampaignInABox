"""
engine/archive/trend_analysis.py

Computes long-term trends by precinct based on historical results.
Outputs derived/archive/precinct_trends.csv
"""
import pandas as pd
import numpy as np
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DERIVED_DIR = BASE_DIR / "derived" / "archive"
LOG_DIR = BASE_DIR / "logs" / "archive"

logger = logging.getLogger("trend_analysis")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(LOG_DIR / "archive_ingest.log")
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(fh)

def calculate_linear_trend(series_x, series_y):
    if len(series_x) < 2:
        return 0.0
    # simple slope calc
    try:
        slope, _ = np.polyfit(series_x, series_y, 1)
        return slope
    except:
        return 0.0

def build_trends():
    infile = DERIVED_DIR / "normalized_elections.csv"
    if not infile.exists():
        logger.error("normalized_elections.csv not found.")
        return

    df = pd.read_csv(infile)
    if df.empty:
        return

    # Sort by time
    df = df.sort_values(["state", "county", "precinct", "year"])
    
    trends = []
    
    for (state, county, prec), group in df.groupby(["state", "county", "precinct"]):
        years = group["year"].values
        turnouts = group["turnout_rate"].values
        supports = group["support_rate"].values
        registered = group["registered"].values
        
        # We calculate per-year delta
        t_trend = calculate_linear_trend(years, turnouts)
        s_trend = calculate_linear_trend(years, supports)
        r_trend = calculate_linear_trend(years, registered)
        
        trends.append({
            "state": state,
            "county": county,
            "precinct": prec,
            "turnout_trend_per_year": round(t_trend, 5),
            "support_trend_per_year": round(s_trend, 5),
            "registration_shift_per_year": round(r_trend, 2)
        })

    tdf = pd.DataFrame(trends)
    outfile = DERIVED_DIR / "precinct_trends.csv"
    tdf.to_csv(outfile, index=False)
    logger.info(f"Built trend analysis for {len(tdf)} precincts.")
    
if __name__ == "__main__":
    build_trends()
    print("Trend analysis complete.")
