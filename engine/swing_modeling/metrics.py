"""
engine/swing_modeling/metrics.py — Prompt 26

Swing modeling evaluation metrics.

Computes:
  - Precision, Recall, F1 for swing detection
  - MAE for support change and turnout change prediction
  - Ranking usefulness (top-N coverage of true high-movement precincts)
  - Confidence-stratified evaluation
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class SwingMetrics:
    """Full evaluation metrics for one backtest fold."""
    held_out_year:        int
    total_precincts:      int

    # Swing detection classification metrics
    precision:            float
    recall:               float
    f1:                   float
    true_positives:       int
    false_positives:      int
    false_negatives:      int

    # Prediction error metrics
    support_mae:          float    # mean absolute error of support change prediction
    turnout_mae:          float    # mean absolute error of turnout change prediction

    # Ranking usefulness
    top10_true_rate:      float    # fraction of top-10 predicted that were truly high-movement
    top20_true_rate:      float
    top50_true_rate:      float

    # Confidence stratification
    high_conf_precision:  float    # precision among high-confidence predictions
    med_conf_precision:   float
    low_conf_precision:   float

    # Data sufficiency
    usable_precincts:     int
    low_data_precincts:   int

    # Verdict
    verdict:              str    # "useful" | "marginally_useful" | "insufficient_data" | "poor"


def compute_metrics(
    swing_scores: list,               # list[SwingResult] for training elections
    actual_swing_mask: dict,          # {precinct_id: bool} — True if actually swung
    actual_support_changes: dict,     # {precinct_id: float} — actual delta in support_rate
    actual_turnout_changes: dict,     # {precinct_id: float} — actual delta in turnout_rate
    held_out_year: int,
    threshold_score: float = 0.40,   # score threshold for "predicted swing"
    rules: Optional[dict] = None,
) -> SwingMetrics:
    """
    Compute full evaluation metrics for one backtest fold.

    Args:
        swing_scores:           predicted SwingResults (training years only)
        actual_swing_mask:      ground truth — which precincts actually swung
        actual_support_changes: actual support rate delta per precinct in held-out year
        actual_turnout_changes: actual turnout rate delta per precinct in held-out year
        held_out_year:          the election year held out
        threshold_score:        swing_score threshold to call "predicted swing"
        rules:                  swing_rules.yaml dict (optional)

    Returns:
        SwingMetrics
    """
    import numpy as np

    predicted_swing = {r.precinct for r in swing_scores if r.swing_score >= threshold_score}
    actual_swing    = {p for p, v in actual_swing_mask.items() if v}

    all_precincts = set(r.precinct for r in swing_scores)

    # Classification metrics
    tp = len(predicted_swing & actual_swing)
    fp = len(predicted_swing - actual_swing)
    fn = len(actual_swing - predicted_swing)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    # MAE for support and turnout changes
    support_errors, turnout_errors = [], []
    for r in swing_scores:
        if r.precinct in actual_support_changes:
            # Predicted: how much we expected support to move = swing_score * support_volatility
            predicted_delta = r.swing_score * r.support_volatility
            actual_delta    = abs(actual_support_changes[r.precinct])
            support_errors.append(abs(predicted_delta - actual_delta))
        if r.precinct in actual_turnout_changes:
            predicted_delta = r.swing_score * r.turnout_volatility
            actual_delta    = abs(actual_turnout_changes[r.precinct])
            turnout_errors.append(abs(predicted_delta - actual_delta))

    support_mae = float(np.mean(support_errors)) if support_errors else float("nan")
    turnout_mae = float(np.mean(turnout_errors)) if turnout_errors else float("nan")

    # Ranking usefulness — sort by swing_score descending
    sorted_scores = sorted(swing_scores, key=lambda r: r.swing_score, reverse=True)

    def top_n_rate(n: int) -> float:
        top = sorted_scores[:n]
        if not top:
            return 0.0
        hits = sum(1 for r in top if actual_swing_mask.get(r.precinct, False))
        return round(hits / len(top), 4)

    top10 = top_n_rate(10)
    top20 = top_n_rate(20)
    top50 = top_n_rate(50)

    # Confidence stratification
    def conf_precision(conf_min: float, conf_max: float) -> float:
        tier = [r for r in swing_scores if conf_min <= r.confidence < conf_max
                and r.swing_score >= threshold_score]
        if not tier:
            return float("nan")
        hits = sum(1 for r in tier if actual_swing_mask.get(r.precinct, False))
        return round(hits / len(tier), 4)

    high_conf_prec = conf_precision(0.75, 1.01)
    med_conf_prec  = conf_precision(0.50, 0.75)
    low_conf_prec  = conf_precision(0.00, 0.50)

    # Data sufficiency
    low_data = sum(1 for r in swing_scores if r.elections_counted < 2)

    # Verdict
    if len(all_precincts) < 5:
        verdict = "insufficient_data"
    elif f1 >= 0.60:
        verdict = "useful"
    elif f1 >= 0.35:
        verdict = "marginally_useful"
    else:
        verdict = "poor"

    return SwingMetrics(
        held_out_year=held_out_year,
        total_precincts=len(all_precincts),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        true_positives=tp, false_positives=fp, false_negatives=fn,
        support_mae=round(support_mae, 6) if not (support_mae != support_mae) else 0.0,
        turnout_mae=round(turnout_mae, 6) if not (turnout_mae != turnout_mae) else 0.0,
        top10_true_rate=top10, top20_true_rate=top20, top50_true_rate=top50,
        high_conf_precision=high_conf_prec if not (high_conf_prec != high_conf_prec) else 0.0,
        med_conf_precision=med_conf_prec   if not (med_conf_prec  != med_conf_prec)  else 0.0,
        low_conf_precision=low_conf_prec   if not (low_conf_prec  != low_conf_prec)  else 0.0,
        usable_precincts=len(all_precincts) - low_data,
        low_data_precincts=low_data,
        verdict=verdict,
    )
