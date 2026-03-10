"""
engine/voters/persuasion_model.py — Prompt 12

Computes Persuasion Score (PS) for each voter.

PS represents the likelihood (0-1) that a voter is persuadable — i.e., they could
be moved by campaign contact. A high PS voter is neither a strong partisan nor a
confirmed non-voter; they are reachable and open.

Three factors:
  Party strength  (40%) — N/DTS/NPP → persuadable; D/R → not
  Age factor      (30%) — 25-65 sweet spot
  Turnout factor  (30%) — moderate TPS (0.30-0.70) = most persuadable

Formula:
  PS = 0.40*party_score + 0.30*age_score + 0.30*turnout_score

Outputs:
  derived/voter_models/<run_id>__persuasion_scores.parquet  (local only, .gitignored)
  derived/voter_models/<run_id>__precinct_persuasion_scores.csv (safe to commit)
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
log = logging.getLogger(__name__)

VOTER_MODELS_DIR = BASE_DIR / "derived" / "voter_models"

# ── Factor weights ─────────────────────────────────────────────────────────────
PARTY_WEIGHT = 0.40
AGE_WEIGHT   = 0.30
TURNOUT_WEIGHT = 0.30

# ── Party scoring ─────────────────────────────────────────────────────────────

# Raw party score 0.0-1.0: strong partisan = low score, independent = high score
PARTY_SCORES = {
    "D": 0.10,   # Dem partisan — unlikely to be persuaded
    "R": 0.10,   # Rep partisan — unlikely to be persuaded
    "N": 0.95,   # No Party Preference / Decline to State
    "DTS": 0.95,
    "L": 0.70,   # Libertarian — some persuadability
    "G": 0.65,   # Green
    "A": 0.60,   # American Independent
    "O": 0.50,   # Other / unknown
}


def _party_score(party_col: pd.Series) -> pd.Series:
    """Map normalized party label → persuasion party score."""
    return party_col.map(lambda p: PARTY_SCORES.get(str(p).strip().upper(), 0.50))


# ── Age scoring ────────────────────────────────────────────────────────────────

def _age_score(age_col: pd.Series) -> pd.Series:
    """
    Convert age to a persuasion likelihood factor.
    Peak persuadability: 25-65.
    Young (<25) and older (>65) voters are slightly less persuadable on average.
    """
    age = pd.to_numeric(age_col, errors="coerce").fillna(40)  # default 40 if missing

    score = pd.Series(0.60, index=age_col.index)  # base
    score = score.where(age < 25, score)            # young: 0.60
    score = score.where(age > 65,                   # old: 0.65
                        score.where(age > 65, 0.65))

    # Peak: 25-65 → scale from 0.80 to 1.0
    peak_mask = (age >= 25) & (age <= 65)
    # Scores within peak: highest at 35-55, slightly lower at edges
    peak_score = 0.80 + 0.20 * np.clip(
        1 - abs(age - 45) / 25, 0, 1
    )
    score = score.where(~peak_mask, peak_score)
    return score.clip(0.0, 1.0).round(4)


# ── Turnout factor for persuasion ─────────────────────────────────────────────

def _turnout_score_for_persuasion(tps_col: pd.Series) -> pd.Series:
    """
    Convert TPS to a persuasion-relevant turnout factor.

    Logic:
      Very low TPS (< 0.15): voter probably won't show up regardless → low value
      Moderate TPS (0.30-0.70): shows up sometimes → high persuasion value
      Very high TPS (>0.85): strong regular voter → may be set in views
    """
    tps = tps_col.fillna(0.5)
    score = pd.Series(0.0, index=tps.index)

    # Very low (<0.15): score = 0.20
    score = score.where(tps >= 0.15, 0.20)
    # Low (0.15-0.30): score = 0.50
    low_mask = (tps >= 0.15) & (tps < 0.30)
    score = score.where(~low_mask, 0.50)
    # Moderate (0.30-0.70): score = 0.90-1.0 (peak)
    mod_mask = (tps >= 0.30) & (tps <= 0.70)
    mod_score = 0.90 + 0.10 * np.clip(1 - abs(tps - 0.50) / 0.30, 0, 1)
    score = score.where(~mod_mask, mod_score)
    # High (0.70-0.85): score = 0.70
    high_mask = (tps > 0.70) & (tps <= 0.85)
    score = score.where(~high_mask, 0.70)
    # Very high (>0.85): score = 0.50 (strong partisans less persuadable)
    very_high_mask = tps > 0.85
    score = score.where(~very_high_mask, 0.50)

    return score.clip(0.0, 1.0).round(4)


# ── PS Computation ─────────────────────────────────────────────────────────────

def compute_ps(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Persuasion Score (PS) for each voter.

    Requires:
      - party_normalized (from voter_parser) or party
      - age (numeric) — optional
      - tps (from turnout_propensity) — optional, defaults to 0.5

    Returns voter_df with new column 'ps' (0-1 float).
    """
    df = voter_df.copy()

    # Party score
    party_col = None
    for c in ["party_normalized", "party", "Party", "PartyCode"]:
        if c in df.columns:
            party_col = c
            break

    if party_col:
        party_s = _party_score(df[party_col])
    else:
        log.warning("[PS] No party column — using default party score 0.50")
        party_s = pd.Series(0.50, index=df.index)

    # Age score
    age_col = None
    for c in ["age", "Age", "AGE", "Calculated_Age"]:
        if c in df.columns:
            age_col = c
            break

    if age_col:
        age_s = _age_score(df[age_col])
    else:
        log.info("[PS] No age column — using neutral age score 0.80")
        age_s = pd.Series(0.80, index=df.index)

    # Turnout factor
    if "tps" in df.columns:
        turn_s = _turnout_score_for_persuasion(df["tps"])
    else:
        log.info("[PS] No TPS column — using neutral turnout factor 0.75")
        turn_s = pd.Series(0.75, index=df.index)

    # Combine
    df["ps"] = (
        PARTY_WEIGHT   * party_s +
        AGE_WEIGHT     * age_s +
        TURNOUT_WEIGHT * turn_s
    ).clip(0.0, 1.0).round(4)

    # PS tier
    df["ps_tier"] = pd.cut(
        df["ps"],
        bins=[0, 0.25, 0.45, 0.65, 0.80, 1.001],
        labels=["very_low", "low", "moderate", "high", "very_high"],
        include_lowest=True,
    ).astype(str)

    log.info(
        f"[PS] Computed PS for {len(df):,} voters — "
        f"mean={df['ps'].mean():.3f}, std={df['ps'].std():.3f}"
    )
    return df


