"""
engine/voters/targeting_quadrants.py — Prompt 12

Assigns each voter to a targeting quadrant based on TPS and PS scores.

Quadrants:
  base_voter          — High TPS (≥0.60), Low PS (<0.40)  → GOTV / VBM chase
  low_priority        — Low TPS (<0.40), Low PS (<0.40)   → Minimal investment
  persuasion_target   — Mid-High TPS (≥0.50), High PS (≥0.60) → Mail + Digital
  turnout_persuasion  — Low TPS (<0.50), High PS (≥0.60) → GOTV + persuasion
  high_value          — High TPS (≥0.60), Very High PS (≥0.70) → Priority field

Outputs:
  derived/voter_segments/<run_id>__targeting_quadrants.parquet  (local only, .gitignored)
  derived/voter_segments/<run_id>__targeting_quadrants.csv      (precinct counts, safe to commit)
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SEGMENTS_DIR = BASE_DIR / "derived" / "voter_segments"

log = logging.getLogger(__name__)

# ── Quadrant definitions ───────────────────────────────────────────────────────
# Checked in priority order — first match wins

QUADRANT_DEFINITIONS = [
    # name, label, tps_min, tps_max, ps_min, ps_max, priority program
    ("high_value",          "🌟 High Value Target",     0.60, 1.00, 0.70, 1.00),
    ("persuasion_target",   "💬 Persuasion Target",     0.50, 1.00, 0.60, 1.00),
    ("base_voter",          "🟦 Base Voter (GOTV)",     0.60, 1.00, 0.00, 0.40),
    ("turnout_persuasion",  "🔄 Turnout+Persuasion",   0.00, 0.50, 0.60, 1.00),
    ("low_priority",        "⬜ Low Priority",          0.00, 0.40, 0.00, 0.40),
]

# Programs recommended per quadrant
QUADRANT_PROGRAMS = {
    "high_value":         ["field_canvass", "mail", "digital", "phone"],
    "persuasion_target":  ["mail", "digital"],
    "base_voter":         ["gotv_mail", "vbm_chase", "gotv_phone"],
    "turnout_persuasion": ["gotv_mail", "persuasion_digital"],
    "low_priority":       [],
    "other":              [],
}


def assign_quadrant(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'quadrant' and 'programs' columns to voter DataFrame.

    Requires 'tps' and 'ps' columns.
    """
    df = voter_df.copy()

    if "tps" not in df.columns or "ps" not in df.columns:
        log.warning("[QUADRANTS] Missing tps or ps columns — all voters assigned to 'other'")
        df["quadrant"] = "other"
        df["programs"] = ""
        return df

    tps = df["tps"].fillna(0.5)
    ps  = df["ps"].fillna(0.5)

    quadrant = pd.Series("other", index=df.index)

    # Apply in reverse priority (first defined = highest priority, so iterate in reverse
    # and overwrite — last write to non-'other' wins with ordered priority)
    for q_name, _, tps_min, tps_max, ps_min, ps_max in reversed(QUADRANT_DEFINITIONS):
        mask = (tps >= tps_min) & (tps <= tps_max) & (ps >= ps_min) & (ps <= ps_max)
        quadrant = quadrant.where(~mask, q_name)

    df["quadrant"] = quadrant
    df["programs"] = df["quadrant"].map(
        lambda q: "|".join(QUADRANT_PROGRAMS.get(q, []))
    )

    dist = df["quadrant"].value_counts()
    log.info(f"[QUADRANTS] Quadrant distribution:\n{dist.to_string()}")
    return df


# ── Precinct Aggregation ────────────────────────────────────────────────────────

ALL_QUADRANTS = [q[0] for q in QUADRANT_DEFINITIONS] + ["other"]


def aggregate_quadrants_to_precinct(voter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate targeting quadrant assignments to precinct-level counts.

    Returns a DataFrame with columns:
      canonical_precinct_id, total_voters,
      <quadrant>_count, <quadrant>_pct,
      avg_tps, avg_ps, dominant_quadrant
    """
    if "canonical_precinct_id" not in voter_df.columns:
        log.warning("[QUADRANTS] No canonical_precinct_id — cannot aggregate")
        return pd.DataFrame()

    if "quadrant" not in voter_df.columns:
        voter_df = assign_quadrant(voter_df)

    # Count per quadrant per precinct
    pivot = (
        voter_df.groupby(["canonical_precinct_id", "quadrant"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    # Ensure all quadrant columns present
    for q in ALL_QUADRANTS:
        if q not in pivot.columns:
            pivot[q] = 0
    pivot = pivot.rename(columns={q: f"{q}_count" for q in ALL_QUADRANTS if q in pivot.columns})

    # Totals
    totals = voter_df.groupby("canonical_precinct_id").size().reset_index(name="total_voters")
    pivot = pivot.merge(totals, on="canonical_precinct_id", how="left")

    # Pct columns
    for q in ALL_QUADRANTS:
        cnt = f"{q}_count"
        if cnt in pivot.columns:
            pivot[f"{q}_pct"] = (pivot[cnt] / pivot["total_voters"]).round(4)

    # TPS / PS averages
    for col in ["tps", "ps"]:
        if col in voter_df.columns:
            avg = voter_df.groupby("canonical_precinct_id")[col].mean().round(4).reset_index(name=f"avg_{col}")
            pivot = pivot.merge(avg, on="canonical_precinct_id", how="left")

    # Dominant quadrant (largest count)
    count_cols = [f"{q}_count" for q in ALL_QUADRANTS if f"{q}_count" in pivot.columns]
    if count_cols:
        pivot["dominant_quadrant"] = pivot[count_cols].idxmax(axis=1).str.replace("_count", "")

    log.info(f"[QUADRANTS] Aggregated across {len(pivot):,} precincts")
    return pivot


# ── Output Writers ──────────────────────────────────────────────────────────────

def write_targeting_quadrants(voter_df: pd.DataFrame, run_id: str) -> tuple[Path, Path]:
    """
    Write:
      1. Voter-level Parquet (local only, .gitignored via *.parquet in .gitignore)
      2. Precinct-level CSV (safe to commit)
    """
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    parquet_path = SEGMENTS_DIR / f"{run_id}__targeting_quadrants.parquet"
    try:
        voter_df.to_parquet(parquet_path, index=False)
        log.info(f"[QUADRANTS] Wrote voter quadrants: {parquet_path}")
    except Exception as e:
        log.warning(f"[QUADRANTS] Could not write Parquet: {e}")

    precinct_df = aggregate_quadrants_to_precinct(voter_df)
    csv_path = SEGMENTS_DIR / f"{run_id}__targeting_quadrants.csv"
    if not precinct_df.empty:
        precinct_df.to_csv(csv_path, index=False)
        log.info(f"[QUADRANTS] Wrote precinct quadrants: {csv_path}")

    return parquet_path, csv_path
