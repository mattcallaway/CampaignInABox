"""
scripts/tools/run_p25a1_repair.py — Prompt 25A.1

Pipeline runner for source registry validation and confidence repair:
1. Load both registries
2. Run domain verification and confidence recalculation on all entries
3. Assert confidence policy correctness
4. Generate suspicious_sources.md report and registry_health.json
5. Update campaign_state.json with source_registry_health
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

RUN_ID = "20260313__p25a1"
BASE_DIR = Path(os.getcwd())

print("=== Prompt 25A.1 Source Registry Repair ===")
print()

# Phase 1: Load allowlist
print("-- Phase 1: Domain Allowlist --")
from engine.source_registry.source_verifier import (
    load_domain_allowlist,
    check_domain_allowlist,
    extract_domain,
    verify_source,
)
allowlist = load_domain_allowlist()
gov_count      = len(allowlist.get("gov_tier", {}).get("domains", []))
official_count = len(allowlist.get("official_tier", {}).get("domains", []))
academic_count = len(allowlist.get("academic_tier", {}).get("domains", []))
print(f"  gov_tier:      {gov_count} domains (max 0.99)")
print(f"  official_tier: {official_count} domains (max 0.90)")
print(f"  academic_tier: {academic_count} domains (max 0.85)")

# Phase 2: Run registry repair
print()
print("-- Phase 2: Registry Repair --")
from engine.source_registry.registry_repair import run_registry_repair

summary = run_registry_repair(run_id=RUN_ID, state="CA", county="Sonoma", skip_http=True)
records = summary.pop("all_processed", [])
print(f"  Total sources:   {summary['total_sources']}")
print(f"  Verified:        {summary['verified_sources']}")
print(f"  Heuristic-capped:{summary['heuristic_sources']}")
print(f"  Invalid domain:  {summary['domains_not_in_allowlist']}")
print(f"  Suspicious:      {summary['suspicious_entries']}")
print(f"  Coverage:        {summary['registry_coverage']}")
print(f"  Health JSON:     {summary['health_path']}")
print(f"  Report:          {summary['report_path']}")

# Phase 3: Confidence assertion checks
print()
print("-- Phase 3: Assertion Checks --")
errors = []

gov_domains = ["socoe.us", "sos.ca.gov", "elections.cdn.sos.ca.gov", "vig.cdn.sos.ca.gov"]
academic_domains = ["statewidedatabase.org", "electionstats.org", "nces.ed.gov"]

for r in records:
    sid = r.get("source_id", "?")
    domain = r.get("domain", "")
    conf_new = r.get("confidence_recalculated", 0)
    conf_old = r.get("confidence_default_original", 0)
    origin = r.get("source_origin", "")
    tier = r.get("domain_tier", "")

    # Gov domains should NOT be downgraded below their original stated confidence
    # (they're allowlisted — the tier ceiling may still reduce statewidedatabase from 0.97 to 0.85,
    # but gov-tier sources should keep their original confidence_default)
    if domain in gov_domains and conf_new < conf_old - 0.001:
        errors.append(f"FAIL: {sid} gov domain {domain} downgraded from {conf_old:.2f} to {conf_new:.2f}")

    # Academic domains should be capped at 0.85
    if domain in academic_domains and conf_new > 0.85:
        errors.append(f"FAIL: {sid} academic domain {domain} scored {conf_new:.2f} (expected <=0.85)")

    # heuristic_candidate should be capped at 0.59
    if origin == "heuristic_candidate" and conf_new > 0.59:
        errors.append(f"FAIL: {sid} heuristic_candidate scored {conf_new:.2f} (expected <=0.59)")

for r in records:
    sid = r.get("source_id", "?")
    conf_new = r.get("confidence_recalculated", 0)
    conf_old = r.get("confidence_default_original", 0)
    changed = r.get("confidence_changed", False)
    reason = r.get("confidence_reason", "")[:70]
    tier = r.get("domain_tier", "?")
    chg = f"{conf_old:.2f} -> {conf_new:.2f}" if changed else f"= {conf_new:.2f}"
    print(f"  [{tier[:12]:12}] {sid:<40} {chg}  {reason}")

print()
if errors:
    print(f"ASSERTION FAILURES: {len(errors)}")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print(f"All {len(records)} assertions passed.")

# Phase 4: Update campaign_state.json
print()
print("-- Phase 4: Update campaign_state.json --")
STATE_PATH = BASE_DIR / "derived" / "state" / "latest" / "campaign_state.json"
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
        state["source_registry_health"] = registry_health
        STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        print(f"  campaign_state.json updated with source_registry_health")
    except Exception as e:
        print(f"  WARNING: {e}")
else:
    print(f"  WARNING: campaign_state.json not found")

print()
print("=== ALL PHASES COMPLETE ===")
print(f"  Sources: {summary['total_sources']} | Verified: {summary['verified_sources']} | Coverage: {summary['registry_coverage']}")
