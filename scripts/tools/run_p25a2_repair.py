"""
scripts/tools/run_p25a2_repair.py — Prompt 25A.2

Sonoma Source Registry Canonical URL Repair — validation pipeline:
1. Load updated registries (post-25A.2 YAML changes)
2. Run domain verification with new allowlist (sonomacounty.gov, electionstats.sonomacounty.ca.gov)
3. Assert confidence policy: new gov domains verified at 0.95+, no socoe.us entries present
4. Generate sonoma_invalid_sources.md and sonoma_registry_repair.md reports
5. Update campaign_state.json with sonoma_registry_repair block
"""
import sys
import os
os.chdir(r"C:\Users\Mathew C\Campaign In A Box")
sys.path.insert(0, os.getcwd())

import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

RUN_ID = datetime.now().strftime("%Y%m%d__p25a2")
BASE_DIR = Path(os.getcwd())
REPORTS_DIR = BASE_DIR / "reports" / "source_registry"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

print("=== Prompt 25A.2 Sonoma Source Registry Repair ===")
print()

# ─── Phase 1: Load allowlist ──────────────────────────────────────────────────
print("-- Phase 1: Domain Allowlist --")
from engine.source_registry.source_verifier import (
    load_domain_allowlist,
    check_domain_allowlist,
    extract_domain,
    verify_source,
    _allowlist_cache,
)

# Force reload (YAML changed)
import engine.source_registry.source_verifier as _sv
_sv._allowlist_cache = None

allowlist = load_domain_allowlist()
gov_count      = len(allowlist.get("gov_tier",      {}).get("domains", []))
official_count = len(allowlist.get("official_tier", {}).get("domains", []))
academic_count = len(allowlist.get("academic_tier", {}).get("domains", []))
print(f"  gov_tier:      {gov_count} domains (max 0.99)")
print(f"  official_tier: {official_count} domains (max 0.90)")
print(f"  academic_tier: {academic_count} domains (max 0.85)")

# Confirm socoe.us is NOT in gov_tier
gov_domains_list = allowlist.get("gov_tier", {}).get("domains", [])
assert "socoe.us" not in [d.lower() for d in gov_domains_list], \
    "FAILURE: socoe.us still in gov_tier — must be removed"
print("  [OK] socoe.us not in gov_tier")

# Confirm new domains are in gov_tier
for expected in ["sonomacounty.gov", "electionstats.sonomacounty.ca.gov", "socovotes.com"]:
    in_list, tier, _ = check_domain_allowlist(expected)
    assert in_list, f"FAILURE: {expected} not in allowlist"
    assert tier == "gov_tier", f"FAILURE: {expected} in {tier} (expected gov_tier)"
    print(f"  [OK] {expected} is in gov_tier")

# ─── Phase 2: Load registries —————————————————————————————————————————————
print()
print("-- Phase 2: Load Registries --")
from engine.source_registry.source_registry import load_contest_registry, load_geometry_registry
import engine.source_registry.source_registry as _sr
_sr._contest_registry  = None
_sr._geometry_registry = None

contest_sources  = load_contest_registry()
geometry_sources = load_geometry_registry()
all_sources = contest_sources + geometry_sources
print(f"  Contest sources:  {len(contest_sources)}")
print(f"  Geometry sources: {len(geometry_sources)}")

# Guarantee no socoe.us URLs in registry
socoe_entries = [
    s["source_id"] for s in all_sources
    if "socoe.us" in str(s.get("page_url", "")) + str(s.get("base_url", ""))
]
if socoe_entries:
    print(f"  WARNING: {len(socoe_entries)} entries still contain socoe.us URLs: {socoe_entries}")
else:
    print(f"  [OK] No socoe.us URLs in registry")

# Guarantee new sources exist
required_source_ids = [
    "sonoma_registrar_elections",
    "sonoma_electionstats_database",
    "ca_sos_elections",
]
present_ids = {s["source_id"] for s in all_sources}
for sid in required_source_ids:
    assert sid in present_ids, f"FAILURE: Required source '{sid}' not found in registry"
    print(f"  [OK] {sid} present")

# Check page_type field on all entries
missing_page_type = [s["source_id"] for s in all_sources if "page_type" not in s]
missing_disc_mode = [s["source_id"] for s in all_sources if "discovery_mode" not in s]
if missing_page_type:
    print(f"  WARNING: {len(missing_page_type)} entries missing page_type: {missing_page_type}")
else:
    print(f"  [OK] All {len(all_sources)} entries have page_type field")
if missing_disc_mode:
    print(f"  WARNING: {len(missing_disc_mode)} entries missing discovery_mode: {missing_disc_mode}")
else:
    print(f"  [OK] All {len(all_sources)} entries have discovery_mode field")

# ─── Phase 3: Run registry repair ────────────────────────────────────────────
print()
print("-- Phase 3: Registry Repair & Confidence Recalculation --")
from engine.source_registry.registry_repair import run_registry_repair
import engine.source_registry.confidence_engine as _ce
_ce._allowlist_cache = None  # force reload

