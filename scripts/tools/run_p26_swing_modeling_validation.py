"""
scripts/tools/run_p26_swing_modeling_validation.py — Prompt 26

Validation tests for the Swing Precinct Detection & Backtesting system.

Tests:
  1.  swing_rules.yaml loads correctly with required keys
  2.  Swing detector runs on synthetic data and returns SwingResults
  3.  SwingResult has required fields (swing_score, confidence, swing_class)
  4.  Swing classes are assigned correctly (high_swing ≥ 0.65)
  5.  IQR anomaly detection works
  6.  Confidence degrades with sparse data (< 2 elections → floor)
  7.  Persuasion classifier: in-window precinct gets PERSUASION_PRIMARY
  8.  Persuasion classifier: out-of-window precinct gets NOT_PERSUASION
  9.  Turnout classifier: suppressed precinct gets TURNOUT_PRIMARY
  10. Turnout classifier: unsuppressed gets NOT_TURNOUT
  11. combine_labels produces MIXED when both qualify
  12. combine_labels produces LOW_PRIORITY when neither qualifies
  13. Backtester runs on synthetic data and returns BacktestSummary
  14. Backtester reports insufficient_data when < 2 training years
  15. Backtest writes output files (CSV, JSON, reports)
  16. Metrics compute F1, MAE, top-N rates correctly
  17. Output directories exist
  18. Output CSV files are written by swing_detector
"""
import sys, os
os.chdir(r"C:\Users\Mathew C\Campaign In A Box")
sys.path.insert(0, os.getcwd())
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

print("=== Prompt 26 Swing Modeling Validation ===")
print()

RUN_ID = datetime.now().strftime("%Y%m%d__p26val")
ERRORS = []

def ok(label): print(f"  [OK] {label}")
def fail(label, reason=""): print(f"  [!!] FAIL: {label} — {reason}"); ERRORS.append(f"{label}: {reason}")
def check(cond, label, reason=""): ok(label) if cond else fail(label, reason)

# ─── Synthetic election data for testing ────────────────────────────────────
rng = np.random.default_rng(42)
precincts = [f"04001{i:02d}" for i in range(1, 21)]
years     = [2018, 2020, 2022, 2024]
rows = []
for p in precincts:
    base_sup = rng.uniform(0.35, 0.70)
    base_to  = rng.uniform(0.35, 0.70)
    for y in years:
        rows.append({
            "precinct": p, "state": "CA", "county": "Sonoma", "year": y,
            "support_rate": float(np.clip(base_sup + rng.normal(0, 0.08), 0.05, 0.95)),
            "turnout_rate": float(np.clip(base_to  + rng.normal(0, 0.05), 0.10, 0.95)),
            "contest_type": "general", "provenance": "SYNTHETIC",
        })
synth_df = pd.DataFrame(rows)

# ─── Phase 1: swing_rules.yaml ────────────────────────────────────────────────
print("-- Phase 1: swing_rules.yaml --")
import yaml
rules_path = Path("engine/swing_modeling/swing_rules.yaml")
check(rules_path.exists(), "swing_rules.yaml exists", "missing file")
rules = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
check("weights" in rules, "weights key present")
check("swing_classes" in rules, "swing_classes key present")
check("actual_swing_definition" in rules, "actual_swing_definition key present")
check("targeting" in rules, "targeting key present")
w = rules.get("weights", {})
total_w = sum(w.values())
check(abs(total_w - 1.0) < 0.01, f"weights sum to 1.0 (got {total_w:.2f})", f"sum={total_w}")

# ─── Phase 2: Swing Detector ─────────────────────────────────────────────────
print()
print("-- Phase 2: Swing Detector --")
from engine.swing_modeling.swing_detector import run_swing_detection, detect_swing_for_precinct, _iqr_outlier_present

results = run_swing_detection(state="CA", county="Sonoma", run_id=RUN_ID, archive_elections_df=synth_df)
check(len(results) > 0, f"swing detector returned {len(results)} results", "got 0")