# ── Precinct Aggregation ───────────────────────────────────────────────────────

def aggregate_ps_to_precinct(voter_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate PS to precinct-level statistics."""
    if "canonical_precinct_id" not in voter_df.columns or "ps" not in voter_df.columns:
        return pd.DataFrame()

    grp = voter_df.groupby("canonical_precinct_id")
    agg = grp["ps"].agg(
        avg_ps="mean",
        median_ps="median",
        std_ps="std",
        p10_ps=lambda x: x.quantile(0.10),
        p90_ps=lambda x: x.quantile(0.90),
    ).round(4).reset_index()

    agg["total_voters"] = grp["ps"].count().values

    high_ps = (voter_df["ps"] >= 0.60).groupby(voter_df["canonical_precinct_id"]).sum().reset_index()
    high_ps.columns = ["canonical_precinct_id", "persuadable_count"]
    agg = agg.merge(high_ps, on="canonical_precinct_id", how="left")
    agg["persuadable_pct"] = (agg["persuadable_count"] / agg["total_voters"]).round(4)

    log.info(f"[PS] Aggregated PS across {len(agg):,} precincts")
    return agg


# ── Output Writers ─────────────────────────────────────────────────────────────

def write_persuasion_scores(voter_df: pd.DataFrame, run_id: str) -> tuple[Path, Path]:
    """Write voter-level Parquet (local only) and precinct CSV."""
    VOTER_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    parquet_path = VOTER_MODELS_DIR / f"{run_id}__persuasion_scores.parquet"
    try:
        voter_df.to_parquet(parquet_path, index=False)
        log.info(f"[PS] Wrote voter scores: {parquet_path}")
    except Exception as e:
        log.warning(f"[PS] Could not write Parquet: {e}")

    precinct_df = aggregate_ps_to_precinct(voter_df)
    csv_path = VOTER_MODELS_DIR / f"{run_id}__precinct_persuasion_scores.csv"
    if not precinct_df.empty:
        precinct_df.to_csv(csv_path, index=False)
        log.info(f"[PS] Wrote precinct scores: {csv_path}")

    return parquet_path, csv_path