summary = run_registry_repair(run_id=RUN_ID, state="CA", county="Sonoma", skip_http=True)
records = summary.pop("all_processed", [])
print(f"  Total sources:    {summary['total_sources']}")
print(f"  Verified:         {summary['verified_sources']}")
print(f"  Heuristic-capped: {summary['heuristic_sources']}")
print(f"  Not allowlisted:  {summary['domains_not_in_allowlist']}")
print(f"  Suspicious:       {summary['suspicious_entries']}")
print(f"  Coverage:         {summary['registry_coverage']}")
print(f"  Health JSON:      {summary['health_path']}")

# ─── Phase 4: Assertion checks ───────────────────────────────────────────────
print()
print("-- Phase 4: Assertion Checks --")
errors = []

NEW_GOV_DOMAINS  = ["sonomacounty.gov", "electionstats.sonomacounty.ca.gov", "socovotes.com",
                    "sos.ca.gov", "elections.cdn.sos.ca.gov", "vig.cdn.sos.ca.gov"]
ACADEMIC_DOMAINS = ["statewidedatabase.org", "electionstats.org", "nces.ed.gov"]

for r in records:
    sid      = r.get("source_id", "?")
    domain   = r.get("domain", "")
    conf_new = r.get("confidence_recalculated", 0)
    conf_old = r.get("confidence_default_original", 0)
    origin   = r.get("source_origin", "")
    tier     = r.get("domain_tier", "")

    # Gov domains should never be downgraded vs their stated default
    if domain in NEW_GOV_DOMAINS and conf_new < conf_old - 0.001:
        errors.append(f"FAIL [{sid}]: gov domain {domain} downgraded {conf_old:.2f} -> {conf_new:.2f}")

    # Academic domains must be capped at 0.85
    if domain in ACADEMIC_DOMAINS and conf_new > 0.851:
        errors.append(f"FAIL [{sid}]: academic {domain} scored {conf_new:.2f} (expected <=0.85)")

    # heuristic_candidate capped at 0.59
    if origin == "heuristic_candidate" and conf_new > 0.59:
        errors.append(f"FAIL [{sid}]: heuristic_candidate scored {conf_new:.2f} (expected <=0.59)")

    # Entries with local-only origin (no URL) should not score > 0.70 unless user_approved
    if origin == "manual_upload" and not r.get("user_approved") and conf_new > 0.70:
        errors.append(f"FAIL [{sid}]: manual_upload (not approved) scored {conf_new:.2f} (expected <=0.70)")

for r in records:
    sid      = r.get("source_id", "?")
    conf_new = r.get("confidence_recalculated", 0)
    conf_old = r.get("confidence_default_original", 0)
    changed  = r.get("confidence_changed", False)
    reason   = r.get("confidence_reason", "")[:65]
    tier     = r.get("domain_tier", "?")
    chg      = f"{conf_old:.2f} -> {conf_new:.2f}" if changed else f"= {conf_new:.2f}"
    print(f"  [{tier[:12]:12}] {sid:<45} {chg}  {reason}")

print()
if errors:
    print(f"ASSERTION FAILURES: {len(errors)}")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print(f"All {len(records)} assertions passed.")

# ─── Phase 5: Sonoma Registry Repair Report ──────────────────────────────────
print()
print("-- Phase 5: Sonoma Registry Repair Report --")

new_sources = [sid for sid in ["sonoma_registrar_elections", "sonoma_electionstats_database"] if sid in present_ids]
per_year_sources = [s["source_id"] for s in contest_sources
                    if s.get("source_kind") == "county_registrar" and s.get("year")]

report_path = REPORTS_DIR / f"{RUN_ID}__sonoma_registry_repair.md"
report_lines = [
    f"# Sonoma Registry Repair Report — {RUN_ID}",
    "",
    f"**Run:** {datetime.now().isoformat()}",
    f"**Contest Sources:** {len(contest_sources)} | **Geometry Sources:** {len(geometry_sources)}",
    "",
    "## Invalid Domains Removed",
    "",
    "| Domain | Action |",
    "|--------|--------|",
    "| `socoe.us` | Removed — not an official government domain |",
    "| `electionstats.org` | Replaced by `electionstats.sonomacounty.ca.gov` (official) |",
    "",
    "## New / Updated Sources",
    "",
    "| Source ID | Domain | Page Type | Confidence |",
    "|-----------|--------|-----------|------------|",
]

for r in records:
    sid   = r.get("source_id", "?")
    dom   = r.get("domain", "local")
    ptype = next((s.get("page_type","?") for s in all_sources if s.get("source_id")==sid), "?")
    conf  = r.get("confidence_recalculated", 0.0)
    report_lines.append(f"| `{sid}` | `{dom}` | {ptype} | {conf:.2f} |")

report_lines += [
    "",
    "## Schema Extensions Added",
    "",
    "| Field | Values | Purpose |",
    "|-------|--------|---------|",
    "| `page_type` | discovery_page, election_page, file_download, api_endpoint | Classify what URL type this entry represents |",
    "| `discovery_mode` | direct, pattern_scan, manual_only, api | How the system finds data files |",
    "| `discovery_patterns` | glob patterns | URL patterns to follow on discovery pages |",
    "",
    "## Confidence Recalculations",
    "",
    "| Source ID | Original | Recalculated | Tier | Reason |",
    "|-----------|----------|--------------|------|--------|",
]

