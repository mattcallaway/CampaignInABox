"""
engine/performance/performance_ingest.py — Prompt 18

Ingests runtime campaign data from data/campaign_runtime/, neutralizes metrics,
connects to precincts, and outputs an aggregated performance metrics CSV.
"""
from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

log = logging.getLogger(__name__)

def ingest_performance_data(base_dir: Path | str, run_id: str) -> Path | None:
    """
    Scans `data/campaign_runtime/` for CSVs (field, fundraising, etc.).
    Aggregates them into a unified performance metrics dataframe by date/precinct.
    If no data exists, creates an empty dataframe with correct schema.
    """
    root = Path(base_dir)
    runtime_dir = root / "data" / "campaign_runtime"
    out_dir = root / "derived" / "performance" / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "performance_metrics.csv"

    # Standard schema
    columns = [
        "date",
        "precinct",
        "doors_knocked",
        "calls_made",
        "texts_sent",
        "mail_sent",
        "digital_spend",
        "volunteer_hours",
        "fundraising_total"
    ]

    all_data = []

    # Helper to load all CSVs in a specific subfolder
    def _load_folder(folder_name: str) -> list[pd.DataFrame]:
        dfs = []
        d = runtime_dir / folder_name
        if not d.exists():
            return dfs
        for f in d.rglob("*.csv"):
            try:
                df = pd.read_csv(f)
                # Ensure 'date' column exists, otherwise use file date or today
                if "date" not in df.columns:
                    df["date"] = pd.Timestamp.today().strftime("%Y-%m-%d")
                
                # Precinct may not apply to all (e.g., fundraising)
                if "precinct" not in df.columns:
                    df["precinct"] = "ALL"
                
                dfs.append(df)
            except Exception as e:
                log.warning(f"Failed to read {f}: {e}")
        return dfs

    # Field data (doors, calls, texts)
    field_dfs = _load_folder("field")
    for df in field_dfs:
        for c in columns:
            if c not in df.columns:
                df[c] = 0
        all_data.append(df[columns])

    # Fundraising data
    fund_dfs = _load_folder("fundraising")
    for df in fund_dfs:
        for c in columns:
            if c not in df.columns:
                df[c] = 0
        all_data.append(df[columns])

    # Volunteer data (shifts -> hours)
    vol_dfs = _load_folder("volunteers")
    for df in vol_dfs:
        if "shifts" in df.columns:
            df["volunteer_hours"] = df["shifts"] * 3  # Assume 3 hr shift if unknown
        for c in columns:
            if c not in df.columns:
                df[c] = 0
        all_data.append(df[columns])

    # Digital / Mail
    digital_dfs = _load_folder("digital")
    mail_dfs = _load_folder("mail")
    for df in digital_dfs + mail_dfs:
        for c in columns:
            if c not in df.columns:
                df[c] = 0
        all_data.append(df[columns])

    if not all_data:
        # Generate empty schema
        final_df = pd.DataFrame(columns=columns)
    else:
        # Combine
        combined = pd.concat(all_data, ignore_index=True)
        # Ensure types for aggregation
        for col in columns[2:]: # skip date/precinct
            combined[col] = pd.to_numeric(combined[col], errors="coerce").fillna(0)
        
        # Group by Date and Precinct
        final_df = combined.groupby(["date", "precinct"]).sum().reset_index()

    # Save
    final_df.to_csv(out_path, index=False)
    
    # Also save historic copy tied to run_id
    hist_dir = root / "derived" / "performance"
    hist_dir.mkdir(exist_ok=True)
    final_df.to_csv(hist_dir / f"{run_id}__performance_metrics.csv", index=False)

    return out_path
