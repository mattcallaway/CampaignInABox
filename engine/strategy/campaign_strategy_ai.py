"""
engine/strategy/campaign_strategy_ai.py — Prompt 13

Campaign strategy synthesis engine. Reads campaign_config.yaml + all
pipeline derived outputs and computes:

  - Vote Path (base votes, persuasion needed, GOTV needed, win number)
  - Budget Allocation (rule-based proportional optimizer)
  - Field Strategy (doors needed, weekly pace, canvasser staffing)
  - Risk Analysis (turnout, persuasion, coverage risks)

Writes to derived/strategy/<run_id>__*.csv (safe to commit).
"""
from __future__ import annotations

import datetime
import logging
import math
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from engine.utils.helpers import g as _g, find_latest_csv, BASE_DIR, load_yaml, load_json
from engine.utils.derived_data_reader import DerivedDataReader

CONFIG_PATH = BASE_DIR / "config" / "campaign_config.yaml"
STRATEGY_DIR = BASE_DIR / "derived" / "strategy"

log = logging.getLogger(__name__)

# ── Config Loading ─────────────────────────────────────────────────────────────

def load_campaign_config() -> dict:
    """Load campaign_config.yaml. Returns empty dict if missing."""
    return load_yaml(CONFIG_PATH)


# ── Input Loading (C02 fix: uses DerivedDataReader instead of broken path) ─────

