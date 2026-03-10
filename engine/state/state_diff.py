"""
engine/state/state_diff.py — Prompt 14.5

Computes a structured diff between two campaign state snapshots.

Entry point:
    diff_campaign_states(old_state, new_state, run_id, project_root)

Writes:
    reports/state/<RUN_ID>__state_diff.md
    derived/state/history/<RUN_ID>__state_diff.json
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# ── Fields to compare ────────────────────────────────────────────────────────
NUMERIC_FIELDS: list[tuple[str, ...]] = [
    ("model_summary", "win_probability"),
    ("model_summary", "expected_margin"),
    ("model_summary", "baseline_support"),
    ("model_summary", "baseline_turnout"),
    ("strategy_summary", "win_number"),
    ("strategy_summary", "vote_path_coverage"),
    ("strategy_summary", "field_pace_doors_per_week"),
    ("war_room_summary", "actual_field_doors"),
    ("war_room_summary", "actual_spend"),
    ("war_room_summary", "data_requests_count"),
    ("war_room_summary", "real_metrics_count"),
    ("provenance_summary", "REAL"),
    ("provenance_summary", "SIMULATED"),
    ("provenance_summary", "ESTIMATED"),
    ("provenance_summary", "MISSING"),
]

TEXT_FIELDS: list[tuple[str, ...]] = [
    ("campaign_setup", "election_date"),
    ("campaign_setup", "target_vote_share"),
    ("campaign_setup", "total_budget"),
    ("war_room_summary", "war_room_ready"),
    ("war_room_summary", "current_risk_level"),
    ("voter_intelligence_summary", "voter_file_loaded"),
    ("voter_intelligence_summary", "gotv_universe_size"),
    ("voter_intelligence_summary", "persuasion_universe_size"),
]


def _g(d: Any, *keys, default=None) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _pct_change(old: Any, new: Any) -> Optional[str]:
    try:
        o, n = float(old), float(new)
        if o == 0:
            return f"+{n:.2f}" if n != 0 else "no change"
        delta = (n - o) / abs(o) * 100
        sign  = "+" if delta >= 0 else ""
        return f"{sign}{delta:.1f}%"
    except (TypeError, ValueError):
        return None


def diff_campaign_states(
    old_state: dict,
    new_state: dict,
    run_id: str,
    project_root: Path,
) -> dict:
    """
    Compare old_state to new_state and write diff files.

    Returns the diff as a dict.
    """
    now = datetime.utcnow().isoformat()

    diff: dict = {
        "run_id":           run_id,
        "new_run_id":       new_state.get("run_id"),
        "old_run_id":       old_state.get("run_id") if old_state else None,
        "generated_at":     now,
        "prior_state_found": bool(old_state),
        "numeric_changes":  [],
        "text_changes":     [],
        "recommendations_changed": False,
        "data_requests_delta": 0,
        "risk_level_change": None,
        "key_changes": [],
    }

    if not old_state:
        diff["summary"] = "No prior state found. This is the first state snapshot."
        _write_diff(diff, run_id, project_root, new_state)
        return diff

    # ── Numeric comparisons ───────────────────────────────────────────────────
    for path in NUMERIC_FIELDS:
        old_val = _g(old_state, *path)
        new_val = _g(new_state, *path)
        if old_val == new_val:
            continue
        label = " → ".join(path)
        pct   = _pct_change(old_val, new_val)
        change = {
            "field":   label,
            "old":     _fmt(old_val),
            "new":     _fmt(new_val),
            "pct_change": pct,
        }
        diff["numeric_changes"].append(change)
        # Surface big wins/losses
        if "win_probability" in label and pct:
            diff["key_changes"].append(f"Win probability: {_fmt(old_val)} → {_fmt(new_val)} ({pct})")
        if "vote_path_coverage" in label and pct:
            diff["key_changes"].append(f"Vote path coverage: {_fmt(old_val)} → {_fmt(new_val)} ({pct})")
        if "real_metrics" in label.lower():
            diff["key_changes"].append(f"Real data metrics: {_fmt(old_val)} → {_fmt(new_val)}")

    # ── Text / categorical comparisons ────────────────────────────────────────
    for path in TEXT_FIELDS:
        old_val = _g(old_state, *path)
        new_val = _g(new_state, *path)
        if str(old_val) == str(new_val):
            continue
        label = " → ".join(path)
        diff["text_changes"].append({
            "field": label,
            "old":   _fmt(old_val),
            "new":   _fmt(new_val),
        })
        if "risk_level" in label:
            diff["risk_level_change"] = f"{_fmt(old_val)} → {_fmt(new_val)}"
            diff["key_changes"].append(f"Risk level: {_fmt(old_val)} → {_fmt(new_val)}")
        if "war_room_ready" in label:
            diff["key_changes"].append(f"War Room ready: {_fmt(old_val)} → {_fmt(new_val)}")

    # ── Data requests delta ───────────────────────────────────────────────────
    old_dr = len(old_state.get("data_requests", []))
    new_dr = len(new_state.get("data_requests", []))
    diff["data_requests_delta"] = new_dr - old_dr

    # ── Recommendations changed ───────────────────────────────────────────────
    old_recs = [r.get("description") for r in old_state.get("recommendations", [])]
    new_recs = [r.get("description") for r in new_state.get("recommendations", [])]
    diff["recommendations_changed"] = old_recs != new_recs

    # ── Summary sentence ─────────────────────────────────────────────────────
    n_changes = len(diff["numeric_changes"]) + len(diff["text_changes"])
    diff["summary"] = (
        f"{n_changes} field(s) changed since {old_state.get('run_id','prior run')}. "
        + (f"Key changes: {'; '.join(diff['key_changes'])}" if diff["key_changes"] else "No headline changes.")
    )

    _write_diff(diff, run_id, project_root, new_state)
    return diff


def _write_diff(diff: dict, run_id: str, project_root: Path, new_state: dict) -> None:
    """Write diff to JSON (history) and Markdown (reports)."""
    hist_dir   = project_root / "derived" / "state" / "history"
    reports_dir = project_root / "reports" / "state"
    hist_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = hist_dir / f"{run_id}__state_diff.json"
    json_path.write_text(json.dumps(diff, indent=2, default=str), encoding="utf-8")
    log.info(f"State diff JSON → {json_path.name}")

    # Markdown report
    md = _build_diff_md(diff, new_state)
    md_path = reports_dir / f"{run_id}__state_diff.md"
    md_path.write_text(md, encoding="utf-8")
    log.info(f"State diff MD → {md_path.name}")


def _build_diff_md(diff: dict, new_state: dict) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    run_id = diff.get("run_id", "")
    old_id = diff.get("old_run_id", "None")

    lines = [
        f"# Campaign State Diff",
        f"**Run:** `{run_id}`  **Prior:** `{old_id}`  **Generated:** {now}",
        "",
        f"## Summary",
        f"{diff.get('summary', '')}",
        "",
    ]

    if not diff.get("prior_state_found"):
        lines += ["> No prior state found. This is the first state snapshot.", ""]
        return "\n".join(lines)

    if diff.get("key_changes"):
        lines += ["## Key Changes", ""]
        for kc in diff["key_changes"]:
            lines.append(f"- {kc}")
        lines.append("")

    if diff.get("numeric_changes"):
        lines += [
            "## Numeric Field Changes",
            "",
            "| Field | Old | New | Change |",
            "|-------|-----|-----|--------|",
        ]
        for c in diff["numeric_changes"]:
            pct = c.get("pct_change") or ""
            lines.append(f"| {c['field']} | {c['old']} | {c['new']} | {pct} |")
        lines.append("")

    if diff.get("text_changes"):
        lines += [
            "## Categorical / Text Changes",
            "",
            "| Field | Old | New |",
            "|-------|-----|-----|",
        ]
        for c in diff["text_changes"]:
            lines.append(f"| {c['field']} | {c['old']} | {c['new']} |")
        lines.append("")

    dr_delta = diff.get("data_requests_delta", 0)
    if dr_delta != 0:
        arrow = "increased" if dr_delta > 0 else "decreased"
        lines.append(f"**Data Requests:** {arrow} by {abs(dr_delta)} since prior run.")
        lines.append("")

    rl = diff.get("risk_level_change")
    if rl:
        lines.append(f"**Risk Level Changed:** {rl}")
        lines.append("")

    lines += [
        "---",
        f"*All provenance types: REAL, SIMULATED, ESTIMATED, MISSING.*",
        f"*Enter real field/volunteer/budget data in the War Room to upgrade ESTIMATED → REAL.*",
    ]
    return "\n".join(lines)
