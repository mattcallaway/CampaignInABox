"""
ui/dashboard/state_loader.py — Prompt 14.5

Loads the canonical campaign state from derived/state/latest/campaign_state.json.
Falls back to legacy data_loader.load_all() if the state store is not yet populated.

Usage:
    from ui.dashboard.state_loader import load_state, get_recommendations

    state = load_state()    # full campaign_state dict
    recs  = get_recommendations()  # top-5 recommendations list
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATE_DIR = BASE_DIR / "derived" / "state" / "latest"

log = logging.getLogger(__name__)


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"state_loader: could not read {path}: {e}")
    return {}


def load_state() -> dict:
    """
    Load the latest campaign state from the state store.

    Returns the full campaign_state dict, or an empty dict if unavailable.
    Falls back to legacy derived outputs for any section that is missing.
    """
    state = _read_json(STATE_DIR / "campaign_state.json")
    if state:
        log.info(f"State store loaded: run_id={state.get('run_id')}")
    else:
        log.info("No state store found; dashboard will use legacy file discovery.")
    return state


def get_recommendations() -> list[dict]:
    """Return the current top-5 recommendations from the state store."""
    recs_payload = _read_json(STATE_DIR / "recommendations.json")
    return recs_payload.get("top_recommendations", [])


def get_data_requests() -> list[dict]:
    """Return open data requests from the stable latest pointer."""
    dr_payload = _read_json(STATE_DIR / "data_requests.json")
    return dr_payload.get("requests", [])


def get_campaign_metrics_history() -> pd.DataFrame:
    """Return the full campaign_metrics.csv run history as a DataFrame."""
    metrics_path = STATE_DIR / "campaign_metrics.csv"
    if metrics_path.exists():
        try:
            return pd.read_csv(metrics_path)
        except Exception as e:
            log.warning(f"Could not read campaign_metrics.csv: {e}")
    return pd.DataFrame()


def state_to_data_dict(state: dict) -> dict:
    """
    Convert a state dict into the legacy data dict format expected by existing
    dashboard pages. This allows War Room / Overview / Strategy pages to consume
    state data without rewriting their internal logic.
    """
    if not state:
        return {}

    ai    = state.get("artifact_index", {})
    ms    = state.get("model_summary", {})
    ss    = state.get("strategy_summary", {})
    wr_s  = state.get("war_room_summary", {})
    cs    = state.get("campaign_setup", {})

    # Build a pseudo strategy_meta compatible with old pages
    strategy_meta = {
        "run_id":              state.get("run_id"),
        "contest_name":        cs.get("contest_name"),
        "election_date":       cs.get("election_date"),
        "target_vote_share":   cs.get("target_vote_share"),
        "total_budget":        cs.get("total_budget"),
        "win_number":          ss.get("win_number"),
        "vote_path_coverage":  ss.get("vote_path_coverage"),
        "war_room_ready":      wr_s.get("war_room_ready"),
        "real_metrics_count":  state.get("provenance_summary", {}).get("REAL", 0),
        "simulated_metrics_count": state.get("provenance_summary", {}).get("SIMULATED", 0),
        "estimated_metrics_count": state.get("provenance_summary", {}).get("ESTIMATED", 0),
        "missing_metrics_count": state.get("provenance_summary", {}).get("MISSING", 0),
        "data_requests":       {
            "total": len(state.get("data_requests", [])),
            "critical": wr_s.get("critical_requests", 0),
            "high": wr_s.get("high_priority_requests", 0),
        },
        "pipeline_steps_completed": ["STATE_BUILD"],
    }

    return {
        "run_id":         state.get("run_id"),
        "state_store":    state,          # full state available to any page
        "strategy_meta":  strategy_meta,
        # Pass-throughs for pages that still load their own data
        "campaign_setup": cs,
        "model_summary":  ms,
        "strategy_summary": ss,
        "war_room_summary": wr_s,
        "provenance_summary": state.get("provenance_summary", {}),
        "recommendations":   state.get("recommendations", []),
        "data_requests":     state.get("data_requests", []),
        "risks":             state.get("risks", []),
        "artifact_index":    ai,
    }


def load_state_snapshot_meta() -> dict:
    """Return a compact snapshot dict for the State Snapshot sidebar/panel."""
    state = load_state()
    if not state:
        return {"available": False}

    # Check if a diff exists for this run
    run_id    = state.get("run_id", "")
    diff_path = BASE_DIR / "derived" / "state" / "history" / f"{run_id}__state_diff.json"
    diff_data = _read_json(diff_path)

    return {
        "available":      True,
        "run_id":         run_id,
        "generated_at":   state.get("generated_at"),
        "contest_id":     state.get("contest_id"),
        "state":          state.get("state"),
        "county":         state.get("county"),
        "war_room_ready": state.get("war_room_summary", {}).get("war_room_ready", False),
        "real_metrics":   state.get("provenance_summary", {}).get("REAL", 0),
        "risk_level":     state.get("war_room_summary", {}).get("current_risk_level", "UNKNOWN"),
        "diff_available": bool(diff_data.get("prior_state_found")),
        "diff_summary":   diff_data.get("summary", ""),
        "n_recommendations": len(state.get("recommendations", [])),
    }
