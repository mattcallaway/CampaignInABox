# engine/swing_modeling/__init__.py — Prompt 26
"""
Backtested Swing Precinct Detection & Persuasion Target Modeling

Public API:
  from engine.swing_modeling import run_swing_detection, run_backtest
  from engine.swing_modeling import run_persuasion_targeting, run_turnout_targeting
"""
from engine.swing_modeling.swing_detector import run_swing_detection, SwingResult
from engine.swing_modeling.persuasion_target_model import run_persuasion_targeting, PersuasionResult
from engine.swing_modeling.turnout_opportunity_model import run_turnout_targeting, TurnoutResult, combine_labels
from engine.swing_modeling.backtester import run_backtest, BacktestSummary
from engine.swing_modeling.metrics import compute_metrics, SwingMetrics

__all__ = [
    "run_swing_detection", "SwingResult",
    "run_persuasion_targeting", "PersuasionResult",
    "run_turnout_targeting", "TurnoutResult", "combine_labels",
    "run_backtest", "BacktestSummary",
    "compute_metrics", "SwingMetrics",
]
