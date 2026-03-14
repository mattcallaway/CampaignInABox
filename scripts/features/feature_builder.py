"""
scripts/features/feature_builder.py

Computes precinct-level base features from contest results.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Bootstrap
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.lib.schema import canonicalize_df, validate_schema

def build_precinct_base_features(model_df: pd.DataFrame, contest_id: str) -> pd.DataFrame:
    """
    Input: Standard precinct model DataFrame (with YES/NO, etc.)
    Output: Features DataFrame with growth metrics and stabilitized values.
    """
    print(f"[Features] Building base features for {contest_id}")
    
    # 1. Canonicalize
    df = canonicalize_df(model_df.copy())

    # 1b. Deduplicate columns — canonicalize_df can rename registered_voters→registered
    #     while registered already exists, producing two 'registered' columns.
    #     Keep the LAST occurrence (the canonical/renamed one) and drop earlier dupes.
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated(keep="last")]
    
    # 2. Extract core metrics
    # After canonicalize_df, columns like "yes_pct" or "SupportPct" should already be "support_pct"
    target_cols = ["canonical_precinct_id", "registered", "ballots_cast", "turnout_pct", "support_pct"]
    
    # Identify which support column we have if it's candidate mode
    if "target_choice_pct" in df.columns and "support_pct" not in df.columns:
        df = df.rename(columns={"target_choice_pct": "support_pct"})
    
    # Ensure all target_cols exist in df, if not, add as nan or zero
    for c in target_cols:
        if c not in df.columns:
            print(f"[Features] [WARN] Expected column {c} missing, filling with zeros")
            df[c] = 0.0
            
    # Subset to usable columns — guaranteed no dupes at this point
    feature_df = df[target_cols].copy()
    
    # Helper: ensure a column is always a 1-D Series even if somehow still a DataFrame
    def _col(name: str) -> pd.Series:
        col = feature_df[name]
        if isinstance(col, pd.DataFrame):
            col = col.iloc[:, -1]  # take last/canonical column
        return col.astype(float)

    # 3. Compute derived growth/stability features
    # Log transform for scale-invariant modeling
    feature_df["log_registered"]  = np.log1p(_col("registered"))
    feature_df["sqrt_registered"] = np.sqrt(_col("registered"))
    
    # Ratio: ballots cast per registered (same as turnout but explicit and raw)
    feature_df["ballots_cast_per_registered"] = (
        _col("ballots_cast") / _col("registered").replace(0, np.nan)
    ).fillna(0.0)
    
    # Support density: registered * support_pct
    feature_df["support_density"] = _col("registered") * _col("support_pct")
    
    validate_schema(feature_df)
    
    return feature_df

if __name__ == "__main__":
    # Test stub
    test_data = pd.DataFrame({
        "mprec": ["1", "2"],
        "registered": [1000, 2000],
        "ballots_cast": [500, 1500],
        "turnout_pct": [0.5, 0.75],
        "yes_pct": [0.6, 0.4]
    })
    res = build_precinct_base_features(test_data, "test_contest")
    print(res.head())
