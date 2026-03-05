"""
scripts/simulation/simulation_engine.py

Simulation Engine — deterministic forecast + Monte Carlo simulation.
Produces per-precinct vote estimates and win probability distributions.

Modes:
  deterministic — expected_votes_for/against/margin per precinct
  monte_carlo   — 1000 iterations with turnout/support random variance
  both          — runs deterministic then Monte Carlo
"""
from __future__ import annotations

import sys
import datetime
import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_ITERATIONS       = 1000
DEFAULT_TURNOUT_VARIANCE = 0.03
DEFAULT_SUPPORT_VARIANCE = 0.02
SEED                     = 42


# ══════════════════════════════════════════════════════════════════════════════
# Deterministic Forecast
# ══════════════════════════════════════════════════════════════════════════════
def run_deterministic_forecast(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each precinct compute expected votes for/against and margin.

    Required columns (at least one pairing):
      - registered, turnout_pct, support_pct   (canonical)
      - OR registered, ballots_cast, support_pct
    """
    out = df.copy()

    # Normalise column names
    if "canonical_precinct_id" in out.columns:
        out = out.rename(columns={"canonical_precinct_id": "precinct_id"})

    reg = pd.to_numeric(out.get("registered", out.get("Registered", pd.Series(dtype=float))),
                        errors="coerce").fillna(0)

    # Turnout
    if "turnout_pct" in out.columns:
        tp = pd.to_numeric(out["turnout_pct"], errors="coerce").fillna(0)
        # If > 1 it was already expressed as pct (0-100)
        tp = tp.where(tp <= 1.0, tp / 100.0)
        votes = reg * tp
    elif "ballots_cast" in out.columns or "Ballots Cast" in out.columns:
        bc_col = "ballots_cast" if "ballots_cast" in out.columns else "Ballots Cast"
        votes = pd.to_numeric(out[bc_col], errors="coerce").fillna(0)
        tp = (votes / reg.replace(0, np.nan)).fillna(0)
    else:
        tp = pd.Series([0.5] * len(out))
        votes = reg * 0.5

    # Support
    sp_col = next((c for c in ["support_pct", "YesPct", "yes_pct", "TargetChoicePct"]
                   if c in out.columns), None)
    if sp_col:
        sp = pd.to_numeric(out[sp_col], errors="coerce").fillna(0.5)
        sp = sp.where(sp <= 1.0, sp / 100.0)
    else:
        sp = pd.Series([0.5] * len(out))

    votes_for     = (votes * sp).round(1)
    votes_against = (votes * (1 - sp)).round(1)
    margin        = (votes_for - votes_against).round(1)

    result = pd.DataFrame({
        "precinct_id":     out.get("precinct_id", out.index.astype(str)),
        "registered":      reg.round(0).astype(int),
        "turnout_pct":     tp.round(4),
        "support_pct":     sp.round(4),
        "votes_for":       votes_for,
        "votes_against":   votes_against,
        "margin":          margin,
    })
    return result.sort_values("margin", ascending=False).reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# Monte Carlo Simulation
# ══════════════════════════════════════════════════════════════════════════════
def run_monte_carlo(
    df: pd.DataFrame,
    iterations:       int   = DEFAULT_ITERATIONS,
    turnout_variance: float = DEFAULT_TURNOUT_VARIANCE,
    support_variance: float = DEFAULT_SUPPORT_VARIANCE,
    scenarios: Optional[list[str]] = None,
    seed: int = SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run Monte Carlo simulation.

    Returns:
        (simulation_results_df, scenario_summary_df)
    """
    rng = np.random.default_rng(seed)

    if scenarios is None:
        scenarios = [
            "baseline",
            "field_program_light",
            "field_program_medium",
            "field_program_heavy",
        ]

    # Extract base arrays
    det = run_deterministic_forecast(df)
    registered = det["registered"].values.astype(float)
    base_tp    = det["turnout_pct"].values
    base_sp    = det["support_pct"].values

    # Scenario field effect multipliers on support
    scenario_effects = {
        "baseline":              0.00,
        "field_program_light":   0.01,
        "field_program_medium":  0.02,
        "field_program_heavy":   0.035,
    }

    rows = []
    for scenario in scenarios:
        effect = scenario_effects.get(scenario, 0.0)
        for i in range(iterations):
            # Randomise
            tp_sim = np.clip(base_tp + rng.normal(0, turnout_variance, len(base_tp)), 0.01, 0.99)
            sp_sim = np.clip(base_sp + rng.normal(0, support_variance, len(base_sp)) + effect, 0.01, 0.99)

            votes_for     = float((registered * tp_sim * sp_sim).sum())
            votes_against = float((registered * tp_sim * (1 - sp_sim)).sum())
            margin        = votes_for - votes_against
            avg_turnout   = float(tp_sim.mean())

            rows.append({
                "scenario":           scenario,
                "iteration":          i + 1,
                "expected_votes_for": round(votes_for, 0),
                "expected_votes_against": round(votes_against, 0),
                "margin":             round(margin, 0),
                "avg_turnout":        round(avg_turnout, 4),
                "win":                int(margin > 0),
            })

    sim_df = pd.DataFrame(rows)

    # Scenario summary
    summary_rows = []
    for scenario in scenarios:
        sub = sim_df[sim_df["scenario"] == scenario]
        summary_rows.append({
            "scenario":        scenario,
            "win_probability": round(float(sub["win"].mean()), 4),
            "median_margin":   round(float(sub["margin"].median()), 0),
            "p10_margin":      round(float(sub["margin"].quantile(0.10)), 0),
            "p90_margin":      round(float(sub["margin"].quantile(0.90)), 0),
            "avg_turnout":     round(float(sub["avg_turnout"].mean()), 4),
        })

    summary_df = pd.DataFrame(summary_rows)
    return sim_df, summary_df


# ══════════════════════════════════════════════════════════════════════════════
# Write outputs
# ══════════════════════════════════════════════════════════════════════════════
def write_simulation_outputs(
    det_df: pd.DataFrame,
    sim_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    state: str,
    county: str,
    contest: str,
    run_id: str,
) -> dict[str, Path]:
    out_dir = BASE_DIR / "derived" / "simulation" / state / county / contest
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {}
    if not det_df.empty:
        p = out_dir / f"{run_id}__deterministic_forecast.csv"
        det_df.to_csv(p, index=False)
        paths["deterministic_forecast"] = p

    if not sim_df.empty:
        p = out_dir / f"{run_id}__simulation_results.csv"
        sim_df.to_csv(p, index=False)
        paths["simulation_results"] = p

    if not summary_df.empty:
        p = out_dir / f"{run_id}__scenario_summary.csv"
        summary_df.to_csv(p, index=False)
        paths["scenario_summary"] = p

    return paths


# ══════════════════════════════════════════════════════════════════════════════
# Public entry point
# ══════════════════════════════════════════════════════════════════════════════
def run_simulation(
    model_df: pd.DataFrame,
    state: str,
    county: str,
    contest: str,
    run_id: str,
    mode: str = "both",
    iterations: int = DEFAULT_ITERATIONS,
    turnout_variance: float = DEFAULT_TURNOUT_VARIANCE,
    support_variance: float = DEFAULT_SUPPORT_VARIANCE,
    logger=None,
) -> dict:
    """
    Main entry point. Returns dict with:
      - paths: written file paths
      - deterministic: DataFrame
      - simulation_results: DataFrame
      - scenario_summary: DataFrame
      - win_probability: float (baseline)
    """
    if logger: logger.info(f"[SIM] mode={mode} on {len(model_df)} precincts")

    det_df     = pd.DataFrame()
    sim_df     = pd.DataFrame()
    summary_df = pd.DataFrame()

    if mode in ("deterministic", "both"):
        det_df = run_deterministic_forecast(model_df)
        if logger: logger.info(f"[SIM] Deterministic: {len(det_df)} rows, total_margin={det_df['margin'].sum():+.0f}")

    source_df = model_df if not det_df.empty else model_df
    if mode in ("monte_carlo", "both") and len(source_df) > 0:
        sim_df, summary_df = run_monte_carlo(
            source_df,
            iterations=iterations,
            turnout_variance=turnout_variance,
            support_variance=support_variance,
        )
        baseline_wp = float(summary_df.loc[summary_df["scenario"] == "baseline", "win_probability"].iloc[0]) \
            if "baseline" in summary_df["scenario"].values else 0.0
        if logger: logger.info(f"[SIM] Monte Carlo: {len(sim_df)} rows, baseline win_prob={baseline_wp:.1%}")

    paths = write_simulation_outputs(det_df, sim_df, summary_df, state, county, contest, run_id)

    baseline_row = summary_df[summary_df["scenario"] == "baseline"].iloc[0] if not summary_df.empty else None
    win_prob = float(baseline_row["win_probability"]) if baseline_row is not None else None
    median_margin = float(baseline_row["median_margin"]) if baseline_row is not None else None

    return {
        "paths":               paths,
        "deterministic":       det_df,
        "simulation_results":  sim_df,
        "scenario_summary":    summary_df,
        "win_probability":     win_prob,
        "median_margin":       median_margin,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Simulation Engine")
    parser.add_argument("--input",    required=True, help="Path to precinct_model CSV")
    parser.add_argument("--state",    default="CA")
    parser.add_argument("--county",   required=True)
    parser.add_argument("--contest",  required=True)
    parser.add_argument("--run-id",   default=datetime.datetime.now().strftime("%Y-%m-%d__%H%M%S__manual"))
    parser.add_argument("--mode",     default="both", choices=["deterministic", "monte_carlo", "both"])
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    result = run_simulation(df, args.state, args.county, args.contest, args.run_id, args.mode, args.iterations)
    print(f"\nSimulation complete:")
    for k, v in result["paths"].items():
        print(f"  {k}: {v}")
    if result["win_probability"] is not None:
        print(f"\n  Baseline Win Probability: {result['win_probability']:.1%}")
        print(f"  Median Margin:            {result['median_margin']:+,.0f} votes")
