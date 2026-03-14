"""
engine/diagnostics/pipeline_observer.py — Prompt 31 Feature 9

Reads a completed pipeline run log and produces a concise summary
report in reports/pipeline_runs/<run_id>/pipeline_summary.md
"""
from __future__ import annotations

import re
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    step: str
    status: str       # DONE | SKIP | FAIL | CRASH
    duration_s: Optional[float] = None
    note: str = ""


@dataclass
class PipelineRunSummary:
    run_id: str
    contest_slug: str
    state: str
    county: str
    year: str
    started_at: str
    rows_loaded: Optional[int]
    precinct_join_rate: Optional[float]
    geometry_join: str
    archive_built: bool
    steps: list[StepResult] = field(default_factory=list)
    overall: str = "UNKNOWN"    # SUCCESS | PARTIAL | FAILED

    def to_markdown(self) -> str:
        icon = {"SUCCESS": "✅", "PARTIAL": "⚠️", "FAILED": "❌", "UNKNOWN": "❓"}.get(self.overall, "•")
        lines = [
            f"# Pipeline Run Summary — {self.run_id}",
            f"**Status:** {icon} {self.overall}",
            f"**Contest:** {self.contest_slug}",
            f"**State/County/Year:** {self.state} / {self.county} / {self.year}",
            f"**Started:** {self.started_at}",
            "",
            "## Key Metrics",
            "",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Rows Loaded | {self.rows_loaded or 'UNKNOWN'} |",
            f"| Precinct Join Rate | {f'{self.precinct_join_rate:.1%}' if self.precinct_join_rate is not None else 'UNKNOWN'} |",
            f"| Geometry Join | {self.geometry_join} |",
            f"| Archive Built | {'YES' if self.archive_built else 'NO'} |",
            "",
            "## Step Results",
            "",
            "| Step | Status | Duration | Note |",
            "|---|---|---|---|",
        ]
        status_icons = {"DONE": "✅", "SKIP": "⏭️", "FAIL": "❌", "CRASH": "💥"}
        for s in self.steps:
            si = status_icons.get(s.status, "•")
            dur = f"{s.duration_s:.1f}s" if s.duration_s is not None else "—"
            lines.append(f"| {s.step} | {si} {s.status} | {dur} | {s.note[:60]} |")
        return "\n".join(lines)


# Patterns for parsing pipeline log lines
_STEP_PATTERN   = re.compile(r"\[STEP \] (DONE|SKIP|FAIL|CRASH)\s+\[(\w+)\]\s+([\w_]+)\s*(?:\(([0-9.]+)s\))?")
_ROWS_PATTERN   = re.compile(r"(\d+)\s+(?:precinct\s+rows|rows loaded|precincts)", re.IGNORECASE)
# Archive is built when DOWNLOAD_HISTORICAL_ELECTIONS or ARCHIVE_INGEST step succeeds
_ARCHIVE_PATTERN = re.compile(
    r"(DOWNLOAD_HISTORICAL_ELECTIONS|ARCHIVE_INGEST|ARCHIVE_BUILD).*DONE", re.IGNORECASE
)
_JOIN_PATTERN   = re.compile(r"join(?:ed)?\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)


def parse_run_log(log_path: Path) -> PipelineRunSummary:
    """Parse a run log file into a PipelineRunSummary."""
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    lines_list = text.splitlines()

    # Extract run_id from filename
    run_id = log_path.stem.replace("__run", "")

    # Extract header values
    state = re.search(r"state=(\w+)", text)
    county = re.search(r"county=(\w+)", text)
    year = re.search(r"year=(\d+)", text)
    slug = re.search(r"(?:slug|contest_slug)=(\S+)", text)
    started = re.search(r"Started\s*:\s*(\S+)", text)

    steps: list[StepResult] = []
    for m in _STEP_PATTERN.finditer(text):
        status_code = m.group(1)
        ok_or_kw    = m.group(2)
        step_name   = m.group(3)
        dur_raw     = m.group(4)
        steps.append(StepResult(
            step=step_name,
            status=status_code,
            duration_s=float(dur_raw) if dur_raw else None,
            note=ok_or_kw,
        ))

    # Rows loaded
    rows_m = _ROWS_PATTERN.search(text)
    rows_loaded = int(rows_m.group(1)) if rows_m else None

    # Archive built? Check log AND disk presence as fallback
    archive_built = bool(_ARCHIVE_PATTERN.search(text))
    if not archive_built:
        # Fallback: check if derived/archive/ dir has content on disk
        # (handles cases where the step name changed or log was truncated)
        archive_disk = log_path.parent.parent.parent.parent / "derived" / "archive"
        if not archive_disk.exists():
            # Try resolving from log path up to project root
            p = log_path
            for _ in range(10):
                candidate = p / "derived" / "archive"
                if candidate.exists():
                    archive_disk = candidate
                    break
                p = p.parent
        if archive_disk.exists() and any(archive_disk.iterdir()):
            archive_built = True

    # Join rate
    join_m = _JOIN_PATTERN.search(text)
    join_rate = (int(join_m.group(1)) / int(join_m.group(2))) if join_m and int(join_m.group(2)) > 0 else None

    # Geometry join
    if re.search(r"LOAD_GEOMETRY.*DONE", text, re.IGNORECASE):
        geometry_join = "SUCCESS"
    elif re.search(r"LOAD_GEOMETRY.*SKIP", text, re.IGNORECASE):
        geometry_join = "SKIPPED"
    else:
        geometry_join = "UNKNOWN"

    # Overall
    fail_steps = [s for s in steps if s.status in ("FAIL", "CRASH")]
    done_steps = [s for s in steps if s.status == "DONE"]
    if fail_steps:
        overall = "FAILED"
    elif done_steps:
        overall = "SUCCESS" if not fail_steps else "PARTIAL"
    else:
        overall = "UNKNOWN"

    return PipelineRunSummary(
        run_id=run_id,
        contest_slug=slug.group(1) if slug else "unknown",
        state=state.group(1) if state else "CA",
        county=county.group(1) if county else "Sonoma",
        year=year.group(1) if year else "unknown",
        started_at=started.group(1) if started else "unknown",
        rows_loaded=rows_loaded,
        precinct_join_rate=join_rate,
        geometry_join=geometry_join,
        archive_built=archive_built,
        steps=steps,
        overall=overall,
    )


def write_run_summary(
    log_path: Path,
    project_root: Path,
    run_id: Optional[str] = None,
) -> Path:
    """Parse log and write summary markdown."""
    summary = parse_run_log(log_path)
    rid = run_id or summary.run_id
    out_dir = project_root / "reports" / "pipeline_runs" / rid
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "pipeline_summary.md"
    out.write_text(summary.to_markdown(), encoding="utf-8")
    # Also write JSON
    (out_dir / "pipeline_summary.json").write_text(
        json.dumps({
            "run_id": summary.run_id,
            "overall": summary.overall,
            "contest_slug": summary.contest_slug,
            "rows_loaded": summary.rows_loaded,
            "archive_built": summary.archive_built,
            "precinct_join_rate": summary.precinct_join_rate,
            "geometry_join": summary.geometry_join,
            "steps": [{"step": s.step, "status": s.status, "duration_s": s.duration_s} for s in summary.steps],
        }, indent=2),
        encoding="utf-8",
    )
    logger.info(f"[OBSERVER] Summary written: {out}")
    return out
