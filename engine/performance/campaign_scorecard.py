"""
engine/performance/campaign_scorecard.py — Prompt 18

Generates a holistic Campaign Health Index (CHI) and a Markdown scorecard.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

def generate_campaign_scorecard(base_dir: Path | str, run_id: str, drift_data: dict, assumptions: dict) -> dict:
    root = Path(base_dir)
    perf_dir = root / "derived" / "performance"
    perf_dir.mkdir(parents=True, exist_ok=True)
    report_dir = root / "reports" / "performance"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    health_file = perf_dir / f"{run_id}__campaign_health.json"
    scorecard_file = report_dir / f"{run_id}__campaign_scorecard.md"

    doors_pct = drift_data.get("doors_pct", 0)
    calls_pct = drift_data.get("calls_pct", 0)
    turnout_drift = drift_data.get("turnout_lift_drift", 0.0)
    
    # 1. Calculate Campaign Health Index (CHI)
    # Weigh field strongly. -1.0 to 1.0 roughly.
    chi_score = (doors_pct * 0.4) + (calls_pct * 0.2) + (turnout_drift * 10 * 0.4)
    
    fails = assumptions.get("failures_count", 0)
    chi_score -= (fails * 0.1)  # Penalize for bad assumptions
    
    health_status = "STABLE"
    if chi_score > 0.1: health_status = "STRONG"
    elif chi_score < -0.2: health_status = "WARNING"
    elif chi_score < -0.5: health_status = "CRITICAL"

    health_data = {
        "chi_score": round(chi_score, 4),
        "status": health_status,
        "doors_health": "AHEAD" if doors_pct > 0 else "BEHIND" if doors_pct < -0.1 else "ON_TRACK",
        "calls_health": "AHEAD" if calls_pct > 0 else "BEHIND" if calls_pct < -0.1 else "ON_TRACK",
    }

    with open(health_file, "w") as f:
        json.dump(health_data, f, indent=2)

    # 2. Write Markdown Scorecard
    with open(scorecard_file, "w", encoding="utf-8") as f:
        f.write("# 🏆 Campaign Performance Scorecard\n\n")
        f.write(f"**Run ID:** `{run_id}`  \n")
        f.write(f"**Overall Health:** `{health_status}` (Index: {round(chi_score, 2)})\n\n")
        
        f.write("## Operations Pacing\n")
        f.write(f"- **Doors:** {health_data['doors_health']}\n")
        f.write(f"- **Calls:** {health_data['calls_health']}\n\n")
        
        f.write("## Strategic Drift\n")
        d_color = "red" if turnout_drift < 0 else "green"
        f.write(f"- **Turnout Lift Delta:** <span style='color:{d_color}'>{round(turnout_drift*100, 2)}%</span>\n")

    return health_data
