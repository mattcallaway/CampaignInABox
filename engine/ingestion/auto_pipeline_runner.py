"""
engine/ingestion/auto_pipeline_runner.py — Prompt 31 Feature 2

Evaluates whether a detected contest file is ready to run through
the pipeline automatically, and either suggests or triggers the run.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from engine.ingestion.contest_file_watcher import DetectedContestFile, scan_for_new_contest_files

logger = logging.getLogger(__name__)


@dataclass
class PipelineSuggestion:
    contest_slug: str
    year: str
    state: str
    county: str
    contest_file: str
    reason: str
    confidence: str          # HIGH | MEDIUM | LOW
    auto_run_eligible: bool
    suggestion: str          # "RUN_PIPELINE" | "REVIEW_FIRST" | "ALREADY_RUN"


def suggest_pipeline_runs(
    project_root: Path,
    state: str = "CA",
    county: str = "Sonoma",
    archive_dir: Optional[Path] = None,
) -> list[PipelineSuggestion]:
    """
    Inspect detected contest files and suggest pipeline runs.

    A contest is eligible for auto-run when:
    - A file with a precinct column is present in raw/
    - No existing archive output exists for that contest
    """
    detected = scan_for_new_contest_files(project_root, state, county)

    # Check which contests already have archive outputs
    archive_root = archive_dir or (project_root / "derived" / "archive" / state / county)

    suggestions: list[PipelineSuggestion] = []
    seen_slugs: set[str] = set()

    for f in detected:
        if f.contest_slug in seen_slugs:
            continue
        seen_slugs.add(f.contest_slug)

        # Check for existing archive
        archive_path = archive_root / f.year / f.contest_slug
        already_run = archive_path.exists() and any(archive_path.iterdir())

        if already_run:
            suggestion = "ALREADY_RUN"
            confidence = "HIGH"
            reason = f"Archive already exists at derived/archive/{state}/{county}/{f.year}/{f.contest_slug}/"
            auto_run_eligible = False
        elif f.status == "READY_FOR_PIPELINE":
            suggestion = "RUN_PIPELINE"
            confidence = "HIGH"
            reason = (
                f"File '{f.filename}' has precinct column '{f.precinct_col}' "
                f"with {f.precinct_rows} rows — ready for pipeline."
            )
            auto_run_eligible = True
        elif f.status == "NEEDS_REVIEW":
            suggestion = "REVIEW_FIRST"
            confidence = "LOW"
            reason = f"File '{f.filename}' has no detectable precinct column — manual review required."
            auto_run_eligible = False
        else:
            suggestion = "REVIEW_FIRST"
            confidence = "MEDIUM"
            reason = "File status unclear."
            auto_run_eligible = False

        suggestions.append(PipelineSuggestion(
            contest_slug=f.contest_slug,
            year=f.year, state=state, county=county,
            contest_file=f.filename,
            reason=reason, confidence=confidence,
            auto_run_eligible=auto_run_eligible,
            suggestion=suggestion,
        ))

    return suggestions


def run_pipeline_for_contest(
    project_root: Path,
    state: str,
    county: str,
    year: str,
    contest_slug: str,
    dry_run: bool = False,
) -> dict:
    """
    Trigger the pipeline for a specific contest.

    Set dry_run=True to log the command without executing.
    Returns a dict with status and output.
    """
    cmd = [
        sys.executable, str(project_root / "scripts" / "run_pipeline.py"),
        "--state", state,
        "--county", county,
        "--year", year,
        "--contest-slug", contest_slug,
        "--log-level", "verbose",
    ]

    logger.info(f"[AUTO_PIPELINE] Command: {' '.join(cmd)}")

    if dry_run:
        return {"status": "DRY_RUN", "command": " ".join(cmd)}

    try:
        result = subprocess.run(
            cmd, cwd=str(project_root),
            capture_output=True, text=True, timeout=900,
        )
        return {
            "status": "SUCCESS" if result.returncode == 0 else "FAILED",
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-3000:] if result.stdout else "",
            "stderr_tail": result.stderr[-1000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "error": "Pipeline exceeded 15-minute timeout"}
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


def write_suggestion_report(
    suggestions: list[PipelineSuggestion],
    project_root: Path,
) -> Path:
    """Write pipeline suggestions as JSON."""
    out_dir = project_root / "reports" / "auto_pipeline"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d__%H%M%S")
    out = out_dir / f"{ts}__suggestions.json"
    out.write_text(
        json.dumps({"suggestions": [asdict(s) for s in suggestions]}, indent=2),
        encoding="utf-8",
    )
    return out
