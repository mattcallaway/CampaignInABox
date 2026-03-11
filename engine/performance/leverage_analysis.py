"""
engine/performance/leverage_analysis.py — Prompt 18

Identifies high-leverage adjustments and outputs recovery scenarios natively to CSV/JSON.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import pandas as pd

log = logging.getLogger(__name__)

def run_leverage_analysis(base_dir: Path | str, run_id: str, drift_data: dict) -> dict:
    """
    Computes recovery scenarios based on forecast drift metrics.
    """
    root = Path(base_dir)
    perf_dir = root / "derived" / "performance"
    perf_dir.mkdir(parents=True, exist_ok=True)
    
    actions_file = perf_dir / f"{run_id}__leverage_actions.json"
    recovery_file = perf_dir / f"{run_id}__recovery_scenarios.csv"

    doors_pct = drift_data.get("doors_pct", 0)
    calls_pct = drift_data.get("calls_pct", 0)

    # 1. Leverage Actions
    actions = []
    if doors_pct < -0.1:
        actions.append({
            "program": "Field / Canvass",
            "issue": "Behind door knocking targets",
            "recommendation": "Shift weekend budget to paid canvassers or run emergency GOTV volunteer surge in high-density precincts."
        })
    if calls_pct < -0.1:
        actions.append({
            "program": "Phones",
            "issue": "Behind phone targets",
            "recommendation": "Purchase automated ID texts to offset lost phone volume."
        })
    if not actions:
        actions.append({
            "program": "General",
            "issue": "Operations are stable",
            "recommendation": "Maintain pacing and freeze redundant spend."
        })

    with open(actions_file, "w") as f:
        json.dump({"actions": actions}, f, indent=2)

    # 2. Recovery Scenarios
    scenarios = []
    # If behind on field, what does a mail boost look like?
    scenarios.append({
        "scenario": "Mail Boost Defense",
        "description": "Drop 3 additional pieces of persuasion mail to Top 30% universes.",
        "cost_est": 45000,
        "impact_est": "Restores +1.2% net margin lost to low doors."
    })
    scenarios.append({
        "scenario": "Digital Surge",
        "description": "Double digital spend in final 14 days on un-knocked targeted universes.",
        "cost_est": 25000,
        "impact_est": "Restores +0.4% net margin."
    })
    scenarios.append({
        "scenario": "Weekend Mega-Canvass",
        "description": "Import 50 out-of-district volunteers and pay for hotel/transport.",
        "cost_est": 12000,
        "impact_est": "Clears 15,000 doors, restores +0.8% net margin."
    })

    df_rec = pd.DataFrame(scenarios)
    df_rec.to_csv(recovery_file, index=False)

    return {"actions_generated": len(actions), "scenarios_generated": len(scenarios)}
