"""
engine/archive/election_similarity.py — Prompt 24 Rebuild

Ranks historical elections by similarity to the active contest.
Uses multi-factor scoring on:
  - contest type match
  - turnout environment (mean and variance)
  - support distribution shape
  - jurisdiction match
  - macro context (if available)

Output is machine-usable: strategy and calibration engines can
weight historical data by similarity score.

Requires: derived/archive/normalized_elections.csv
          derived/archive/precinct_profiles.csv
          config/campaign_config.yaml
Outputs:  derived/archive/similar_elections.csv
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
DERIVED_DIR = BASE_DIR / "derived" / "archive"


def _load_campaign_config() -> dict:
    try:
        import yaml
        p = BASE_DIR / "config" / "campaign_config.yaml"
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def compute_similarity(
    elections_df: pd.DataFrame,
    active_contest_type: str,
    active_county: str,
    active_state: str,
    active_turnout_prior: float = 0.45,
    active_support_prior: float = 0.50,
) -> pd.DataFrame:
    """
    Score each historical election by similarity to the active contest.

    Similarity components (weighted sum → 0-1 score):
      1. Contest type match (0.35 weight)
      2. Jurisdiction match (0.20 weight)
      3. Turnout proximity (0.25 weight) — |historical_mean - active_prior|
      4. Support proximity (0.20 weight) — |historical_support_mean - active_prior|

    Returns DataFrame with columns:
      contest, year, county, state, contest_type,
      historical_turnout_mean, historical_support_mean,
      similarity_score, rank
    """
    # Aggregate elections to contest level
    agg = elections_df.groupby(["contest", "year", "county", "state", "contest_type"]).agg(
        hist_turnout_mean=("turnout_rate", "mean"),
        hist_turnout_sd=("turnout_rate", "std"),
        hist_support_mean=("support_rate", "mean"),
        hist_support_sd=("support_rate", "std"),
        precincts=("precinct", "nunique"),
        provenance=("provenance", "first"),
    ).reset_index()

    agg["hist_turnout_sd"]  = agg["hist_turnout_sd"].fillna(0.0)
    agg["hist_support_sd"]  = agg["hist_support_sd"].fillna(0.0)

    # ── Scoring ──────────────────────────────────────────────────────────────

    # 1. Contest type match
    agg["_type_score"] = agg["contest_type"].apply(
        lambda ct: 1.0 if ct == active_contest_type
        else 0.6 if ct in ("local_special", "local_general") and active_contest_type in ("local_special", "local_general")
        else 0.3
    )

    # 2. Jurisdiction match
    agg["_juris_score"] = (
        (agg["county"] == active_county).astype(float) * 0.7
        + (agg["state"] == active_state).astype(float) * 0.3
    )

    # 3. Turnout proximity (0 = perfect match, penalize distance)
    agg["_turnout_score"] = 1 - np.clip(
        np.abs(agg["hist_turnout_mean"].fillna(active_turnout_prior) - active_turnout_prior) * 5,
        0, 1
    )

    # 4. Support proximity
    agg["_support_score"] = 1 - np.clip(
        np.abs(agg["hist_support_mean"].fillna(active_support_prior) - active_support_prior) * 5,
        0, 1
    )

    # Weighted sum
    agg["similarity_score"] = (
        agg["_type_score"]    * 0.35
        + agg["_juris_score"] * 0.20
        + agg["_turnout_score"] * 0.25
        + agg["_support_score"] * 0.20
    ).round(4)

    agg = agg.sort_values("similarity_score", ascending=False).reset_index(drop=True)
    agg["rank"] = agg.index + 1

    # Drop scoring internals
    result = agg.drop(columns=[c for c in agg.columns if c.startswith("_")])
    return result


def run_similarity(run_id: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Run election similarity scoring using active campaign config.
    """
    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M%S") + "__similarity"

    elections_path = DERIVED_DIR / "normalized_elections.csv"
    if not elections_path.exists():
        log.error("[SIMILARITY] normalized_elections.csv not found — run archive_ingest first")
        return None

    elections_df = pd.read_csv(elections_path)
    for col in ["turnout_rate", "support_rate"]:
        elections_df[col] = pd.to_numeric(elections_df[col], errors="coerce")

    cfg = _load_campaign_config()
    active_type   = cfg.get("campaign", {}).get("contest_type", "ballot_measure")
    active_county = cfg.get("campaign", {}).get("county", "")
    active_state  = cfg.get("campaign", {}).get("state", "CA")
    turnout_prior = 0.45  # default if no calibration available
    support_prior = 0.50

    result = compute_similarity(
        elections_df,
        active_contest_type=active_type,
        active_county=active_county,
        active_state=active_state,
        active_turnout_prior=turnout_prior,
        active_support_prior=support_prior,
    )

    out = DERIVED_DIR / "similar_elections.csv"
    result.to_csv(out, index=False)
    log.info(f"[SIMILARITY] Wrote {len(result)} elections ranked by similarity → {out}")

    # Log top 3
    for _, row in result.head(3).iterrows():
        log.info(f"[SIMILARITY] #{int(row['rank'])}: {row['contest']} ({row['year']}) "
                 f"score={row['similarity_score']:.3f} type={row['contest_type']}")

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_similarity()
    print("Election similarity scoring complete.")
