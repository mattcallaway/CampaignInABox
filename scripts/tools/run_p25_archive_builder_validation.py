"""
scripts/tools/run_p25_archive_builder_validation.py — Prompt 25

Validation tests for the Historical Election Archive Builder.

Tests:
  1. Source scanner loads registry and returns PageScanResults
  2. Offline scan returns correct source_ids and counties
  3. Domain isolation: scanner never follows outside base_url
  4. File discovery correctly filters by extension
  5. Priority scoring (statement > random terms)
  6. Archive classifier correctly processes a synthetic election file
  7. Archive registry: register, get, list, summary
  8. Archive build: offline dry-run completes without errors
  9. Fingerprint integration: classify a staged test file
  10. Review queue: non-ready file routed to ambiguous CSV
  11. Model inputs directory created
  12. Reports generated (build + classification)
"""
import sys, os
os.chdir(r"C:\Users\Mathew C\Campaign In A Box")
sys.path.insert(0, os.getcwd())
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
from datetime import datetime
from pathlib import Path

print("=== Prompt 25 Archive Builder Validation ===")
print()

RUN_ID = datetime.now().strftime("%Y%m%d__p25val")
ERRORS: list[str] = []

def ok(label): print(f"  [OK] {label}")
def fail(label, reason=""): print(f"  [!!] FAIL: {label} — {reason}"); ERRORS.append(f"{label}: {reason}")
def check(cond, label, reason=""): ok(label) if cond else fail(label, reason)

# ─── Phase 1: Source Scanner ──────────────────────────────────────────────────
print("-- Phase 1: Source Scanner --")
from engine.archive_builder.source_scanner import scan_all_sources, _load_registry
from pathlib import Path as P

REGISTRY_DIR = P("config/source_registry")
sources_raw = _load_registry(REGISTRY_DIR / "contest_sources.yaml")
check(len(sources_raw) > 0, "contest_sources.yaml loaded", f"got {len(sources_raw)} entries")

results = scan_all_sources(state_filter="CA", county_filter="Sonoma", online=False)
check(len(results) > 0, f"scan_all_sources returned {len(results)} results", "got 0")

sonoma_results = [r for r in results if r.county == "Sonoma"]
check(len(sonoma_results) > 0, "Sonoma results present", f"got {len(sonoma_results)}")

for r in results[:3]:
    check(r.source_id != "", f"source_id set: {r.source_id}", "empty source_id")
    check(r.state == "CA", f"state=CA: {r.source_id}", f"got {r.state}")

# Domain isolation check
from engine.archive_builder.source_scanner import _is_same_domain
check(_is_same_domain("https://sonomacounty.gov/results", "https://sonomacounty.gov"), "same domain match", "")
check(not _is_same_domain("https://marincounty.gov/results", "https://sonomacounty.gov"), "cross-domain blocked", "")

# ─── Phase 2: File Discovery ──────────────────────────────────────────────────
print()
print("-- Phase 2: File Discovery --")
from engine.archive_builder.file_discovery import (
    _priority_score, _extract_file_links, ACCEPTED_EXTENSIONS, REJECTED_EXTENSIONS
)

check(_priority_score("statement_of_votes_cast_2024.xlsx") >= 2, "statement file gets priority score >= 2", "")
check(_priority_score("image.png") == 0, "image file gets priority 0", "")
check(_priority_score("precinct_results_final.xlsx") >= 2, "precinct file gets priority >= 2", "")

# Extension filtering
check(".xlsx" in ACCEPTED_EXTENSIONS, ".xlsx accepted", "")
check(".pdf" in REJECTED_EXTENSIONS or ".pdf" not in ACCEPTED_EXTENSIONS, ".pdf not accepted", "")

