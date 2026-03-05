"""
scripts/lib/integrity.py  — Prompt 8.6 (updated)

Enforce precinct-level data constraints with deterministic repair.

Rules:
  1.  registered, ballots_cast, yes_votes, no_votes → integers
  2.  registered == 0 but ballots_cast > 0 → CRITICAL flag (do NOT repair)
  3.  ballots_cast > registered > 0  → scale ballots/yes/no down
  4.  yes + no > ballots_cast → scale yes/no down proportionally
  5.  Recompute turnout_pct and support_pct after repair

Outputs:
  derived/diagnostics/<contest_id>__integrity_repairs.csv
  reports/qa/<RUN_ID>__integrity_repairs.md
"""
from __future__ import annotations

import csv
import datetime
import math
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def enforce_precinct_constraints(
    df: pd.DataFrame,
    id_col: str = "canonical_precinct_id",
    registered_col: str = "registered",
    ballots_col: str = "ballots_cast",
    yes_col: Optional[str] = "yes_votes",
    no_col: Optional[str] = "no_votes",
    log_ctx: str = "",
    logger=None,
    contest_id: str = "unknown",
    run_id: str = "unknown",
) -> tuple[pd.DataFrame, dict]:
    """
    Apply constraint enforcement to a precinct DataFrame.

    Returns:
        (df_fixed, repair_report)

    The repair_report dict includes:
        repaired_rows, critical_rows, before_totals, after_totals,
        repairs (list of per-precinct records), join_guard_critical (bool)
    """
    df = df.copy()
    repairs: list[dict] = []
    critical_rows: list[dict] = []

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _int(val):
        try:
            f = float(val)
            return 0 if math.isnan(f) else max(0, int(f))
        except Exception:
            return 0

    def _safe_pct(num, den):
        try:
            if den <= 0:
                return 0.0
            return round(float(num) / float(den), 6)
        except Exception:
            return 0.0

    # Check which columns exist
    has_yes = yes_col and yes_col in df.columns
    has_no  = no_col  and no_col  in df.columns
    has_id  = id_col in df.columns

    # Convert to numeric first
    for col in [registered_col, ballots_col]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ([yes_col] if has_yes else []) + ([no_col] if has_no else []):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # ── Countywide totals BEFORE ──────────────────────────────────────────────
    before_totals = _compute_totals(df, registered_col, ballots_col,
                                    yes_col if has_yes else None,
                                    no_col  if has_no  else None)

    # ── Per-row pass ──────────────────────────────────────────────────────────
    for idx, row in df.iterrows():
        pid     = row.get(id_col, idx) if has_id else idx
        reg_raw = row[registered_col]
        bal_raw = row[ballots_col]
        yes_raw = row[yes_col] if has_yes else 0
        no_raw  = row[no_col]  if has_no  else 0

        reg = _int(reg_raw)
        bal = _int(bal_raw)
        yes = _int(yes_raw)
        no  = _int(no_raw)

        changed = False
        rule    = None

        # Rule 1: clamp negatives
        if reg < 0:
            reg = 0; changed = True; rule = "neg_reg"
        if bal < 0:
            bal = 0; changed = True; rule = rule or "neg_bal"
        if yes < 0:
            yes = 0; changed = True; rule = rule or "neg_yes"
        if no < 0:
            no  = 0; changed = True; rule = rule or "neg_no"

        # Rule 2: registered == 0 but ballots > 0 → CRITICAL, no repair
        if reg == 0 and bal > 0:
            critical_rows.append({
                "precinct_id": pid,
                "rule": "REG_ZERO_BALLOTS_NONZERO",
                "registered": reg,
                "ballots_cast": bal,
                "note": "Likely join/extraction error — registered not mapped from workbook",
            })
            # Still write canonical integers (don't change values)
            df.at[idx, registered_col] = reg
            df.at[idx, ballots_col]    = bal
            if has_yes: df.at[idx, yes_col] = yes
            if has_no:  df.at[idx, no_col]  = no
            continue

        # Rule 3: ballots > registered (and registered > 0)
        if reg > 0 and bal > reg:
            scale = reg / bal
            bal_new = reg
            yes_new = math.floor(yes * scale) if has_yes else 0
            no_new  = math.floor(no  * scale) if has_no  else 0
            repairs.append({
                "precinct_id":   pid,
                "rule":          "BALLOTS_EXCEED_REG",
                "reg_before":    reg, "bal_before": bal,
                "yes_before":    yes, "no_before":  no,
                "bal_after":     bal_new,
                "yes_after":     yes_new, "no_after": no_new,
                "scale_factor":  round(scale, 6),
            })
            bal = bal_new; yes = yes_new; no = no_new
            changed = True; rule = "BALLOTS_EXCEED_REG"

        # Rule 4: yes + no > ballots
        if has_yes and has_no and (yes + no) > bal and bal > 0:
            total_votes = yes + no
            if total_votes > 0:
                yes_new = math.floor(yes * bal / total_votes)
                no_new  = bal - yes_new
                repairs.append({
                    "precinct_id": pid,
                    "rule":        "YES_NO_EXCEED_BALLOTS",
                    "reg_before":  reg, "bal_before": bal,
                    "yes_before":  yes, "no_before":  no,
                    "yes_after":   yes_new, "no_after": no_new,
                    "scale_factor": round(bal / total_votes, 6),
                })
                yes = yes_new; no = no_new
                changed = True; rule = rule or "YES_NO_EXCEED_BALLOTS"

        # Write back integers
        df.at[idx, registered_col] = reg
        df.at[idx, ballots_col]    = bal
        if has_yes: df.at[idx, yes_col] = yes
        if has_no:  df.at[idx, no_col]  = no

    # ── Recompute derived metrics ─────────────────────────────────────────────
    if "turnout_pct" in df.columns:
        df["turnout_pct"] = df.apply(
            lambda r: _safe_pct(r[ballots_col], r[registered_col]), axis=1
        )
    if "support_pct" in df.columns and has_yes:
        df["support_pct"] = df.apply(
            lambda r: _safe_pct(r[yes_col], r[ballots_col]), axis=1
        )

    # ── Countywide totals AFTER ───────────────────────────────────────────────
    after_totals = _compute_totals(df, registered_col, ballots_col,
                                   yes_col if has_yes else None,
                                   no_col  if has_no  else None)

    # ── Summary logging ───────────────────────────────────────────────────────
    n_repaired  = len(repairs)
    n_critical  = len(critical_rows)

    if logger:
        if n_critical:
            logger.warn(
                f"  [INTEGRITY] {n_critical} precinct(s) CRITICAL — "
                f"registered=0 but ballots>0. Indicates data extraction issue."
            )
        if n_repaired:
            logger.info(f"  [INTEGRITY] {n_repaired} precinct(s) repaired (scaling applied)")
        if n_repaired == 0 and n_critical == 0:
            logger.info(f"  [INTEGRITY] All {len(df)} precincts pass constraints — no repairs needed")

    # ── Build report ──────────────────────────────────────────────────────────
    report = {
        "context":          log_ctx,
        "contest_id":       contest_id,
        "run_id":           run_id,
        "timestamp":        datetime.datetime.now().isoformat(),
        "total_rows":       len(df),
        "repaired_rows":    n_repaired,
        "critical_rows":    n_critical,
        "join_guard_critical": False,   # set True externally if JoinExplosionError caught
        "before_totals":    before_totals,
        "after_totals":     after_totals,
        "repairs":          repairs[:50],
        "critical_list":    critical_rows[:50],
    }

    _write_integrity_report(report, contest_id, run_id)

    return df, report


