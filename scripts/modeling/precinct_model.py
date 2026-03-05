"""
scripts/modeling/precinct_model.py

Builds canonical precinct model DataFrame at MPREC (or SRPREC fallback).
Merges geometry + contest vote totals + strategy metrics.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import json

from .targeting_engine import compute_targeting_metrics

# ---------------------------------------------------------------------------

# ID normalization helpers
# ---------------------------------------------------------------------------

def normalize_id(value) -> str:
    """
    Normalize a precinct ID to zero-padded string.
    Never returns a float representation.
    """
    if value is None:
        return ""
    s = str(value).strip()
    # Strip trailing .0 from float-read IDs
    s = re.sub(r"\.0+$", "", s)
    return s


def normalize_id_series(series: pd.Series) -> pd.Series:
    """Normalize a full column of IDs."""
    cleaned = series.apply(normalize_id)
    max_len = cleaned.str.len().max()
    if pd.isna(max_len) or max_len == 0:
        return cleaned
    return cleaned.str.zfill(int(max_len))


# ---------------------------------------------------------------------------
# Precinct model builder
# ---------------------------------------------------------------------------

def build_precinct_model(
    contest_df: pd.DataFrame,
    canvas_id_col: str,
    geography_level: str = "MPREC",
    gdf=None,
    geo_id_col: str | None = None,
    config: dict | None = None,
) -> pd.DataFrame:
    """
    Build canonical precinct model DataFrame.

    Parameters
    ----------
    contest_df : pd.DataFrame
        Aggregated vote results per precinct. Must have columns:
        [canvas_id_col, 'Registered', 'BallotsCast', and contest columns]
    canvas_id_col : str
        Column name for the precinct ID in contest_df.
    geography_level : str
        'MPREC' or 'SRPREC'
    gdf : GeoDataFrame or None
        Geometry to join (optional). If None, model has no geometry.
    geo_id_col : str or None
        ID column in gdf to join on.
    config : dict
        Model parameter config (weights, thresholds).

    Returns
    -------
    pd.DataFrame with computed metrics and tier scores.
    """
    config = config or {}
    weights = config.get("scoring", {}).get("weights", {
        "turnout_pct": 0.30,
        "yes_pct":     0.35,
        "registered":  0.15,
        "swing_index": 0.20,
    })
    thresholds = config.get("scoring", {}).get("thresholds", {
        "tier_1_cutoff": 0.75,
        "tier_2_cutoff": 0.50,
        "tier_3_cutoff": 0.25,
    })

    df = contest_df.copy()

    # Normalize ID column
    df[canvas_id_col] = normalize_id_series(df[canvas_id_col].astype(str))

    # Ensure numeric vote columns
    for col in ["Registered", "BallotsCast"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Use the targeting engine
    df = compute_targeting_metrics(
        df, 
        weights=config.get("scoring", {}).get("weights", {}),
        thresholds=config.get("scoring", {}).get("thresholds", {}),
        contest_type=config.get("contest_type", "ballot_measure"),
        target_candidate=config.get("target_candidate")
    )

    # Rank (1 = highest priority)
    if "TargetScore" in df.columns:
        df["Rank"] = df["TargetScore"].rank(ascending=False, method="min").astype(int)

    # Geography level tag
    df["GeographyLevel"] = geography_level

    # Join geometry if provided
    if gdf is not None and geo_id_col is not None and not isinstance(gdf, dict):
        try:
            # gdf is expected to be a GeoDataFrame
            geo_df = gdf[[geo_id_col, "geometry"]].copy()
            geo_df[geo_id_col] = normalize_id_series(geo_df[geo_id_col].astype(str))
            df = df.merge(
                geo_df,
                left_on=canvas_id_col,
                right_on=geo_id_col,
                how="left",
            )
        except Exception:
            pass  # Geometry join failure is non-fatal; logged by caller

    return df


def build_targeting_list(model_df: pd.DataFrame, min_score: float = 0.30) -> pd.DataFrame:
    """
    Build a campaign targeting list from the precinct model.
    Returns precincts above min_score, sorted by Rank.
    """
    cols = [
        c for c in [
            "Rank", "TargetTier", "TargetScore",
            "TurnoutPct", "SupportPct", "SwingIndex",
            "Registered", "BallotsCast",
            "GeographyLevel",
        ]
        if c in model_df.columns
    ]
    # Add ID column (first column that ends in _ID or is known)
    id_candidates = [c for c in model_df.columns if "ID" in c.upper() or c.upper() == "PRECINCT"]
    if id_candidates:
        cols = [id_candidates[0]] + cols

    targeting = (
        model_df[cols]
        .loc[model_df["TargetScore"] >= min_score]
        .sort_values("Rank")
        .reset_index(drop=True)
    )
    return targeting