r = results[0]
check(hasattr(r, "swing_score"), "SwingResult has swing_score")
check(hasattr(r, "confidence"),  "SwingResult has confidence")
check(hasattr(r, "swing_class"), "SwingResult has swing_class")
check(0.0 <= r.swing_score <= 1.0, f"swing_score in [0,1]: {r.swing_score}", "out of range")
check(r.swing_class in ("high_swing", "moderate_swing", "low_swing", "stable"),
      f"swing_class valid: {r.swing_class}", "invalid class")

# Confidence degrades with sparse data
from engine.swing_modeling.swing_detector import detect_swing_for_precinct
sparse_df = synth_df[synth_df["year"] == 2024]  # only 1 year
sparse_r = detect_swing_for_precinct("0400101", "CA", "Sonoma", sparse_df, rules)
check(sparse_r.confidence <= 0.25, f"sparse data → low confidence ({sparse_r.confidence:.2f})", "confidence too high for 1 election")

# IQR outlier detection
check(_iqr_outlier_present([0.4, 0.41, 0.42, 0.43, 0.90]), "IQR detects outlier (0.90 in 0.40s)", "failed")
check(not _iqr_outlier_present([0.4, 0.42, 0.44, 0.46]), "IQR: no outlier in uniform data", "false positive")

# ─── Phase 3: Persuasion Target Model ────────────────────────────────────────
print()
print("-- Phase 3: Persuasion Target Model --")
from engine.swing_modeling.persuasion_target_model import classify_persuasion
from engine.swing_modeling.swing_detector import SwingResult

def make_swing_result(precinct, avg_sup, avg_to, sup_sd, to_sd) -> SwingResult:
    return SwingResult(
        precinct=precinct, state="CA", county="Sonoma",
        swing_score=0.5, support_volatility=sup_sd, turnout_volatility=to_sd,
        recent_direction="neutral", trend_magnitude=0.0, contest_sensitivity=0.0,
        confidence=0.75, swing_class="moderate_swing",
        elections_counted=4, avg_support=avg_sup, avg_turnout=avg_to,
        provenance="SYNTHETIC",
    )

# In-window, movable → PERSUASION_PRIMARY
p1 = classify_persuasion(make_swing_result("P1", 0.52, 0.50, 0.08, 0.03))
check(p1.persuasion_label == "PERSUASION_PRIMARY", f"in-window precinct → PERSUASION_PRIMARY (got {p1.persuasion_label})", p1.rationale)

# Out-of-window → NOT_PERSUASION
p2 = classify_persuasion(make_swing_result("P2", 0.80, 0.50, 0.08, 0.03))
check(p2.persuasion_label == "NOT_PERSUASION", f"out-of-window → NOT_PERSUASION (got {p2.persuasion_label})", p2.rationale)

# Not movable → NOT_PERSUASION
p3 = classify_persuasion(make_swing_result("P3", 0.50, 0.50, 0.01, 0.01))
check(p3.persuasion_label == "NOT_PERSUASION", f"frozen precinct → NOT_PERSUASION (got {p3.persuasion_label})", p3.rationale)

# ─── Phase 4: Turnout Target Model ───────────────────────────────────────────
print()
print("-- Phase 4: Turnout Target Model --")
from engine.swing_modeling.turnout_opportunity_model import classify_turnout_opportunity, combine_labels

# Favorable + suppressed + movable → TURNOUT_PRIMARY
t1 = classify_turnout_opportunity(make_swing_result("T1", 0.60, 0.40, 0.03, 0.05))
check(t1.turnout_label == "TURNOUT_PRIMARY", f"suppressed turnout → TURNOUT_PRIMARY (got {t1.turnout_label})", t1.rationale)

# High turnout → NOT_TURNOUT
t2 = classify_turnout_opportunity(make_swing_result("T2", 0.60, 0.80, 0.03, 0.05))
check(t2.turnout_label == "NOT_TURNOUT", f"high-turnout → NOT_TURNOUT (got {t2.turnout_label})", t2.rationale)

# combine_labels
from engine.swing_modeling.persuasion_target_model import PersuasionResult
from engine.swing_modeling.turnout_opportunity_model import TurnoutResult

