"""
engine/war_room/status_engine.py — Prompt 14

War Room Status Engine: produces daily campaign status summaries.

Outputs:
  derived/war_room/<run_id>__daily_status.json
  reports/war_room/<run_id>__daily_status.md
  reports/war_room/<run_id>__campaign_war_room_summary.md

Every metric includes provenance source_type reference.
"""
from __future__ import annotations

import datetime
import json
import logging
import math
from pathlib import Path
from typing import Any, Optional

BASE_DIR      = Path(__file__).resolve().parent.parent.parent
WAR_ROOM_DIR  = BASE_DIR / "derived" / "war_room"
REPORTS_DIR   = BASE_DIR / "reports" / "war_room"

log = logging.getLogger(__name__)


def _g(d: dict, *keys, default=None) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def _find_latest_csv(directory: Path, pattern: str):
    try:
        import pandas as pd
        matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return pd.read_csv(matches[0])
    except Exception:
        pass
    return None


def compute_war_room_status(
    campaign_config: dict,
    runtime_summary: dict,
    data_requests: list[dict],
    provenance_records: Optional[list] = None,
) -> dict:
    """
    Compute the full war room status dict for daily reporting.
    """
    cfg = campaign_config or {}
    rt  = runtime_summary.get("metrics", {})
    presence = runtime_summary.get("presence", {})

    # ── Timeline ──────────────────────────────────────────────────────────────
    today = datetime.date.today()
    election_date_str = _g(cfg, "campaign", "election_date")
    days_to_election = None
    weeks_to_election = None
    try:
        election_date = datetime.date.fromisoformat(str(election_date_str))
        days_to_election = (election_date - today).days
        weeks_to_election = max(days_to_election / 7, 0)
    except Exception:
        pass

    # ── Vote Path ─────────────────────────────────────────────────────────────
    vote_path_df = _find_latest_csv(BASE_DIR / "derived" / "strategy", "*__vote_path.csv")
    vp = {}
    if vote_path_df is not None and not vote_path_df.empty:
        vp = vote_path_df.iloc[0].to_dict()

    win_number       = int(vp.get("win_number", 0))
    base_votes       = int(vp.get("base_votes", 0))
    pers_needed      = int(vp.get("persuasion_votes_needed", 0))
    gotv_needed      = int(vp.get("gotv_votes_needed", 0))
    coverage         = float(vp.get("coverage_rate", 0))
    expected_voters  = int(vp.get("expected_voters", 0))

    # ── Win Probability (from simulation if exists) ────────────────────────────
    win_prob = None
    win_prob_source = "MISSING"
    sim_dir = BASE_DIR / "derived" / "scenario_forecasts"
    if sim_dir.exists():
        sim_files = sorted(sim_dir.rglob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if sim_files:
            try:
                import pandas as pd
                sim_df = pd.read_csv(sim_files[0])
                for col in ["win_probability", "p_win", "prob_win", "sim_win_rate"]:
                    if col in sim_df.columns:
                        win_prob = float(sim_df[col].mean())
                        win_prob_source = "SIMULATED"
                        break
            except Exception:
                pass

    if win_prob is None:
        # Heuristic estimate: vote path coverage as proxy
        if coverage > 0:
            win_prob = min(coverage * 0.55, 0.90)
            win_prob_source = "ESTIMATED"

    # ── Field Pace ────────────────────────────────────────────────────────────
    field_strat_df = _find_latest_csv(BASE_DIR / "derived" / "strategy", "*__field_strategy.csv")
    target_doors_per_week = 0
    if field_strat_df is not None and not field_strat_df.empty:
        if "total_doors" in field_strat_df.columns:
            target_doors_per_week = int(field_strat_df["total_doors"].mean())
        elif "doors_per_week_needed" in field_strat_df.columns:
            target_doors_per_week = int(field_strat_df["doors_per_week_needed"].iloc[0])

    actual_doors = rt.get("total_doors_knocked", 0)
    weekly_doors = rt.get("weekly_avg_doors_last4w", 0)
    field_pace_pct = (weekly_doors / target_doors_per_week * 100) if target_doors_per_week else None
    field_pace_source = "REAL" if presence.get("field_results") else "SIMULATED"

    # ── Volunteer Pace ────────────────────────────────────────────────────────
    vol_target = _g(cfg, "volunteers", "volunteers_per_week", default=10)
    vol_actual  = rt.get("avg_volunteers_per_week")
    vol_pace_pct = (vol_actual / vol_target * 100) if (vol_actual and vol_target) else None
    vol_pace_source = "REAL" if presence.get("volunteer_log") else "ESTIMATED"

    # ── Budget Status ─────────────────────────────────────────────────────────
    total_budget = _g(cfg, "budget", "total_budget", default=0)
    actual_spend = rt.get("total_actual_spend", 0)
    budget_burn_pct = (actual_spend / total_budget * 100) if total_budget > 0 else None

    # Expected burn: linear based on campaign timeline
    expected_burn_pct = None
    if days_to_election is not None and total_budget > 0:
        # Rough total campaign length = 90 days from today + remaining
        # We assume campaign started 90 days before election
        total_campaign_days = 90
        days_elapsed = max(total_campaign_days - (days_to_election or 0), 0)
        expected_burn_pct = days_elapsed / total_campaign_days * 100
    budget_source = "REAL" if presence.get("budget_actuals") else "ESTIMATED"

    # ── Risks ─────────────────────────────────────────────────────────────────
    risk_df = _find_latest_csv(BASE_DIR / "derived" / "strategy", "*__risk_analysis.csv")
    top_risks = []
    if risk_df is not None and not risk_df.empty:
        high = risk_df[risk_df.get("level", risk_df.columns[0]) == "HIGH"] if "level" in risk_df.columns else risk_df.head(2)
        for _, row in high.head(3).iterrows():
            top_risks.append(str(row.get("risk", row.iloc[0])))

    # Additional real-time risks
    if win_prob is not None and win_prob < 0.50:
        top_risks.insert(0, f"Win probability below 50% ({win_prob:.0%}) — strategy adjustment needed")
    if field_pace_pct is not None and field_pace_pct < 70:
        top_risks.append(f"Field pace {field_pace_pct:.0f}% of target — volunteer/canvasser gap")
    if vol_pace_pct is not None and vol_pace_pct < 60:
        top_risks.append("Volunteer pace significantly below weekly goal")
    if not presence.get("field_results"):
        top_risks.append("No real canvass data — forecasts rely entirely on model priors")

    # ── Next 72h Priorities ───────────────────────────────────────────────────
    priorities = []
    critical_reqs = [r for r in data_requests if r["priority"] == "critical"]
    if critical_reqs:
        priorities.extend([r["recommended_ui_action"] for r in critical_reqs[:2]])
    if not presence.get("field_results"):
        priorities.append("Begin field canvassing and log first week's results in War Room")
    if not presence.get("volunteer_log"):
        priorities.append("Log volunteer shifts from last week")
    if weeks_to_election is not None and weeks_to_election <= 4:
        priorities.append("FINAL STRETCH: Shift to GOTV — VBM chase, election day ops")
    if not priorities:
        priorities.append("Continue field program per weekly plan")
        priorities.append("Update War Room with latest field results and volunteer logs")

    # ── Assemble Status Dict ──────────────────────────────────────────────────
    status = {
        "generated_at": datetime.datetime.now().isoformat(),
        "run_date": today.isoformat(),
        "contest_name": _g(cfg, "campaign", "contest_name", default="Campaign"),
        "election_date": election_date_str,
        "days_to_election": days_to_election,
        "weeks_to_election": round(weeks_to_election, 1) if weeks_to_election is not None else None,

        "win_probability": {
            "value": round(win_prob, 4) if win_prob is not None else None,
            "source_type": win_prob_source,
            "display": f"{win_prob:.1%}" if win_prob is not None else "Unknown",
        },
        "vote_path": {
            "win_number": win_number,
            "base_votes": base_votes,
            "persuasion_needed": pers_needed,
            "gotv_needed": gotv_needed,
            "coverage_rate": coverage,
            "source_type": "SIMULATED" if win_number > 0 else "MISSING",
        },
        "field_pace": {
            "target_doors_per_week": target_doors_per_week,
            "actual_doors_total":   actual_doors,
            "weekly_avg_doors":     weekly_doors,
            "pace_pct":             round(field_pace_pct, 1) if field_pace_pct else None,
            "source_type":          field_pace_source,
        },
        "volunteer_status": {
            "target_per_week": vol_target,
            "actual_avg":      round(vol_actual, 1) if vol_actual else None,
            "pace_pct":        round(vol_pace_pct, 1) if vol_pace_pct else None,
            "source_type":     vol_pace_source,
        },
        "budget_status": {
            "total_budget":        total_budget,
            "actual_spend":        actual_spend,
            "burn_pct":            round(budget_burn_pct, 1) if budget_burn_pct is not None else None,
            "expected_burn_pct":   round(expected_burn_pct, 1) if expected_burn_pct is not None else None,
            "source_type":         budget_source,
        },
        "top_risks": top_risks[:5],
        "next_72h_priorities": priorities[:5],
        "data_completeness": {
            "has_field_results":   presence.get("field_results", False),
            "has_volunteer_log":   presence.get("volunteer_log", False),
            "has_budget_actuals":  presence.get("budget_actuals", False),
            "has_contact_results": presence.get("contact_results", False),
            "data_requests_count": len(data_requests),
            "critical_requests":   sum(1 for r in data_requests if r["priority"] == "critical"),
        },
    }
    return status


def write_daily_status_json(status: dict, run_id: str) -> Path:
    WAR_ROOM_DIR.mkdir(parents=True, exist_ok=True)
    out = WAR_ROOM_DIR / f"{run_id}__daily_status.json"
    out.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
    log.info(f"[STATUS] Written: {out}")
    return out


def write_daily_status_md(status: dict, run_id: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")
    contest = status.get("contest_name", "Campaign")
    days    = status.get("days_to_election")
    wk      = status.get("weeks_to_election")
    wp      = status.get("win_probability", {})
    vp      = status.get("vote_path", {})
    fp      = status.get("field_pace", {})
    vs      = status.get("volunteer_status", {})
    bs      = status.get("budget_status", {})
    dc      = status.get("data_completeness", {})

    src_icon = {"REAL": "🟢", "SIMULATED": "🔵", "ESTIMATED": "🟡", "MISSING": "🔴"}

    lines = [
        f"# Daily Campaign Status — {contest}",
        f"*Generated: {now} | Run ID: `{run_id}`*",
        "",
        "---",
        "",
        "## Campaign Snapshot",
        "",
        f"| Metric | Value | Source |",
        f"|--------|-------|--------|",
        f"| Election Date | {status.get('election_date', '—')} | — |",
        f"| Days to Election | {days if days is not None else '—'} | — |",
        f"| Win Probability | {wp.get('display', '—')} | {src_icon.get(wp.get('source_type',''), '⬜')} {wp.get('source_type','—')} |",
        f"| Win Number | {vp.get('win_number', 0):,} votes | {src_icon.get(vp.get('source_type',''), '⬜')} {vp.get('source_type','—')} |",
        f"| Vote Path Coverage | {vp.get('coverage_rate', 0):.1%} | {src_icon.get(vp.get('source_type',''), '⬜')} {vp.get('source_type','—')} |",
        f"| Field Pace | {fp.get('pace_pct','—')}% of target | {src_icon.get(fp.get('source_type',''), '⬜')} {fp.get('source_type','—')} |",
        f"| Volunteers/Week | {vs.get('actual_avg','—')} / {vs.get('target_per_week','—')} | {src_icon.get(vs.get('source_type',''), '⬜')} {vs.get('source_type','—')} |",
        f"| Budget Burn | {bs.get('burn_pct','—')}% spent | {src_icon.get(bs.get('source_type',''), '⬜')} {bs.get('source_type','—')} |",
        "",
        "## Data Status",
        "",
        f"| Dataset | Status |",
        f"|---------|--------|",
        f"| Field Results | {'🟢 Loaded' if dc.get('has_field_results') else '🔴 Missing'} |",
        f"| Volunteer Log | {'🟢 Loaded' if dc.get('has_volunteer_log') else '🔴 Missing'} |",
        f"| Budget Actuals | {'🟢 Loaded' if dc.get('has_budget_actuals') else '🔴 Missing'} |",
        f"| Contact Results | {'🟢 Loaded' if dc.get('has_contact_results') else '🔴 Missing'} |",
        f"| Open Data Requests | {dc.get('data_requests_count', 0)} ({dc.get('critical_requests', 0)} critical) |",
        "",
        "## Top Risks",
        "",
    ]
    for risk in status.get("top_risks", [])[:5]:
        lines.append(f"- ⚠️ {risk}")

    lines += [
        "",
        "## Next 72-Hour Priorities",
        "",
    ]
    for p in status.get("next_72h_priorities", [])[:5]:
        lines.append(f"1. {p}")

    lines += [
        "",
        "---",
        f"*Campaign In A Box — Run ID: `{run_id}`*",
        "",
        "> **Provenance Legend:** 🟢 REAL | 🔵 SIMULATED | 🟡 ESTIMATED | 🔴 MISSING",
    ]

    out = REPORTS_DIR / f"{run_id}__daily_status.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[STATUS] Daily status MD: {out}")
    return out


def write_war_room_summary_md(status: dict, data_requests: list, run_id: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().strftime("%B %d, %Y")
    contest = status.get("contest_name", "Campaign")
    wp = status.get("win_probability", {})
    dc = status.get("data_completeness", {})

    real_count = sum(1 for v in status.get("data_completeness", {}).values()
                     if v is True)

    lines = [
        f"# Campaign War Room Summary — {contest}",
        f"*{now} | Run ID: `{run_id}`*",
        "",
        "---",
        "",
        "## 1. Current Campaign State",
        "",
        f"**Election in:** {status.get('days_to_election','—')} days "
        f"({status.get('weeks_to_election','—')} weeks)",
        f"**Win Probability:** {wp.get('display','—')} "
        f"*(source: {wp.get('source_type','—')})*",
        f"**Vote Path:** {status['vote_path'].get('coverage_rate',0):.1%} covered "
        f"— win number is {status['vote_path'].get('win_number',0):,} votes",
        "",
        "## 2. Real vs. Simulated Data Summary",
        "",
        "| Dataset | Status |",
        "|---------|--------|",
        f"| Field Results | {'🟢 REAL — actual canvass data loaded' if dc.get('has_field_results') else '🔴 MISSING — using configured prior (22% contact rate)'} |",
        f"| Volunteer Logs | {'🟢 REAL — actual shift data loaded' if dc.get('has_volunteer_log') else '🟡 ESTIMATED — using configured volunteer capacity'} |",
        f"| Budget Actuals | {'🟢 REAL — actual spend loaded' if dc.get('has_budget_actuals') else '🟡 ESTIMATED — using planned budget only'} |",
        f"| Contact/ID Results | {'🟢 REAL — ID results loaded' if dc.get('has_contact_results') else '🔵 SIMULATED — using PS model scores'} |",
        f"| Win Probability | 🔵 SIMULATED — Monte Carlo model |",
        f"| Turnout Model | {'🔵 SIMULATED — calibrated from history' if (BASE_DIR/'derived'/'calibration'/'model_parameters.json').exists() else '🟡 ESTIMATED — prior only'} |",
        "",
        "## 3. Updated Field Priorities",
        "",
        f"**Persuasion target:** {status['vote_path'].get('persuasion_needed',0):,} votes needed",
        f"**GOTV target:** {status['vote_path'].get('gotv_needed',0):,} votes needed",
        f"**Current field pace:** {status['field_pace'].get('pace_pct','—')}% of target",
        "",
        "## 4. Updated Budget Priorities",
        "",
        f"**Total Budget:** ${status['budget_status'].get('total_budget',0):,}",
        f"**Actual Spend:** ${status['budget_status'].get('actual_spend',0):,} "
        f"({status['budget_status'].get('burn_pct','—')}%)",
        "",
        "## 5. Risks and Gaps",
        "",
    ]
    for risk in status.get("top_risks", [])[:5]:
        lines.append(f"- ⚠️ {risk}")

    lines += [
        "",
        "## 6. Immediate Asks for Staff",
        "",
    ]
    high_reqs = [r for r in data_requests if r["priority"] in ("critical", "high")][:4]
    for req in high_reqs:
        lines.append(f"- {req['icon']} **{req['title']}** — {req['recommended_ui_action']}")

    lines += [
        "",
        "## 7. Recommended Next Actions",
        "",
    ]
    for i, p in enumerate(status.get("next_72h_priorities", [])[:5], 1):
        lines.append(f"{i}. {p}")

    lines += [
        "",
        "---",
        "*All figures with 🔵 SIMULATED or 🟡 ESTIMATED labels are model-derived "
        "and should be treated as directional, not precise. Enter real campaign data "
        "in the War Room to improve accuracy.*",
    ]

    out = REPORTS_DIR / f"{run_id}__campaign_war_room_summary.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[STATUS] War Room summary: {out}")
    return out
