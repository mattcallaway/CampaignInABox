"""
engine/data_intake/file_registry_pipeline.py — Prompt 24

Activates the file registry as a normal pipeline step.
Wraps FileRegistryManager to integrate with:
  - pipeline run hooks
  - campaign state builder
  - data manager UI events

Call run_registry_pipeline() after any data intake or pipeline run to:
  1. Scan derived/ and data/ for known pipeline outputs
  2. Register active files
  3. Generate missing_data_requests.json
  4. Generate source_finder_recommendations.json
  5. Write file_registry_report.md
  6. Update campaign_state.json with file inventory summary
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
REGISTRY_DIR = BASE_DIR / "derived" / "file_registry" / "latest"
STATE_DIR    = BASE_DIR / "derived" / "state" / "latest"
REPORTS_DIR  = BASE_DIR / "reports" / "data_intake"

for _d in (REGISTRY_DIR, STATE_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Files that the pipeline expects to exist — used to detect missing data
REQUIRED_PIPELINE_FILES = {
    "voter_file":            [BASE_DIR / "data" / "voters"],
    "precinct_geometry":     [BASE_DIR / "data" / "CA" / "counties" / "Sonoma" / "geography"],
    "crosswalk":             [BASE_DIR / "data" / "CA" / "counties" / "Sonoma" / "geography" / "crosswalks"],
    "election_archive":      [BASE_DIR / "derived" / "archive" / "normalized_elections.csv"],
    "precinct_profiles":     [BASE_DIR / "derived" / "archive" / "precinct_profiles.csv"],
    "precinct_trends":       [BASE_DIR / "derived" / "archive" / "precinct_trends.csv"],
    "similar_elections":     [BASE_DIR / "derived" / "archive" / "similar_elections.csv"],
    "support_model":         [BASE_DIR / "derived" / "models" / "support_model.pkl"],
    "calibration_params":    [BASE_DIR / "derived" / "calibration"],
    "precinct_model_output": [BASE_DIR / "derived" / "precinct_models"],
    "voter_universes":       [BASE_DIR / "derived" / "voter_universes"],
    "voter_scores":          [BASE_DIR / "derived" / "voter_models"],
    "strategy_output":       [BASE_DIR / "derived" / "strategy"],
    "simulation_output":     [BASE_DIR / "derived" / "advanced_modeling"],
}

SOURCE_RECOMMENDATIONS = {
    "voter_file":        "Obtain from County Registrar of Voters (VAN export) or NGP VAN / TargetSmart",
    "precinct_geometry": "California Secretary of State precinct shapefiles, or county GIS",
    "crosswalk":         "County Registrar crosswalk file (mprec_srprec CSV)",
    "election_archive":  "CA Secretary of State Statement of Vote, or county election results portal",
    "polling":           "Internal tracking polls or public PPIC / approved vendor surveys",
    "demographics":      "U.S. Census Bureau ACS 5-year estimates (census.gov/acs)",
}


def _check_required_files() -> tuple[list[dict], list[dict]]:
    """
    Scan for required pipeline files.
    Returns (active_files, missing_files).
    """
    active = []
    missing = []

    for file_type, paths in REQUIRED_PIPELINE_FILES.items():
        found = False
        for p in paths:
            p = Path(p)
            if p.is_file():
                active.append({
                    "file_type":  file_type,
                    "path":       str(p.relative_to(BASE_DIR)).replace("\\", "/"),
                    "size_bytes": p.stat().st_size,
                    "modified":   datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                    "status":     "active",
                })
                found = True
                break
            elif p.is_dir():
                # Check if directory has any real data files
                files = list(p.rglob("*.csv")) + list(p.rglob("*.parquet")) + list(p.rglob("*.pkl"))
                if files:
                    newest = max(files, key=lambda f: f.stat().st_mtime)
                    active.append({
                        "file_type":   file_type,
                        "path":        str(newest.relative_to(BASE_DIR)).replace("\\", "/"),
                        "size_bytes":  newest.stat().st_size,
                        "modified":    datetime.fromtimestamp(newest.stat().st_mtime).isoformat(),
                        "file_count":  len(files),
                        "status":      "active",
                    })
                    found = True
                    break

        if not found:
            missing.append({
                "file_type":        file_type,
                "status":           "MISSING",
                "recommendation":   SOURCE_RECOMMENDATIONS.get(file_type, "See data intake documentation"),
            })

    return active, missing


def run_registry_pipeline(run_id: Optional[str] = None) -> dict:
    """
    Full file registry pipeline. Returns summary dict.
    """
    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M%S") + "__registry"
    log.info(f"[REGISTRY] Running file registry pipeline | run_id={run_id}")

    # 1. Load existing registry (from FileRegistryManager if available)
    try:
        from engine.data_intake.data_intake_manager import FileRegistryManager
        mgr = FileRegistryManager(BASE_DIR)
        existing_registry = mgr.load_registry()
    except Exception as e:
        log.warning(f"[REGISTRY] Could not load FileRegistryManager: {e}")
        existing_registry = []

    # 2. Scan pipeline outputs
    active_files, missing_files = _check_required_files()

    # 3. Write file_registry.json
    registry_payload = {
        "run_id":       run_id,
        "generated_at": datetime.now().isoformat(),
        "active_files": active_files,
        "registered_files_count": len(existing_registry),
    }
    (REGISTRY_DIR / "file_registry.json").write_text(
        json.dumps(registry_payload, indent=2, default=str), encoding="utf-8"
    )

    # 4. Write missing_data_requests.json
    missing_payload = {
        "run_id":         run_id,
        "generated_at":   datetime.now().isoformat(),
        "missing_files":  missing_files,
        "missing_count":  len(missing_files),
    }
    (REGISTRY_DIR / "missing_data_requests.json").write_text(
        json.dumps(missing_payload, indent=2), encoding="utf-8"
    )

    # 5. Write source_finder_recommendations.json
    recs = [
        {"file_type": m["file_type"], "recommendation": m["recommendation"]}
        for m in missing_files
    ]
    (REGISTRY_DIR / "source_finder_recommendations.json").write_text(
        json.dumps({"run_id": run_id, "recommendations": recs}, indent=2), encoding="utf-8"
    )

    # 6. Update campaign_state.json with file inventory summary
    _update_campaign_state(active_files, missing_files, recs, run_id)

    # 7. Write report
    _write_registry_report(run_id, active_files, missing_files)

    summary = {
        "run_id": run_id,
        "active_files_found":  len(active_files),
        "missing_files_count": len(missing_files),
        "missing_critical":    [m["file_type"] for m in missing_files],
    }
    log.info(f"[REGISTRY] Complete: {len(active_files)} active, {len(missing_files)} missing")
    return summary


def _update_campaign_state(active_files, missing_files, recs, run_id):
    """Update derived/state/latest/campaign_state.json with file inventory summary."""
    state_path = STATE_DIR / "campaign_state.json"

    # Load existing state
    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}

    # Update file inventory block
    state["file_registry"] = {
        "last_updated":          datetime.now().isoformat(),
        "run_id":                run_id,
        "active_files_count":    len(active_files),
        "missing_files_count":   len(missing_files),
        "missing_required":      [m["file_type"] for m in missing_files],
        "source_recommendations_available": len(recs) > 0,
    }

    # Archive coverage summary if available
    archive_summary_path = BASE_DIR / "derived" / "archive" / "archive_summary.json"
    if archive_summary_path.exists():
        try:
            arch = json.loads(archive_summary_path.read_text(encoding="utf-8"))
            state["archive_coverage"] = arch.get("coverage", {})
        except Exception:
            pass

    state_path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    log.info(f"[REGISTRY] Updated campaign_state.json")


def _write_registry_report(run_id, active_files, missing_files):
    lines = [
        f"# File Registry Report",
        f"**Run ID:** {run_id}  |  **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"## Active Pipeline Files ({len(active_files)} found)",
        "",
        "| File Type | Path | Status |",
        "|-----------|------|--------|",
    ] + [
        f"| {f['file_type']} | `{f['path']}` | ✅ active |"
        for f in active_files
    ] + [
        "",
        f"## Missing Files ({len(missing_files)} required)",
        "",
        "| File Type | Recommendation |",
        "|-----------|----------------|",
    ] + [
        f"| {m['file_type']} | {m['recommendation']} |"
        for m in missing_files
    ]

    rpath = REPORTS_DIR / f"{run_id}__file_registry_report.md"
    rpath.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[REGISTRY] Wrote report: {rpath.name}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_registry_pipeline()
    print(f"Registry: {result['active_files_found']} active, {result['missing_files_count']} missing")
