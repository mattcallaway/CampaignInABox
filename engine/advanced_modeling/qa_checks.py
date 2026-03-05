"""
engine/advanced_modeling/qa_checks.py — Prompt 10

QA sanity checks for advanced modeling outputs.

Checks:
1. Lift magnitude in plausible range
2. Diminishing returns monotonicity
3. Allocation sums equal max_total_shifts
4. Net gain non-negative where expected
"""
from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def run_qa_checks(
    scenarios_df:  pd.DataFrame,
    alloc_df:      pd.DataFrame,
    curve_df:      pd.DataFrame,
    universe_df:   pd.DataFrame,
    cfg:           dict,
    run_id:        str,
    contest_id:    str,
    out_dir:       Optional[Path] = None,
) -> dict:
    """
    Run sanity checks and write QA report.

    Returns a dict with 'pass_count', 'fail_count', 'warnings', 'errors'.
    """
    checks   = []
    warnings = []
    errors   = []
    ts       = datetime.datetime.now().isoformat()

    curves  = cfg.get("curves",    {})
    max_to  = float(curves.get("max_turnout_lift_pct",   0.08))
    max_pe  = float(curves.get("max_persuasion_lift_pct", 0.06))
    opt     = cfg.get("optimizer", {})
    scen    = cfg.get("scenarios", {})

    # ── CHECK 1: Lift magnitude plausible ───────────────────────────────────
    if alloc_df.empty:
        checks.append(("lift_magnitude", "SKIP", "alloc_df empty"))
    else:
        if "turnout_lift" in alloc_df.columns:
            max_observed_to = alloc_df["turnout_lift"].max()
            if max_observed_to > max_to + 0.001:
                errors.append(f"Turnout lift {max_observed_to:.4f} exceeds max {max_to}")
                checks.append(("lift_magnitude", "FAIL", f"turnout_lift {max_observed_to:.4f} > {max_to}"))
            else:
                checks.append(("lift_magnitude", "PASS", f"max turnout_lift={max_observed_to:.4f}"))
        if "persuasion_lift" in alloc_df.columns:
            max_observed_pe = alloc_df["persuasion_lift"].max()
            if max_observed_pe > max_pe + 0.001:
                errors.append(f"Persuasion lift {max_observed_pe:.4f} exceeds max {max_pe}")
                checks.append(("persuasion_lift_magnitude", "FAIL", f"persuasion_lift {max_observed_pe:.4f} > {max_pe}"))
            else:
                checks.append(("persuasion_lift_magnitude", "PASS", f"max persuasion_lift={max_observed_pe:.4f}"))

    # ── CHECK 2: Diminishing returns monotonicity ───────────────────────────
    if curve_df.empty:
        checks.append(("monotonicity", "SKIP", "curve_df empty"))
    elif "marginal_gain_votes" in curve_df.columns:
        mg = curve_df["marginal_gain_votes"].tolist()
        non_monotone = sum(1 for i in range(1, len(mg)) if mg[i] > mg[i-1] + 0.01)
        if non_monotone > len(mg) * 0.1 and len(mg) > 5:
            warnings.append(f"Allocation curve not strictly monotone: {non_monotone}/{len(mg)} non-decreasing steps")
            checks.append(("monotonicity", "WARN", f"{non_monotone} non-monotone steps"))
        else:
            checks.append(("monotonicity", "PASS", f"curve length={len(mg)}, ok"))

    # ── CHECK 3: Allocation sums ─────────────────────────────────────────────
    if not alloc_df.empty and "shifts_assigned" in alloc_df.columns:
        total = int(alloc_df["shifts_assigned"].sum())
        expected = int(opt.get("max_total_shifts", 100))
        if abs(total - expected) > 1:
            warnings.append(f"Total shifts {total} ≠ expected {expected}")
            checks.append(("allocation_sum", "WARN", f"sum={total}, expected={expected}"))
        else:
            checks.append(("allocation_sum", "PASS", f"sum={total}"))

    # ── CHECK 4: Net gain non-negative ───────────────────────────────────────
    if not scenarios_df.empty and "expected_net_gain_votes" in scenarios_df.columns:
        neg = (scenarios_df["expected_net_gain_votes"] < -0.01).sum()
        if neg > 0:
            warnings.append(f"{neg} scenarios have negative net gain — check lift math")
            checks.append(("net_gain_positive", "WARN", f"{neg} negative scenarios"))
        else:
            checks.append(("net_gain_positive", "PASS", "all gains >= 0"))

    # ── CHECK 5: Scenario order (more budget → more gain) ───────────────────
    if not scenarios_df.empty and "expected_net_gain_votes" in scenarios_df.columns:
        ordered_names = ["baseline", "lite", "medium", "heavy"]
        ordered_gains = []
        for n in ordered_names:
            row = scenarios_df[scenarios_df["scenario"] == n]
            if not row.empty:
                ordered_gains.append((n, float(row.iloc[0]["expected_net_gain_votes"])))
        is_monotone = all(ordered_gains[i][1] <= ordered_gains[i+1][1]
                          for i in range(len(ordered_gains)-1)) if len(ordered_gains) > 1 else True
        if not is_monotone:
            warnings.append("Scenario gains not monotone with budget — possible optimizer issue")
            checks.append(("scenario_monotone", "WARN", str(ordered_gains)))
        else:
            checks.append(("scenario_monotone", "PASS", f"{len(ordered_gains)} ordered scenarios ok"))

    # ── Write QA report ───────────────────────────────────────────────────────
    pass_count = sum(1 for _, s, _ in checks if s == "PASS")
    warn_count = sum(1 for _, s, _ in checks if s == "WARN")
    fail_count = sum(1 for _, s, _ in checks if s == "FAIL")
    skip_count = sum(1 for _, s, _ in checks if s == "SKIP")

    if out_dir is None:
        out_dir = BASE_DIR / "reports" / "qa"
    out_dir.mkdir(parents=True, exist_ok=True)
    qa_path = out_dir / f"{run_id}__advanced_modeling_checks.md"

    rows_md = "\n".join(
        f"| {name} | {'✅' if s=='PASS' else '⚠️' if s=='WARN' else '❌' if s=='FAIL' else '⏭️'} {s} | {note} |"
        for name, s, note in checks
    )

    md = f"""# Advanced Modeling QA Report
**Run ID:** `{run_id}` | **Contest:** `{contest_id}` | **Generated:** {ts}

## Summary
| Status | Count |
|---|---|
| ✅ PASS | {pass_count} |
| ⚠️ WARN | {warn_count} |
| ❌ FAIL | {fail_count} |
| ⏭️ SKIP | {skip_count} |

## Check Results
| Check | Status | Notes |
|---|---|---|
{rows_md}

{"## ⚠️ Warnings" + chr(10) + chr(10).join(f"- {w}" for w in warnings) if warnings else ""}
{"## ❌ Errors" + chr(10) + chr(10).join(f"- {e}" for e in errors) if errors else ""}
"""
    qa_path.write_text(md, encoding="utf-8")
    log.info(f"[QA] Advanced modeling QA: PASS={pass_count}, WARN={warn_count}, FAIL={fail_count} → {qa_path.name}")

    return {
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "warnings":   warnings,
        "errors":     errors,
    }
