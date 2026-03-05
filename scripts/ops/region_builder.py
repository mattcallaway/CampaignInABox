"""
scripts/ops/region_builder.py

Implements deterministic precinct clustering into strategic regions.
Groups 5-25 regions based on geography (centroids) and political metrics.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

def build_strategic_regions(
    df: pd.DataFrame, 
    n_regions: int = 10, 
    seed: int = 42,
    logger = None
) -> pd.DataFrame:
    """
    Cluster precincts into deterministic regions.
    df must contain: canonical_precinct_id, turnout_pct, support_pct, registered.
    Optional: lat, lon (centroids).
    """
    if df.empty:
        return pd.DataFrame()

    # 1. Prepare Features
    features = ["turnout_pct", "support_pct"]
    
    # Check for geometry centroids
    has_geo = "lat" in df.columns and "lon" in df.columns
    if has_geo:
        features += ["lat", "lon"]
        if logger: logger.info(f"  Clustering using Geography + Political metrics")
    else:
        if logger: logger.warn("  Centroids missing; fallback to political-only clustering")

    # 2. Normalize
    subset = df[features].fillna(0)
    # Simple min-max normalization
    subset_norm = (subset - subset.min()) / (subset.max() - subset.min() + 1e-9)
    
    X = subset_norm.values
    
    # 3. Deterministic K-Means (Simplified)
    np.random.seed(seed)
    n_regions = min(n_regions, len(df))
    
    # Initial centroids: stratified or just random based on seed
    initial_indices = np.random.choice(len(df), n_regions, replace=False)
    centroids = X[initial_indices]
    
    for _ in range(20): # 20 iterations is enough for small N
        # Assign
        distances = np.linalg.norm(X[:, np.newaxis] - centroids, axis=2)
        labels = np.argmin(distances, axis=1)
        
        # Update
        new_centroids = np.array([
            X[labels == i].mean(axis=0) if len(X[labels == i]) > 0 else centroids[i]
            for i in range(n_regions)
        ])
        
        if np.allclose(centroids, new_centroids):
            break
        centroids = new_centroids

    # 4. Result Formatting
    res_df = df[["canonical_precinct_id"]].copy()
    res_df["region_id"] = [f"REGION_{l+1:02d}" for l in labels]
    
    # Add rank based on total registered in region (strategic priority)
    region_reg = df.groupby(res_df["region_id"])["registered"].sum()
    region_ranks = region_reg.sort_values(ascending=False).index.tolist()
    rank_map = {rid: i+1 for i, rid in enumerate(region_ranks)}
    res_df["region_rank"] = res_df["region_id"].map(rank_map)
    
    return res_df

def generate_region_summary(df: pd.DataFrame, regions_df: pd.DataFrame) -> str:
    """Create a human-readable markdown summary of regions."""
    merged = pd.merge(df, regions_df, on="canonical_precinct_id", how="left")

    # Guard: if region_id is missing (regions_df was empty or had no match), return minimal summary
    if "region_id" not in merged.columns or merged["region_id"].isna().all():
        return "# Strategic Region Summary\n\n_No regional data available — run pipeline with geopandas enabled for full region clustering._\n"

    merged["region_id"] = merged["region_id"].fillna("REGION_UNASSIGNED")

    summary_rows = []
    summary_rows.append("# Strategic Region Summary")
    summary_rows.append("Precincts grouped into organizational regions for field management.\n")

    groupby_cols = {
        "canonical_precinct_id": "count",
        "registered": "sum",
    }
    for col in ["turnout_pct", "support_pct"]:
        if col in merged.columns:
            groupby_cols[col] = "mean"

    stats = merged.groupby("region_id").agg(groupby_cols).sort_values("registered", ascending=False)
    
    summary_rows.append("| Region ID | Precincts | Registered | Avg Turnout | Avg Support |")
    summary_rows.append("|---|---|---|---|---|")
    for rid, row in stats.iterrows():
        summary_rows.append(f"| {rid} | {row['canonical_precinct_id']} | {int(row['registered']):,} | {row['turnout_pct']:.1%} | {row['support_pct']:.1%} |")
    
    summary_rows.append("\n## Strategic Recommmendations")
    top_region = stats.index[0]
    summary_rows.append(f"- **Top Priority:** `{top_region}` holds the highest concentration of registered voters. Recommend placing a Region Captain here first.")
    
    return "\n".join(summary_rows)
