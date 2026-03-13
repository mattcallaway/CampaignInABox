"""
engine/swing_modeling/backtester.py — Prompt 26

Historical backtester for swing precinct predictions.

Method (held-out validation):
  For each available election year (2020, 2022, 2024...):
    - Hold out that year's results
    - Use ONLY prior years to build swing scores
    - Compare predicted swing precincts vs. actual movement in held-out year
    - Compute precision, recall, F1, MAE

Safety guardrails:
  - Never train and test on the same election
  - Never use future elections to predict earlier ones
  - Do not mix counties or jurisdictions
  - Clearly report insufficient data when archive is thin

Outputs:
  derived/swing_modeling/<RUN_ID>__backtest_results.csv
  derived/swing_modeling/<RUN_ID>__backtest_summary.json
  reports/swing_modeling/<RUN_ID>__backtest_report.md
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
DERIVED_DIR = BASE_DIR / "derived" / "swing_modeling"
REPORTS_DIR = BASE_DIR / "reports" / "swing_modeling"
RULES_PATH  = Path(__file__).resolve().parent / "swing_rules.yaml"

DERIVED_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}


@dataclass
class BacktestFold:
    """Result of one held-out backtest fold."""
    held_out_year:      int
    training_years:     list
    n_training_elections: int
    n_precincts:        int
    actually_swung:     int
    predicted_swing:    int
    precision:          float
    recall:             float
    f1:                 float
    support_mae:        float
    turnout_mae:        float
    top10_true_rate:    float
    top20_true_rate:    float
    high_conf_precision: float
    verdict:            str
    false_positives_examples: list  # top 3 FP precinct IDs
    false_negatives_examples: list  # top 3 FN precinct IDs


@dataclass
class BacktestSummary:
    run_id:             str
    state:              str
    county:             str
    folds_run:          int
    total_precincts:    int
    avg_precision:      float
    avg_recall:         float
    avg_f1:             float
    avg_support_mae:    float
    avg_top10_rate:     float
    overall_verdict:    str         # validated | partial | insufficient_data
    backtest_status:    str         # ACTIVE_VALIDATED | ACTIVE_LOW_CONFIDENCE | DISABLED_INSUFFICIENT_BACKTEST
    years_available:    list
    years_needed_for_strong_validation: list
    data_sufficiency_note: str
    folds:              list        # list of BacktestFold dicts


def _actual_swing_mask(held_out_df, training_df, rules: dict) -> tuple[dict, dict, dict]:
    """
    Compute which precincts actually swung in the held-out year.

    Returns:
        swing_mask:       {precinct: bool}
        support_changes:  {precinct: float}  (held_out_support - train_avg_support)
        turnout_changes:  {precinct: float}
    """
    import pandas as pd
    import numpy as np

    swing_def = rules.get("actual_swing_definition", {})
    abs_sup_thresh = swing_def.get("absolute_support_threshold", 0.05)
    abs_to_thresh  = swing_def.get("absolute_turnout_threshold", 0.05)
    pct_thresh     = swing_def.get("percentile_threshold", 75)

    # Training averages per precinct
    train_avg = training_df.groupby("precinct").agg(
        avg_sup=("support_rate", "mean"),
        avg_to= ("turnout_rate", "mean"),
    ).reset_index()

    # Held-out actuals
    held_sup = held_out_df.groupby("precinct")["support_rate"].mean().reset_index(name="actual_sup")
    held_to  = held_out_df.groupby("precinct")["turnout_rate"].mean().reset_index(name="actual_to")

    merged = train_avg.merge(held_sup, on="precinct", how="inner")
    merged = merged.merge(held_to,  on="precinct", how="inner")
    merged["sup_delta"] = (merged["actual_sup"] - merged["avg_sup"]).abs()
    merged["to_delta"]  = (merged["actual_to"]  - merged["avg_to"]).abs()

    # Percentile threshold within jurisdiction
    sup_pct_threshold = np.percentile(merged["sup_delta"].dropna(), pct_thresh)
    to_pct_threshold  = np.percentile(merged["to_delta"].dropna(),  pct_thresh)

    swing_mask:      dict = {}
    support_changes: dict = {}
    turnout_changes: dict = {}

    for _, row in merged.iterrows():
        prec = row["precinct"]
        sup_d = row["sup_delta"]
        to_d  = row["to_delta"]
        # "Actually swung" = above absolute threshold AND in top percentile
        swung = (
            (sup_d >= abs_sup_thresh and sup_d >= sup_pct_threshold)
            or
            (to_d  >= abs_to_thresh  and to_d  >= to_pct_threshold)
        )
        swing_mask[prec]      = bool(swung)
        support_changes[prec] = float(row["actual_sup"] - row["avg_sup"])
        turnout_changes[prec] = float(row["actual_to"]  - row["avg_to"])

    return swing_mask, support_changes, turnout_changes


def run_backtest(
    elections_df,
    state: str = "CA",
    county: str = "Sonoma",
    run_id: Optional[str] = None,
    min_training_years: int = 2,
) -> BacktestSummary:
    """
    Run held-out backtesting for all available election years.

    For each year where sufficient training elections precede it:
      - Hold out that year
      - Train on prior years only
      - Predict swing → compare with actual

    Args:
        elections_df:        full normalized elections DataFrame for the jurisdiction
        state, county:       jurisdiction scope
        run_id:              run identifier
        min_training_years:  minimum number of training years required to run a fold

    Returns:
        BacktestSummary
    """
    import pandas as pd
    import numpy as np
    from engine.swing_modeling.swing_detector import run_swing_detection, detect_swing_for_precinct
    from engine.swing_modeling.metrics import compute_metrics

    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M")
    rules  = _load_rules()

    # Filter to jurisdiction
    df = elections_df.copy()
    if "state"  in df.columns: df = df[df["state"].str.lower()  == state.lower()]
    if "county" in df.columns: df = df[df["county"].str.lower() == county.lower()]

    for col in ["support_rate", "turnout_rate", "year"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    available_years = sorted(df["year"].dropna().unique().tolist())
    folds: list[BacktestFold] = []
    all_results_rows = []

    # ── Cross-time validation: hold out each year (never future-train) ─────────
    for held_year in available_years:
        training_years = [y for y in available_years if y < held_year]
        if len(training_years) < min_training_years:
            log.info(f"[BACKTEST] Skip held_year={held_year} — only {len(training_years)} training years (need {min_training_years})")
            continue

        train_df   = df[df["year"].isin(training_years)]
        held_df    = df[df["year"] == held_year]

        # Run swing detection on training data only
        swing_results = run_swing_detection(
            state=state, county=county, run_id=None,
            archive_elections_df=train_df,
        )

        # Compute actual swing in held-out year
        swing_mask, support_chg, turnout_chg = _actual_swing_mask(held_df, train_df, rules)

        # Compute metrics
        m = compute_metrics(
            swing_scores         = swing_results,
            actual_swing_mask    = swing_mask,
            actual_support_changes = support_chg,
            actual_turnout_changes = turnout_chg,
            held_out_year        = int(held_year),
            rules                = rules,
        )

        # Examples: top FPs (predicted swing but didn't) and FNs (swung but missed)
        predicted_set = {r.precinct for r in swing_results if r.swing_score >= 0.40}
        actual_set    = {p for p, v in swing_mask.items() if v}
        fp_list = sorted(predicted_set - actual_set, key=lambda p: -next(
            (r.swing_score for r in swing_results if r.precinct == p), 0))[:3]
        fn_list = sorted(actual_set - predicted_set, key=lambda p: -abs(
            support_chg.get(p, 0)))[:3]

        fold = BacktestFold(
            held_out_year=int(held_year), training_years=training_years,
            n_training_elections=len(training_years), n_precincts=m.total_precincts,
            actually_swung=int(sum(swing_mask.values())),
            predicted_swing=len(predicted_set & set(swing_mask)),
            precision=m.precision, recall=m.recall, f1=m.f1,
            support_mae=m.support_mae, turnout_mae=m.turnout_mae,
            top10_true_rate=m.top10_true_rate, top20_true_rate=m.top20_true_rate,
            high_conf_precision=m.high_conf_precision, verdict=m.verdict,
            false_positives_examples=fp_list, false_negatives_examples=fn_list,
        )
        folds.append(fold)

        # Accumulate per-precinct rows for CSV
        sr_map = {r.precinct: r for r in swing_results}
        for prec, swung in swing_mask.items():
            r = sr_map.get(prec)
            all_results_rows.append({
                "held_out_year": held_year,
                "precinct": prec,
                "predicted_swing": prec in predicted_set,
                "actually_swung": swung,
                "swing_score": r.swing_score if r else None,
                "confidence": r.confidence if r else None,
                "support_change": support_chg.get(prec),
                "turnout_change": turnout_chg.get(prec),
            })

        log.info(
            f"[BACKTEST] Held_year={held_year}: precision={m.precision:.2f} "
            f"recall={m.recall:.2f} F1={m.f1:.2f} verdict={m.verdict}"
        )

    # ── Overall summary ───────────────────────────────────────────────────────
    if folds:
        avg_prec    = float(np.mean([f.precision for f in folds]))
        avg_recall  = float(np.mean([f.recall    for f in folds]))
        avg_f1      = float(np.mean([f.f1        for f in folds]))
        avg_sup_mae = float(np.mean([f.support_mae for f in folds]))
        avg_top10   = float(np.mean([f.top10_true_rate for f in folds]))
    else:
        avg_prec = avg_recall = avg_f1 = avg_sup_mae = avg_top10 = 0.0

    # Determine overall verdict and strategy-engine status label
    if not folds:
        overall_verdict = "insufficient_data"
        bt_status = "DISABLED_INSUFFICIENT_BACKTEST"
        suf_note = (f"No backtest folds could run — need at least {min_training_years + 1} "
                    f"election years. Currently have: {available_years}. "
                    f"Need years: {_years_needed(available_years, min_training_years)}")
    elif avg_f1 >= 0.55:
        overall_verdict = "validated"
        bt_status = "ACTIVE_VALIDATED"
        suf_note = f"Backtest validated across {len(folds)} folds. Avg F1={avg_f1:.2f}"
    elif avg_f1 >= 0.30:
        overall_verdict = "partial"
        bt_status = "ACTIVE_LOW_CONFIDENCE"
        suf_note = f"Partial validation ({len(folds)} folds, Avg F1={avg_f1:.2f}). More historical elections needed."
    else:
        overall_verdict = "insufficient_data"
        bt_status = "DISABLED_INSUFFICIENT_BACKTEST"
        suf_note = f"Backtest quality too low (Avg F1={avg_f1:.2f}). Swing targeting disabled."

    summary = BacktestSummary(
        run_id=run_id, state=state, county=county,
        folds_run=len(folds),
        total_precincts=folds[0].n_precincts if folds else 0,
        avg_precision=round(avg_prec, 4),
        avg_recall=round(avg_recall, 4),
        avg_f1=round(avg_f1, 4),
        avg_support_mae=round(avg_sup_mae, 6),
        avg_top10_rate=round(avg_top10, 4),
        overall_verdict=overall_verdict,
        backtest_status=bt_status,
        years_available=available_years,
        years_needed_for_strong_validation=_years_needed(available_years, min_training_years),
        data_sufficiency_note=suf_note,
        folds=[asdict(f) for f in folds],
    )

    # ── Write outputs ─────────────────────────────────────────────────────────
    _write_results_csv(all_results_rows, run_id)
    _write_summary_json(summary, run_id)
    _write_backtest_report(summary, run_id)
    _write_data_sufficiency_report(summary, available_years, run_id)

    return summary


def _years_needed(available: list, min_training: int) -> list:
    """Suggest additional years that would enable stronger validation."""
    last = max(available) if available else 2020
    needed = []
    if len(available) < min_training + 2:
        for y in range(last + 2, last + 8, 2):
            needed.append(y)
            if len(available) + len(needed) >= min_training + 2:
                break
    return needed


def _write_results_csv(rows: list, run_id: str) -> None:
    import pandas as pd
    if not rows:
        return
    df = pd.DataFrame(rows)
    out = DERIVED_DIR / f"{run_id}__backtest_results.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    log.info(f"[BACKTEST] Results CSV → {out}")


def _write_summary_json(summary: BacktestSummary, run_id: str) -> None:
    out = DERIVED_DIR / f"{run_id}__backtest_summary.json"
    out.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")
    log.info(f"[BACKTEST] Summary JSON → {out}")


def _write_backtest_report(summary: BacktestSummary, run_id: str) -> None:
    lines = [
        f"# Backtest Report — {run_id}",
        f"**Jurisdiction:** {summary.state} / {summary.county}",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**Overall verdict:** `{summary.overall_verdict}`  |  **Strategy status:** `{summary.backtest_status}`",
        "",
        "## Aggregate Metrics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Folds run | {summary.folds_run} |",
        f"| Avg Precision | {summary.avg_precision:.3f} |",
        f"| Avg Recall | {summary.avg_recall:.3f} |",
        f"| Avg F1 | {summary.avg_f1:.3f} |",
        f"| Avg Support MAE | {summary.avg_support_mae:.4f} |",
        f"| Top-10 True Rate | {summary.avg_top10_rate:.1%} |",
        "",
        "## Fold-by-Fold Results",
        "",
        "| Held-Out Year | Training Years | Precision | Recall | F1 | Support MAE | Verdict |",
        "|---------------|----------------|-----------|--------|----|-------------|---------|",
    ]
    for f in summary.folds:
        years_str = ", ".join(str(y) for y in f["training_years"])
        lines.append(
            f"| {f['held_out_year']} | {years_str} "
            f"| {f['precision']:.3f} | {f['recall']:.3f} | {f['f1']:.3f} "
            f"| {f['support_mae']:.4f} | {f['verdict']} |"
        )

    lines += [
        "",
        "## Narrative Summary",
        "",
        f"**Would this model have helped?** {_narrative_verdict(summary)}",
        "",
        f"**Where would it have failed?** {_narrative_failures(summary)}",
        "",
        "## Data Sufficiency",
        "",
        summary.data_sufficiency_note,
    ]

    path = REPORTS_DIR / f"{run_id}__backtest_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[BACKTEST] Report → {path}")


def _narrative_verdict(summary: BacktestSummary) -> str:
    if summary.overall_verdict == "validated":
        return (f"Yes. Avg F1={summary.avg_f1:.2f} across {summary.folds_run} folds. "
                f"Top-10 precision={summary.avg_top10_rate:.1%}.")
    elif summary.overall_verdict == "partial":
        return (f"Partially. F1={summary.avg_f1:.2f} is marginal — useful for ranking "
                f"but not reliable for individual precinct decisions.")
    else:
        return (f"No — insufficient backtest data (F1={summary.avg_f1:.2f}, "
                f"folds={summary.folds_run}). Do not rely on swing targeting.")


def _narrative_failures(summary: BacktestSummary) -> str:
    fp_examples, fn_examples = [], []
    for f in summary.folds:
        fp_examples.extend(f.get("false_positives_examples", [])[:2])
        fn_examples.extend(f.get("false_negatives_examples", [])[:2])
    fp_str = ", ".join(str(p) for p in fp_examples[:5]) if fp_examples else "none identified"
    fn_str = ", ".join(str(p) for p in fn_examples[:5]) if fn_examples else "none identified"
    return (f"Top false positives (predicted swing, didn't): {fp_str}. "
            f"Top false negatives (missed actual swing): {fn_str}.")


def _write_data_sufficiency_report(summary: BacktestSummary, available_years: list, run_id: str) -> None:
    lines = [
        f"# Data Sufficiency Report — {run_id}",
        f"**Jurisdiction:** {summary.state} / {summary.county}",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "## Archive Depth",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Election years available | {len(available_years)} |",
        f"| Years | {', '.join(str(y) for y in available_years) or 'none'} |",
        f"| Backtest folds run | {summary.folds_run} |",
        f"| Comparable contest counts | general elections preferred |",
        "",
        "## Sufficiency Verdict",
        "",
        summary.data_sufficiency_note,
        "",
        "## Years Needed for Stronger Validation",
        "",
    ]
    if summary.years_needed_for_strong_validation:
        for y in summary.years_needed_for_strong_validation:
            lines.append(f"- {y} election data")
        lines.append("")
        lines.append("> Add these election years to `data/elections/CA/Sonoma/` and re-run archive build.")
    else:
        lines.append("Current archive depth is sufficient for validation.")

    path = REPORTS_DIR / f"{run_id}__data_sufficiency_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[BACKTEST] Sufficiency report → {path}")
