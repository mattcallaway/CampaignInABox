"""
engine/war_room/data_requests.py — Prompt 14

Data Request Engine: inspects current campaign state and generates a structured
list of missing inputs that would improve strategy quality.

Output: derived/war_room/<run_id>__data_requests.json

Each request has:
  request_type, priority, why_needed, what_it_improves, recommended_ui_action
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
WAR_ROOM_DIR = BASE_DIR / "derived" / "war_room"

log = logging.getLogger(__name__)

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def generate_data_requests(
    runtime_summary: dict,
    provenance_records: Optional[list] = None,
    campaign_config: Optional[dict] = None,
) -> list[dict]:
    """
    Inspect runtime data presence and provenance to generate prioritized data requests.

    Returns list of request dicts sorted by priority.
    """
    cfg      = campaign_config or {}
    presence = runtime_summary.get("presence", {})
    metrics  = runtime_summary.get("metrics", {})
    requests = []

    # ── 1. Campaign Config ────────────────────────────────────────────────────
    if not cfg:
        requests.append({
            "request_type": "campaign_config",
            "priority": "critical",
            "icon": "⚠️",
            "title": "Campaign not configured",
            "why_needed": "No campaign_config.yaml found. The strategy engine has no contest name, election date, or budget to work with.",
            "what_it_improves": "Enables vote path calculation, field strategy, budget allocation, and all War Room outputs.",
            "recommended_ui_action": "Go to 🗳️ Campaign Setup and complete the campaign form.",
        })
    else:
        election_date = cfg.get("campaign", {}).get("election_date")
        if not election_date:
            requests.append({
                "request_type": "election_date",
                "priority": "critical",
                "icon": "📅",
                "title": "Election date missing",
                "why_needed": "No election date configured. Field strategy, timeline, and GOTV ramp cannot be computed.",
                "what_it_improves": "Timeline, field plan, GOTV pacing.",
                "recommended_ui_action": "Update Election Date in 🗳️ Campaign Setup.",
            })

        total_budget = cfg.get("budget", {}).get("total_budget", 0)
        if total_budget == 0:
            requests.append({
                "request_type": "budget_config",
                "priority": "high",
                "icon": "💰",
                "title": "No budget configured",
                "why_needed": "Total budget is $0 in campaign config. Budget allocation model cannot run.",
                "what_it_improves": "Budget allocation, resource optimization, ROI estimates.",
                "recommended_ui_action": "Enter total budget in 🗳️ Campaign Setup → Budget section.",
            })

    # ── 2. Field Results ──────────────────────────────────────────────────────
    if not presence.get("field_results"):
        requests.append({
            "request_type": "field_results",
            "priority": "high",
            "icon": "🚪",
            "title": "No real canvass results uploaded",
            "why_needed": "Current contact rate (22%) and turnout lift (6%) are configured estimates. No actual canvass data.",
            "what_it_improves": "Turnout calibration, daily forecast accuracy, persuasion targeting",
            "recommended_ui_action": "Enter Field Data in the War Room → Field tab.",
        })
    else:
        # Field results exist — check if they're recent (within 7 days)
        field_df = runtime_summary.get("field_results")
        if field_df is not None and "date" in field_df.columns:
            try:
                import pandas as pd
                latest = pd.to_datetime(field_df["date"], errors="coerce").max()
                if pd.notna(latest):
                    import datetime
                    days_old = (datetime.date.today() - latest.date()).days
                    if days_old > 7:
                        requests.append({
                            "request_type": "field_results_stale",
                            "priority": "medium",
                            "icon": "📊",
                            "title": f"Field results are {days_old} days old",
                            "why_needed": "Field data hasn't been updated in over a week. Daily forecast may not reflect current pace.",
                            "what_it_improves": "Daily field pace accuracy, win probability estimate.",
                            "recommended_ui_action": "Upload latest field results in War Room → Field tab.",
                        })
            except Exception:
                pass

    # ── 3. Volunteer Data ─────────────────────────────────────────────────────
    if not presence.get("volunteer_log"):
        requests.append({
            "request_type": "volunteer_log",
            "priority": "high",
            "icon": "🙋",
            "title": "No volunteer shift logs entered",
            "why_needed": f"Volunteer capacity is estimated at {cfg.get('volunteers',{}).get('volunteers_per_week',10)}/week from config. No actual shift data.",
            "what_it_improves": "Field capacity forecast, GOTV achievability, weekly progress tracking.",
            "recommended_ui_action": "Log volunteer shifts in War Room → Volunteers tab.",
        })

    # ── 4. Budget Actuals ─────────────────────────────────────────────────────
    if not presence.get("budget_actuals"):
        requests.append({
            "request_type": "budget_actuals",
            "priority": "medium",
            "icon": "💳",
            "title": "No budget actuals entered",
            "why_needed": "Current budget display shows planned allocations only. No actual spend has been entered.",
            "what_it_improves": "Cash burn analysis, budget reallocation recommendations, burn-rate vs. timeline alerts.",
            "recommended_ui_action": "Enter budget actuals in War Room → Budget tab.",
        })
    else:
        actual_spend = metrics.get("total_actual_spend", 0)
        total_budget = cfg.get("budget", {}).get("total_budget", 0)
        if total_budget > 0:
            burn_pct = actual_spend / total_budget
            if burn_pct > 0.75:
                requests.append({
                    "request_type": "budget_overspend_risk",
                    "priority": "critical" if burn_pct > 0.90 else "high",
                    "icon": "🔥",
                    "title": f"Budget {burn_pct:.0%} spent — check cash runway",
                    "why_needed": f"${actual_spend:,.0f} of ${total_budget:,} total budget spent ({burn_pct:.0%}).",
                    "what_it_improves": "Prevents unexpected budget shortage near election day.",
                    "recommended_ui_action": "Review budget actuals and fundraising status.",
                })

    # ── 5. Contact / ID Results ───────────────────────────────────────────────
    if not presence.get("contact_results"):
        requests.append({
            "request_type": "contact_results",
            "priority": "medium",
            "icon": "📋",
            "title": "No contact ID results uploaded",
            "why_needed": "Persuasion rate is modeled from party strength / age (estimated). No field ID data.",
            "what_it_improves": "Persuasion model accuracy, supporter ID tracking, opposition count.",
            "recommended_ui_action": "Upload contact results in War Room → Contacts tab.",
        })

    # ── 6. Voter File ─────────────────────────────────────────────────────────
    from pathlib import Path as _Path
    voter_parquet = None
    vm_dir = BASE_DIR / "derived" / "voter_models"
    if vm_dir.exists():
        pqs = sorted(vm_dir.glob("*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True)
        if pqs:
            voter_parquet = pqs[0]

    if voter_parquet is None:
        requests.append({
            "request_type": "voter_file",
            "priority": "medium",
            "icon": "🗂️",
            "title": "No voter file loaded",
            "why_needed": "Persuadable universe, TPS, and PS scores all rely on a voter file. Currently using heuristic estimates.",
            "what_it_improves": "Persuasion targeting accuracy, GOTV targeting, universe sizing.",
            "recommended_ui_action": "Generate or upload a voter file and re-run the pipeline.",
        })

    # ── Sort by priority ──────────────────────────────────────────────────────
    requests.sort(key=lambda r: PRIORITY_ORDER.get(r["priority"], 99))
    return requests


def write_data_requests(requests: list[dict], run_id: str) -> Path:
    """Write data requests JSON to derived/war_room/."""
    WAR_ROOM_DIR.mkdir(parents=True, exist_ok=True)
    out = WAR_ROOM_DIR / f"{run_id}__data_requests.json"
    payload = {
        "run_id": run_id,
        "total_requests": len(requests),
        "critical_count": sum(1 for r in requests if r["priority"] == "critical"),
        "high_count":     sum(1 for r in requests if r["priority"] == "high"),
        "medium_count":   sum(1 for r in requests if r["priority"] == "medium"),
        "low_count":      sum(1 for r in requests if r["priority"] == "low"),
        "requests": requests,
    }
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    log.info(f"[DATA_REQUESTS] Written {len(requests)} requests to {out}")
    return out


def load_data_requests(run_id: Optional[str] = None) -> Optional[dict]:
    """Load the latest (or specific) data_requests JSON."""
    try:
        if run_id:
            p = WAR_ROOM_DIR / f"{run_id}__data_requests.json"
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        matches = sorted(WAR_ROOM_DIR.glob("*__data_requests.json"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return json.loads(matches[0].read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"[DATA_REQUESTS] Could not load: {e}")
    return None