def _compute_totals(df, reg_col, bal_col, yes_col, no_col) -> dict:
    totals = {
        "registered":   int(pd.to_numeric(df.get(reg_col, pd.Series()), errors="coerce").fillna(0).sum()),
        "ballots_cast": int(pd.to_numeric(df.get(bal_col, pd.Series()), errors="coerce").fillna(0).sum()),
    }
    if yes_col and yes_col in df.columns:
        totals["yes_votes"] = int(pd.to_numeric(df[yes_col], errors="coerce").fillna(0).sum())
    if no_col and no_col in df.columns:
        totals["no_votes"] = int(pd.to_numeric(df[no_col], errors="coerce").fillna(0).sum())
    return totals


def _write_integrity_report(report: dict, contest_id: str, run_id: str) -> None:
    """Write CSV diagnostics and Markdown QA report."""
    diag_dir = BASE_DIR / "derived" / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    qa_dir = BASE_DIR / "reports" / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    # CSV (repairs + criticals)
    csv_path = diag_dir / f"{contest_id}__integrity_repairs.csv"
    all_rows = report["repairs"] + report.get("critical_list", [])
    if all_rows:
        fieldnames = sorted({k for r in all_rows for k in r.keys()})
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_rows)

    # Markdown
    bt = report["before_totals"]
    at = report["after_totals"]

    md = [
        f"# Integrity Repair Report",
        f"**Contest:** `{contest_id}`  **Run:** `{run_id}`  **Context:** {report.get('context', '')}",
        f"\n## Summary",
        f"- Total precincts: {report['total_rows']}",
        f"- Repaired: {report['repaired_rows']}",
        f"- Critical (NOT repaired — data quality issue): {report['critical_rows']}",
        f"\n## Countywide Totals",
        "| Metric | Before | After |",
        "|---|---|---|",
        f"| Registered | {bt.get('registered', 0):,} | {at.get('registered', 0):,} |",
        f"| Ballots Cast | {bt.get('ballots_cast', 0):,} | {at.get('ballots_cast', 0):,} |",
    ]
    if "yes_votes" in bt:
        md.append(f"| Yes Votes | {bt.get('yes_votes', 0):,} | {at.get('yes_votes', 0):,} |")
    if "no_votes" in bt:
        md.append(f"| No Votes | {bt.get('no_votes', 0):,} | {at.get('no_votes', 0):,} |")

    if report["critical_rows"]:
        md.append(f"\n## ⚠️ Critical Rows (Not Repaired)")
        md.append("| Precinct | Rule | Registered | Ballots | Note |")
        md.append("|---|---|---|---|---|")
        for r in report.get("critical_list", [])[:20]:
            md.append(
                f"| {r.get('precinct_id', '?')} | {r.get('rule', '?')} "
                f"| {r.get('registered', 0)} | {r.get('ballots_cast', 0)} | {r.get('note', '')} |"
            )
    if report["repaired_rows"]:
        md.append(f"\n## Repaired Precincts (top 50)")
        md.append("| Precinct | Rule | Bal Before | Bal After | Scale |")
        md.append("|---|---|---|---|---|")
        for r in report["repairs"][:50]:
            md.append(
                f"| {r.get('precinct_id', '?')} | {r.get('rule', '?')} "
                f"| {r.get('bal_before', 0)} | {r.get('bal_after', 0)} "
                f"| {r.get('scale_factor', 1.0):.4f} |"
            )

    md_path = qa_dir / f"{run_id}__integrity_repairs.md"
    md_path.write_text("\n".join(md), encoding="utf-8")


# Backward-compat alias
write_integrity_report = _write_integrity_report
