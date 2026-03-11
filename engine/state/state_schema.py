"""
engine/state/state_schema.py — Prompt 14.5

Canonical schema for the Campaign State Store.
Provides the empty skeleton and a type-annotated dataclass-style
builder so every caller constructs state objects the same way.

Security: NEVER populate voter names, addresses, VAN IDs, or raw
contact logs. Only aggregated precinct-level counts are allowed.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# ── Canonical top-level keys (required for validation) ──────────────────────
REQUIRED_KEYS: tuple[str, ...] = (
    "run_id",
    "contest_id",
    "state",
    "county",
    "generated_at",
    "campaign_setup",
    "model_summary",
    "strategy_summary",
    "war_room_summary",
    "voter_intelligence_summary",
    "provenance_summary",
    "data_requests",
    "risks",
    "recommendations",
    "artifact_index",
    "jurisdictions",
    "contests",
    "multi_jurisdiction_forecast",
)

# ── Section schemas (used as typing hints / defaults) ────────────────────────

def empty_campaign_setup() -> dict:
    return {
        "contest_name":       None,
        "contest_type":       None,
        "election_date":      None,
        "target_vote_share":  None,
        "total_budget":       None,
        "field_budget":       None,
        "mail_budget":        None,
        "digital_budget":     None,
        "volunteers_per_week": None,
        "contact_rate":       None,
        "turnout_lift":       None,
        "strategy_priorities": [],
    }


def empty_model_summary() -> dict:
    return {
        "precinct_count":       None,
        "turf_count":           None,
        "region_count":         None,
        "scenario_count":       None,
        "baseline_support":     None,
        "baseline_turnout":     None,
        "win_probability":      None,
        "expected_margin":      None,
        "advanced_modeling_used": False,
    }


def empty_strategy_summary() -> dict:
    return {
        "recommended_strategy":    None,
        "win_number":              None,
        "base_votes":              None,
        "persuasion_votes_needed": None,
        "gotv_votes_needed":       None,
        "vote_path_coverage":      None,
        "top_target_precinct_count": None,
        "top_turf_count":          None,
        "field_pace_doors_per_week": None,
        "total_budget":            None,
    }


def empty_war_room_summary() -> dict:
    return {
        "war_room_ready":        False,
        "real_metrics_count":    0,
        "simulated_metrics_count": 0,
        "estimated_metrics_count": 0,
        "missing_metrics_count": 0,
        "current_risk_level":    "UNKNOWN",
        "daily_status_available": False,
        "data_requests_count":   0,
        "critical_requests":     0,
        "high_priority_requests": 0,
        "actual_field_doors":    0,
        "actual_volunteer_count": 0,
        "actual_spend":          0,
    }


def empty_voter_intelligence_summary() -> dict:
    return {
        "voter_file_loaded":         False,
        "precinct_match_rate":       None,
        "gotv_universe_size":        None,
        "persuasion_universe_size":  None,
        "turnout_propensity_coverage": None,
        "persuasion_score_coverage": None,
    }


def empty_provenance_summary() -> dict:
    return {
        "REAL":      0,
        "SIMULATED": 0,
        "ESTIMATED": 0,
        "MISSING":   0,
        "total":     0,
        "war_room_ready": False,
    }


def empty_artifact_index() -> dict:
    return {
        "strategy_meta":       None,
        "strategy_summary":    None,
        "precinct_model":      None,
        "targeting_list":      None,
        "simulation_results":  None,
        "field_plan":          None,
        "voter_universes":     None,
        "audit_report":        None,
        "daily_status":        None,
        "metric_provenance":   None,
        "forecast_comparison": None,
        "campaign_state":      None,
    }


def make_empty_state() -> dict:
    """Return a fully-structured empty campaign state dict."""
    return {
        "run_id":                      "",
        "contest_id":                  "",
        "state":                       "",
        "county":                      "",
        "generated_at":                "",
        "campaign_setup":              empty_campaign_setup(),
        "model_summary":               empty_model_summary(),
        "strategy_summary":            empty_strategy_summary(),
        "war_room_summary":            empty_war_room_summary(),
        "voter_intelligence_summary":  empty_voter_intelligence_summary(),
        "provenance_summary":          empty_provenance_summary(),
        "data_requests":               [],
        "risks":                       [],
        "recommendations":             [],
        "artifact_index":              empty_artifact_index(),
        "jurisdictions":               [],
        "contests":                    [],
        "multi_jurisdiction_forecast": {},
    }


def state_to_csv_row(state: dict) -> dict:
    """Flatten state to a single-row summary dict for campaign_metrics.csv."""
    cs = state.get("campaign_setup", {})
    ms = state.get("model_summary", {})
    ss = state.get("strategy_summary", {})
    wr = state.get("war_room_summary", {})
    ps = state.get("provenance_summary", {})
    vi = state.get("voter_intelligence_summary", {})
    return {
        "run_id":               state.get("run_id"),
        "contest_id":           state.get("contest_id"),
        "state":                state.get("state"),
        "county":               state.get("county"),
        "generated_at":         state.get("generated_at"),
        "election_date":        cs.get("election_date"),
        "target_vote_share":    cs.get("target_vote_share"),
        "total_budget":         cs.get("total_budget"),
        "precinct_count":       ms.get("precinct_count"),
        "win_probability":      ms.get("win_probability"),
        "expected_margin":      ms.get("expected_margin"),
        "baseline_support":     ms.get("baseline_support"),
        "baseline_turnout":     ms.get("baseline_turnout"),
        "win_number":           ss.get("win_number"),
        "vote_path_coverage":   ss.get("vote_path_coverage"),
        "field_pace_doors_wk":  ss.get("field_pace_doors_per_week"),
        "war_room_ready":       wr.get("war_room_ready"),
        "real_metrics":         ps.get("REAL"),
        "simulated_metrics":    ps.get("SIMULATED"),
        "estimated_metrics":    ps.get("ESTIMATED"),
        "missing_metrics":      ps.get("MISSING"),
        "data_requests":        wr.get("data_requests_count"),
        "voter_file_loaded":    vi.get("voter_file_loaded"),
        "gotv_universe":        vi.get("gotv_universe_size"),
        "persuasion_universe":  vi.get("persuasion_universe_size"),
    }