def load_campaign_inputs(
    contest_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    """
    Load all available pipeline derived outputs for strategy synthesis.
    Uses DerivedDataReader for run_id-aware, contest-aware resolution.
    """
    reader = DerivedDataReader(contest_id=contest_id, run_id=run_id)
    return {
        "config":                   load_campaign_config(),
        "precinct_model":           reader.precinct_model(),
        "voter_universes":           reader.voter_universes(),
        "targeting_quadrants":       reader.targeting_quadrants(),
        "tps_precinct":              reader.precinct_turnout_scores(),
        "ps_precinct":               reader.precinct_persuasion_scores(),
        "precinct_voter_metrics":    reader.precinct_voter_metrics(),
        "simulations":               reader.simulations(),    # C02: now searches correct paths
        "calibration_params":        reader.calibration_params(),
    }


# ── Vote Path ─────────────────────────────────────────────────────────────────

def compute_vote_path(inputs: dict) -> dict:
    """
    Compute the vote path: how many votes are needed and where they come from.

    Returns a dict with:
      registered, expected_voters, votes_needed_to_win,
      base_votes, persuasion_votes_needed, gotv_votes_needed,
      cumulative_total, coverage_rate
    """
    cfg = inputs.get("config", {})
    target_vote_share = _g(cfg, "targets", "target_vote_share", default=0.52)
    win_margin = _g(cfg, "targets", "win_margin", default=0.04)

    # Registered voters from precinct model
    pm = inputs.get("precinct_model")
    registered = 0
    if pm is not None and not pm.empty:
        for col in ["registered", "total_registered", "reg_voters"]:
            if col in pm.columns:
                registered = int(pd.to_numeric(pm[col], errors="coerce").sum())
                break

    # Baseline turnout
    cal = inputs.get("calibration_params", {})
    baseline_turnout = cal.get("baseline_turnout_mean", 0.42)  # prior = 42%

    expected_voters = int(registered * baseline_turnout) if registered else 50000

    # Win number = expected_voters × target_vote_share
    win_number = int(math.ceil(expected_voters * target_vote_share))

    # Stretch goal includes margin
    stretch_number = int(math.ceil(expected_voters * (target_vote_share + win_margin)))

    # Base votes from committed supporters
    # Use voter universe data if available
    uni = inputs.get("voter_universes")
    base_votes = 0
    total_voters_on_file = 0

    if uni is not None and not uni.empty:
        for col in ["total_voters", "total_voters_on_file"]:
            if col in uni.columns:
                total_voters_on_file = int(uni[col].sum())
                break

        # Base = high-value persuasion already won + base supporters
        for col_set in [
            ["high_value_persuasion_count", "base_mobilization_count"],
            ["high_propensity_count", "base_supporters_count"],
        ]:
            found = [c for c in col_set if c in uni.columns]
            if found:
                base_raw = sum(int(uni[c].sum()) for c in found)
                # Scale to expected turnout
                if total_voters_on_file > 0:
                    base_votes = int(base_raw / total_voters_on_file * expected_voters * 0.85)
                break

    # Fallback: estimate base as 35% of expected voters
    if base_votes == 0:
        base_votes = int(expected_voters * 0.35)

    # How many votes to close
    gap = win_number - base_votes

    # M-02 Fix: configurable persuasion/GOTV split (was hardcoded 0.65/0.35)
    persuasion_share = float(_g(cfg, "strategy", "persuasion_gotv_split", default=0.65))
    persuasion_share = max(0.0, min(1.0, persuasion_share))  # clamp to [0,1]
    gotv_share = 1.0 - persuasion_share

    persuasion_votes_needed = max(int(gap * persuasion_share), 0)
    gotv_votes_needed       = max(int(gap * gotv_share), 0)

    cumulative_total = base_votes + persuasion_votes_needed + gotv_votes_needed
    coverage_rate = cumulative_total / win_number if win_number else 1.0

    result = {
        "registered": registered,
        "expected_voters": expected_voters,
        "baseline_turnout_pct": baseline_turnout,
        "win_number": win_number,
        "stretch_number": stretch_number,
        "base_votes": base_votes,
        "votes_gap": gap,
        "persuasion_votes_needed": persuasion_votes_needed,
        "gotv_votes_needed": gotv_votes_needed,
        "cumulative_total": cumulative_total,
        "coverage_rate": coverage_rate,
        "status": "on_track" if coverage_rate >= 1.0 else "gap_exists",
    }
    log.info(
        f"[STRATEGY_AI] Vote path: registered={registered:,}, "
        f"expected={expected_voters:,}, win_number={win_number:,}, "
        f"base={base_votes:,}, gap={gap:,}"
    )
    return result


# ── Budget Allocation ──────────────────────────────────────────────────────────

PRIORITY_WEIGHTS = {"Low": 0.6, "Medium": 1.0, "High": 1.6}


def compute_budget_allocation(inputs: dict) -> dict:
    """
    Compute budget allocation across programs.

    If explicit budget is set in config, use it as-is.
    Otherwise use priority weights to allocate.

    Returns a dict with per-program budget + rationale.
    """
    cfg = inputs.get("config", {})
    total = _g(cfg, "budget", "total_budget", default=150000)
    if total <= 0:
        total = 150000

    # Use explicit budgets if set meaningfully
    explicit = {
        "field":    _g(cfg, "budget", "field_budget", default=0),
        "mail":     _g(cfg, "budget", "mail_budget", default=0),
        "digital":  _g(cfg, "budget", "digital_budget", default=0),
        "research": _g(cfg, "budget", "research_budget", default=0),
    }
    explicit_sum = sum(explicit.values())

    if explicit_sum > 0 and abs(explicit_sum - total) < total * 0.10:
        # Trust explicit allocation (within 10% of total)
        scale = total / explicit_sum
        allocation = {k: round(v * scale) for k, v in explicit.items()}
        method = "explicit_from_config"
    else:
        # Priority-weighted allocation
        persuasion_w = PRIORITY_WEIGHTS.get(_g(cfg, "strategy", "persuasion_priority", default="High"), 1.0)
        turnout_w    = PRIORITY_WEIGHTS.get(_g(cfg, "strategy", "turnout_priority", default="Medium"), 1.0)
        base_w       = PRIORITY_WEIGHTS.get(_g(cfg, "strategy", "base_mobilization_priority", default="Medium"), 1.0)
        mail_w       = PRIORITY_WEIGHTS.get(_g(cfg, "strategy", "mail_priority", default="Medium"), 1.0)
        digital_w    = PRIORITY_WEIGHTS.get(_g(cfg, "strategy", "digital_priority", default="Low"), 1.0)

        # Field covers persuasion + GOTV + base
        field_w = persuasion_w * 0.5 + turnout_w * 0.3 + base_w * 0.2

        weights = {
            "field": field_w,
            "mail": mail_w,
            "digital": digital_w,
            "research": 0.5,  # always some research
        }
        total_w = sum(weights.values())
        allocation = {k: round(total * v / total_w) for k, v in weights.items()}
        method = "priority_weighted"

    # ROI estimates (simplified)
    cost_per_persuasion_contact = _g(cfg, "field_program", "doors_per_canvasser_per_day", default=40)
    field_contacts_possible = int(allocation["field"] / max(cost_per_persuasion_contact * 2, 1) * 100)
    mail_pieces_possible    = int(allocation["mail"] / 0.65)  # ~$0.65/piece
    digital_impressions     = int(allocation["digital"] / 0.003)  # ~$3 CPM

    return {
        "total": total,
        "field": allocation.get("field", 0),
        "mail": allocation.get("mail", 0),
        "digital": allocation.get("digital", 0),
        "research": allocation.get("research", 0),
        "method": method,
        "roi_estimates": {
            "field_contacts_possible": field_contacts_possible,
            "mail_pieces_possible": mail_pieces_possible,
            "digital_impressions": digital_impressions,
        },
    }


# ── Field Strategy ─────────────────────────────────────────────────────────────

def compute_field_strategy(inputs: dict, vote_path: dict) -> dict:
    """
    Compute field program requirements: doors, pace, canvasser staffing.
    """
    cfg = inputs.get("config", {})

    # Election timing
    election_date_str = _g(cfg, "campaign", "election_date", default=None)
    today = datetime.date.today()
    if election_date_str:
        try:
            election_date = datetime.date.fromisoformat(str(election_date_str))
            days_to_election = (election_date - today).days
        except Exception:
            days_to_election = 84  # 12-week default
    else:
        days_to_election = 84

    days_per_week = _g(cfg, "field_program", "days_per_week", default=5)
    weeks_to_election = max(days_to_election / 7, 1)

    # Field assumptions
    doors_per_day = _g(cfg, "field_program", "doors_per_canvasser_per_day", default=40)
    contact_rate = _g(cfg, "field_program", "contact_success_rate", default=0.22)
    persuasion_rate = _g(cfg, "field_program", "persuasion_rate_per_contact", default=0.04)
    turnout_lift = _g(cfg, "field_program", "turnout_lift_per_contact", default=0.06)

    # Persuasion doors needed
    persvotes = vote_path.get("persuasion_votes_needed", 500)
    if persuasion_rate * contact_rate > 0:
        persuasion_doors_needed = int(persvotes / (persuasion_rate * contact_rate))
    else:
        persuasion_doors_needed = 0

    # GOTV doors needed
    gotvotes = vote_path.get("gotv_votes_needed", 300)
    if turnout_lift * contact_rate > 0:
        gotv_doors_needed = int(gotvotes / (turnout_lift * contact_rate))
    else:
        gotv_doors_needed = 0

    total_doors_needed = persuasion_doors_needed + gotv_doors_needed
    doors_per_week_needed = total_doors_needed / weeks_to_election if weeks_to_election else total_doors_needed

    # Volunteer capacity
    volunteers = _g(cfg, "volunteers", "volunteers_per_week", default=10)
    shifts = _g(cfg, "volunteers", "avg_shifts_per_volunteer", default=2)
    hours = _g(cfg, "volunteers", "shift_length_hours", default=3)
    contacts_per_hour = _g(cfg, "volunteers", "contacts_per_hour", default=8)
    volunteer_contacts_per_week = volunteers * shifts * hours * contacts_per_hour
    volunteer_doors_per_week = volunteer_contacts_per_week / contact_rate if contact_rate else 0

    # Canvassers needed (in addition to volunteers)
    gap_doors_per_week = max(doors_per_week_needed - volunteer_doors_per_week, 0)
    paid_canvassers_needed = int(math.ceil(gap_doors_per_week / (doors_per_day * days_per_week))) if doors_per_day else 0

    # Weekly plan
    weekly_plan = []
    remaining_persuasion = persuasion_doors_needed
    remaining_gotv = gotv_doors_needed
    capacity_per_week = int(volunteer_doors_per_week + paid_canvassers_needed * doors_per_day * days_per_week)

    for wk in range(1, int(weeks_to_election) + 1):
        # Ramp up: start with persuasion, shift to GOTV in final 4 weeks
        weeks_remaining = weeks_to_election - wk
        if weeks_remaining <= 4:
            gotv_pct = min(0.80, 0.20 + (4 - weeks_remaining) * 0.15)
        else:
            gotv_pct = 0.20
        persuasion_pct = 1 - gotv_pct

        wk_cap = min(capacity_per_week, remaining_persuasion + remaining_gotv)
        wk_pers_doors = min(int(wk_cap * persuasion_pct), remaining_persuasion)
        wk_gotv_doors = min(int(wk_cap * gotv_pct), remaining_gotv)
        remaining_persuasion -= wk_pers_doors
        remaining_gotv -= wk_gotv_doors
        weekly_plan.append({
            "week": wk,
            "persuasion_doors": wk_pers_doors,
            "gotv_doors": wk_gotv_doors,
            "total_doors": wk_pers_doors + wk_gotv_doors,
            "expected_persuasion_contacts": int(wk_pers_doors * contact_rate),
            "expected_gotv_contacts": int(wk_gotv_doors * contact_rate),
        })

    return {
        "persuasion_doors_needed": persuasion_doors_needed,
        "gotv_doors_needed": gotv_doors_needed,
        "total_doors_needed": total_doors_needed,
        "doors_per_week_needed": round(doors_per_week_needed),
        "volunteer_doors_per_week": round(volunteer_doors_per_week),
        "paid_canvassers_needed": paid_canvassers_needed,
        "weeks_to_election": round(weeks_to_election, 1),
        "days_to_election": days_to_election,
        "weekly_plan": weekly_plan,
    }


# ── Risk Analysis ──────────────────────────────────────────────────────────────

RISK_LEVELS = {"LOW": "🟢 Low", "MEDIUM": "🟡 Medium", "HIGH": "🔴 High"}


def compute_risk_analysis(inputs: dict, vote_path: dict, field_strategy: dict) -> list[dict]:
    """Identify and quantify main campaign risks."""
    risks = []
    cfg = inputs.get("config", {})
    cal = inputs.get("calibration_params", {})

    # 1. Turnout risk
    turnout_variance = cal.get("turnout_variance", 0.06)
    if turnout_variance > 0.08:
        level = "HIGH"
    elif turnout_variance > 0.04:
        level = "MEDIUM"
    else:
        level = "LOW"
    risks.append({
        "risk": "Turnout Uncertainty",
        "level": level,
        "description": f"Baseline turnout variance ±{turnout_variance:.0%}. "
                       f"Low-turnout scenario reduces expected voters by ~{int(vote_path['expected_voters'] * turnout_variance):,}.",
        "mitigation": "Increase GOTV investment; mail VBM chase list to high-propensity supporters.",
    })

    # 2. Persuasion universe size
    uni = inputs.get("voter_universes")
    persuasion_available = 0
    if uni is not None and not uni.empty:
        for col in ["persuasion_universe_count", "persuadable_count", "persuadable_count"]:
            if col in uni.columns:
                persuasion_available = int(uni[col].sum())
                break

    persvotes_needed = vote_path.get("persuasion_votes_needed", 999)
    if persuasion_available > 0:
        ratio = persuasion_available / persvotes_needed if persvotes_needed else 99
        if ratio < 1.5:
            level = "HIGH"
        elif ratio < 3.0:
            level = "MEDIUM"
        else:
            level = "LOW"
        risks.append({
            "risk": "Persuasion Universe Size",
            "level": level,
            "description": f"{persuasion_available:,} persuadable voters available vs {persvotes_needed:,} needed ({ratio:.1f}× coverage).",
            "mitigation": "Lower PS threshold in targeting_quadrants.py" if ratio < 2 else
                          "Universe is adequate — prioritize high-PS precincts.",
        })

    # 3. Canvasser gap
    paid_needed = field_strategy.get("paid_canvassers_needed", 0)
    if paid_needed > 20:
        level = "HIGH"
    elif paid_needed > 5:
        level = "MEDIUM"
    else:
        level = "LOW"
    risks.append({
        "risk": "Canvasser Staffing",
        "level": level,
        "description": f"{paid_needed} paid canvassers needed beyond volunteer capacity "
                       f"({field_strategy.get('volunteer_doors_per_week',0):,} volunteer doors/week "
                       f"vs {field_strategy.get('doors_per_week_needed',0):,} needed).",
        "mitigation": "Recruit more volunteers, hire canvassers, or reduce persuasion target threshold.",
    })

    # 4. Voter data coverage
    vm = inputs.get("precinct_voter_metrics")
    if vm is not None and not vm.empty:
        pm = inputs.get("precinct_model")
        precincts_model = len(pm) if pm is not None else 1
        precincts_with_voters = len(vm)
        coverage = precincts_with_voters / precincts_model if precincts_model else 1.0
        level = "HIGH" if coverage < 0.50 else "MEDIUM" if coverage < 0.80 else "LOW"
        risks.append({
            "risk": "Voter File Precinct Coverage",
            "level": level,
            "description": f"{precincts_with_voters:,}/{precincts_model:,} precincts matched ({coverage:.0%}).",
            "mitigation": "Ensure voter file includes all Sonoma precinct codes. Check voter_parser precinct normalization.",
        })

    # 5. Timeline risk
    days_to_election = field_strategy.get("days_to_election", 90)
    if days_to_election < 30:
        level = "HIGH"
    elif days_to_election < 60:
        level = "MEDIUM"
    else:
        level = "LOW"
    risks.append({
        "risk": "Campaign Timeline",
        "level": level,
        "description": f"{days_to_election} days ({field_strategy.get('weeks_to_election', 0):.1f} weeks) until election.",
        "mitigation": "Front-load persuasion; shift to GOTV in final 4 weeks." if days_to_election >= 30 else
                      "Very short timeline — prioritize mail and digital; limited field available.",
    })

    return risks


# ── Output Writers ─────────────────────────────────────────────────────────────

def write_strategy_outputs(
    vote_path: dict,
    budget: dict,
    field_strategy: dict,
    risks: list[dict],
    run_id: str,
) -> dict[str, Path]:
    """Write all strategy CSVs to derived/strategy/."""
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}

    # Vote path CSV
    vp_path = STRATEGY_DIR / f"{run_id}__vote_path.csv"
    pd.DataFrame([{k: v for k, v in vote_path.items() if not isinstance(v, (dict, list))}]).to_csv(vp_path, index=False)
    paths["vote_path"] = vp_path
    log.info(f"[STRATEGY_AI] Wrote vote path: {vp_path}")

    # Budget allocation CSV
    ba_path = STRATEGY_DIR / f"{run_id}__budget_allocation.csv"
    ba_rows = [
        {"program": "Field Canvassing", "budget": budget.get("field", 0), "pct": budget.get("field", 0) / max(budget.get("total", 1), 1)},
        {"program": "Mail",             "budget": budget.get("mail", 0),  "pct": budget.get("mail", 0)  / max(budget.get("total", 1), 1)},
        {"program": "Digital",          "budget": budget.get("digital", 0), "pct": budget.get("digital", 0) / max(budget.get("total", 1), 1)},
        {"program": "Research",         "budget": budget.get("research", 0), "pct": budget.get("research", 0) / max(budget.get("total", 1), 1)},
    ]
    pd.DataFrame(ba_rows).to_csv(ba_path, index=False)
    paths["budget_allocation"] = ba_path
    log.info(f"[STRATEGY_AI] Wrote budget allocation: {ba_path}")

    # Field strategy CSV
    fs_path = STRATEGY_DIR / f"{run_id}__field_strategy.csv"
    weekly = field_strategy.get("weekly_plan", [])
    if weekly:
        pd.DataFrame(weekly).to_csv(fs_path, index=False)
    else:
        pd.DataFrame([{k: v for k, v in field_strategy.items() if not isinstance(v, (dict, list))}]).to_csv(fs_path, index=False)
    paths["field_strategy"] = fs_path
    log.info(f"[STRATEGY_AI] Wrote field strategy: {fs_path}")

    # Risk analysis CSV
    rk_path = STRATEGY_DIR / f"{run_id}__risk_analysis.csv"
    pd.DataFrame(risks).to_csv(rk_path, index=False)
    paths["risk_analysis"] = rk_path
    log.info(f"[STRATEGY_AI] Wrote risk analysis: {rk_path}")

    return paths


# ── Main Entry Point ────────────────────────────────────────────────────────────

def generate_strategy_bundle(run_id: str) -> dict:
    """
    Full strategy generation pipeline. Call this from run_pipeline.py.

    Returns dict with all computed strategy objects + output paths.
    """
    log.info(f"[STRATEGY_AI] Generating strategy bundle for run {run_id}")
    inputs = load_campaign_inputs(run_id)

    if not inputs["config"]:
        log.warning("[STRATEGY_AI] No campaign config found — using defaults. Run Campaign Setup to configure.")

    vote_path     = compute_vote_path(inputs)
    budget        = compute_budget_allocation(inputs)
    field         = compute_field_strategy(inputs, vote_path)
    risks         = compute_risk_analysis(inputs, vote_path, field)
    paths         = write_strategy_outputs(vote_path, budget, field, risks, run_id)

    return {
        "vote_path": vote_path,
        "budget": budget,
        "field_strategy": field,
        "risks": risks,
        "output_paths": paths,
        "inputs": inputs,
    }
