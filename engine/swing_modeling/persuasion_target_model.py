"""
engine/swing_modeling/persuasion_target_model.py — Prompt 26

Persuasion target classifier.

A precinct is a PERSUASION_PRIMARY target when:
  - avg_support is within the competitive window (e.g. 30–65%)
  - support_volatility is meaningful (movable)
  - turnout is not the dominant limiting factor
  - confidence is sufficient

Output labels per precinct:
  PERSUASION_PRIMARY
  NOT_PERSUASION

A precinct may also be labeled MIXED in the final combined output if
it qualifies for both persuasion and turnout targets. That combination
is resolved in __init__ / run_targeting().
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)
RULES_PATH = Path(__file__).resolve().parent / "swing_rules.yaml"


def _load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}


@dataclass
class PersuasionResult:
    precinct:           str
    state:              str
    county:             str
    persuasion_label:   str     # PERSUASION_PRIMARY | NOT_PERSUASION
    support_in_window:  bool
    support_movable:    bool
    turnout_dominant:   bool
    confidence:         float
    avg_support:        Optional[float]
    support_sd:         float
    avg_turnout:        Optional[float]
    rationale:          str


def classify_persuasion(swing_result) -> PersuasionResult:
    """
    Classify whether a precinct is a persuasion target based on its SwingResult.

    A precinct qualifies as PERSUASION_PRIMARY if:
      1. avg_support is in the competitive window (30–65%)
      2. support_volatility >= min_support_sd (support is movable)
      3. The turnout component does NOT dominate over the support component

    Args:
        swing_result:  SwingResult from swing_detector

    Returns:
        PersuasionResult
    """
    rules   = _load_rules()
    tgt     = rules.get("targeting", {})
    window  = tgt.get("persuasion_support_window", [0.30, 0.65])
    min_sd  = tgt.get("persuasion_min_support_sd", 0.03)
    max_to_dom = tgt.get("persuasion_max_turnout_dominance", 0.60)

    avg_sup = swing_result.avg_support
    sup_sd  = swing_result.support_volatility
    avg_to  = swing_result.avg_turnout
    conf    = swing_result.confidence

    # Check each condition
    support_in_window = (
        avg_sup is not None
        and window[0] <= avg_sup <= window[1]
    )
    support_movable = sup_sd >= min_sd

    # Is turnout the dominant variable?
    # Defined as: turnout_volatility * 2 > support_volatility (turnout swings more)
    turnout_dominant = (
        swing_result.turnout_volatility * 2.0 > swing_result.support_volatility
        and (avg_to is not None and avg_to < 0.55)
    )

    qualifies = support_in_window and support_movable and not turnout_dominant

    reasons = []
    if not support_in_window:
        reasons.append(f"avg_support={avg_sup:.3f} outside window {window}")
    if not support_movable:
        reasons.append(f"support_sd={sup_sd:.3f} < min {min_sd}")
    if turnout_dominant:
        reasons.append(f"turnout_volatility dominates support_volatility")

    label = "PERSUASION_PRIMARY" if qualifies else "NOT_PERSUASION"
    rationale = "; ".join(reasons) if reasons else "all persuasion conditions met"

    return PersuasionResult(
        precinct=swing_result.precinct, state=swing_result.state, county=swing_result.county,
        persuasion_label=label, support_in_window=support_in_window,
        support_movable=support_movable, turnout_dominant=turnout_dominant,
        confidence=conf, avg_support=avg_sup, support_sd=sup_sd,
        avg_turnout=avg_to, rationale=rationale,
    )


def run_persuasion_targeting(swing_results: list, run_id: Optional[str] = None) -> list[PersuasionResult]:
    """
    Classify all precincts for persuasion potential.

    Args:
        swing_results: list[SwingResult]
        run_id:        run identifier

    Returns:
        list[PersuasionResult]
    """
    from datetime import datetime
    import pandas as pd

    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M")
    results = [classify_persuasion(r) for r in swing_results]

    # Write output
    out_dir = Path(__file__).resolve().parent.parent.parent / "derived" / "swing_modeling"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([r.__dict__ for r in results])
    out = out_dir / f"{run_id}__persuasion_targets.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    log.info(f"[PERSUASION] {sum(1 for r in results if r.persuasion_label == 'PERSUASION_PRIMARY')} persuasion targets → {out}")
    return results
