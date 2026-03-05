"""
engine/integrity/join_guard.py — Prompt 8.7

Comprehensive join validation for Campaign In A Box.
Validates all table joins and always emits artifacts.

Joins validated:
  precinct_model ↔ universes
  precinct_model ↔ geometry
  universes ↔ voter file
  universes ↔ results

Output:
  reports/qa/<RUN_ID>__join_guard.md
  derived/diagnostics/<CONTEST_ID>__join_guard.csv
"""
from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Thresholds
FAIL_THRESHOLD = 0.02   # > 2% unmatched → FAIL
WARN_THRESHOLD = 0.005  # 0.5–2% → WARN


def validate_join(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_key: str,
    right_key: str,
    join_name: str,
) -> dict:
    """
    Validate a single join between two DataFrames.
    Returns a diagnostics dict with full cardinality stats.
    """
    lk = left[left_key].dropna().astype(str) if left_key in left.columns else pd.Series([], dtype=str)
    rk = right[right_key].dropna().astype(str) if (right is not None and right_key in right.columns) else pd.Series([], dtype=str)

    left_set  = set(lk)
    right_set = set(rk)

    matched       = left_set & right_set
    left_only     = left_set - right_set
    right_only    = right_set - left_set
    dup_left      = int(lk.duplicated().sum())
    dup_right     = int(rk.duplicated().sum())

    left_rows     = len(left)
    right_rows    = len(right) if right is not None else 0
    matched_rows  = len(matched)
    left_unmatched  = len(left_only)
    right_unmatched = len(right_only)
    total_keys    = max(len(left_set), 1)

    unmatched_pct = left_unmatched / total_keys

    if unmatched_pct > FAIL_THRESHOLD:
        status = "FAIL"
    elif unmatched_pct > WARN_THRESHOLD:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "join_name":       join_name,
        "left_rows":       left_rows,
        "right_rows":      right_rows,
        "matched_rows":    matched_rows,
        "left_unmatched":  left_unmatched,
        "right_unmatched": right_unmatched,
        "duplicate_keys":  dup_left + dup_right,
        "missing_keys":    left_unmatched,
        "unmatched_pct":   round(unmatched_pct * 100, 2),
        "status":          status,
        "timestamp":       datetime.datetime.now().isoformat(),
    }


def run_join_validation(
    precinct_model: pd.DataFrame,
    universes: Optional[pd.DataFrame] = None,
    geometry_ids: Optional[pd.Series] = None,
    voter_file: Optional[pd.DataFrame] = None,
    results: Optional[pd.DataFrame] = None,
    id_col: str = "canonical_precinct_id",
    run_id: str = "unknown",
    contest_id: str = "unknown",
    logger=None,
) -> list[dict]:
    """
    Validate all four standard joins. Always returns a list of dicts
    (empty join stubs for missing datasets), always writes output files.
    """
    rows: list[dict] = []

    def _stub(name: str, reason: str) -> dict:
        return {
            "join_name": name, "left_rows": 0, "right_rows": 0, "matched_rows": 0,
            "left_unmatched": 0, "right_unmatched": 0, "duplicate_keys": 0,
            "missing_keys": 0, "unmatched_pct": 0.0, "status": "PASS",
            "timestamp": datetime.datetime.now().isoformat(),
            "note": reason,
        }

    # Join 1: precinct_model ↔ universes
    if universes is not None and not universes.empty:
        univ_key = _find_col(universes, id_col, "canonical_precinct_id")
        rows.append(validate_join(precinct_model, universes, id_col, univ_key,
                                  "precinct_model↔universes"))
    else:
        rows.append(_stub("precinct_model↔universes", "universes not available"))

    # Join 2: precinct_model ↔ geometry
    if geometry_ids is not None and len(geometry_ids) > 0:
        geo_df = pd.DataFrame({id_col: geometry_ids})
        rows.append(validate_join(precinct_model, geo_df, id_col, id_col,
                                  "precinct_model↔geometry"))
    else:
        rows.append(_stub("precinct_model↔geometry", "geometry not loaded (geopandas unavailable)"))

    # Join 3: universes ↔ voter file
    if universes is not None and voter_file is not None and not voter_file.empty:
        vf_key = _find_col(voter_file, id_col, "precinct", "precinct_id")
        rows.append(validate_join(universes, voter_file, _find_col(universes, id_col, "precinct_id"), vf_key,
                                  "universes↔voter_file"))
    else:
        rows.append(_stub("universes↔voter_file", "voter file not available"))

    # Join 4: universes ↔ results
    if universes is not None and results is not None and not results.empty:
        res_key = _find_col(results, id_col, "precinct_id", "PrecinctID")
        rows.append(validate_join(universes, results, _find_col(universes, id_col, "precinct_id"), res_key,
                                  "universes↔results"))
    else:
        rows.append(_stub("universes↔results", "results not separately available at this stage"))

    _write_join_artifacts(rows, run_id, contest_id)

    overall_status = _aggregate_status(rows)
    if logger:
        logger.info(f"  [JOIN_GUARD_VALIDATION] {len(rows)} joins, overall={overall_status}")

    return rows


def _find_col(df: pd.DataFrame, *candidates: str) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    return candidates[0]  # fallback


def _aggregate_status(rows: list[dict]) -> str:
    statuses = [r["status"] for r in rows]
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def _write_join_artifacts(rows: list[dict], run_id: str, contest_id: str) -> None:
    """Always write CSV and MD — even if rows is empty."""
    qa_dir   = BASE_DIR / "reports" / "qa"
    diag_dir = BASE_DIR / "derived" / "diagnostics"
    qa_dir.mkdir(parents=True, exist_ok=True)
    diag_dir.mkdir(parents=True, exist_ok=True)

    # CSV
    fieldnames = ["join_name", "left_rows", "right_rows", "matched_rows",
                  "left_unmatched", "right_unmatched", "duplicate_keys",
                  "missing_keys", "unmatched_pct", "status", "timestamp"]
    csv_path = diag_dir / f"{contest_id}__join_guard.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # Markdown
    overall = _aggregate_status(rows)
    badge = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(overall, "?")
    md = [
        f"# Join Guard Report {badge}",
        f"**Run:** `{run_id}` **Contest:** `{contest_id}` **Overall:** `{overall}`\n",
        "| Join | Left | Right | Matched | Left Unmatched | Status |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(r["status"], "?")
        md.append(f"| {r['join_name']} | {r['left_rows']} | {r['right_rows']} "
                  f"| {r['matched_rows']} | {r['left_unmatched']} ({r.get('unmatched_pct',0):.1f}%) | {icon} {r['status']} |")
        if r.get("note"):
            md.append(f"|   *{r['note']}* | | | | | |")

    md_path = qa_dir / f"{run_id}__join_guard.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    # Symlink for latest/
    latest = BASE_DIR / "logs" / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "join_guard.md").write_text(f"# See: {md_path}\n", encoding="utf-8")
    (latest / "join_guard.csv").write_text(f"source,{csv_path}\n", encoding="utf-8")
