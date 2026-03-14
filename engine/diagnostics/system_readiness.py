"""
engine/diagnostics/system_readiness.py — Prompt 31 Feature 7

Evaluates overall system readiness and produces a readable report.
Does NOT modify any data or UI.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

STATUS_PRESENT    = "PRESENT"
STATUS_MISSING    = "MISSING"
STATUS_OK         = "OK"
STATUS_WARN       = "WARN"
STATUS_FAIL       = "FAIL"
STATUS_UNKNOWN    = "UNKNOWN"
STATUS_NOT_BUILT  = "NOT BUILT"


@dataclass
class ReadinessCheck:
    name: str
    status: str
    detail: str
    action: Optional[str] = None


@dataclass
class SystemReadinessReport:
    generated_at: str
    overall: str                       # READY | PARTIAL | NOT_READY
    checks: list[ReadinessCheck] = field(default_factory=list)
    action_required: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        icon = {"READY": "✅", "PARTIAL": "⚠️", "NOT_READY": "❌"}.get(self.overall, "•")
        lines = [
            "# System Readiness Report",
            f"**Generated:** {self.generated_at}",
            f"**Overall Status:** {icon} {self.overall}",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
        ]
        status_icons = {
            STATUS_PRESENT: "✅", STATUS_OK: "✅", STATUS_MISSING: "❌",
            STATUS_FAIL: "❌", STATUS_NOT_BUILT: "⏳", STATUS_WARN: "⚠️", STATUS_UNKNOWN: "❓",
        }
        for c in self.checks:
            si = status_icons.get(c.status, "•")
            lines.append(f"| {c.name} | {si} {c.status} | {c.detail} |")

        if self.action_required:
            lines += ["", "## Actions Required", ""]
            for act in self.action_required:
                lines.append(f"- {act}")

        return "\n".join(lines)


def evaluate_system_state(
    project_root: Path,
    state: str = "CA",
    county: str = "Sonoma",
) -> SystemReadinessReport:
    """Evaluate complete system readiness."""
    checks: list[ReadinessCheck] = []
    actions: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Contest data ──────────────────────────────────────────────────────────
    contest_root = project_root / "data" / "contests" / state / county
    contest_files = list(contest_root.rglob("raw/*.xlsx")) + list(contest_root.rglob("raw/*.csv")) if contest_root.exists() else []
    checks.append(ReadinessCheck(
        name="Contest Data",
        status=STATUS_PRESENT if contest_files else STATUS_MISSING,
        detail=f"{len(contest_files)} file(s) in data/contests/{state}/{county}/*/raw/",
        action=None if contest_files else f"Upload election results to data/contests/{state}/{county}/<year>/<slug>/raw/",
    ))
    if not contest_files:
        actions.append("Upload contest data via Data Manager → Upload New File")

    # ── Pipeline run history ──────────────────────────────────────────────────
    log_dir = project_root / "logs" / "runs"
    run_logs = sorted(log_dir.glob("*.log")) if log_dir.exists() else []
    last_run = run_logs[-1].name if run_logs else None
    checks.append(ReadinessCheck(
        name="Pipeline Run",
        status="OK" if run_logs else "NOT BUILT",
        detail=f"Last run: {last_run}" if last_run else "No pipeline runs found in logs/runs/",
        action=None if run_logs else "Run pipeline via Pipeline Runner",
    ))
    if not run_logs:
        actions.append("Run the pipeline for your contest via Pipeline Runner")

    # ── Archive ───────────────────────────────────────────────────────────────
    archive_root = project_root / "derived" / "archive" / state / county
    archive_dirs = [d for d in archive_root.rglob("*") if d.is_dir()] if archive_root.exists() else []
    checks.append(ReadinessCheck(
        name="Archive",
        status=STATUS_PRESENT if archive_dirs else STATUS_NOT_BUILT,
        detail=f"{len(archive_dirs)} archive directory(s) in derived/archive/{state}/{county}/",
        action=None if archive_dirs else "Run pipeline — ARCHIVE_INGEST step builds derived/archive/",
    ))
    if not archive_dirs:
        actions.append("Ensure ARCHIVE_INGEST step completes without error in pipeline run")

    # ── Crosswalk files ───────────────────────────────────────────────────────
    xwalk_dir = project_root / "data" / state / "counties" / county / "geography" / "crosswalks"
    xwalk_files = list(xwalk_dir.glob("*")) if xwalk_dir.exists() else []
    checks.append(ReadinessCheck(
        name="Crosswalk Files",
        status=STATUS_PRESENT if xwalk_files else STATUS_MISSING,
        detail=f"{len(xwalk_files)} file(s) in data/{state}/counties/{county}/geography/crosswalks/",
    ))
    if not xwalk_files:
        actions.append("Place crosswalk CSV files in data/CA/counties/Sonoma/geography/crosswalks/")

    # ── Geometry (precinct shapes) ────────────────────────────────────────────
    shapes_dir = project_root / "data" / state / "counties" / county / "geography" / "precinct_shapes"
    shape_files = list(shapes_dir.glob("*")) if shapes_dir.exists() else []
    checks.append(ReadinessCheck(
        name="Precinct Geometry",
        status=STATUS_PRESENT if shape_files else STATUS_MISSING,
        detail=f"{len(shape_files)} file(s) in precinct_shapes/",
    ))
    if not shape_files:
        actions.append("Download Sonoma precinct boundary files and place in data/CA/counties/Sonoma/geography/precinct_shapes/")

    # ── Map outputs ───────────────────────────────────────────────────────────
    map_dir = project_root / "derived" / "maps"
    map_files = list(map_dir.glob("*.geojson")) if map_dir.exists() else []
    checks.append(ReadinessCheck(
        name="Map Outputs",
        status=STATUS_PRESENT if map_files else STATUS_NOT_BUILT,
        detail=f"{len(map_files)} GeoJSON map(s) in derived/maps/",
    ))

    # ── Precinct join quality ─────────────────────────────────────────────────
    review_dir = project_root / "derived" / "precinct_id_review"
    join_rate_str = STATUS_UNKNOWN
    if review_dir.exists():
        jq_files = sorted(review_dir.glob("*__join_quality.json"))
        if jq_files:
            try:
                jq = json.loads(jq_files[-1].read_text(encoding="utf-8"))
                pct = jq.get("pct_joined", 0)
                join_rate_str = f"{pct:.1%}"
            except Exception:
                pass
    checks.append(ReadinessCheck(
        name="Precinct Join Rate",
        status=STATUS_UNKNOWN if join_rate_str == STATUS_UNKNOWN else (STATUS_OK if "%" in join_rate_str else STATUS_WARN),
        detail=join_rate_str,
    ))

    # ── Model calibration ─────────────────────────────────────────────────────
    model_dir = project_root / "derived" / "models"
    model_files = list(model_dir.rglob("*.json")) if model_dir.exists() else []
    checks.append(ReadinessCheck(
        name="Model Calibration",
        status=STATUS_OK if model_files else STATUS_NOT_BUILT,
        detail=f"{len(model_files)} model file(s) in derived/models/",
    ))

    # ── Overall ───────────────────────────────────────────────────────────────
    statuses = {c.status for c in checks}
    if STATUS_MISSING in statuses or STATUS_FAIL in statuses:
        overall = "NOT_READY"
    elif STATUS_NOT_BUILT in statuses or STATUS_WARN in statuses:
        overall = "PARTIAL"
    else:
        overall = "READY"

    return SystemReadinessReport(
        generated_at=now,
        overall=overall,
        checks=checks,
        action_required=actions,
    )


def write_readiness_report(project_root: Path, out_path: Optional[Path] = None) -> Path:
    report = evaluate_system_state(project_root)
    dest = out_path or (project_root / "reports" / "system_readiness.md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(report.to_markdown(), encoding="utf-8")
    logger.info(f"[READINESS] Report written: {dest}")
    return dest
