"""
engine/voters/universe_builder.py — Prompt 11

Classify voters into targeting universes and aggregate to precinct level.

Universe definitions (heuristic; configurable):
  high_propensity   — voted in ≥4 of last 5 elections
  low_propensity    — voted in ≤1 of last 5 elections
  persuadable       — ≥2 elections AND party = N/DTS (or swing R/D)
  base_supporters   — ≥3 elections AND party = D
  likely_opposition — ≥3 elections AND party = R
  other             — everyone else

Output:
  derived/voter_universes/<RUN_ID>__universes.csv   (precinct-level, SAFE to commit)
  derived/voter_universes/<RUN_ID>__voter_segments.parquet  (voter-level, .gitignored)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
log = logging.getLogger(__name__)


# ── Universe Classification ────────────────────────────────────────────────────

def classify_voters(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a 'universe' column to each voter record.

    Requires columns:
      - propensity_score (float 0-1, from voter_parser)
      - party_normalized (str: D, R, N, L, G, A, O)

    Returns df with new column 'universe'.
    """
    df = voter_df.copy()

    # Defaults
    prop = df.get("propensity_score", pd.Series(0.0, index=df.index)).fillna(0.0)
    party = df.get("party_normalized", pd.Series("O", index=df.index)).fillna("O")
    elections = df.get("elections_participated", pd.Series(0, index=df.index)).fillna(0)

    # Classify — order matters (first match wins)
    universe = pd.Series("other", index=df.index)

    # High propensity: voted in ≥4 of last 5 (propensity ≥ 0.80)
    high_prop_mask = prop >= 0.80
    universe[high_prop_mask & party.isin(["D", "N", "L", "G", "A"])] = "high_propensity"

    # Low propensity: voted in ≤1 of last 5 (propensity ≤ 0.20)
    low_prop_mask = prop <= 0.20
    universe[low_prop_mask] = "low_propensity"

    # Persuadable: ≥2 elections AND not strong partisan (N or swing)
    persuadable_mask = (elections >= 2) & party.isin(["N", "DTS"])
    universe[persuadable_mask] = "persuadable"

    # Base supporters: ≥3 elections AND party = D
    base_mask = (elections >= 3) & (party == "D")
    universe[base_mask] = "base_supporters"

    # Likely opposition: ≥3 elections AND party = R
    opp_mask = (elections >= 3) & (party == "R")
    universe[opp_mask] = "likely_opposition"

    df["universe"] = universe

    dist = df["universe"].value_counts()
    log.info(f"[UNIVERSE_BUILDER] Universe distribution:\n{dist.to_string()}")
    return df


# ── Precinct Aggregation ───────────────────────────────────────────────────────

UNIVERSE_COLS = [
    "high_propensity",
    "low_propensity",
    "persuadable",
    "base_supporters",
    "likely_opposition",
    "other",
]


def aggregate_to_precinct(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate voter-level universe data to precinct-level counts.

    Returns a DataFrame with columns:
      canonical_precinct_id, total_voters, <universe>_count,
      <universe>_pct, avg_propensity
    """
    if "canonical_precinct_id" not in voter_df.columns:
        log.warning("[UNIVERSE_BUILDER] No canonical_precinct_id — cannot aggregate")
        return pd.DataFrame()

    if "universe" not in voter_df.columns:
        voter_df = classify_voters(voter_df)

    # Count per universe per precinct
    pivot = (
        voter_df.groupby(["canonical_precinct_id", "universe"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    # Ensure all universe columns exist even if zero
    for col in UNIVERSE_COLS:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot = pivot.rename(columns={c: f"{c}_count" for c in UNIVERSE_COLS if c in pivot.columns})

    # Total voters per precinct
    totals = voter_df.groupby("canonical_precinct_id").size().reset_index(name="total_voters")
    pivot = pivot.merge(totals, on="canonical_precinct_id", how="left")

    # Pct columns
    for col in UNIVERSE_COLS:
        cnt_col = f"{col}_count"
        if cnt_col in pivot.columns:
            pivot[f"{col}_pct"] = (pivot[cnt_col] / pivot["total_voters"]).round(4)

    # Average propensity per precinct
    if "propensity_score" in voter_df.columns:
        avg_prop = (
            voter_df.groupby("canonical_precinct_id")["propensity_score"]
            .mean()
            .reset_index(name="avg_propensity")
        )
        pivot = pivot.merge(avg_prop, on="canonical_precinct_id", how="left")

    log.info(f"[UNIVERSE_BUILDER] Aggregated {len(voter_df):,} voters "
             f"across {len(pivot):,} precincts")
    return pivot


# ── Output Writers ────────────────────────────────────────────────────────────

def write_universes(
    precinct_df: pd.DataFrame,
    voter_df: pd.DataFrame,
    run_id: str,
) -> tuple[Path, Optional[Path]]:
    """
    Write:
      1. Precinct-level universe counts CSV (safe to commit)
      2. Voter-level segments Parquet (local only, .gitignored)

    Returns (precinct_csv_path, voter_parquet_path).
    """
    out_dir = BASE_DIR / "derived" / "voter_universes"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Precinct-level (safe)
    csv_path = out_dir / f"{run_id}__universes.csv"
    precinct_df.to_csv(csv_path, index=False)
    log.info(f"[UNIVERSE_BUILDER] Wrote universe precinct summary: {csv_path}")

    # Voter-level Parquet (.gitignored)
    parquet_path = None
    if voter_df is not None and not voter_df.empty:
        seg_path = out_dir / f"{run_id}__voter_segments.parquet"
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
    for col in UNIVERSE_COLS:
        cnt_col = f"{col}_count"
        if cnt_col in precinct_df.columns:
            n = int(precinct_df[cnt_col].sum())
            pct = n / total * 100 if total > 0 else 0
            lines.append(f"| {col.replace('_', ' ').title()} | {n:,} | {pct:.1f}% |\n")
    return "\n".join(lines)
