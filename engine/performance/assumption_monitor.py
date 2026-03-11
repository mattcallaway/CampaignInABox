"""
engine/performance/assumption_monitor.py — Prompt 18

Evaluates runtime constraints (e.g. doors per hour, persuasion pace)
against strategic baseline. Flags ASSUMPTION_FAILURE if drift is severe.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import pandas as pd

log = logging.getLogger(__name__)

def check_assumptions(base_dir: Path | str, run_id: str) -> dict:
    root = Path(base_dir)
    perf_file = root / "derived" / "performance" / "latest" / "performance_metrics.csv"
    baseline_file = root / "derived" / "strategy" / "baseline_plan.json"
    
    out_dir = root / "reports" / "performance"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / f"{run_id}__assumption_failures.md"

    # Default missing values gracefully
    baseline = {}
    if baseline_file.exists():
        with open(baseline_file, "r") as f:
            baseline = json.load(f)

    actuals = {}
    if perf_file.exists():
        try:
            df = pd.read_csv(perf_file)
            if not df.empty:
                actuals = df.sum(numeric_only=True).to_dict()
        except Exception:
            pass

    failures = []
    
    # 1. Door Knock Efficiency
    expected_dph = baseline.get("expected_doors_per_hour", 18.0)
    actual_doors = actuals.get("doors_knocked", 0)
    actual_hours = actuals.get("volunteer_hours", 0)
    
    observed_dph = (actual_doors / actual_hours) if actual_hours > 0 else 0
    if actual_hours > 10 and observed_dph < (expected_dph * 0.75):
        failures.append({
            "assumption": "Voter Contact Efficiency",
            "expected": f"{expected_dph} doors/hr",
            "observed": f"{round(observed_dph, 1)} doors/hr",
            "impact": "Field program requires 25%+ more volunteer shifts to hit targets.",
            "status": "ASSUMPTION_FAILURE"
        })

    # 2. Call Efficiency
    expected_cph = baseline.get("expected_calls_per_hour", 35.0)
    actual_calls = actuals.get("calls_made", 0)
    
    # Let's say we assume 50% of vol hours go to doors, 50% to phones for simplified diagnostic
    phone_hours = actual_hours * 0.5
    observed_cph = (actual_calls / phone_hours) if phone_hours > 0 else 0
    if phone_hours > 10 and observed_cph < (expected_cph * 0.75):
        failures.append({
            "assumption": "Phone Bank Efficiency",
            "expected": f"{expected_cph} calls/hr",
            "observed": f"{round(observed_cph, 1)} calls/hr",
            "impact": "Phone program lagging; may need to buy vendor calls.",
            "status": "ASSUMPTION_FAILURE"
        })

    # Write Markdown Report
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# Campaign Assumption Diagnostic\n\n")
        if not failures:
            f.write("✅ All monitored assumptions are holding stable within 25% tolerance.\n")
        else:
            f.write("🚨 **ASSUMPTION FAILURES DETECTED**\n\n")
            for fail in failures:
                f.write(f"### {fail['assumption']}\n")
                f.write(f"- **Expected:** {fail['expected']}\n")
                f.write(f"- **Observed:** {fail['observed']}\n")
                f.write(f"- **Impact:** {fail['impact']}\n\n")

    return {"failures_count": len(failures), "report": report_file}
