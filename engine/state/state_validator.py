"""
engine/state/state_validator.py — Prompt 14.5

Validates a campaign state dict against the canonical schema.
Writes a validation report to reports/validation/.

Entry point:
    validate_state(state, run_id, project_root) -> (bool, list[str])
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _g(d: Any, *keys, default=None) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def validate_state(
    state: dict,
    run_id: str,
    project_root: Path,
) -> tuple[bool, list[str]]:
    """
    Validate the campaign state dict.

    Returns:
        (passed: bool, issues: list[str])
    Side-effect: writes reports/validation/<run_id>__state_validation.md
    """
    from engine.state.state_schema import REQUIRED_KEYS

    issues: list[str] = []
    warnings: list[str] = []

    # 1. Required top-level keys
    for key in REQUIRED_KEYS:
        if key not in state:
            issues.append(f"MISSING required key: '{key}'")

    # 2. run_id / contest_id non-empty
    if not state.get("run_id"):
        issues.append("run_id is empty")
    if not state.get("contest_id"):
        warnings.append("contest_id is empty — may be unconfigured")

    # 3. Artifact index — paths that exist must point to real files
    ai = state.get("artifact_index", {})
    for name, rel_path in ai.items():
        if rel_path is not None:
            full = project_root / rel_path
            if not full.exists():
                warnings.append(f"artifact_index.{name} points to non-existent file: {rel_path}")

    # 4. Numeric summaries where strategy exists
    ss = state.get("strategy_summary", {})
    ms = state.get("model_summary", {})
    if ai.get("strategy_meta"):
        if ss.get("win_number") is None:
            warnings.append("strategy_summary.win_number is None but strategy_meta is present")
        if ms.get("precinct_count") is None or ms.get("precinct_count") == 0:
            warnings.append("model_summary.precinct_count is 0 or None")

    # 5. Provenance totals consistent
    ps = state.get("provenance_summary", {})
    total_prov = ps.get("REAL", 0) + ps.get("SIMULATED", 0) + ps.get("ESTIMATED", 0) + ps.get("MISSING", 0)
    stated_total = ps.get("total", 0)
    if stated_total > 0 and total_prov != stated_total:
        warnings.append(f"provenance_summary.total ({stated_total}) != sum of types ({total_prov})")

    # 6. Recommendations non-empty when strategy exists
    recs = state.get("recommendations", [])
    if ai.get("strategy_meta") and len(recs) == 0:
        warnings.append("recommendations list is empty despite strategy being generated")

    # 7. No voter-level PII check (field names in campaign_setup only)
    forbidden = ["voter_id", "van_id", "first_name", "last_name", "address", "phone", "email"]
    state_str = json.dumps(state).lower()
    for f_ in forbidden:
        if f'"' + f_ + '"' in state_str:
            issues.append(f"SECURITY: state contains forbidden PII field name '{f_}'")

    passed = len(issues) == 0
    _write_validation_report(state, run_id, project_root, issues, warnings, passed)
    return passed, issues + warnings


def _write_validation_report(
    state: dict,
    run_id: str,
    project_root: Path,
    issues: list[str],
    warnings: list[str],
    passed: bool,
) -> None:
    val_dir = project_root / "reports" / "validation"
    val_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    status_icon = "✅ PASS" if passed else "❌ FAIL"
    lines = [
        f"# State Validation Report — {status_icon}",
        f"**Run:** `{run_id}`  **Validated:** {now}",
        "",
        f"**Issues:** {len(issues)}  **Warnings:** {len(warnings)}",
        "",
    ]
    if issues:
        lines += ["## ❌ Issues (must fix)", ""]
        for iss in issues:
            lines.append(f"- {iss}")
        lines.append("")
    if warnings:
        lines += ["## ⚠️ Warnings (review)", ""]
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Quick summary table
    ps = state.get("provenance_summary", {})
    ai = state.get("artifact_index", {})
    lines += [
        "## State Summary",
        "",
        f"| Key | Value |",
        f"|-----|-------|",
        f"| run_id | `{state.get('run_id')}` |",
        f"| contest_id | `{state.get('contest_id')}` |",
        f"| recommendations | {len(state.get('recommendations', []))} |",
        f"| data_requests | {len(state.get('data_requests', []))} |",
        f"| risks | {len(state.get('risks', []))} |",
        f"| provenance REAL | {ps.get('REAL', 0)} |",
        f"| provenance SIMULATED | {ps.get('SIMULATED', 0)} |",
        f"| provenance ESTIMATED | {ps.get('ESTIMATED', 0)} |",
        f"| provenance MISSING | {ps.get('MISSING', 0)} |",
        f"| war_room_ready | {state.get('war_room_summary', {}).get('war_room_ready', False)} |",
        f"| artifact_index keys present | {sum(1 for v in ai.values() if v)} / {len(ai)} |",
        "",
        "---",
        "*State validation by engine/state/state_validator.py — Prompt 14.5*",
    ]
    out_path = val_dir / f"{run_id}__state_validation.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"State validation report → {out_path.name} | passed={passed}")
