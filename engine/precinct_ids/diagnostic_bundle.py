"""
engine/precinct_ids/diagnostic_bundle.py — Prompt 29

Writes the 5-file diagnostic bundle to reports/crosswalk_repair/<RUN_ID>/

Files written:
  1. crosswalk_repair_summary.md       — human-readable executive summary
  2. crosswalk_repair_trace.json       — machine-readable deep trace
  3. precinct_join_diagnostics.csv     — row-level join diagnostics
  4. map_render_diagnostics.md         — map behavior explanation
  5. pre_audit_human_review.md         — pre-audit worksheet
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def write_diagnostic_bundle(
    run_id:           str,
    state:            str,
    county:           str,
    contest_slug:     str,
    contest_file:     str,
    introspect_reports: list,          # list[CrosswalkFileReport]
    join_quality_report,               # JoinQualityReport
    trace_rows:       list[dict],      # sampled join trace rows
    output_dir:       Optional[Path] = None,
) -> dict[str, Path]:
    """
    Write all 5 diagnostic files. Returns {name: path}.
    """
    if output_dir is None:
        output_dir = BASE_DIR / "reports" / "crosswalk_repair" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    ts  = datetime.now().strftime("%Y-%m-%d %H:%M")
    jq  = join_quality_report
    paths: dict[str, Path] = {}

    # ── File 1: Executive Summary MD ─────────────────────────────────────────
    ok_files   = [r for r in introspect_reports if r.detection_ok]
    fail_files = [r for r in introspect_reports if not r.detection_ok]
    summary_md = [
        f"# Crosswalk Repair Summary",
        f"**Run:** `{run_id}`  **Generated:** {ts}",
        f"**Contest:** `{contest_slug}`  **State:** `{state}`  **County:** `{county}`",
        "",
        "---",
        "",
        "## Status",
        "",
        f"| Item | Result |",
        f"|---|---|",
        f"| Crosswalk files inspected | {len(introspect_reports)} |",
        f"| Detection OK | {len(ok_files)} |",
        f"| Detection failed (identity fallback risk) | {len(fail_files)} |",
        f"| Join quality verdict | **{jq.quality_verdict}** |",
        f"| Total contest rows | {jq.total_contest_rows} |",
        f"| Joined to geometry | {jq.total_joined} ({jq.pct_joined}%) |",
        f"| Unjoined | {jq.total_unjoined} |",
        f"| Identity fallbacks | {jq.identity_fallbacks} |",
        "",
        "---",
        "",
        "## What Was Repaired (Prompt 29)",
        "",
        "- `detect_crosswalk_columns()` upgraded from uppercase-only alias matching to a 3-tier",
        "  resolution system: (1) per-file config override, (2) expanded alias table including",
        "  lowercase column names, (3) filename heuristic tiebreaker.",
        "- `config/precinct_id/crosswalk_column_hints.yaml` created with explicit column hints",
        "  for all 5 Sonoma crosswalk files.",
        "- `load_crosswalk_from_category()` now emits an explicit `IDENTITY_FALLBACK_USED`",
        "  diagnostic instead of silently returning `{}, False`.",
        "- Join outcome taxonomy added (`engine/precinct_ids/join_outcomes.py`).",
        "- Per-row ID trace module added (`engine/precinct_ids/id_trace.py`).",
        "- Join quality metrics module added (`engine/precinct_ids/join_quality.py`).",
        "- Human review queue writer added (`engine/precinct_ids/review_queue.py`).",
        "",
    ]

    if fail_files:
        summary_md += [
            "## Remaining Issues (Crosswalk Detection Failures)",
            "",
        ]
        for r in fail_files:
            summary_md.append(f"- `{r.filename}`: {r.detection_failure_reason}")
        summary_md.append("")

    if jq.quality_notes:
        summary_md += ["## Quality Notes", ""]
        for note in jq.quality_notes:
            summary_md.append(f"- {note}")
        summary_md.append("")

    summary_md += [
        "## Next Recommended Action",
        "",
        "1. Review `pre_audit_human_review.md` for any outstanding ambiguities.",
        "2. If identity fallbacks still occur, add entries to `config/precinct_id/crosswalk_column_hints.yaml`.",
        "3. Re-run the pipeline and check that join quality verdict improves to GOOD.",
        "4. If precinct value remaps are needed, add them to `config/precinct_id/manual_mapping_overrides.yaml`.",
    ]

    p1 = output_dir / "crosswalk_repair_summary.md"
    p1.write_text("\n".join(summary_md), encoding="utf-8")
    paths["crosswalk_repair_summary"] = p1

    # ── File 2: Deep Trace JSON ───────────────────────────────────────────────
    from dataclasses import asdict
    trace_json = {
        "run_id":      run_id,
        "state":       state,
        "county":      county,
        "contest_slug": contest_slug,
        "contest_file": contest_file,
        "generated":   ts,
        "crosswalk_files": [asdict(r) for r in introspect_reports],
        "join_quality":    asdict(jq),
        "sampled_trace_rows": trace_rows[:500],
    }
    p2 = output_dir / "crosswalk_repair_trace.json"
    p2.write_text(json.dumps(trace_json, indent=2, default=str), encoding="utf-8")
    paths["crosswalk_repair_trace"] = p2

    # ── File 3: Row-level join diagnostics CSV ────────────────────────────────
    p3 = output_dir / "precinct_join_diagnostics.csv"
    if trace_rows:
        fieldnames = list(trace_rows[0].keys()) if trace_rows else []
        with open(p3, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(trace_rows[:2000])
        paths["precinct_join_diagnostics"] = p3

    # ── File 4: Map render diagnostics MD ────────────────────────────────────
    map_md = [
        f"# Map Render Diagnostics",
        f"**Run:** `{run_id}`  **Generated:** {ts}",
        "",
        "## Geometry File Used",
        f"- State: `{state}`, County: `{county}`",
        f"- Geometry type: MPREC (preferred) → SRPREC (fallback)",
        f"- Source directory: `data/{state}/counties/{county}/geography/precinct_shapes/`",
        "",
        "## Join Coverage",
        f"- Contest rows with precinct data: {jq.total_contest_rows}",
        f"- Joined to geometry: {jq.total_joined} ({jq.pct_joined}%)",
        f"- Not joined: {jq.total_unjoined}",
        f"- Identity fallbacks used: {jq.identity_fallbacks}",
        "",
        "## Why Scattered/Wrong Precincts Appeared Previously",
        "",
        "Before Prompt 29 repair:",
        "- `detect_crosswalk_columns()` expected uppercase column names (BLOCK20, MPREC_ID, SRPREC_ID)",
        "- Sonoma crosswalk files use lowercase short names (block, mprec, srprec)",
        "- Every crosswalk silently failed with `return {}, False`",
        "- Contest precinct strings were used **as-is** as geometry join keys",
        "- If any raw precinct strings accidentally matched geometry IDs, those",
        "  precincts appeared on the map — hence the 'random scattered' pattern",
        "",
        "## After Prompt 29 Repair",
        f"- Crosswalk detection: {len(ok_files)}/{len(introspect_reports)} files OK",
        f"- Join quality: **{jq.quality_verdict}** ({jq.pct_joined}% joined)",
        "",
        "## Action Required If Map Is Still Sparse",
        "1. Check `crosswalk_repair_summary.md` for remaining detection failures",
        "2. Open `derived/precinct_id_review/*__crosswalk_review.csv` for specifics",
        "3. Add missing hints to `config/precinct_id/crosswalk_column_hints.yaml`",
    ]
    p4 = output_dir / "map_render_diagnostics.md"
    p4.write_text("\n".join(map_md), encoding="utf-8")
    paths["map_render_diagnostics"] = p4

    # ── File 5: Pre-audit human review worksheet ──────────────────────────────
    review_md = [
        f"# Pre-Audit Human Review Worksheet",
        f"**Run:** `{run_id}`  **Generated:** {ts}",
        "",
        "> This document must be reviewed by a human before the next full audit.",
        "> Fill in the **Human Decision** column for each item.",
        "",
        "---",
        "",
        "## 1. Crosswalk Detection Status",
        "",
        "| File | Detection OK? | Source Col | Target Col | Action Needed |",
        "|---|---|---|---|---|",
    ]
    for r in introspect_reports:
        status  = "✅ Yes" if r.detection_ok else "❌ No"
        src     = r.source_col or "NOT FOUND"
        tgt     = r.target_col or "NOT FOUND"
        action  = "None" if r.detection_ok else f"Add hint for `{r.filename}` in crosswalk_column_hints.yaml"
        review_md.append(f"| `{r.filename}` | {status} | `{src}` | `{tgt}` | {action} |")

    review_md += [
        "",
        "---",
        "",
        "## 2. Join Quality Summary",
        "",
        f"- Verdict: **{jq.quality_verdict}**",
        f"- % Joined: {jq.pct_joined}%",
        f"- Identity fallbacks: {jq.identity_fallbacks}",
        "",
        "**Human Decision:** Is this join rate acceptable for the next audit? ____",
        "",
        "---",
        "",
        "## 3. Questions for Human Review",
        "",
        "1. Are all 5 crosswalk files the correct vintage (g24) for this contest year?",
        "   - **Answer:** ____",
        "",
        "2. Do any precinct IDs in the uploaded contest file look like truncated/stripped values?",
        "   - Check `precinct_join_diagnostics.csv` column `raw_precinct_value`",
        "   - **Answer:** ____",
        "",
        "3. If identity fallback was used, do any map points appear at wrong locations?",
        "   - **Answer:** ____",
        "",
        "4. Is the crosswalk repair complete, or are further manual overrides needed?",
        "   - If yes, add entries to `config/precinct_id/manual_mapping_overrides.yaml`",
        "   - **Answer:** ____",
        "",
        "---",
        "",
        "## 4. Files to Inspect",
        "",
        f"- `reports/crosswalk_repair/{run_id}/crosswalk_repair_summary.md`",
        f"- `reports/crosswalk_repair/{run_id}/crosswalk_repair_trace.json`",
        f"- `reports/crosswalk_repair/{run_id}/precinct_join_diagnostics.csv`",
        f"- `derived/precinct_id_review/{run_id}__crosswalk_review.csv`",
        f"- `derived/precinct_id_review/{run_id}__join_review.csv`",
        f"- `config/precinct_id/crosswalk_column_hints.yaml`",
        f"- `config/precinct_id/manual_mapping_overrides.yaml`",
        "",
        "---",
        "",
        "## 5. Platform Readiness for Next Audit",
        "",
        f"**Current join quality:** {jq.quality_verdict}",
        "**Ready for full audit?** ____",
        "**Reviewer:** ____",
        "**Review date:** ____",
    ]
    p5 = output_dir / "pre_audit_human_review.md"
    p5.write_text("\n".join(review_md), encoding="utf-8")
    paths["pre_audit_human_review"] = p5

    log.info(f"[BUNDLE] Diagnostic bundle written to {output_dir}")
    return paths
