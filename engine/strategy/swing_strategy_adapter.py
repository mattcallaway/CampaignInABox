"""
engine/strategy/swing_strategy_adapter.py — Prompt 26

Validation-aware adapter between the swing modeling system
and the strategy engine.

This adapter lets the strategy engine OPTIONALLY consume
swing model outputs — but only when backtest quality is sufficient.

Strategy engine output labels:
  ACTIVE_VALIDATED              — swing targeting used, backtest confirmed
  ACTIVE_LOW_CONFIDENCE         — swing targeting used with caveats
  DISABLED_INSUFFICIENT_BACKTEST — not enough historical data to validate

   Usage in generate_strategy_bundle:
     from engine.strategy.swing_strategy_adapter import load_swing_inputs
     swing = load_swing_inputs(run_id)
     bundle["swing"] = swing
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SWING_DIR   = BASE_DIR / "derived" / "swing_modeling"
REPORTS_DIR = BASE_DIR / "reports"  / "swing_modeling"

# Minimum avg_f1 required to use swing outputs in strategy
VALIDATION_THRESHOLD = 0.50


def load_swing_inputs(run_id: Optional[str] = None) -> dict:
    """
    Load swing model outputs for the strategy engine.

    Resolves the most recent backtest_summary.json in
    derived/swing_modeling/ unless run_id is provided.

    Returns a dict with:
      backtest_status:  ACTIVE_VALIDATED | ACTIVE_LOW_CONFIDENCE | DISABLED_INSUFFICIENT_BACKTEST
      avg_f1:           float
      top_swing_precincts: list[dict]
      persuasion_targets:  list[dict]
      turnout_targets:     list[dict]
      use_swing:           bool — True only when backtest quality is sufficient
      rationale:           str — human-readable reason for status
    """
    # Find the right backtest summary
    summary_path = _find_summary(run_id)
    if summary_path is None:
        return _insufficient_result("No backtest_summary.json found in derived/swing_modeling/")

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as e:
        return _insufficient_result(f"Could not load backtest summary: {e}")

    status  = summary.get("backtest_status", "DISABLED_INSUFFICIENT_BACKTEST")
    avg_f1  = summary.get("avg_f1", 0.0)
    run_id_ = summary.get("run_id", "unknown")
    use_swing = avg_f1 >= VALIDATION_THRESHOLD

    # Load swing scores
    top_swing = _load_csv_as_list(SWING_DIR / f"{run_id_}__swing_scores.csv",
                                  limit=50, filter_col="swing_class", filter_vals=["high_swing", "moderate_swing"])
    persuasion = _load_csv_as_list(SWING_DIR / f"{run_id_}__persuasion_targets.csv",
                                   limit=50, filter_col="persuasion_label", filter_vals=["PERSUASION_PRIMARY"])
    turnout    = _load_csv_as_list(SWING_DIR / f"{run_id_}__turnout_targets.csv",
                                   limit=50, filter_col="turnout_label", filter_vals=["TURNOUT_PRIMARY"])

    if use_swing:
        rationale = (
            f"Swing targeting ACTIVE: backtest validated ({summary.get('folds_run', 0)} folds, "
            f"avg F1={avg_f1:.2f}). Top {len(top_swing)} swing precincts identified."
        )
    elif status == "ACTIVE_LOW_CONFIDENCE":
        rationale = (
            f"Swing targeting ACTIVE with LOW CONFIDENCE: F1={avg_f1:.2f} is below threshold={VALIDATION_THRESHOLD}. "
            f"Use with caution."
        )
    else:
        rationale = (
            f"Swing targeting DISABLED: {summary.get('data_sufficiency_note', 'insufficient backtest data')})"
        )

    log.info(f"[SWING_ADAPTER] status={status} use_swing={use_swing} avg_f1={avg_f1:.3f}")

    return {
        "backtest_status":       status,
        "avg_f1":                avg_f1,
        "avg_precision":         summary.get("avg_precision", 0.0),
        "avg_recall":            summary.get("avg_recall", 0.0),
        "folds_run":             summary.get("folds_run", 0),
        "years_available":       summary.get("years_available", []),
        "top_swing_precincts":   top_swing,
        "persuasion_targets":    persuasion,
        "turnout_targets":       turnout,
        "use_swing":             use_swing,
        "rationale":             rationale,
        "run_id":                run_id_,
    }


def _find_summary(run_id: Optional[str]) -> Optional[Path]:
    if run_id:
        p = SWING_DIR / f"{run_id}__backtest_summary.json"
        return p if p.exists() else None
    # Find most recent
    candidates = sorted(SWING_DIR.glob("*__backtest_summary.json"), reverse=True)
    return candidates[0] if candidates else None


def _load_csv_as_list(
    path: Path,
    limit: int = 50,
    filter_col: Optional[str] = None,
    filter_vals: Optional[list] = None,
) -> list[dict]:
    if not path.exists():
        return []
    try:
        import pandas as pd
        df = pd.read_csv(path)
        if filter_col and filter_vals and filter_col in df.columns:
            df = df[df[filter_col].isin(filter_vals)]
        return df.head(limit).to_dict(orient="records")
    except Exception as e:
        log.debug(f"[SWING_ADAPTER] Could not load {path.name}: {e}")
        return []


def _insufficient_result(reason: str) -> dict:
    return {
        "backtest_status":       "DISABLED_INSUFFICIENT_BACKTEST",
        "avg_f1":                0.0,
        "avg_precision":         0.0,
        "avg_recall":            0.0,
        "folds_run":             0,
        "years_available":       [],
        "top_swing_precincts":   [],
        "persuasion_targets":    [],
        "turnout_targets":       [],
        "use_swing":             False,
        "rationale":             reason,
        "run_id":                None,
    }
