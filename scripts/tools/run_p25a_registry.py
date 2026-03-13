"""
scripts/tools/run_p25a_registry.py — Prompt 25A

Pipeline runner for the source registry validation:
- Load contest and geometry registries
- Run source registry diagnostics report
- Update campaign_state.json with source_registry_summary
- Test resolver with a sample query
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

RUN_ID = "20260313__p25a"

# ── Phase 1: Load registries ──────────────────────────────────────────────────
print("=== Phase 1: Load Registries ===")
from engine.source_registry.source_registry import (
    load_contest_registry,
    load_geometry_registry,
    find_contest_sources,
    find_geometry_sources,
)

contest_sources  = load_contest_registry()
geometry_sources = load_geometry_registry()
print(f"Contest sources: {len(contest_sources)}")
print(f"Geometry sources: {len(geometry_sources)}")

# ── Phase 2: Test resolver ─────────────────────────────────────────────────
print("\n=== Phase 2: Test Resolver ===")
from engine.source_registry.source_resolver import (
    resolve_contest_source,
    resolve_geometry_source,
    summarize_registry_coverage,
)

r1 = resolve_contest_source(state="CA", county="Sonoma", year=2024, election_type="general")
print(f"  CA/Sonoma/2024/general -> high={len(r1.high_confidence)}, med={len(r1.medium_confidence)}, fallback={r1.fallback_required}")
if r1.best:
    print(f"  Best: {r1.best.get('source_id')} (score={r1.best.get('_match_score')})")

r2 = resolve_geometry_source(state="CA", county="Sonoma", boundary_type="crosswalk")
print(f"  CA/Sonoma/crosswalk -> high={len(r2.high_confidence)}, med={len(r2.medium_confidence)}")
if r2.best:
    print(f"  Best geometry: {r2.best.get('source_id')}")


# ── Phase 3: Registry Diagnostics Report ─────────────────────────────────────
print("\n=== Phase 3: Registry Diagnostics Report ===")
from engine.source_registry.source_registry_report import run_registry_report

summary = run_registry_report(run_id=RUN_ID, state="CA", county="Sonoma")
print(f"  Contest sources: {summary['contest_sources']}")
print(f"  Geometry sources: {summary['geometry_sources']}")
print(f"  Coverage: {summary['registry_coverage']}")
print(f"  Years covered: {summary['years_covered']}")
print(f"  Report: {summary['report_path']}")

# ── Phase 4: Update campaign_state.json ───────────────────────────────────────
print("\n=== Phase 4: Update campaign_state.json ===")
STATE_PATH = BASE_DIR / "derived" / "state" / "latest" / "campaign_state.json"
registry_coverage = summarize_registry_coverage(state="CA", county="Sonoma")

if STATE_PATH.exists():
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        state["source_registry_summary"] = {
            "contest_sources":   registry_coverage["contest_sources"],
            "geometry_sources":  registry_coverage["geometry_sources"],
            "approved_sources":  registry_coverage["approved_sources"],
            "registry_coverage": registry_coverage["registry_coverage"],
            "last_updated":      datetime.now().isoformat(),
        }
        STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        print(f"  campaign_state.json updated with source_registry_summary")
    except Exception as e:
        print(f"  WARNING: Could not update campaign_state.json: {e}")
else:
    print("  WARNING: campaign_state.json not found — skipping state update")

print(f"\nPhase 4 coverage: {registry_coverage}")
print("\n=== ALL PHASES COMPLETE ===")
print(f"Contest: {len(contest_sources)}, Geometry: {len(geometry_sources)}, Coverage: {registry_coverage['registry_coverage']}")
