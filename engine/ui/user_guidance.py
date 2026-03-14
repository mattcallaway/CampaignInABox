"""
engine/ui/user_guidance.py — Prompt 31 Feature 3

Inspects the system state and produces human-readable guidance
telling the user what to do next. Acts as the system co-pilot.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Guidance action priorities ────────────────────────────────────────────────
PRIORITY_CRITICAL  = "CRITICAL"
PRIORITY_IMPORTANT = "IMPORTANT"
PRIORITY_INFO      = "INFO"
PRIORITY_OK        = "OK"


@dataclass
class GuidanceItem:
    priority: str
    title: str
    detail: str
    action: str
    where_in_ui: str


@dataclass
class SystemGuidance:
    summary: str
    overall_status: str        # READY | NEEDS_ACTION | CRITICAL
    items: list[GuidanceItem] = field(default_factory=list)
    contest_data_present: bool = False
    pipeline_run: bool = False
    archive_built: bool = False
    crosswalk_join_rate: Optional[float] = None
    geometry_join_coverage: Optional[float] = None
    modeling_ready: bool = False

    def to_markdown(self) -> str:
        lines = [
            f"# System Guidance — {self.overall_status}",
            "",
            f"**Summary:** {self.summary}",
            "",
            "## System Status",
            f"| Check | Status |",
            f"|---|---|",
            f"| Contest data present | {'✅ YES' if self.contest_data_present else '❌ NO'} |",
            f"| Pipeline run | {'✅ YES' if self.pipeline_run else '⏳ NO'} |",
            f"| Archive built | {'✅ YES' if self.archive_built else '⏳ NO'} |",
            f"| Crosswalk join rate | {f'{self.crosswalk_join_rate:.1%}' if self.crosswalk_join_rate is not None else 'UNKNOWN'} |",
            f"| Geometry join coverage | {f'{self.geometry_join_coverage:.1%}' if self.geometry_join_coverage is not None else 'UNKNOWN'} |",
            f"| Modeling ready | {'✅ YES' if self.modeling_ready else '⏳ NO'} |",
            "",
            "## Recommended Actions",
        ]
        for item in self.items:
            icon = {"CRITICAL": "🚨", "IMPORTANT": "⚠️", "INFO": "ℹ️", "OK": "✅"}.get(item.priority, "•")
            lines += [
                f"### {icon} {item.title}",
                f"**Detail:** {item.detail}",
                f"**Action:** {item.action}",
                f"**Where:** {item.where_in_ui}",
                "",
            ]
        return "\n".join(lines)


def evaluate_guidance(
    project_root: Path,
    state: str = "CA",
    county: str = "Sonoma",
    contest_slug: Optional[str] = None,
    year: Optional[str] = None,
) -> SystemGuidance:
    """
    Inspect system state and produce guidance for the user.
    """
    items: list[GuidanceItem] = []

    # ── 1. Contest data check ─────────────────────────────────────────────────
    contest_root = project_root / "data" / "contests" / state / county
    contest_files_found: list[Path] = []
    if contest_root.exists():
        for raw_file in contest_root.rglob("raw/*"):
            if raw_file.is_file() and raw_file.suffix.lower() in (".xlsx", ".xls", ".csv"):
                contest_files_found.append(raw_file)
    contest_data_present = bool(contest_files_found)

    if not contest_data_present:
        items.append(GuidanceItem(
            priority=PRIORITY_CRITICAL,
            title="No Contest Data Found",
            detail=f"No election result files found in data/contests/{state}/{county}/",
            action="Upload an election results file (XLS/CSV) via Data Manager → Upload New File",
            where_in_ui="Sidebar → Data → Data Manager → 📤 Upload New File",
        ))

    # ── 2. Pipeline run check ─────────────────────────────────────────────────
    archive_root = project_root / "derived" / "archive" / state / county
    archive_files: list[Path] = []
    if archive_root.exists():
        archive_files = [p for p in archive_root.rglob("*.json") if p.is_file()]
    archive_built = bool(archive_files)

    log_dir = project_root / "logs" / "runs"
    pipeline_logs = sorted(log_dir.glob("*.log")) if log_dir.exists() else []
    pipeline_run = bool(pipeline_logs)

    if contest_data_present and not pipeline_run:
        items.append(GuidanceItem(
            priority=PRIORITY_IMPORTANT,
            title="Pipeline Not Yet Run",
            detail="Contest data is present but the pipeline has not been executed.",
            action="Go to Pipeline Runner, select your contest, and click 'Run Modeling Pipeline'",
            where_in_ui="Sidebar → System → 🛠️ Pipeline Runner",
        ))
    elif pipeline_run and not archive_built:
        items.append(GuidanceItem(
            priority=PRIORITY_IMPORTANT,
            title="Pipeline Run but Archive Empty",
            detail="A pipeline run was recorded but no archive outputs were found.",
            action="Check the pipeline log for errors. Look for ARCHIVE_INGEST DONE in the log.",
            where_in_ui="Sidebar → System → 🛠️ Pipeline Runner → Last Run Log",
        ))

    # ── 3. Crosswalk check ────────────────────────────────────────────────────
    xwalk_dir = project_root / "data" / state / "counties" / county / "geography" / "crosswalks"
    crosswalk_ok = xwalk_dir.exists() and any(xwalk_dir.iterdir())
    crosswalk_join_rate: Optional[float] = None

    review_dir = project_root / "derived" / "precinct_id_review"
    if review_dir.exists():
        summaries = list(review_dir.glob("*__join_quality.json"))
        if summaries:
            try:
                jq = json.loads(summaries[-1].read_text(encoding="utf-8"))
                crosswalk_join_rate = jq.get("pct_joined")
            except Exception:
                pass

    if not crosswalk_ok:
        items.append(GuidanceItem(
            priority=PRIORITY_IMPORTANT,
            title="No Crosswalk Files Found",
            detail=f"Crosswalk directory missing or empty: data/{state}/counties/{county}/geography/crosswalks/",
            action="Place Sonoma crosswalk CSV files in the crosswalks directory.",
            where_in_ui="Filesystem: data/CA/counties/Sonoma/geography/crosswalks/",
        ))
    elif crosswalk_join_rate is not None and crosswalk_join_rate < 0.85:
        items.append(GuidanceItem(
            priority=PRIORITY_IMPORTANT,
            title=f"Low Crosswalk Join Rate ({crosswalk_join_rate:.1%})",
            detail="Less than 85% of precincts successfully joined via crosswalk.",
            action="Check reports/crosswalk_repair/ for detection failures. Update crosswalk_column_hints.yaml.",
            where_in_ui="Filesystem: reports/crosswalk_repair/ and config/precinct_id/crosswalk_column_hints.yaml",
        ))

    # ── 4. Geometry check ─────────────────────────────────────────────────────
    geo_dir = project_root / "data" / state / "counties" / county / "geography" / "precinct_shapes"
    geometry_ok = geo_dir.exists() and any(geo_dir.iterdir())
    if not geometry_ok:
        items.append(GuidanceItem(
            priority=PRIORITY_IMPORTANT,
            title="No Precinct Geometry Files",
            detail=f"No shapefile or GeoJSON found in data/{state}/counties/{county}/geography/precinct_shapes/",
            action="Download and place precinct boundary files in precinct_shapes/",
            where_in_ui=f"Filesystem: data/{state}/counties/{county}/geography/precinct_shapes/",
        ))

    # ── 5. Map check ─────────────────────────────────────────────────────────
    map_dir = project_root / "derived" / "maps"
    map_files = list(map_dir.glob("*.geojson")) if map_dir.exists() else []
    if archive_built and not map_files:
        items.append(GuidanceItem(
            priority=PRIORITY_INFO,
            title="Map Not Generated",
            detail="Archive is built but no GeoJSON map files found in derived/maps/",
            action="Re-run the pipeline — the geometry join step produces the map output.",
            where_in_ui="Sidebar → System → 🛠️ Pipeline Runner",
        ))

    # ── 6. Modeling readiness ─────────────────────────────────────────────────
    model_dir = project_root / "derived" / "models"
    modeling_ready = model_dir.exists() and any(model_dir.rglob("*.json"))
    if archive_built and not modeling_ready:
        items.append(GuidanceItem(
            priority=PRIORITY_INFO,
            title="Model Calibration Not Run",
            detail="Archive is built but no calibration model outputs found.",
            action="Ensure MODEL_CALIBRATION step completed in the pipeline run.",
            where_in_ui="Sidebar → System → 🛠️ Pipeline Runner → run log",
        ))

    # ── 7. All good ───────────────────────────────────────────────────────────
    if not items:
        items.append(GuidanceItem(
            priority=PRIORITY_OK,
            title="System Ready",
            detail="Contest data present, pipeline run, archive built, geometry available.",
            action="Review the Precinct Map and Historical Archive pages for results.",
            where_in_ui="Sidebar → Geography → 🗺️ Precinct Map | Sidebar → Intelligence → 🗃️ Historical Archive",
        ))

    # ── Determine overall status ──────────────────────────────────────────────
    priorities = [i.priority for i in items]
    if PRIORITY_CRITICAL in priorities:
        overall_status = "CRITICAL"
        summary = "System cannot run — critical configuration missing."
    elif PRIORITY_IMPORTANT in priorities:
        overall_status = "NEEDS_ACTION"
        summary = "System partially configured — action required before full operation."
    else:
        overall_status = "READY"
        summary = "System appears ready for normal operation."

    return SystemGuidance(
        summary=summary,
        overall_status=overall_status,
        items=items,
        contest_data_present=contest_data_present,
        pipeline_run=pipeline_run,
        archive_built=archive_built,
        crosswalk_join_rate=crosswalk_join_rate,
        geometry_join_coverage=None,
        modeling_ready=modeling_ready,
    )
