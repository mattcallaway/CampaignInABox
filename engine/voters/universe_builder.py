"""
engine/voters/universe_builder.py — Prompt 11/12 (upgraded)

Classify voters into targeting universes and aggregate to precinct level.

Prompt 12 upgrade: when TPS + PS scores are available, uses threshold-based
universe assignment. Falls back to propensity_score heuristics (Prompt 11)
when scores are missing.

Universe definitions:
  GOTV universe          — TPS < 0.40 AND (D or N party)
  Persuasion universe    — PS > 0.60 AND moderate TPS (0.30-0.70)
  High-value persuasion  — PS > 0.75 AND TPS > 0.40
  Base mobilization      — TPS < 0.55 AND TPS > 0.20 AND party == D
  Low turnout persuadables — TPS < 0.30 AND PS > 0.50

Fallback heuristics (Prompt 11, no TPS/PS):
  high_propensity   — propensity ≥ 0.80
  low_propensity    — propensity ≤ 0.20
  persuadable       — ≥2 elections AND N/DTS party
  base_supporters   — ≥3 elections AND D
  likely_opposition — ≥3 elections AND R
  other             — everyone else

Outputs:
  derived/voter_universes/<RUN_ID>__universes.csv        (precinct-level, SAFE to commit)
  derived/voter_universes/<RUN_ID>__voter_segments.parquet (voter-level, .gitignored)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
log = logging.getLogger(__name__)

UNIVERSE_DIR = BASE_DIR / "derived" / "voter_universes"

# ── TPS/PS-aware universe thresholds ─────────────────────────────────────────

GOTV_TPS_MAX          = 0.40
PERSUASION_PS_MIN     = 0.60
PERSUASION_TPS_MIN    = 0.30
PERSUASION_TPS_MAX    = 0.70
HIGH_VALUE_PS_MIN     = 0.75
HIGH_VALUE_TPS_MIN    = 0.40
BASE_MOB_TPS_MAX      = 0.55
BASE_MOB_TPS_MIN      = 0.20
LOW_TURN_PERS_TPS_MAX = 0.30
LOW_TURN_PERS_PS_MIN  = 0.50

# ── Universe names ─────────────────────────────────────────────────────────────

UNIVERSE_COLS_V11 = [
    "high_propensity",
    "low_propensity",
    "persuadable",
    "base_supporters",
    "likely_opposition",
    "other",
]

UNIVERSE_COLS_V12 = [
    "gotv_universe",
    "persuasion_universe",
    "high_value_persuasion",
    "base_mobilization",
    "low_turnout_persuadables",
    "likely_opposition",
    "other",
]


# ── Prompt 12 (TPS/PS-aware) Classification ───────────────────────────────────

def _classify_with_scores(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    TPS + PS threshold-based universe classification (Prompt 12).
    Priority order: high_value > persuasion > gotv > base_mob > low_turn_pers > opposition > other
    """
    df = voter_df.copy()
    tps   = df["tps"].fillna(0.5)
    ps    = df["ps"].fillna(0.5)
    party = df.get("party_normalized", pd.Series("O", index=df.index)).fillna("O")

    universe = pd.Series("other", index=df.index)

    # Definitions in ascending priority (later overwrites earlier)
    # 1. Likely opposition
    opp_mask = (party == "R") & (tps >= 0.50)
    universe[opp_mask] = "likely_opposition"

    # 2. Low turnout persuadables
    lt_mask = (tps < LOW_TURN_PERS_TPS_MAX) & (ps > LOW_TURN_PERS_PS_MIN)
    universe[lt_mask] = "low_turnout_persuadables"

    # 3. Base mobilization
    base_mask = (tps >= BASE_MOB_TPS_MIN) & (tps < BASE_MOB_TPS_MAX) & (party == "D")
    universe[base_mask] = "base_mobilization"

    # 4. GOTV universe
    gotv_mask = (tps < GOTV_TPS_MAX) & party.isin(["D", "N", "DTS", "L", "G"])
    universe[gotv_mask] = "gotv_universe"

    # 5. Persuasion universe (overwrites GOTV for voters matching both)
    pers_mask = (
        (ps > PERSUASION_PS_MIN) &
        (tps >= PERSUASION_TPS_MIN) & (tps <= PERSUASION_TPS_MAX)
    )
    universe[pers_mask] = "persuasion_universe"

    # 6. High-value persuasion (highest priority — overwrites persuasion)
    hv_mask = (ps > HIGH_VALUE_PS_MIN) & (tps > HIGH_VALUE_TPS_MIN)
    universe[hv_mask] = "high_value_persuasion"

    df["universe"] = universe
    dist = df["universe"].value_counts()
    log.info(f"[UNIVERSE_BUILDER] Prompt-12 universe distribution:\n{dist.to_string()}")
    return df


# ── Prompt 11 (heuristic) Classification ─────────────────────────────────────

