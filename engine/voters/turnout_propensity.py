"""
engine/voters/turnout_propensity.py — Prompt 12

Computes Turnout Propensity Score (TPS) for each voter.

TPS represents the probability (0-1) that a voter will turn out, based on
weighted vote history across election types with recency decay.

Election type weights:
  General election → 1.0
  Primary election → 0.8
  Municipal        → 0.7
  Special election → 0.6

Recency decay: elections in the last 4 years are weighted 1.25×.

Outputs:
  derived/voter_models/<run_id>__turnout_scores.parquet  (local only, .gitignored)
  derived/voter_models/<run_id>__precinct_turnout_scores.csv (safe to commit)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional
import datetime

import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
log = logging.getLogger(__name__)

VOTER_MODELS_DIR = BASE_DIR / "derived" / "voter_models"

# ── Election type detection ────────────────────────────────────────────────────
# Matched against vote history column names (case-insensitive)

ELECTION_TYPE_WEIGHTS = {
    "general": 1.0,
    "primary": 0.8,
    "municipal": 0.7,
    "local": 0.7,
    "special": 0.6,
    "runoff": 0.6,
    "default": 0.75,   # unknown type
}

RECENCY_BOOST = 1.25       # applied to elections in last 4 years
RECENCY_CUTOFF_YEARS = 4   # years ago threshold for recency boost


def _classify_election_type(col_name: str) -> str:
    """Classify a vote history column name into an election type."""
    col_lower = col_name.lower()
    for etype in ["general", "primary", "municipal", "local", "special", "runoff"]:
        if etype in col_lower:
            return etype
    return "default"


def _extract_year_from_col(col_name: str) -> Optional[int]:
    """Extract a 4-digit year from a column name, if present."""
    matches = re.findall(r"\b(20\d{2}|19\d{2})\b", col_name)
    if matches:
        return int(matches[-1])  # take last 4-digit year found
    return None


def _build_election_weights(history_cols: list[str]) -> dict[str, float]:
    """
    Build a weight dict {col_name: weight} for all vote history columns.
    Applies election type weights and recency decay.
    """
    current_year = datetime.datetime.now().year
    weights = {}

    for col in history_cols:
        etype = _classify_election_type(col)
        base_weight = ELECTION_TYPE_WEIGHTS.get(etype, ELECTION_TYPE_WEIGHTS["default"])

        yr = _extract_year_from_col(col)
        if yr is not None and (current_year - yr) <= RECENCY_CUTOFF_YEARS:
            weight = base_weight * RECENCY_BOOST
        else:
            weight = base_weight

        weights[col] = weight

    return weights


# ── Participation parsing ──────────────────────────────────────────────────────

def _parse_participation(series: pd.Series) -> pd.Series:
    """Convert vote history column to binary (1=voted, 0=did not)."""
    s = series.astype(str).str.upper().str.strip()
    return s.isin(["1", "Y", "YES", "X", "V", "TRUE", "VOTED"]).astype(float)


# ── TPS Computation ────────────────────────────────────────────────────────────

def compute_tps(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute TPS for each voter.

    Requires vote_history_cols to be present (detected by voter_parser).
    Falls back to propensity_score if no history columns available.

    Returns voter_df with new column 'tps' (0-1 float).
    """
    df = voter_df.copy()

    # Detect vote history columns
    history_cols = [c for c in df.columns if any(
        c.lower().startswith(p.lower())
        for p in ["vote_history_", "vh_", "election_", "general_", "primary_", "special_", "municipal_"]
    )]

    if not history_cols:
        # Fallback: use propensity_score computed in Prompt 11
        if "propensity_score" in df.columns:
            log.info("[TPS] No vote history cols found — using propensity_score as TPS")
            df["tps"] = df["propensity_score"].fillna(0.0).clip(0.0, 1.0)
        else:
            log.warning("[TPS] No vote history or propensity_score — TPS defaulting to 0.5")
            df["tps"] = 0.5
        return df

    weights = _build_election_weights(history_cols)
    total_weight = sum(weights.values())

    if total_weight == 0:
        df["tps"] = 0.5
        return df

    weighted_sum = pd.Series(0.0, index=df.index)
    for col, w in weights.items():
        weighted_sum += _parse_participation(df[col]) * w

    df["tps"] = (weighted_sum / total_weight).clip(0.0, 1.0).round(4)

    # Propensity tier
    df["tps_tier"] = pd.cut(
        df["tps"],
        bins=[0, 0.20, 0.40, 0.60, 0.80, 1.001],
        labels=["very_low", "low", "moderate", "high", "very_high"],
        include_lowest=True,
    ).astype(str)

    log.info(
        f"[TPS] Computed TPS for {len(df):,} voters — "
        f"mean={df['tps'].mean():.3f}, std={df['tps'].std():.3f}"
    )
    return df


# ── Precinct Aggregation ───────────────────────────────────────────────────────

def aggregate_tps_to_precinct(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate TPS to precinct-level statistics.

    Returns a DataFrame with precinct TPS metrics.
    """
    if "canonical_precinct_id" not in voter_df.columns or "tps" not in voter_df.columns:
        log.warning("[TPS] Missing precinct or tps column — cannot aggregate")
        return pd.DataFrame()

    grp = voter_df.groupby("canonical_precinct_id")

    agg = grp["tps"].agg(
        avg_tps="mean",
        median_tps="median",
        std_tps="std",
        p10_tps=lambda x: x.quantile(0.10),
        p90_tps=lambda x: x.quantile(0.90),
    ).round(4).reset_index()

    agg["total_voters"] = grp["tps"].count().values

    # High/low propensity counts
    high_prop = (voter_df["tps"] >= 0.60).groupby(voter_df["canonical_precinct_id"]).sum().reset_index()
    high_prop.columns = ["canonical_precinct_id", "high_propensity_count"]
    low_prop = (voter_df["tps"] < 0.30).groupby(voter_df["canonical_precinct_id"]).sum().reset_index()
    low_prop.columns = ["canonical_precinct_id", "low_propensity_count"]

    agg = agg.merge(high_prop, on="canonical_precinct_id", how="left")
    agg = agg.merge(low_prop, on="canonical_precinct_id", how="left")

    agg["high_propensity_pct"] = (agg["high_propensity_count"] / agg["total_voters"]).round(4)
    agg["low_propensity_pct"] = (agg["low_propensity_count"] / agg["total_voters"]).round(4)

    log.info(f"[TPS] Aggregated TPS across {len(agg):,} precincts")
    return agg


# ── Output Writers ────────────────────────────────────────────────────────────

def write_turnout_scores(voter_df: pd.DataFrame, run_id: str) -> tuple[Path, Path]:
    """
    Write:
      1. Voter-level Parquet (local only, .gitignored)
      2. Precinct-level CSV (safe to commit)
    """
    VOTER_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Voter-level (gitignored)
    parquet_path = VOTER_MODELS_DIR / f"{run_id}__turnout_scores.parquet"
    try:
        voter_df.to_parquet(parquet_path, index=False)
        log.info(f"[TPS] Wrote voter scores: {parquet_path}")
    except Exception as e:
        log.warning(f"[TPS] Could not write Parquet: {e}")

    # Precinct-level aggregate (safe to commit)
    precinct_df = aggregate_tps_to_precinct(voter_df)
    csv_path = VOTER_MODELS_DIR / f"{run_id}__precinct_turnout_scores.csv"
    if not precinct_df.empty:
        precinct_df.to_csv(csv_path, index=False)
        log.info(f"[TPS] Wrote precinct scores: {csv_path}")

    return parquet_path, csv_path
