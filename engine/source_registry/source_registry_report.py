"""
engine/source_registry/source_registry_report.py — Prompt 25A

Source Registry Diagnostics and Report Generator.

Generates:
  - reports/source_registry/<RUN_ID>__source_registry_report.md
  - derived/source_registry/<RUN_ID>__contest_registry_snapshot.json
  - derived/source_registry/<RUN_ID>__geometry_registry_snapshot.json
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from engine.source_registry.source_registry import (
    load_contest_registry,
    load_geometry_registry,
)
from engine.source_registry.source_resolver import summarize_registry_coverage

log = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = BASE_DIR / "reports" / "source_registry"
DERIVED_DIR = BASE_DIR / "derived" / "source_registry"


def run_registry_report(
    run_id: Optional[str] = None,
    state: str = "CA",
    county: Optional[str] = None,
) -> dict:
    """
    Generate the source registry diagnostics report.

    Args:
        run_id: Pipeline run ID (defaults to timestamp)
        state: State to focus on for coverage analysis
        county: County to focus on

    Returns:
        Summary dict
    """
    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M%S")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    contest_sources  = load_contest_registry()
    geometry_sources = load_geometry_registry()

    # ── Analysis ──────────────────────────────────────────────────────────────

    # Approved
    approved_contest  = [s for s in contest_sources  if s.get("user_approved")]
    approved_geometry = [s for s in geometry_sources if s.get("user_approved")]

    # By jurisdiction
    contest_by_jtype = {}
    for s in contest_sources:
        jtype = s.get("jurisdiction_type", "unknown")
        contest_by_jtype.setdefault(jtype, []).append(s.get("source_id"))

    # By county
    contest_by_county: dict[str, list] = {}
    for s in contest_sources:
        county_val = s.get("county") or "statewide"
        contest_by_county.setdefault(county_val, []).append(s.get("source_id"))

    # By year
    years_covered: set[int] = set()
    for s in contest_sources:
        yr = s.get("year")
        if isinstance(yr, list):
            years_covered.update(yr)
        elif yr:
            years_covered.add(yr)

    # Official vs unofficial
    official_sources  = [s for s in contest_sources if s.get("official_status") in ["certified", "official"]]
    unofficial_sources = [s for s in contest_sources if s.get("official_status") not in ["certified", "official"]]

    # Auto-ingest allowed
    auto_ingest_sources = [s for s in contest_sources if s.get("auto_ingest_allowed")]
    requires_confirm    = [s for s in contest_sources if s.get("requires_confirmation")]

    # Low confidence
    low_conf_sources = [s for s in contest_sources if s.get("confidence_default", 1.0) < 0.70]

    # Geometry stats
    geo_by_type: dict[str, list] = {}
    for s in geometry_sources:
        btype = s.get("boundary_type", "unknown")
        geo_by_type.setdefault(btype, []).append(s.get("source_id"))

    preferred_geo = [s for s in geometry_sources if s.get("preferred")]

    # Coverage
    coverage_summary = summarize_registry_coverage(state=state, county=county)

    # ── JSON Snapshots ────────────────────────────────────────────────────────

    contest_snapshot = {
        "run_id":       run_id,
        "generated_at": datetime.now().isoformat(),
        "total_sources": len(contest_sources),
        "approved":     len(approved_contest),
        "official":     len(official_sources),
        "auto_ingest":  len(auto_ingest_sources),
        "years_covered": sorted(years_covered),
        "by_county":    {k: len(v) for k, v in contest_by_county.items()},
        "by_jurisdiction_type": {k: len(v) for k, v in contest_by_jtype.items()},
        "sources":      contest_sources,
    }

    geo_snapshot = {
        "run_id":       run_id,
        "generated_at": datetime.now().isoformat(),
        "total_sources": len(geometry_sources),
        "approved":     len(approved_geometry),
        "preferred":    len(preferred_geo),
        "by_boundary_type": {k: len(v) for k, v in geo_by_type.items()},
        "sources":      geometry_sources,
    }

    cjson = DERIVED_DIR / f"{run_id}__contest_registry_snapshot.json"
    gjson = DERIVED_DIR / f"{run_id}__geometry_registry_snapshot.json"

    cjson.write_text(json.dumps(contest_snapshot, indent=2, default=str), encoding="utf-8")
    gjson.write_text(json.dumps(geo_snapshot, indent=2, default=str), encoding="utf-8")

    log.info(f"[REGISTRY_REPORT] Contest snapshot → {cjson.name}")
    log.info(f"[REGISTRY_REPORT] Geometry snapshot → {gjson.name}")

    # ── Markdown Report ───────────────────────────────────────────────────────

    lines = [
        f"# Source Registry Report",
        f"**Run ID:** {run_id}  |  **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Contest sources | {len(contest_sources)} |",
        f"| Approved contest sources | {len(approved_contest)} |",
        f"| Official/certified contest sources | {len(official_sources)} |",
        f"| Auto-ingest enabled | {len(auto_ingest_sources)} |",
        f"| Requires user confirmation | {len(requires_confirm)} |",
        f"| Geometry sources | {len(geometry_sources)} |",
        f"| Approved geometry sources | {len(approved_geometry)} |",
        f"| Preferred geometry sources | {len(preferred_geo)} |",
        f"| Years with contest coverage | {', '.join(str(y) for y in sorted(years_covered)) or 'none'} |",
        f"| Registry coverage rating | **{coverage_summary['registry_coverage']}** |",
        "",
        "## Contest Sources by County",
        "",
        "| County | No. Sources |",
        "|--------|-------------|",
    ]

    for county_name, source_list in sorted(contest_by_county.items()):
        lines.append(f"| {county_name} | {len(source_list)} |")

    lines += [
        "",
        "## Contest Sources by Jurisdiction Type",
        "",
        "| Jurisdiction Type | No. Sources |",
        "|-------------------|-------------|",
    ]
    for jtype, source_list in sorted(contest_by_jtype.items()):
        lines.append(f"| {jtype} | {len(source_list)} |")

    lines += [
        "",
        "## Geometry Sources by Boundary Type",
        "",
        "| Boundary Type | No. Sources |",
        "|---------------|-------------|",
    ]
    for btype, source_list in sorted(geo_by_type.items()):
        lines.append(f"| {btype} | {len(source_list)} |")

    # Gaps
    lines += ["", "## Registry Gaps", ""]
    expected_years = [2016, 2018, 2020, 2022, 2024]
    missing_years = [y for y in expected_years if y not in years_covered]
    if missing_years:
        lines.append(f"⚠️ **Missing contest coverage for years:** {', '.join(str(y) for y in missing_years)}")
    else:
        lines.append("✅ Coverage for all expected years (2016–2024) present in registry.")

    crosswalk_types = {s.get("boundary_type") for s in geometry_sources}
    if "crosswalk" not in crosswalk_types:
        lines.append("⚠️ **No crosswalk source found** — MPREC↔SRPREC crosswalk required for joining SOS and county data.")
    else:
        lines.append("✅ Crosswalk source(s) present in geometry registry.")

    # Low confidence
    if low_conf_sources:
        lines += [
            "",
            "## Low-Confidence Sources (< 0.70)",
            "",
            "These sources should be reviewed before use:",
            "",
            "| Source ID | Confidence | Notes |",
            "|-----------|------------|-------|",
        ]
        for s in low_conf_sources:
            lines.append(f"| {s.get('source_id')} | {s.get('confidence_default', '?')} | {s.get('notes', '')[:60]} |")

    # Inactive / Unapproved
    unapproved = [s for s in contest_sources if not s.get("user_approved")]
    if unapproved:
        lines += [
            "",
            f"## Unapproved Contest Sources ({len(unapproved)})",
            "",
            "These sources have not yet been confirmed by a user:",
            "",
            "| Source ID | Year | Confidence |",
            "|-----------|------|------------|",
        ]
        for s in unapproved[:10]:
            lines.append(f"| {s.get('source_id')} | {s.get('year', 'any')} | {s.get('confidence_default', '?')} |")
        if len(unapproved) > 10:
            lines.append(f"| …and {len(unapproved) - 10} more | | |")

    rpath = REPORTS_DIR / f"{run_id}__source_registry_report.md"
    rpath.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[REGISTRY_REPORT] Report → {rpath.name}")

    summary = {
        "run_id":            run_id,
        "contest_sources":   len(contest_sources),
        "geometry_sources":  len(geometry_sources),
        "approved_sources":  len(approved_contest) + len(approved_geometry),
        "registry_coverage": coverage_summary["registry_coverage"],
        "years_covered":     sorted(years_covered),
        "report_path":       str(rpath),
    }

    log.info(f"[REGISTRY_REPORT] Complete: {len(contest_sources)} contest, {len(geometry_sources)} geometry sources")
    return summary
