"""
engine/performance/forecast_drift.py — Prompt 18

Computes drift between planned strategic assumptions and actual runtime performance.
Outputs turnout drift, support drift, and operational deviation.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import pandas as pd

log = logging.getLogger(__name__)

def calculate_forecast_drift(base_dir: Path | str, run_id: str) -> dict:
    root = Path(base_dir)
    perf_file = root / "derived" / "performance" / "latest" / "performance_metrics.csv"
    baseline_file = root / "derived" / "strategy" / "baseline_plan.json"
    
    out_dir = root / "derived" / "performance"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"{run_id}__forecast_drift.csv"

    # Load baseline
    baseline = {}
    if baseline_file.exists():
        with open(baseline_file, "r") as f:
            baseline = json.load(f)

    # Load performance metrics
    actuals = {}
    if perf_file.exists():
        try:
            df = pd.read_csv(perf_file)
            if not df.empty:
                actuals = df.sum(numeric_only=True).to_dict()
        except Exception as e:
            log.warning(f"Error reading performance metrics for drift: {e}")

    # Compute Operational Drift
    drift_records = []

    def _add_drift(metric: str, plan: float, actual: float, type_str: str):
        delta = actual - plan
        pct = (delta / plan) if plan > 0 else 0
        status = "ON_TRACK"
        if pct < -0.1: status = "BEHIND"
        elif pct > 0.1: status = "AHEAD"

        drift_records.append({
            "metric": metric,
            "type": type_str,
            "planned": plan,
            "actual": actual,
            "delta": delta,
            "pct_deviation": round(pct, 4),
            "status": status
        })

    # Operational Metrics
    _add_drift("doors_knocked", baseline.get("target_doors", 0), actuals.get("doors_knocked", 0), "ACTIVITY")
    _add_drift("calls_made", baseline.get("target_calls", 0), actuals.get("calls_made", 0), "ACTIVITY")
    _add_drift("mail_sent", baseline.get("target_mail", 0), actuals.get("mail_sent", 0), "ACTIVITY")
    _add_drift("digital_spend", baseline.get("target_digital_spend", 0), actuals.get("digital_spend", 0), "BUDGET")
    _add_drift("fundraising", baseline.get("target_fundraising", 0), actuals.get("fundraising_total", 0), "BUDGET")

    # Turnout / Support Drift (Simulated based on activity leverage for now, normally reads polling/returns)
    # E.g. If we are behind on doors, our expected turnout lift drops.
    doors_pct = drift_records[0]["pct_deviation"]
    expected_turnout_lift = baseline.get("expected_turnout_lift", 0.0)
    actual_turnout_lift = expected_turnout_lift * max(0, (1 + doors_pct))
    _add_drift("turnout_lift_pct", expected_turnout_lift, actual_turnout_lift, "SUPPORT")

    expected_persuasion = baseline.get("expected_persuasion_lift", 0.0)
    calls_pct = drift_records[1]["pct_deviation"]
    actual_persuasion = expected_persuasion * max(0, (1 + calls_pct))
    _add_drift("persuasion_lift_pct", expected_persuasion, actual_persuasion, "SUPPORT")

    # Output
    drift_df = pd.DataFrame(drift_records)
    drift_df.to_csv(out_csv, index=False)
    
    # Return a summary dict for the state builder
    return {
        "turnout_lift_drift": actual_turnout_lift - expected_turnout_lift,
        "persuasion_lift_drift": actual_persuasion - expected_persuasion,
        "doors_pct": doors_pct,
        "calls_pct": calls_pct
    }
