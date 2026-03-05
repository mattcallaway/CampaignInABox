"""
engine/audit/post_prompt86_audit.py — Prompt 8.7

Guaranteed post-run audit. Runs after every strategy generation.
Always emits reports/audit/post_prompt86_audit.json + .md

system_health: HEALTHY | DEGRADED | FAIL
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent

REQUIRED_ARTIFACTS = [
    "run.log", "pathway.json", "needs.yaml",
    "validation.md", "qa.md",
    "audit_report.json", "audit_report.md",
    "post_prompt86_audit.json", "post_prompt86_audit.md",
    "join_guard.md", "join_guard.csv",
    "integrity_repairs.md", "integrity_repairs.csv",
]


def run_post_prompt86_audit(
    *,
    run_id: str,
    contest_id: str,
    county: str,
    state: str,
    join_guard_rows: Optional[list[dict]] = None,
    integrity_repair_records: Optional[list[dict]] = None,
    geometry_result: Optional[dict] = None,
    strategy_pack_generated: bool = False,
    simulation_results_generated: bool = False,
    warnings: Optional[list[str]] = None,
    errors: Optional[list[str]] = None,
    logger=None,
) -> Path:
    """
    Run the post-run audit and write JSON + MD artifacts.
    Returns path to the JSON file.
    """
    now = datetime.datetime.now()
    warnings = list(warnings or [])
    errors   = list(errors   or [])

    # Check artifacts in logs/latest/
    latest_dir = BASE_DIR / "logs" / "latest"
    artifacts_created: list[str] = []
    missing_artifacts: list[str] = []

    for fname in REQUIRED_ARTIFACTS:
        p = latest_dir / fname
        if p.exists() and p.stat().st_size > 0:
            artifacts_created.append(fname)
        else:
            # Also check direct run-prefixed files
            _alt = _find_run_artifact(run_id, fname)
            if _alt:
                artifacts_created.append(fname)
            else:
                missing_artifacts.append(fname)

    # Join guard summary
    jg_status = "skipped"
    if join_guard_rows:
        statuses = [r.get("status", "PASS") for r in join_guard_rows]
        if "FAIL"  in statuses: jg_status = "FAIL"
        elif "WARN" in statuses: jg_status = "WARN"
        else:                    jg_status = "PASS"

    # Integrity
    integrity_repairs_count = 0
    if integrity_repair_records is not None:
        integrity_repairs_count = sum(
            1 for r in integrity_repair_records
            if r.get("repair_type") != "CRITICAL_NO_REPAIR"
        )

    # Geometry
    geo_status = "skipped"
    if geometry_result:
        geo_status = geometry_result.get("status", "SKIP").lower()

    # System health
    if errors and len(errors) > 0:
        system_health = "FAIL"
    elif not strategy_pack_generated or missing_artifacts:
        system_health = "DEGRADED"
        if missing_artifacts:
            warnings.append(f"Missing artifacts: {', '.join(missing_artifacts)}")
    else:
        system_health = "HEALTHY"

    payload = {
        "run_id":                     run_id,
        "timestamp":                  now.isoformat(),
        "contest_id":                 contest_id,
        "county":                     county,
        "state":                      state,
        "system_health":              system_health,
        "artifacts_created":          artifacts_created,
        "missing_artifacts":          missing_artifacts,
        "geometry_status":            geo_status,
        "join_guard_status":          jg_status,
        "integrity_repairs_count":    integrity_repairs_count,
        "strategy_pack_generated":    strategy_pack_generated,
        "simulation_results_generated": simulation_results_generated,
        "warnings":                   warnings,
        "errors":                     errors,
        "prompt":                     "8.7",
        "model_version":              "8.7",
    }

    _write_audit_artifacts(payload, run_id)

    if logger:
        logger.info(f"  [POST_AUDIT] system_health={system_health}, "
                    f"artifacts={len(artifacts_created)}/{len(REQUIRED_ARTIFACTS)}, "
                    f"missing={missing_artifacts}")

    return BASE_DIR / "reports" / "audit" / f"{run_id}__post_prompt86_audit.json"


def _find_run_artifact(run_id: str, fname: str) -> Optional[Path]:
    """Look in reports/ subdirs for a file matching run_id and basename fragment."""
    stem = Path(fname).stem
    suffix = Path(fname).suffix
    for subdir in ["reports/audit", "reports/qa", "reports/validation", "logs/runs"]:
        d = BASE_DIR / subdir
        if d.exists():
            for p in d.glob(f"*{run_id}*{stem}*{suffix}"):
                if p.is_file() and p.stat().st_size > 0:
                    return p
    return None


def _write_audit_artifacts(payload: dict, run_id: str) -> None:
    audit_dir = BASE_DIR / "reports" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    latest_dir = BASE_DIR / "logs" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = audit_dir / f"{run_id}__post_prompt86_audit.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # MD
    health = payload["system_health"]
    badge = {"HEALTHY": "✅", "DEGRADED": "⚠️", "FAIL": "❌"}.get(health, "?")
    present = len(payload["artifacts_created"])
    total   = len(REQUIRED_ARTIFACTS)
    missing = payload["missing_artifacts"]

    md = [
        f"# Post-Prompt-8.6 Audit {badge}",
        f"**Run:** `{run_id}`",
        f"**Contest:** `{payload['contest_id']}`  **State:** {payload['state']}  **County:** {payload['county']}",
        f"**Timestamp:** {payload['timestamp']}",
        f"**System Health:** `{health}` {badge}\n",
        "## Artifact Status",
        f"**{present}/{total}** required artifacts present" + (" ✅" if not missing else " ⚠️"),
    ]
    if missing:
        md.append("\n### Missing")
        md.extend([f"- `{m}`" for m in missing])
    md += [
        "\n## Diagnostic Status",
        f"| Check | Status |", "|---|---|",
        f"| Geometry | `{payload['geometry_status']}` |",
        f"| Join Guard | `{payload['join_guard_status']}` |",
        f"| Integrity Repairs | {payload['integrity_repairs_count']} repair(s) |",
        f"| Strategy Pack Generated | {'✅' if payload['strategy_pack_generated'] else '❌'} |",
        f"| Simulation Results | {'✅' if payload['simulation_results_generated'] else '❌'} |",
    ]
    if payload["warnings"]:
        md += ["\n## ⚠️ Warnings"]
        md.extend([f"- {w}" for w in payload["warnings"]])
    if payload["errors"]:
        md += ["\n## 🔴 Errors"]
        md.extend([f"- {e}" for e in payload["errors"]])

    md_path = audit_dir / f"{run_id}__post_prompt86_audit.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    # Update latest/ symlinks
    (latest_dir / "post_prompt86_audit.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (latest_dir / "post_prompt86_audit.md").write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    # Also alias as audit_report.json/md (backward compat + artifact_validator lookup)
    (latest_dir / "audit_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (latest_dir / "audit_report.md").write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    # Also write to the canonical audit_report location for backward compat
    (latest_dir / "system_health.json").write_text(
        json.dumps({"system_health": health, "run_id": run_id,
                    "missing_artifacts": missing, "geometry_status": payload["geometry_status"],
                    "join_guard_status": payload["join_guard_status"],
                    "integrity_repairs_count": payload["integrity_repairs_count"]}, indent=2),
        encoding="utf-8"
    )
