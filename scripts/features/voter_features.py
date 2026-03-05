"""
scripts/features/voter_features.py

Ingests county voter file and aggregates to precinct level.
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path

# Bootstrap
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.lib.schema import canonicalize_df

def aggregate_voter_file(voter_file_path: Path, county_slug: str, logger=None) -> pd.DataFrame:
    """
    Detects format, sniffs delimiter, and aggregates by precinct.
    """
    if not voter_file_path.exists():
        if logger: logger.warn(f"Voter file not found at {voter_file_path}")
        return pd.DataFrame()

    if logger: logger.info(f"[VoterAgg] Ingesting {voter_file_path.name}...")
    
    # Sniff delimiter
    ext = voter_file_path.suffix.lower()
    sep = "\t" if ext == ".tsv" else ","
    
    try:
        # Load sample to find precinct field
        chunk = pd.read_csv(voter_file_path, sep=sep, nrows=100)
        df_cols = chunk.columns.tolist()
        
        precinct_col = None
        for c in df_cols:
            if c.lower() in ["mprec", "srprec", "precinct", "precinctid", "voter_precinct"]:
                precinct_col = c
                break
        
        if not precinct_col:
            if logger: logger.warning(f"[VoterAgg] NO precinct column detected in {voter_file_path.name}. Columns: {df_cols}")
            return pd.DataFrame()
        
        # Load full file (only needed columns to save memory)
        # For MVP we look for: Party, BirthDate (for age), [Voted history columns...]
        cols_to_use = [precinct_col]
        party_col = next((c for c in df_cols if "party" in c.lower()), None)
        age_col = next((c for c in df_cols if "age" in c.lower() or "birth" in c.lower()), None)
        
        if party_col: cols_to_use.append(party_col)
        if age_col: cols_to_use.append(age_col)
        
        v_df = pd.read_csv(voter_file_path, sep=sep, usecols=cols_to_use)
        
        if logger: logger.info(f"[VoterAgg] Loaded {len(v_df)} rows. Aggregating...")
        
        # 1. Age calculation if BirthDate
        if age_col and "birth" in age_col.lower():
            # Simplistic age calc
            v_df["v_age"] = 2024 - pd.to_datetime(v_df[age_col], errors='coerce').dt.year
            age_col = "v_age"
            
        agg_logic = {}
        if party_col:
            v_df["is_dem"] = v_df[party_col].astype(str).str.lower().str.startswith("dem")
            v_df["is_rep"] = v_df[party_col].astype(str).str.lower().str.startswith("rep")
            agg_logic["is_dem"] = "mean"
            agg_logic["is_rep"] = "mean"
            
        if age_col:
            agg_logic[age_col] = "mean"
            
        # Count voters per precinct
        v_df["voter_count"] = 1
        agg_logic["voter_count"] = "sum"
            
        precinct_agg = v_df.groupby(precinct_col).agg(agg_logic).reset_index()
        
        # Map to canonical
        if party_col:
            precinct_agg = precinct_agg.rename(columns={"is_dem": "dem_pct_reg", "is_rep": "rep_pct_reg"})
        if age_col:
            precinct_agg = precinct_agg.rename(columns={age_col: "age_mean"})
            
        precinct_agg = precinct_agg.rename(columns={precinct_col: "canonical_precinct_id"})
        
        if logger: logger.info(f"[VoterAgg] Successfully aggregated to {len(precinct_agg)} precincts.")
        return precinct_agg

    except Exception as e:
        if logger: logger.error(f"[VoterAgg] Error processing voter file: {str(e)}")
        return pd.DataFrame()

if __name__ == "__main__":
    # Test stub
    pass