def _classify_with_heuristics(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Heuristic-based universe classification (Prompt 11 fallback).
    Used when TPS/PS scores haven't been computed.
    """
    df = voter_df.copy()
    prop      = df.get("propensity_score", pd.Series(0.0, index=df.index)).fillna(0.0)
    party     = df.get("party_normalized", pd.Series("O", index=df.index)).fillna("O")
    elections = df.get("elections_participated", pd.Series(0, index=df.index)).fillna(0)

    universe = pd.Series("other", index=df.index)
    universe[prop <= 0.20] = "low_propensity"
    universe[(elections >= 2) & party.isin(["N", "DTS"])] = "persuadable"
    universe[(elections >= 3) & (party == "D")] = "base_supporters"
    universe[(elections >= 3) & (party == "R")] = "likely_opposition"
    universe[(prop >= 0.80) & party.isin(["D", "N", "L", "G", "A"])] = "high_propensity"

    df["universe"] = universe
    dist = df["universe"].value_counts()
    log.info(f"[UNIVERSE_BUILDER] Prompt-11 heuristic universe distribution:\n{dist.to_string()}")
    return df


# ── Public API ────────────────────────────────────────────────────────────────

def classify_voters(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify voters into universes.
    Automatically selects Prompt 12 (TPS/PS) or Prompt 11 (heuristic) based
    on column availability.
    """
    has_scores = "tps" in voter_df.columns and "ps" in voter_df.columns
    if has_scores:
        log.info("[UNIVERSE_BUILDER] Using Prompt 12 TPS/PS scoring for universe classification")
        return _classify_with_scores(voter_df)
    else:
        log.info("[UNIVERSE_BUILDER] TPS/PS not available — falling back to heuristic classification")
        return _classify_with_heuristics(voter_df)


# ── Precinct Aggregation ───────────────────────────────────────────────────────

def aggregate_to_precinct(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate voter-level universe data to precinct-level counts and percentages.
    Returns a DataFrame with one row per precinct.
    """
    if "canonical_precinct_id" not in voter_df.columns:
        log.warning("[UNIVERSE_BUILDER] No canonical_precinct_id — cannot aggregate")
        return pd.DataFrame()

    if "universe" not in voter_df.columns:
        voter_df = classify_voters(voter_df)

    # Determine which universe column set is relevant
    all_universes = list(voter_df["universe"].unique())
    is_v12 = any(u in all_universes for u in ["gotv_universe", "persuasion_universe", "high_value_persuasion"])
    universe_cols = UNIVERSE_COLS_V12 if is_v12 else UNIVERSE_COLS_V11

    pivot = (
        voter_df.groupby(["canonical_precinct_id", "universe"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    # Ensure all expected universe columns exist
    for col in universe_cols:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot = pivot.rename(columns={c: f"{c}_count" for c in universe_cols if c in pivot.columns})

    totals = voter_df.groupby("canonical_precinct_id").size().reset_index(name="total_voters")
    pivot = pivot.merge(totals, on="canonical_precinct_id", how="left")

    for col in universe_cols:
        cnt_col = f"{col}_count"
        if cnt_col in pivot.columns:
            pivot[f"{col}_pct"] = (pivot[cnt_col] / pivot["total_voters"]).round(4)

    # Append TPS/PS averages if available
    for score_col in ["tps", "ps", "propensity_score"]:
        if score_col in voter_df.columns:
            avg = (
                voter_df.groupby("canonical_precinct_id")[score_col]
                .mean()
                .reset_index(name=f"avg_{score_col}")
            )
            pivot = pivot.merge(avg, on="canonical_precinct_id", how="left")

    log.info(f"[UNIVERSE_BUILDER] Aggregated {len(voter_df):,} voters across {len(pivot):,} precincts")
    return pivot


# ── Output Writers ─────────────────────────────────────────────────────────────

def write_universes(
    precinct_df: pd.DataFrame,
    voter_df: pd.DataFrame,
    run_id: str,
) -> tuple[Path, Optional[Path]]:
    """
    Write:
      1. Precinct-level universe counts CSV (safe to commit)
      2. Voter-level segments Parquet (local only, .gitignored)
    """
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = UNIVERSE_DIR / f"{run_id}__universes.csv"
    precinct_df.to_csv(csv_path, index=False)
    log.info(f"[UNIVERSE_BUILDER] Wrote universe precinct summary: {csv_path}")

    parquet_path = None
    if voter_df is not None and not voter_df.empty:
        seg_path = UNIVERSE_DIR / f"{run_id}__voter_segments.parquet"
        try:
            voter_df.to_parquet(seg_path, index=False)
            log.info(f"[UNIVERSE_BUILDER] Wrote voter segments (local only): {seg_path}")
            parquet_path = seg_path
        except Exception as e:
            log.warning(f"[UNIVERSE_BUILDER] Could not write voter segments Parquet: {e}")

    return csv_path, parquet_path


# ── Diagnostic Summary ────────────────────────────────────────────────────────

def universe_summary_text(precinct_df: pd.DataFrame) -> str:
    """Generate a human-readable universe summary for strategy pack."""
    lines = ["# Voter Universe Summary\n"]
    if precinct_df.empty:
        lines.append("No voter file loaded — universe data unavailable.\n")
        return "\n".join(lines)

    total = precinct_df["total_voters"].sum() if "total_voters" in precinct_df.columns else 0
    lines.append(f"**Total Voters (on file):** {total:,}\n")
    lines.append(f"**Precincts with Voter Data:** {len(precinct_df):,}\n\n")
    lines.append("| Universe | Voters | % of File |\n|---------|--------|----------|\n")

    for col in UNIVERSE_COLS_V12 + UNIVERSE_COLS_V11:
        cnt_col = f"{col}_count"
        if cnt_col in precinct_df.columns:
            n = int(precinct_df[cnt_col].sum())
            pct = n / total * 100 if total > 0 else 0
            lines.append(f"| {col.replace('_', ' ').title()} | {n:,} | {pct:.1f}% |\n")

    return "\n".join(lines)