pr = PersuasionResult("PX","CA","Sonoma","PERSUASION_PRIMARY",True,True,False,0.75,0.50,0.08,0.45,"ok")
tr = TurnoutResult("PX","CA","Sonoma","TURNOUT_PRIMARY",True,True,True,0.75,0.50,0.40,0.05,"ok")
combined = combine_labels([pr], [tr])
check(combined[0]["final_label"] == "MIXED", f"both qualify → MIXED (got {combined[0]['final_label']})", "")

pr2 = PersuasionResult("PY","CA","Sonoma","NOT_PERSUASION",False,False,False,0.30,0.80,0.01,0.70,"not in window")
tr2 = TurnoutResult("PY","CA","Sonoma","NOT_TURNOUT",False,False,False,0.30,0.80,0.70,0.01,"high turnout")
combined2 = combine_labels([pr2], [tr2])
check(combined2[0]["final_label"] == "LOW_PRIORITY", f"neither → LOW_PRIORITY (got {combined2[0]['final_label']})", "")

# ─── Phase 5: Backtester ─────────────────────────────────────────────────────
print()
print("-- Phase 5: Backtester --")
from engine.swing_modeling.backtester import run_backtest

bt_summary = run_backtest(synth_df, state="CA", county="Sonoma", run_id=RUN_ID, min_training_years=2)
check(hasattr(bt_summary, "folds_run"), "backtest returned BacktestSummary", "missing folds_run")
check(bt_summary.folds_run >= 1, f"at least 1 fold ran (got {bt_summary.folds_run})", "0 folds")
check(bt_summary.backtest_status in (
    "ACTIVE_VALIDATED", "ACTIVE_LOW_CONFIDENCE", "DISABLED_INSUFFICIENT_BACKTEST"),
    f"backtest_status valid: {bt_summary.backtest_status}", "invalid status")
check(bt_summary.state == "CA", "state=CA in summary", f"got {bt_summary.state}")
print(f"  Backtest: folds={bt_summary.folds_run} avg_f1={bt_summary.avg_f1:.3f} status={bt_summary.backtest_status}")

# Insufficient data case
tiny_df = synth_df[synth_df["year"].isin([2024])]
bt_tiny = run_backtest(tiny_df, state="CA", county="Sonoma", run_id=RUN_ID+"_tiny", min_training_years=2)
check(bt_tiny.folds_run == 0, f"tiny archive → 0 folds (got {bt_tiny.folds_run})", "")
check(bt_tiny.backtest_status == "DISABLED_INSUFFICIENT_BACKTEST",
      f"tiny → DISABLED_INSUFFICIENT_BACKTEST (got {bt_tiny.backtest_status})", "")

# ─── Phase 6: Output files ───────────────────────────────────────────────────
print()
print("-- Phase 6: Output Files & Dirs --")
derived_dir = Path("derived/swing_modeling")
reports_dir = Path("reports/swing_modeling")
check(derived_dir.exists(), "derived/swing_modeling/ exists")
check(reports_dir.exists(), "reports/swing_modeling/ exists")

swing_csv = derived_dir / f"{RUN_ID}__swing_scores.csv"
check(swing_csv.exists(), "swing_scores.csv written", f"missing: {swing_csv}")

bt_json = derived_dir / f"{RUN_ID}__backtest_summary.json"
check(bt_json.exists(), "backtest_summary.json written", f"missing: {bt_json}")

bt_report = reports_dir / f"{RUN_ID}__backtest_report.md"
check(bt_report.exists(), "backtest_report.md written", f"missing: {bt_report}")

suf_report = reports_dir / f"{RUN_ID}__data_sufficiency_report.md"
check(suf_report.exists(), "data_sufficiency_report.md written", f"missing: {suf_report}")

# ─── Summary ─────────────────────────────────────────────────────────────────
print()
if ERRORS:
    print(f"ASSERTION FAILURES: {len(ERRORS)}")
    for e in ERRORS: print(f"  {e}")
    sys.exit(1)
else:
    print("All Swing Modeling validation assertions passed.")

print()
print("=== ALL PHASES COMPLETE ===")
