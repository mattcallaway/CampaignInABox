"""
engine/source_registry/registry_repair.py — Prompt 25A.1

Source registry repair module.

Iterates all entries in contest_sources.yaml and geometry_sources.yaml,
runs domain verification and confidence recalculation, flags suspicious
domains, and generates:
  - reports/source_registry/<RUN_ID>__suspicious_sources.md
  - derived/source_registry/<RUN_ID>__registry_health.json

Does NOT automatically delete entries — suspicious entries are flagged
with confidence_recalculated lowered; originals preserved.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from engine.source_registry.source_verifier import verify_source
from engine.source_registry.confidence_engine import (
    recalculate_source_confidence,
    build_confidence_summary,
)

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Known suspicious/fake domain patterns to flag explicitly
SUSPICIOUS_DOMAIN_PATTERNS = [
    "sonomacounty-elections.com",
    "ca-election-results.org",
    "ca-election-results.com",
    "election-results.ca.gov.com",
    "california-elections.org",
]


def _load_yaml_sources(yaml_path: Path) -> list[dict]:
    if not yaml_path.exists():
        log.warning(f"[REPAIR] YAML not found: {yaml_path}")
        return []
    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        return raw.get("sources", [])
    except Exception as e:
        log.error(f"[REPAIR] Failed to load {yaml_path}: {e}")
        return []


def _is_suspicious_domain(domain: str) -> bool:
    domain_lower = domain.lower()
    for pattern in SUSPICIOUS_DOMAIN_PATTERNS:
        if pattern in domain_lower:
            return True
    # Flag domains that try to look like official but aren't
    if ("election" in domain_lower or "vote" in domain_lower or "sos" in domain_lower):
        if not any(d in domain_lower for d in [".gov", "socoe.us", "clarityelections.com",
                                                "statewidedatabase.org", "electionstats.org",
                                                "arcgis.com", "nces.ed.gov", "opendata"]):
            return True
    return False


def run_registry_repair(
    run_id: str = "",
    state: str = "CA",
    county: str = "Sonoma",
    skip_http: bool = True,
) -> dict:
    """
    Run the full registry repair scan across all source YAML files.

    Args:
        run_id: pipeline run ID prefix for output files
        state: filter state for coverage summary
        county: filter county for coverage summary
        skip_http: if True, skip live HTTP checks (use for CI/offline)

    Returns:
        summary dict with health metrics and file paths
    """
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d__%H%M%S")

    contest_path  = BASE_DIR / "config" / "source_registry" / "contest_sources.yaml"
    geometry_path = BASE_DIR / "config" / "source_registry" / "geometry_sources.yaml"

    contest_sources  = _load_yaml_sources(contest_path)
    geometry_sources = _load_yaml_sources(geometry_path)
    all_sources = [("contest", s) for s in contest_sources] + \
                  [("geometry", s) for s in geometry_sources]

    log.info(f"[REPAIR] Scanning {len(all_sources)} sources "
             f"({len(contest_sources)} contest, {len(geometry_sources)} geometry)")

    processed: list[dict] = []
    suspicious: list[dict] = []

    for source_type, source in all_sources:
        vr = verify_source(source, skip_http=skip_http)
        rec = recalculate_source_confidence(source, vr)
        rec["_source_type"] = source_type
        processed.append(rec)

        # Flag suspicious domains or major confidence drops
        domain = vr.domain
        susp_domain = _is_suspicious_domain(domain)
        big_drop = (rec.get("confidence_default_original", 0) - rec.get("confidence_recalculated", 0)) > 0.30

        if susp_domain or (not vr.in_allowlist and vr.url):
            suspicious.append({
                "source_id":             rec.get("source_id"),
                "source_type":           source_type,
                "domain":                domain,
                "url":                   vr.url,
                "domain_tier":           vr.tier,
                "in_allowlist":          vr.in_allowlist,
                "verified":              vr.verified,
                "original_confidence":   rec.get("confidence_default_original"),
                "new_confidence":        rec.get("confidence_recalculated"),
                "confidence_reason":     rec.get("confidence_reason"),
                "suspicious_domain":     susp_domain,
                "big_drop":              big_drop,
                "verification_reason":   vr.reason,
                "warnings":              vr.warnings,
            })

    # ── Health summary ─────────────────────────────────────────────────────────
    summary = build_confidence_summary(processed)
    summary["run_id"] = run_id
    summary["state"] = state
    summary["county"] = county
    summary["suspicious_entries"] = len(suspicious)
    summary["domains_not_in_allowlist"] = sum(
        1 for r in processed if r.get("domain_tier") == "not_allowlisted" and r.get("domain")
    )

    # Coverage rating
    verified_pct = summary["verified_sources"] / max(summary["total_sources"], 1)
    if verified_pct >= 0.80:
        summary["registry_coverage"] = "strong"
    elif verified_pct >= 0.60:
        summary["registry_coverage"] = "partial"
    else:
        summary["registry_coverage"] = "weak"

    # ── Write registry health JSON ─────────────────────────────────────────────
    health_dir = BASE_DIR / "derived" / "source_registry"
    health_dir.mkdir(parents=True, exist_ok=True)
    health_path = health_dir / f"{run_id}__registry_health.json"
    health_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    log.info(f"[REPAIR] Registry health written: {health_path}")

    # ── Write suspicious sources report (Markdown) ────────────────────────────
    report_dir = BASE_DIR / "reports" / "source_registry"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{run_id}__suspicious_sources.md"
    _write_suspicious_report(report_path, suspicious, summary, run_id)
    log.info(f"[REPAIR] Suspicious sources report: {report_path}")

    summary["health_path"]  = str(health_path)
    summary["report_path"]  = str(report_path)
    summary["all_processed"] = processed

    log.info(
        f"[REPAIR] Complete — total={summary['total_sources']} "
        f"verified={summary['verified_sources']} "
        f"suspicious={summary['suspicious_entries']} "
        f"coverage={summary['registry_coverage']}"
    )
    return summary


def _write_suspicious_report(
    path: Path,
    suspicious: list[dict],
    summary: dict,
    run_id: str,
) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# Source Registry Suspicious Sources Report",
        f"",
        f"**Run ID:** `{run_id}`  ",
        f"**Generated:** {ts}  ",
        f"**Total sources scanned:** {summary.get('total_sources', 0)}  ",
        f"**Verified sources:** {summary.get('verified_sources', 0)}  ",
        f"**Suspicious entries:** {summary.get('suspicious_entries', 0)}  ",
        f"**Coverage:** {summary.get('registry_coverage', 'unknown')}  ",
        f"",
        f"---",
        f"",
    ]

    if not suspicious:
        lines.append("## ✅ No Suspicious Sources Found")
        lines.append("")
        lines.append("All registry entries passed domain allowlist and confidence checks.")
        lines.append("")
    else:
        lines.append(f"## ⚠️ Suspicious or Downgraded Sources ({len(suspicious)} entries)")
        lines.append("")
        lines.append("| Source ID | Type | Domain | Tier | In Allowlist | Verified | Prev Conf | New Conf | Reason |")
        lines.append("|-----------|------|--------|------|:---:|:---:|---:|---:|--------|")
        for s in suspicious:
            in_al  = "✅" if s["in_allowlist"] else "❌"
            ver    = "✅" if s["verified"] else "❌"
            susp_m = " 🚨" if s.get("suspicious_domain") else ""
            lines.append(
                f"| `{s['source_id']}`{susp_m} | {s['source_type']} | `{s['domain']}` | "
                f"{s['domain_tier']} | {in_al} | {ver} | "
                f"{s['original_confidence']:.2f} | {s['new_confidence']:.2f} | "
                f"{(s['confidence_reason'] or '')[:60]} |"
            )
        lines.append("")
        lines.append("### Notes")
        lines.append("- 🚨 = Domain matched suspicious pattern list")
        lines.append("- Entries are NOT deleted — confidence downgraded and flagged for review")
        lines.append("- Use the Source Registry UI to approve or reject entries")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## Domain Tier Summary",
        f"",
        f"| Tier | Max Confidence | Entries |",
        f"|------|---------------|---------|",
    ]

    from collections import Counter
    tier_counts = Counter()
    for s in summary.get("all_processed", []):
        tier_counts[s.get("domain_tier", "unknown")] += 1

    tier_order = [
        ("gov_tier",       "0.99"),
        ("official_tier",  "0.90"),
        ("academic_tier",  "0.85"),
        ("not_allowlisted","0.59"),
        ("unknown",        "—"),
    ]
    for tier_key, max_conf in tier_order:
        count = tier_counts.get(tier_key, 0)
        if count:
            lines.append(f"| {tier_key} | {max_conf} | {count} |")

    path.write_text("\n".join(lines), encoding="utf-8")
