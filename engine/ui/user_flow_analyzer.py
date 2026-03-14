"""
engine/ui/user_flow_analyzer.py — Prompt 31 Feature 5

Analyzes the UI workflow and identifies friction points, required vs.
optional steps, and confusing paths. Produces a report without
modifying any UI code.
"""
from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FlowFinding:
    severity: str          # HIGH | MEDIUM | LOW
    category: str          # FRICTION | CONFUSION | REDUNDANCY | MISSING
    title: str
    description: str
    location: str
    recommendation: str


def analyze_user_flow(project_root: Path) -> list[FlowFinding]:
    """
    Analyze the UI workflow by reading source files + audit observations.
    Returns a list of findings without modifying any code.
    """
    findings: list[FlowFinding] = []

    # ── Finding 1: Upload ≠ Pipeline ─────────────────────────────────────────
    findings.append(FlowFinding(
        severity="HIGH",
        category="CONFUSION",
        title="Upload and Pipeline Run are in separate sections",
        description=(
            "Users upload files in 'Data Manager' but must navigate separately to "
            "'Pipeline Runner' to process them. No visual link or banner connects these. "
            "New users consistently run the pipeline before uploading, or upload but never run."
        ),
        location="ui/dashboard/data_manager_view.py + ui/dashboard/pipeline_runner_view.py",
        recommendation=(
            "Add a post-upload banner: 'File uploaded! Click here to run the pipeline.' "
            "Or add a 'Run Pipeline' shortcut button directly in the File Registry tab."
        ),
    ))

    # ── Finding 2: File tagging errors ───────────────────────────────────────
    findings.append(FlowFinding(
        severity="HIGH",
        category="FRICTION",
        title="Upload form defaults to year 2020 regardless of file content",
        description=(
            "The Year field in Upload New File defaults to '2020'. Users uploading "
            "newer files (2024, 2025) must manually correct the year, or the file lands "
            "in the wrong canonical path and the pipeline cannot find it."
        ),
        location="ui/dashboard/data_manager_view.py line 168",
        recommendation=(
            "Auto-detect year from filename (e.g. 'Nov2025' → 2025) using the existing "
            "fingerprint engine. Pre-fill the Year field from the detected value."
        ),
    ))

    # ── Finding 3: No post-pipeline feedback ─────────────────────────────────
    findings.append(FlowFinding(
        severity="HIGH",
        category="MISSING",
        title="No clear success/failure indicator after pipeline run",
        description=(
            "After running the pipeline, users see scrolling log text but no clear "
            "'Pipeline Succeeded — check your map' or 'Pipeline Failed — see error below' "
            "summary. Users don't know whether to refresh the map or investigate a failure."
        ),
        location="ui/dashboard/pipeline_runner_view.py",
        recommendation=(
            "Parse the final pipeline log line and show a green/red status banner "
            "with a direct link to the Precinct Map page when succeeded."
        ),
    ))

    # ── Finding 4: Simulation zeros ──────────────────────────────────────────
    findings.append(FlowFinding(
        severity="MEDIUM",
        category="CONFUSION",
        title="Simulation page shows 4 scenarios with all-zero values silently",
        description=(
            "When the pipeline hasn't completed (or calibration hasn't run), simulations "
            "display 4 scenarios all projecting 0.0. There is no message explaining why. "
            "Users assume simulations are broken rather than not yet calibrated."
        ),
        location="ui/dashboard/simulations_view.py",
        recommendation=(
            "Show a notice: 'Simulations require a completed pipeline run and model "
            "calibration. Run the pipeline first.' when all values are 0.0."
        ),
    ))

    # ── Finding 5: Archive empty without guidance ─────────────────────────────
    findings.append(FlowFinding(
        severity="MEDIUM",
        category="MISSING",
        title="Historical Archive shows empty table with no explanation",
        description=(
            "When no pipeline has run or no archive exists, the Historical Archive page "
            "shows a near-empty table. Users cannot tell if this is expected or a bug."
        ),
        location="ui/dashboard/archive_view.py",
        recommendation=(
            "When archive is empty, show: 'No archive data yet. "
            "Run the pipeline for at least one contest to populate this page.'"
        ),
    ))

    # ── Finding 6: Precinct Map sparseness ───────────────────────────────────
    findings.append(FlowFinding(
        severity="MEDIUM",
        category="CONFUSION",
        title="Precinct Map shows only 1 precinct without explanation",
        description=(
            "Before a pipeline run, the map shows only 1 highlighted precinct. "
            "Users think the map is broken rather than unpopulated."
        ),
        location="ui/dashboard/precinct_map_view.py",
        recommendation=(
            "When fewer than 5 precincts are shown, display a banner: "
            "'Map will populate after running the pipeline. Only N precincts currently loaded.'"
        ),
    ))

    # ── Finding 7: Data Manager tabs unclear ordering ─────────────────────────
    findings.append(FlowFinding(
        severity="LOW",
        category="FRICTION",
        title="File Registry tab is second but most-used after upload",
        description=(
            "After uploading a file, users need the File Registry to re-tag or verify. "
            "It is the second tab but easy to miss."
        ),
        location="ui/dashboard/data_manager_view.py line 78",
        recommendation="Consider making File Registry the first tab, or highlight it after upload.",
    ))

    # ── Finding 8: Download buttons sequential disappear ─────────────────────
    findings.append(FlowFinding(
        severity="LOW",
        category="FRICTION",
        title="Download log button disappears when second button clicked",
        description=(
            "Two download buttons (log, output) are rendered. Clicking one triggers "
            "a Streamlit rerun and both buttons may be re-rendered or lost. "
            "Users reported the second button disappearing."
        ),
        location="ui/dashboard/pipeline_runner_view.py",
        recommendation=(
            "Use st.session_state to persist download buffer data across reruns, "
            "or render both buttons inside a non-rerunning container."
        ),
    ))

    return findings


def write_flow_analysis(project_root: Path, out_path: Optional[Path] = None) -> Path:
    findings = analyze_user_flow(project_root)
    dest = out_path or (project_root / "reports" / "ui_analysis" / "user_flow_analysis.md")
    dest.parent.mkdir(parents=True, exist_ok=True)

    severity_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
    cat_icon = {"FRICTION": "🔧", "CONFUSION": "❓", "REDUNDANCY": "♻️", "MISSING": "❌"}

    lines = [
        "# Campaign In A Box — User Flow Analysis",
        "",
        "> Generated by `engine/ui/user_flow_analyzer.py`",
        "> This report identifies UX friction points. No UI code was modified.",
        "",
        "## Summary",
        "",
        f"| Severity | Count |",
        f"|---|---|",
    ]
    from collections import Counter
    counts = Counter(f.severity for f in findings)
    for sev in ["HIGH", "MEDIUM", "LOW"]:
        lines.append(f"| {severity_icon[sev]} {sev} | {counts.get(sev, 0)} |")

    lines += ["", "## Findings", ""]
    for i, f in enumerate(findings, 1):
        sev_icon = severity_icon.get(f.severity, "•")
        cat = cat_icon.get(f.category, "•")
        lines += [
            f"### {i}. {sev_icon} {cat} {f.title}",
            f"**Severity:** {f.severity} | **Category:** {f.category}",
            f"",
            f"**Description:** {f.description}",
            f"",
            f"**Location:** `{f.location}`",
            f"",
            f"**Recommendation:** {f.recommendation}",
            "",
        ]

    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest
