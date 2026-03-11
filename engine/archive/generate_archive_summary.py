"""
engine/archive/generate_archive_summary.py
Generates derived/archive/archive_summary.json based on ingested archive data.
"""
import pandas as pd
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = BASE_DIR / "derived" / "archive"

def generate_summary():
    infile = ARCHIVE_DIR / "normalized_elections.csv"
    if not infile.exists():
        return
        
    df = pd.read_csv(infile)
    if df.empty: return
    
    summary = {
        "years_covered": list(sorted(df["year"].unique().tolist())),
        "counties_covered": list(sorted(df["county"].unique().tolist())),
        "total_elections": int(df["contest"].nunique()),
        "total_precinct_records": len(df),
        "contest_types_present": list(sorted(df["contest_type"].unique().tolist()))
    }
    
    outfile = ARCHIVE_DIR / "archive_summary.json"
    with open(outfile, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Generated archive summary: {outfile}")

if __name__ == "__main__":
    generate_summary()