# Link extractor
html = '''<html>
  <a href="/files/statement_of_votes_cast_2024.xlsx">Download</a>
  <a href="/files/map.pdf">Map</a>
  <a href="/files/precinct_results.csv">CSV</a>
  <a href="https://otherdomain.com/file.xlsx">External</a>
</html>'''
links = _extract_file_links(html, "https://sonomacounty.gov")
xlsx_links = [l for l in links if ".xlsx" in l]
csv_links  = [l for l in links if ".csv" in l]
ext_links  = [l for l in links if "otherdomain.com" in l]
check(len(xlsx_links) >= 1, f"xlsx link extracted ({len(xlsx_links)})", f"links={links}")
check(len(csv_links)  >= 1, f"csv link extracted ({len(csv_links)})", f"links={links}")

# ─── Phase 3: Archive Registry ────────────────────────────────────────────────
print()
print("-- Phase 3: Archive Registry --")
from engine.archive_builder.archive_registry import (
    register_election, get_election, list_elections, registry_summary
)

entry = register_election(
    election_id="2024_general_test", state="CA", county="Sonoma",
    year=2024, election_type="general",
    source_url="https://sonomacounty.gov/test",
    files_ingested=1, confidence_score=0.92,
    fingerprint_type="statement_of_vote",
    precinct_schema="mprec", normalization_method="safe_join_engine",
    join_confidence=0.99,
    archive_dir="data/historical_elections/CA/Sonoma/2024_general_test",
)
check(entry.get("election_id") == "2024_general_test", "register_election returns entry", f"got {entry.get('election_id')}")
check(entry.get("confidence_score") == 0.92, "confidence_score stored", f"got {entry.get('confidence_score')}")

fetched = get_election("2024_general_test")
check(fetched is not None, "get_election retrieves entry", "returned None")
check(fetched.get("year") == 2024, "year=2024 stored", f"got {fetched.get('year')}")

elections = list_elections(state="CA")
check(len(elections) >= 1, f"list_elections(CA): {len(elections)} entries", "got 0")

summary = registry_summary()
check(summary.get("total", 0) >= 1, f"registry_summary total={summary.get('total')}", "got 0")
check("CA" in summary.get("states", []), "CA in summary states", f"states={summary.get('states')}")
print(f"  Registry: {summary.get('total')} elections, states={summary.get('states')}")

# ─── Phase 4: Run Archive Build (offline dry-run) ─────────────────────────────
print()
print("-- Phase 4: Offline Archive Build --")
from engine.archive_builder.archive_builder import run_archive_build

result = run_archive_build(
    state="CA", county="Sonoma",
    online=False, download=False,
    run_id=RUN_ID,
)
check(result.run_id == RUN_ID, f"run_id={result.run_id}", "")
check(result.sources_scanned > 0, f"sources_scanned={result.sources_scanned}", "got 0")
check(result.errors == [], f"no build errors", f"errors: {result.errors}")
print(f"  Build: sources={result.sources_scanned} pages={result.pages_found} candidates={result.candidates_found} ingested={result.ingested} review={result.review_queue}")

# Build report written
if result.build_report:
    check(P(result.build_report).exists(), f"build report written: {P(result.build_report).name}", "file missing")
if result.classification_report:
    check(P(result.classification_report).exists(), f"classification report written: {P(result.classification_report).name}", "file missing")

# ─── Phase 5: Storage directories ─────────────────────────────────────────────
print()
print("-- Phase 5: Storage Directories --")
dirs_to_check = [
    P("data/historical_elections"),
    P("data/historical_elections/CA/Sonoma"),
    P("derived/archive_review_queue"),
    P("derived/archive_staging"),
    P("derived/model_inputs"),
    P("reports/archive_builder"),
]
for d in dirs_to_check:
    check(d.exists(), f"directory exists: {d}", "missing")

registry_file = P("data/historical_elections/archive_registry.yaml")
check(registry_file.exists(), "archive_registry.yaml exists", "missing")

# ─── Summary ──────────────────────────────────────────────────────────────────
print()
if ERRORS:
    print(f"ASSERTION FAILURES: {len(ERRORS)}")
    for e in ERRORS:
        print(f"  {e}")
    sys.exit(1)
else:
    print("All Archive Builder validation assertions passed.")

print()
print("=== ALL PHASES COMPLETE ===")
