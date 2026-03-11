"""
engine/data_intake/source_finder.py — Prompt 17.5

Generates a structured Internet Source Finder report, combining the missing data requests
with static actionable look-up instructions indicating where on the internet users can find the data.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Web sources guidance catalog
_SOURCE_CATALOG = {
    "election_results": {
        "likely_source_type": "Official County Registrar or Secretary of State",
        "search_keywords": "[County Name] statement of vote results csv xlsx",
        "actionable_steps": [
            "Check your county Registrar of Voters website for past election results.",
            "Look for 'Statement of Vote' (SOV) download links.",
            "Prefer machine-readable formats like CSV or Excel over PDFs."
        ]
    },
    "voter_file": {
        "likely_source_type": "County Registrar or Third-Party Data Vendor",
        "search_keywords": "[State Name] voter file request forms",
        "actionable_steps": [
            "Official voter files usually require formal application or purchase through the state.",
            "Alternatively, export an active voter list from a partisan platform (VAN, PDI, L2).",
            "Be extremely cautious downloading PII online."
        ]
    },
    "polling": {
        "likely_source_type": "Campaign Internal Drive or Public Poll Repositories",
        "search_keywords": "[Contest Name] latest poll cross-tabs pdf csv",
        "actionable_steps": [
            "Check internal campaign strategy files or Google Drive folders.",
            "For public polls, search sites like RealClearPolitics or FiveThirtyEight.",
            "You only need high-level toplines for Campaign In A Box (Support / Oppose / Undecided)."
        ]
    },
    "ballot_returns": {
        "likely_source_type": "County Elections Daily Updates",
        "search_keywords": "[County Name] daily ballot return statistics",
        "actionable_steps": [
            "During the 30-day early voting window, registrars usually post daily aggregate PDFs/CSV.",
            "Also check partisan resources like Political Data Intelligence (PDI) tracking pages."
        ]
    },
    "demographics": {
        "likely_source_type": "US Census Bureau / American Community Survey",
        "search_keywords": "Census ACS 5-year estimate [County Name] education income data",
        "actionable_steps": [
            "Check data.census.gov.",
            "Search for Table S1501 (Educational Attainment) or S1901 (Income)."
        ]
    },
    "precinct_geometry": {
        "likely_source_type": "GIS / Open Data Portals",
        "search_keywords": "[County Name] open data portal voting precinct shapefile",
        "actionable_steps": [
            "Search the county GIS portal (often powered by ArcGIS Hub).",
            "Download exactly one single shapefile (.zip) or geojson format."
        ]
    },
    "crosswalk": {
        "likely_source_type": "Statewide Redistricting Databases",
        "search_keywords": "[State Name] statewide database block to precinct crosswalk",
        "actionable_steps": [
            "Search for block-to-precinct mapping tables, often provided by state legislative redistricting commissions."
        ]
    }
}


def run_source_finder(project_root: str | Path, missing_requests: list[dict], run_id: Optional[str] = None):
    """
    Combine missing data types with source catalog into a JSON and Markdown report.
    """
    root = Path(project_root)
    req_types = [req["data_type"] for req in missing_requests]
    
    recommendations = []
    
    for req in missing_requests:
        dt = req["data_type"]
        catalog_entry = _SOURCE_CATALOG.get(dt)
        if catalog_entry:
            rec = catalog_entry.copy()
            rec["data_type"] = dt
            rec["why_needed"] = req["why_needed"]
            recommendations.append(rec)

    # Output JSON to derived file registry
    dest_dir = root / "derived" / "file_registry" / "latest"
    dest_dir.mkdir(parents=True, exist_ok=True)
    json_payload = {
        "run_id": run_id or "latest",
        "recommendations": recommendations
    }
    (dest_dir / "source_finder_recommendations.json").write_text(
        json.dumps(json_payload, indent=2), encoding="utf-8"
    )

    # Output Markdown to reports/data_intake
    reports_dir = root / "reports" / "data_intake"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    fname = f"{run_id + '__' if run_id else ''}source_finder.md"
    
    md_lines = [
        f"# 🌍 Internet Source Finder Report",
        f"**Run ID:** `{run_id or 'latest'}` | **Date:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "The following external data sources are recommended to locate missing files required by Campaign In A Box.",
        ""
    ]
    
    if not recommendations:
        md_lines.extend([
            "> ✅ **No missing data identified.** Your campaign registry looks fully populated."
        ])
    else:
        for rec in recommendations:
            md_lines.extend([
                f"## 🔎 {rec['data_type'].replace('_', ' ').title()}",
                f"**Why Campaign In A Box needs this:** {rec['why_needed']}",
                "",
                f"- **Likely Source Type:** {rec['likely_source_type']}",
                f"- **Suggested Search Query:** `{rec['search_keywords']}`",
                "",
                "**Actionable Steps:**"
            ])
            for step in rec['actionable_steps']:
                md_lines.append(f"1. {step}")
            md_lines.append("")

    (reports_dir / fname).write_text("\n".join(md_lines), encoding="utf-8")
    
    log.info(f"Source finder report written to {reports_dir / fname}")
    return recommendations
