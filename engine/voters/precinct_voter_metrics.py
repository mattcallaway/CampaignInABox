"""
engine/voters/precinct_voter_metrics.py — Prompt 12

Rolls up voter-level TPS, PS, and quadrant data to precinct-level metrics
and merges with the precinct model for use by the advanced modeling engine.

Output:
  derived/voter_models/<run_id>__precinct_voter_metrics.csv  (safe to commit)
  reports/validation/voter_model_validation.md
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
VOTER_MODELS_DIR = BASE_DIR / "derived" / "voter_models"
REPORTS_DIR = BASE_DIR / "reports" / "validation"

log = logging.getLogger(__name__)


def build_precinct_voter_metrics(
    voter_df: pd.DataFrame,
    precinct_model_df: Optional[pd.DataFrame] = None,
    run_id: str = "latest",
) -> pd.DataFrame:
    """
    Build a comprehensive precinct-level voter metrics table.

    Combines TPS, PS, and quadrant data into one clean DataFrame per precinct.
    Optionally merges with the precinct model.

    Returns: precinct_metrics_df
    """
    required = ["canonical_precinct_id", "tps", "ps", "quadrant"]
    missing = [c for c in required if c not in voter_df.columns]
    if missing:
        log.warning(f"[VOTER_METRICS] Missing columns {missing} — metrics may be incomplete")

    if "canonical_precinct_id" not in voter_df.columns:
        return pd.DataFrame()

    grp = voter_df.groupby("canonical_precinct_id")

    # Core counts
    metrics = grp.size().reset_index(name="total_voters_on_file")

    # TPS metrics
    if "tps" in voter_df.columns:
        tps_agg = grp["tps"].agg(
            avg_tps="mean",
            median_tps="median",
            p90_tps=lambda x: x.quantile(0.90),
        ).round(4).reset_index()
        metrics = metrics.merge(tps_agg, on="canonical_precinct_id", how="left")

        hp = (voter_df["tps"] >= 0.60).groupby(voter_df["canonical_precinct_id"]).sum()
        lp = (voter_df["tps"] < 0.30).groupby(voter_df["canonical_precinct_id"]).sum()
        metrics = metrics.merge(hp.rename("high_propensity_count").reset_index(), on="canonical_precinct_id", how="left")
        metrics = metrics.merge(lp.rename("low_propensity_count").reset_index(), on="canonical_precinct_id", how="left")
        metrics["high_propensity_pct"] = (metrics["high_propensity_count"] / metrics["total_voters_on_file"]).round(4)
        metrics["low_propensity_pct"] = (metrics["low_propensity_count"] / metrics["total_voters_on_file"]).round(4)

    # PS metrics
    if "ps" in voter_df.columns:
        ps_agg = grp["ps"].agg(
            avg_ps="mean",
            median_ps="median",
        ).round(4).reset_index()
        metrics = metrics.merge(ps_agg, on="canonical_precinct_id", how="left")

        persuadable = (voter_df["ps"] >= 0.60).groupby(voter_df["canonical_precinct_id"]).sum()
        metrics = metrics.merge(persuadable.rename("persuadable_count").reset_index(), on="canonical_precinct_id", how="left")
        metrics["persuadable_pct"] = (metrics["persuadable_count"] / metrics["total_voters_on_file"]).round(4)

    # Quadrant counts
    if "quadrant" in voter_df.columns:
        from engine.voters.targeting_quadrants import ALL_QUADRANTS
        q_pivot = (
            voter_df.groupby(["canonical_precinct_id", "quadrant"])
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        for q in ALL_QUADRANTS:
            if q not in q_pivot.columns:
                q_pivot[q] = 0
            q_pivot = q_pivot.rename(columns={q: f"{q}_count"})
        metrics = metrics.merge(q_pivot, on="canonical_precinct_id", how="left")

    # Party breakdown
    if "party_normalized" in voter_df.columns:
        for party, label in [("D", "dem"), ("R", "rep"), ("N", "ind")]:
            cnt = (voter_df["party_normalized"] == party).groupby(voter_df["canonical_precinct_id"]).sum()
            metrics = metrics.merge(
                cnt.rename(f"{label}_count").reset_index(),
                on="canonical_precinct_id", how="left"
            )

    # Merge with precinct model if provided
    if precinct_model_df is not None and not precinct_model_df.empty:
        if "canonical_precinct_id" in precinct_model_df.columns:
            metrics = precinct_model_df.merge(
                metrics, on="canonical_precinct_id", how="left"
            )

    log.info(f"[VOTER_METRICS] Built metrics for {len(metrics):,} precincts, {len(metrics.columns)} columns")
    return metrics


def write_precinct_voter_metrics(metrics_df: pd.DataFrame, run_id: str) -> Path:
    """Write precinct voter metrics CSV (safe to commit)."""
    VOTER_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VOTER_MODELS_DIR / f"{run_id}__precinct_voter_metrics.csv"
    metrics_df.to_csv(out_path, index=False)
    log.info(f"[VOTER_METRICS] Wrote: {out_path}")
    return out_path


def write_voter_model_validation(
    voter_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    run_id: str,
) -> Path:
    """Write a markdown validation report for the voter model."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{run_id}__voter_model_validation.md"

    n_voters = len(voter_df)
    n_precincts = voter_df["canonical_precinct_id"].nunique() if "canonical_precinct_id" in voter_df.columns else 0
    match_rate = n_precincts / max(len(metrics_df), 1)

    lines = [
        f"# Voter Model Validation Report\n",
        f"**Run ID:** `{run_id}`\n",
        f"\n## Voter File Coverage\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total voters on file | {n_voters:,} |",
        f"| Precincts with voter data | {n_precincts:,} |",
        f"| Precinct match rate | {match_rate:.1%} |",
    ]

    if "tps" in voter_df.columns:
        tps = voter_df["tps"].dropna()
        lines += [
            f"\n## Turnout Propensity Score (TPS) Distribution\n",
            f"| Statistic | Value |",
            f"|-----------|-------|",
            f"| Mean | {tps.mean():.3f} |",
            f"| Std | {tps.std():.3f} |",
            f"| P10 | {tps.quantile(0.10):.3f} |",
            f"| P50 | {tps.quantile(0.50):.3f} |",
            f"| P90 | {tps.quantile(0.90):.3f} |",
        ]
        # Distribution warning
        if tps.std() < 0.05:
            lines.append(f"\n> ⚠️ **Warning:** TPS std={tps.std():.3f} is very low — check vote history column detection.\n")

    if "ps" in voter_df.columns:
        ps = voter_df["ps"].dropna()
        lines += [
            f"\n## Persuasion Score (PS) Distribution\n",
            f"| Statistic | Value |",
            f"|-----------|-------|",
            f"| Mean | {ps.mean():.3f} |",
            f"| Std | {ps.std():.3f} |",
            f"| P10 | {ps.quantile(0.10):.3f} |",
            f"| P50 | {ps.quantile(0.50):.3f} |",
            f"| P90 | {ps.quantile(0.90):.3f} |",
        ]

    if "quadrant" in voter_df.columns:
        lines.append(f"\n## Targeting Universe Sizes\n")
        lines.append(f"| Quadrant | Voters | % |")
        lines.append(f"|----------|--------|---|")
        for q, cnt in voter_df["quadrant"].value_counts().items():
            pct = cnt / n_voters * 100
            lines.append(f"| {q} | {cnt:,} | {pct:.1f}% |")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[VOTER_METRICS] Wrote validation report: {out_path}")
    return out_path
