"""
scripts/universes/voter_universe_exporter.py

Handles exporting voter-level universe lists with security redaction.
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional

def export_voter_universes(
    voter_df: pd.DataFrame,
    precinct_universes: pd.DataFrame,
    out_dir: Path,
    run_id: str,
    allowlist_columns: Optional[List[str]] = None,
    chunk_size: int = 50000,
    logger = None
):
    """
    Export voter-level CSVs grouped by universe.
    """
    if voter_df.empty or precinct_universes.empty:
        if logger: logger.warn("  Skipping voter universe export: empty metrics")
        return

    # 1. Merge Universe Info onto Voters
    if "canonical_precinct_id" not in voter_df.columns:
        if logger: logger.error("  Voter DF missing canonical_precinct_id; cannot map universes")
        return

    merged = pd.merge(
        voter_df, 
        precinct_universes[["canonical_precinct_id", "universe_name"]], 
        on="canonical_precinct_id", 
        how="inner"
    )
    
    if merged.empty:
        if logger: logger.warn("  No matches between voters and precinct universes")
        return

    # 2. Apply Security Allowlist
    if allowlist_columns:
        # Filter columns to only those in allowlist that actually exist
        valid_cols = [c for c in allowlist_columns if c in merged.columns] + ["universe_name"]
        export_df = merged[valid_cols]
    else:
        # Default safety: remove common sensitive fields if no explicit allowlist
        sensitive = ["phone", "email", "ssn", "dob"]
        export_df = merged.drop(columns=[c for c in sensitive if c in merged.columns])

    # 3. Export by Universe
    out_dir.mkdir(parents=True, exist_ok=True)
    
    universes = export_df["universe_name"].unique()
    for uni in universes:
        uni_clean = uni.lower().replace(" ", "_").replace("/", "_")
        uni_df = export_df[export_df["universe_name"] == uni]
        
        uni_out = out_dir / f"{run_id}__voter_list__{uni_clean}.csv"
        
        # Chunked export if too large
        if len(uni_df) > chunk_size:
            if logger: logger.info(f"  Exporting {uni} in chunks...")
            for i, chunk in enumerate(range(0, len(uni_df), chunk_size)):
                chunk_df = uni_df.iloc[chunk : chunk + chunk_size]
                chunk_out = out_dir / f"{run_id}__voter_list__{uni_clean}__part{i+1}.csv"
                chunk_df.to_csv(chunk_out, index=False)
        else:
            uni_df.to_csv(uni_out, index=False)
            
    if logger: logger.info(f"  Exported voter universes for {len(universes)} segments to {out_dir}")