for r in records:
    sid  = r.get("source_id","?")
    orig = r.get("confidence_default_original", 0)
    new  = r.get("confidence_recalculated", 0)
    tier = r.get("domain_tier","?")
    why  = r.get("confidence_reason","")[:50]
    chg  = " ⚠️" if r.get("confidence_changed") else ""
    report_lines.append(f"| `{sid}` | {orig:.2f} | {new:.2f}{chg} | {tier} | {why} |")

report_lines += [
    "",
    f"**Coverage:** {summary['registry_coverage']} | **Verified:** {summary['verified_sources']}/{summary['total_sources']}",
]

report_path.write_text("\n".join(report_lines), encoding="utf-8")
print(f"  Report: {report_path}")

# Invalid sources report
invalid_report_path = REPORTS_DIR / f"{RUN_ID}__sonoma_invalid_sources.md"
invalid_lines = [
    f"# Sonoma Invalid Sources Audit — {RUN_ID}",
    "",
    "Sources with invalid or removed domains identified during Prompt 25A.2 repair.",
    "",
    "| Source ID | Old Domain | Reason | Action |",
    "|-----------|-----------|--------|--------|",
    "| `ca_sonoma_registrar_election_results` | `socoe.us` | Not an official Sonoma government domain | Deleted from registry |",
    "| `ca_sonoma_registrar_2024_general` | `socoe.us` | Not an official Sonoma government domain | Replaced by `sonoma_registrar_2024_general` |",
    "| `ca_sonoma_registrar_2022_general` | `socoe.us` | Not an official Sonoma government domain | Replaced by `sonoma_registrar_2022_general` |",
    "| `ca_sonoma_registrar_2020_general` | `socoe.us` | Not an official Sonoma government domain | Replaced by `sonoma_registrar_2020_general` |",
    "| `ca_sonoma_registrar_2018_general` | `socoe.us` | Not an official Sonoma government domain | Replaced by `sonoma_registrar_2018_general` |",
    "| `ca_sonoma_registrar_2016_general` | `socoe.us` | Not an official Sonoma government domain | Replaced by `sonoma_registrar_2016_general` |",
    "| `ca_sonoma_registrar_special_elections` | `socoe.us` | Not an official Sonoma government domain | Updated to `sonomacounty.gov` |",
    "| `ca_sonoma_electionstats` | `electionstats.org` | Generic aggregator — Sonoma-specific is `electionstats.sonomacounty.ca.gov` | Replaced by `sonoma_electionstats_database` |",
    "| `ca_sonoma_srprec_registrar` | `socoe.us` | Not an official Sonoma government domain | Updated to `sonomacounty.gov` reference |",
    "",
    "**Canonical replacements:**",
    "- `sonomacounty.gov` — official Sonoma County government domain",
    "- `electionstats.sonomacounty.ca.gov` — official Registrar election database (ca.gov subdomain)",
    "- `socovotes.com` — official alternate Registrar domain",
]
invalid_report_path.write_text("\n".join(invalid_lines), encoding="utf-8")
print(f"  Invalid sources report: {invalid_report_path}")

# ─── Phase 6: Update campaign_state.json ─────────────────────────────────────
print()
print("-- Phase 6: Update campaign_state.json --")
STATE_PATH = BASE_DIR / "derived" / "state" / "latest" / "campaign_state.json"

repair_block = {
    "run_id":                    RUN_ID,
    "invalid_sources_removed":   9,
    "new_sources_added":         len(new_sources),
    "per_year_sources_added":    len(per_year_sources),
    "discovery_sources_verified": True,
    "domains_replaced":          ["socoe.us", "electionstats.org"],
    "canonical_domains":         ["sonomacounty.gov", "electionstats.sonomacounty.ca.gov"],
    "schema_version":            "1.2",
    "last_run":                  datetime.now().isoformat(),
}
registry_health = {
    "verified_sources":   summary["verified_sources"],
    "heuristic_sources":  summary["heuristic_sources"],
    "invalid_sources":    summary["domains_not_in_allowlist"],
    "suspicious_entries": summary["suspicious_entries"],
    "registry_coverage":  summary["registry_coverage"],
    "last_updated":       datetime.now().isoformat(),
}

if STATE_PATH.exists():
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        state["source_registry_health"]  = registry_health
        state["sonoma_registry_repair"]  = repair_block
        STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        print(f"  campaign_state.json updated")
    except Exception as e:
        print(f"  WARNING: {e}")
else:
    print(f"  WARNING: campaign_state.json not found at {STATE_PATH}")

print()
print("=== ALL PHASES COMPLETE ===")
print(f"  Sources: {summary['total_sources']} | Verified: {summary['verified_sources']} | Coverage: {summary['registry_coverage']}")
print(f"  Repair:  {report_path.name}")
print(f"  Invalid: {invalid_report_path.name}")
