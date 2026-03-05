"""
scripts/modeling/precinct_model.py

Builds canonical precinct model DataFrame at MPREC (or SRPREC fallback).
Merges geometry + contest vote totals + strategy metrics.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


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

    # Turnout
    df["TurnoutPct"] = 0.0
    mask = df["Registered"] > 0
    df.loc[mask, "TurnoutPct"] = (
        df.loc[mask, "BallotsCast"] / df.loc[mask, "Registered"]
    ).clip(0, 1)

    # YesPct / MarginPct (depending on contest type)
    if "Yes" in df.columns and "No" in df.columns:
        df["Yes"] = pd.to_numeric(df["Yes"], errors="coerce").fillna(0)
        df["No"]  = pd.to_numeric(df["No"],  errors="coerce").fillna(0)
        total_yesno = df["Yes"] + df["No"]
        df["YesPct"] = 0.0
        mask2 = total_yesno > 0
        df.loc[mask2, "YesPct"] = (df.loc[mask2, "Yes"] / total_yesno.loc[mask2]).clip(0, 1)
    else:
        df["YesPct"] = None  # Candidate race — handled separately

    # Swing index placeholder (uniform for now; will be replaced with model)
    df["SwingIndex"] = 0.5

    # Composite score
    turnout_norm = df["TurnoutPct"].clip(0, 1)
    yes_norm     = df["YesPct"].fillna(0.5).clip(0, 1) if "YesPct" in df.columns else 0.5
    reg_norm     = (df["Registered"] / df["Registered"].max()).clip(0, 1) if df["Registered"].max() > 0 else 0.0

    df["CompositeScore"] = (
        weights.get("turnout_pct", 0.30) * turnout_norm
        + weights.get("yes_pct",     0.35) * yes_norm
        + weights.get("registered",  0.15) * reg_norm
        + weights.get("swing_index", 0.20) * df["SwingIndex"]
    ).round(6)

    # Tier assignment
    def _tier(score: float) -> int:
        if score >= thresholds.get("tier_1_cutoff", 0.75):
            return 1
        if score >= thresholds.get("tier_2_cutoff", 0.50):
            return 2
        if score >= thresholds.get("tier_3_cutoff", 0.25):
            return 3
        return 4

    df["Tier"] = df["CompositeScore"].apply(_tier)

    # Rank (1 = highest priority)
    df["Rank"] = df["CompositeScore"].rank(ascending=False, method="min").astype(int)

    # Geography level tag
    df["GeographyLevel"] = geography_level

    # Join geometry if provided
    if gdf is not None and geo_id_col is not None and not isinstance(gdf, dict):
        try:
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
            "Rank", "Tier", "CompositeScore",
            "TurnoutPct", "YesPct", "SwingIndex",
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
        .loc[model_df["CompositeScore"] >= min_score]
        .sort_values("Rank")
        .reset_index(drop=True)
    )
    return targeting
