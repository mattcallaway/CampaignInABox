"""
engine/integrity/integrity_repairs.py — Prompt 8.7

Structured repair logging wrapper.
Always emits files even if empty.

Output:
  reports/qa/<RUN_ID>__integrity_repairs.md
  derived/diagnostics/<CONTEST_ID>__integrity_repairs.csv
"""
from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent

REPAIR_FIELDNAMES = [
    "repair_type", "dataset", "field", "original_value",
    "new_value", "reason", "timestamp", "precinct_id",
]


def log_repair(
    records: list[dict],
    *,
    repair_type: str,
    dataset: str,
    field: str,
    original_value,
    new_value,
    reason: str,
    precinct_id: str = "",
) -> None:
    """Append a structured repair record to `records`."""
    records.append({
        "repair_type":    repair_type,
        "dataset":        dataset,
        "field":          field,
        "original_value": original_value,
        "new_value":      new_value,
        "reason":         reason,
        "timestamp":      datetime.datetime.now().isoformat(),
        "precinct_id":    precinct_id,
    })


def build_repair_records_from_integrity_report(report: dict, dataset: str = "precinct_model") -> list[dict]:
    """Convert an integrity.py repair_report dict into structured repair records."""
    records: list[dict] = []
    ts = datetime.datetime.now().isoformat()

    for row in report.get("repairs", []):
        pid = row.get("precinct_id", "")
        rule = row.get("rule", "UNKNOWN")

        if rule == "BALLOTS_EXCEED_REG":
            records.append({
                "repair_type": "SCALE_DOWN",
                "dataset": dataset,
                "field": "ballots_cast",
                "original_value": row.get("bal_before", "?"),
                "new_value": row.get("bal_after", "?"),
                "reason": f"Ballots ({row.get('bal_before')}) exceeded registered ({row.get('reg_before')}). Scaled by {row.get('scale_factor', 1.0):.4f}",
                "timestamp": ts,
                "precinct_id": pid,
            })
        elif rule == "YES_NO_EXCEED_BALLOTS":
            records.append({
                "repair_type": "SCALE_DOWN",
                "dataset": dataset,
                "field": "yes_votes+no_votes",
                "original_value": f"{row.get('yes_before', 0)}+{row.get('no_before', 0)}",
                "new_value": f"{row.get('yes_after', 0)}+{row.get('no_after', 0)}",
                "reason": f"YES+NO exceeded ballots_cast. Scaled proportionally.",
                "timestamp": ts,
                "precinct_id": pid,
            })
        elif rule in ("neg_reg", "neg_bal", "neg_yes", "neg_no"):
            records.append({
                "repair_type": "CLAMP_NEGATIVE",
                "dataset": dataset,
                "field": rule.replace("neg_", ""),
                "original_value": "< 0",
                "new_value": "0",
                "reason": "Negative value clamped to 0",
                "timestamp": ts,
                "precinct_id": pid,
            })

    for row in report.get("critical_list", []):
        records.append({
            "repair_type": "CRITICAL_NO_REPAIR",
            "dataset": dataset,
            "field": "registered",
            "original_value": row.get("registered", 0),
            "new_value": row.get("registered", 0),
            "reason": row.get("note", "registered=0 with ballots>0 — not repaired (data extraction issue)"),
            "timestamp": ts,
            "precinct_id": row.get("precinct_id", ""),
        })

    return records


def write_repair_artifacts(
    records: list[dict],
    run_id: str,
    contest_id: str,
    before_totals: Optional[dict] = None,
    after_totals: Optional[dict] = None,
) -> None:
    """Always write CSV and MD — even if records is empty (emits empty-with-header files)."""
    qa_dir   = BASE_DIR / "reports" / "qa"
    diag_dir = BASE_DIR / "derived" / "diagnostics"
    qa_dir.mkdir(parents=True, exist_ok=True)
    diag_dir.mkdir(parents=True, exist_ok=True)

    # CSV (always written)
    csv_path = diag_dir / f"{contest_id}__integrity_repairs.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REPAIR_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    # Counts by type
    by_type: dict[str, int] = {}
    for r in records:
        by_type[r["repair_type"]] = by_type.get(r["repair_type"], 0) + 1
    critical = by_type.get("CRITICAL_NO_REPAIR", 0)
    repaired = sum(v for k, v in by_type.items() if k != "CRITICAL_NO_REPAIR")

    # Markdown
    health = "✅ Clean" if not records else (
        f"⚠️ {repaired} repair(s), {critical} CRITICAL" if repaired > 0
        else f"🔴 {critical} CRITICAL (data quality — not repaired)"
    )
    md = [
        f"# Integrity Repairs Report",
        f"**Run:** `{run_id}`  **Contest:** `{contest_id}`  **Status:** {health}\n",
    ]

    if before_totals and after_totals:
        md += [
            "## Countywide Totals",
            "| Metric | Before | After |",
            "|---|---|---|",
            f"| Registered | {before_totals.get('registered', 0):,} | {after_totals.get('registered', 0):,} |",
            f"| Ballots Cast | {before_totals.get('ballots_cast', 0):,} | {after_totals.get('ballots_cast', 0):,} |",
            "",
        ]

    if records:
        md += [
            "## Repair Log",
            "| Type | Dataset | Field | Original | New | Reason | Precinct |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in records[:100]:
            md.append(
                f"| {r['repair_type']} | {r['dataset']} | {r['field']} "
                f"| {r['original_value']} | {r['new_value']} "
                f"| {r['reason'][:60]} | {r['precinct_id']} |"
            )
    else:
        md.append("\n✅ No repairs required — all precinct data within constraints.")

    md_path = qa_dir / f"{run_id}__integrity_repairs.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    # Latest symlinks
    latest = BASE_DIR / "logs" / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "integrity_repairs.md").write_text(f"# See: {md_path}\n", encoding="utf-8")
    (latest / "integrity_repairs.csv").write_text(f"source,{csv_path}\n", encoding="utf-8")
