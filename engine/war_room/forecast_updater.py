"""
engine/war_room/forecast_updater.py — Prompt 14

Forecast Update Comparison: re-runs the vote path and field strategy calculations
with runtime-observed contact/persuasion rates, then compares to baseline.

Outputs: derived/war_room/<run_id>__forecast_update_comparison.csv

Maintains two forecast tracks:
  model_forecast_baseline — what the model predicted with configured priors
  war_room_forecast_current — adjusted for actual runtime field observations
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
WAR_ROOM_DIR = BASE_DIR / "derived" / "war_room"

log = logging.getLogger(__name__)


def _g(d: dict, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def _find_latest_csv(directory: Path, pattern: str) -> Optional[pd.DataFrame]:
    try:
        matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return pd.read_csv(matches[0]) if matches else None
    except Exception:
        return None


def compute_forecast_comparison(
    campaign_config: dict,
    runtime_summary: dict,
    run_id: str,
) -> pd.DataFrame:
    """
    Compare baseline model forecast vs. runtime-adjusted forecast.

    Returns a DataFrame with metrics, baseline values, current values, delta, and source.
    """
    cfg      = campaign_config or {}
    rt       = runtime_summary.get("metrics", {})
    presence = runtime_summary.get("presence", {})

    # ── Load baseline from strategy outputs ───────────────────────────────────
    vote_path_df = _find_latest_csv(BASE_DIR / "derived" / "strategy", "*__vote_path.csv")
    field_df     = _find_latest_csv(BASE_DIR / "derived" / "strategy", "*__field_strategy.csv")

    vp_base = {}
    if vote_path_df is not None and not vote_path_df.empty:
        vp_base = vote_path_df.iloc[0].to_dict()

    # ── Baseline assumptions ──────────────────────────────────────────────────
    contact_rate_base   = _g(cfg, "field_program", "contact_success_rate", default=0.22)
    persuasion_rate_base = _g(cfg, "field_program", "persuasion_rate_per_contact", default=0.04)
    turnout_lift_base    = _g(cfg, "field_program", "turnout_lift_per_contact", default=0.06)
    volunteers_base      = _g(cfg, "volunteers", "volunteers_per_week", default=10)

    # ── Runtime overrides (REAL > baseline) ───────────────────────────────────
    contact_rate_current   = rt.get("observed_contact_rate", contact_rate_base)
    persuasion_rate_current = rt.get("observed_persuasion_rate", persuasion_rate_base)
    turnout_lift_current    = turnout_lift_base  # not directly observable yet
    volunteers_current      = rt.get("avg_volunteers_per_week", volunteers_base)

    # ── Impact on vote path ───────────────────────────────────────────────────
    expected_voters = int(vp_base.get("expected_voters", 50000))
    win_number      = int(vp_base.get("win_number", 0))
    base_votes      = int(vp_base.get("base_votes", 0))
    gap             = win_number - base_votes

    import math

    def doors_needed(votes, pers_rate, contact_rate):
        if pers_rate * contact_rate > 0:
            return int(math.ceil(votes / (pers_rate * contact_rate)))
        return 0

    # Baseline doors for persuasion
    pers_votes_base = int(vp_base.get("persuasion_votes_needed", gap * 0.65))
    gotv_votes_base = int(vp_base.get("gotv_votes_needed", gap * 0.35))
    doors_pers_base = doors_needed(pers_votes_base, persuasion_rate_base, contact_rate_base)
    doors_gotv_base = doors_needed(gotv_votes_base, turnout_lift_base, contact_rate_base)

    # Runtime-adjusted
    doors_pers_current = doors_needed(pers_votes_base, persuasion_rate_current, contact_rate_current)
    doors_gotv_current = doors_needed(gotv_votes_base, turnout_lift_current, contact_rate_current)

    # Volunteer capacity
    shifts_base = _g(cfg, "volunteers", "avg_shifts_per_volunteer", default=2)
    hours_base  = _g(cfg, "volunteers", "shift_length_hours", default=3)
    cph         = _g(cfg, "volunteers", "contacts_per_hour", default=8)

    vol_contacts_base    = volunteers_base    * shifts_base * hours_base * cph
    vol_contacts_current = (volunteers_current or volunteers_base) * shifts_base * hours_base * cph

    vol_doors_base    = vol_contacts_base    / contact_rate_base    if contact_rate_base    else 0
    vol_doors_current = vol_contacts_current / contact_rate_current if contact_rate_current else 0

    # ── Build comparison table ─────────────────────────────────────────────────
    rows = [
        {
            "metric": "Contact Rate",
            "model_baseline": f"{contact_rate_base:.1%}",
            "war_room_current": f"{contact_rate_current:.1%}",
            "delta": f"{(contact_rate_current - contact_rate_base):.1%}",
            "current_source": "REAL" if presence.get("field_results") else "ESTIMATED",
            "impact": "Higher rate = fewer doors needed per vote",
        },
        {
            "metric": "Persuasion Rate per Contact",
            "model_baseline": f"{persuasion_rate_base:.1%}",
            "war_room_current": f"{persuasion_rate_current:.1%}",
            "delta": f"{(persuasion_rate_current - persuasion_rate_base):.1%}",
            "current_source": "REAL" if presence.get("contact_results") else "ESTIMATED",
            "impact": "Higher rate = more persuasion from each contact",
        },
        {
            "metric": "Volunteers per Week",
            "model_baseline": str(int(volunteers_base)),
            "war_room_current": str(round(volunteers_current or volunteers_base, 1)),
            "delta": str(round((volunteers_current or volunteers_base) - volunteers_base, 1)),
            "current_source": "REAL" if presence.get("volunteer_log") else "ESTIMATED",
            "impact": "More volunteers = more doors per week",
        },
        {
            "metric": "Persuasion Doors Needed",
            "model_baseline": f"{doors_pers_base:,}",
            "war_room_current": f"{doors_pers_current:,}",
            "delta": f"{doors_pers_current - doors_pers_base:,}",
            "current_source": "SIMULATED",
            "impact": "Total persuasion doors required to hit vote goal",
        },
        {
            "metric": "GOTV Doors Needed",
            "model_baseline": f"{doors_gotv_base:,}",
            "war_room_current": f"{doors_gotv_current:,}",
            "delta": f"{doors_gotv_current - doors_gotv_base:,}",
            "current_source": "SIMULATED",
            "impact": "Total GOTV doors required to hit turnout goal",
        },
        {
            "metric": "Volunteer Doors/Week Capacity",
            "model_baseline": f"{int(vol_doors_base):,}",
            "war_room_current": f"{int(vol_doors_current):,}",
            "delta": f"{int(vol_doors_current - vol_doors_base):,}",
            "current_source": "REAL" if presence.get("volunteer_log") else "ESTIMATED",
            "impact": "Total door capacity from volunteer army each week",
        },
    ]

    total_doors_base    = doors_pers_base    + doors_gotv_base
    total_doors_current = doors_pers_current + doors_gotv_current
    weeks = max(_g(cfg, "field_program", "weeks_before_election") or 12, 1)
    try:
        import datetime
        election_date = datetime.date.fromisoformat(str(_g(cfg, "campaign", "election_date", default="2025-06-03")))
        weeks = max((election_date - datetime.date.today()).days / 7, 1)
    except Exception:
        pass

    rows.append({
        "metric": "Total Doors Needed",
        "model_baseline": f"{total_doors_base:,}",
        "war_room_current": f"{total_doors_current:,}",
        "delta": f"{total_doors_current - total_doors_base:,}",
        "current_source": "SIMULATED",
        "impact": "Total field program scope",
    })
    rows.append({
        "metric": "Doors/Week Required",
        "model_baseline": f"{int(total_doors_base / weeks):,}",
        "war_room_current": f"{int(total_doors_current / weeks):,}",
        "delta": f"{int((total_doors_current - total_doors_base) / weeks):,}",
        "current_source": "SIMULATED",
        "impact": "Weekly pace needed to complete field program",
    })

    return pd.DataFrame(rows)


def write_forecast_comparison(df: pd.DataFrame, run_id: str) -> Path:
    WAR_ROOM_DIR.mkdir(parents=True, exist_ok=True)
    out = WAR_ROOM_DIR / f"{run_id}__forecast_update_comparison.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    log.info(f"[FORECAST_UPDATE] Written: {out}")
    return out
