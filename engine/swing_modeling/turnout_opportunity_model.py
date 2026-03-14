"""
engine/swing_modeling/turnout_opportunity_model.py — Prompt 26

Turnout opportunity classifier.

A precinct is a TURNOUT_PRIMARY target when:
  - avg_support is already favorable (>= 52%)
  - avg_turnout is suppressed (<= 55%)
  - turnout_volatility shows it is movable (>= 3pp SD)
  - turnout should be more impactful than persuasion

A precinct should NOT automatically be both persuasion and turnout
unless both signal sets are independently strong (resolved to MIXED).

Output labels per precinct:
  TURNOUT_PRIMARY
  NOT_TURNOUT
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
class TurnoutResult:
    precinct:           str
    state:              str
    county:             str
    turnout_label:      str     # TURNOUT_PRIMARY | NOT_TURNOUT
    support_favorable:  bool
    turnout_suppressed: bool
    turnout_movable:    bool
    confidence:         float
    avg_support:        Optional[float]
    avg_turnout:        Optional[float]
    turnout_sd:         float
    rationale:          str


def classify_turnout_opportunity(swing_result) -> TurnoutResult:
    """
    Classify whether a precinct is a turnout opportunity based on its SwingResult.

    A precinct qualifies as TURNOUT_PRIMARY if:
      1. avg_support >= favorable_min (support is already on our side)
      2. avg_turnout <= opportunity_max (turnout is suppressed)
      3. turnout_volatility >= min_volatility (turnout can be moved)

    Args:
        swing_result:  SwingResult from swing_detector

    Returns:
        TurnoutResult
    """
    rules    = _load_rules()
    tgt      = rules.get("targeting", {})
    fav_min  = tgt.get("turnout_favorable_min", 0.52)
    to_max   = tgt.get("turnout_opportunity_max_rate", 0.55)
    to_min_v = tgt.get("turnout_min_volatility", 0.03)

    avg_sup = swing_result.avg_support
    avg_to  = swing_result.avg_turnout
    to_sd   = swing_result.turnout_volatility
    conf    = swing_result.confidence

    support_favorable  = avg_sup is not None and avg_sup >= fav_min
    turnout_suppressed = avg_to  is not None and avg_to  <= to_max
    turnout_movable    = to_sd   >= to_min_v

    qualifies = support_favorable and turnout_suppressed and turnout_movable

    reasons = []
    if not support_favorable:
        sup_str = f"{avg_sup:.3f}" if avg_sup is not None else "N/A"
        reasons.append(f"avg_support={sup_str} < {fav_min}")
    if not turnout_suppressed:
        to_str = f"{avg_to:.3f}" if avg_to is not None else "N/A"
        reasons.append(f"avg_turnout={to_str} > {to_max}")
    if not turnout_movable:
        reasons.append(f"turnout_sd={to_sd:.3f} < min {to_min_v}")

    label = "TURNOUT_PRIMARY" if qualifies else "NOT_TURNOUT"
    rationale = "; ".join(reasons) if reasons else "all turnout conditions met"

    return TurnoutResult(
        precinct=swing_result.precinct, state=swing_result.state, county=swing_result.county,
        turnout_label=label, support_favorable=support_favorable,
        turnout_suppressed=turnout_suppressed, turnout_movable=turnout_movable,
        confidence=conf, avg_support=avg_sup, avg_turnout=avg_to,
        turnout_sd=to_sd, rationale=rationale,
    )


def run_turnout_targeting(swing_results: list, run_id: Optional[str] = None) -> list[TurnoutResult]:
    """
    Classify all precincts for turnout opportunity.

    Args:
        swing_results: list[SwingResult]
        run_id:        run identifier

    Returns:
        list[TurnoutResult]
    """
    from datetime import datetime
    import pandas as pd

    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M")
    results = [classify_turnout_opportunity(r) for r in swing_results]

    # Combine labels to final: PERSUASION_PRIMARY, TURNOUT_PRIMARY, MIXED, LOW_PRIORITY
    out_dir = Path(__file__).resolve().parent.parent.parent / "derived" / "swing_modeling"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([r.__dict__ for r in results])
    out = out_dir / f"{run_id}__turnout_targets.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    log.info(f"[TURNOUT] {sum(1 for r in results if r.turnout_label == 'TURNOUT_PRIMARY')} turnout targets → {out}")
    return results


def combine_labels(persuasion_results: list, turnout_results: list) -> list[dict]:
    """
    Combine persuasion and turnout labels into final per-precinct targeting label.

    Final labels:
      PERSUASION_PRIMARY — persuasion only
      TURNOUT_PRIMARY    — turnout only
      MIXED              — both signals present
      LOW_PRIORITY       — neither signal
    """
    p_map = {r.precinct: r.persuasion_label for r in persuasion_results}
    t_map = {r.turnout_label: r for r in turnout_results}    # keyed by precinct
    t_map = {r.precinct: r.turnout_label for r in turnout_results}

    all_precincts = set(p_map) | set(t_map)
    combined = []
    for prec in all_precincts:
        p_label = p_map.get(prec, "NOT_PERSUASION")
        t_label = t_map.get(prec, "NOT_TURNOUT")
        if p_label == "PERSUASION_PRIMARY" and t_label == "TURNOUT_PRIMARY":
            final = "MIXED"
        elif p_label == "PERSUASION_PRIMARY":
            final = "PERSUASION_PRIMARY"
        elif t_label == "TURNOUT_PRIMARY":
            final = "TURNOUT_PRIMARY"
        else:
            final = "LOW_PRIORITY"
        combined.append({"precinct": prec, "final_label": final,
                         "persuasion": p_label, "turnout": t_label})
    return combined
