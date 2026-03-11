"""
engine/data_intake/missing_data_assistant.py — Prompt 17.5

Evaluates the active file registry against the expected file types for the campaign configuration.
Generates a list of missing critical or optional files with recommendations.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Core expectations mapping
_EXPECTED_FILES = {
    "election_results": {
        "priority": "high",
        "why_needed": "Essential for establishing baseline precinct model turning and calibrating assumptions.",
        "example_filename": "county_sov_detail.csv",
        "recommended_destination": "data/elections/{state}/{county}/{contest_id}/"
    },
    "voter_file": {
        "priority": "critical",
        "why_needed": "Required for building the initial targeting universe and simulating specific voter turnout scores.",
        "example_filename": "county_voter_file_extract_2026.csv",
        "recommended_destination": "data/voters/{state}/{county}/"
    },
    "precinct_geometry": {
        "priority": "medium",
        "why_needed": "Necessary for generating the interactive map dashboard and cutting field canvassing turfs.",
        "example_filename": "county_precincts.geojson",
        "recommended_destination": "data/geography/{state}/{county}/"
    },
    "crosswalk": {
        "priority": "medium",
        "why_needed": "Provides block-to-precinct mapping so geographic allocation is more accurate.",
        "example_filename": "block_to_precinct_xwalk.csv",
        "recommended_destination": "data/crosswalks/{state}/{county}/"
    },
    "polling": {
        "priority": "high",
        "why_needed": "Crucial external signal for the Intelligence Fusion layer. Without it, the model relies on baselines only.",
        "example_filename": "latest_benchmark_poll.xlsx",
        "recommended_destination": "data/intelligence/polling/"
    },
    "ballot_returns": {
        "priority": "medium",
        "why_needed": "Allows the war room to project early voting pace and adjust GOTV targets daily.",
        "example_filename": "daily_return_report_aggregate.csv",
        "recommended_destination": "data/intelligence/ballot_returns/"
    },
    "demographics": {
        "priority": "low",
        "why_needed": "Can adjust support models (via education/income indexes) if polling is sparse.",
        "example_filename": "census_acs_precincts.csv",
        "recommended_destination": "data/intelligence/demographics/"
    }
}


def _load_config(root: Path) -> dict:
    import yaml
    try:
        cfg = root / "config" / "campaign_config.yaml"
        if cfg.exists():
            with open(cfg, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


def analyze_missing_data(project_root: str | Path, run_id: Optional[str] = None) -> list[dict]:
    """
    Read active registry and compare to expected file types based on config.
    Writes missing_data_requests.json and returns the missing definitions.
    """
    from engine.data_intake.data_intake_manager import FileRegistryManager
    
    root = Path(project_root)
    cfg = _load_config(root)
    state = cfg.get("campaign", {}).get("state", "CA")
    county = cfg.get("campaign", {}).get("county", "Sonoma")
    contest_id = cfg.get("campaign", {}).get("contest_name", "").replace(" ", "_").lower() or "unknown"

    manager = FileRegistryManager(root)
    registry = manager.load_registry()

    active_types = {r.get("campaign_data_type") for r in registry if r.get("status") in ("ACTIVE", "REGISTERED")}

    missing_requests = []
    
    for c_type, req in _EXPECTED_FILES.items():
        if c_type not in active_types:
            dest = req["recommended_destination"].format(state=state, county=county, contest_id=contest_id)
            missing_requests.append({
                "data_type": c_type,
                "priority": req["priority"],
                "why_needed": req["why_needed"],
                "recommended_destination": dest,
                "example_filename": req["example_filename"]
            })

    # Output to derived
    dest_dir = root / "derived" / "file_registry" / "latest"
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    out_file = dest_dir / "missing_data_requests.json"
    payload = {
        "run_id": run_id or "latest",
        "missing_count": len(missing_requests),
        "requests": missing_requests
    }
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    
    return missing_requests
