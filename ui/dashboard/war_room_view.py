"""
ui/dashboard/war_room_view.py — Prompt 14

Campaign War Room dashboard page. Live ops command center for ongoing campaigns.

5 main panels:
  A) Campaign Snapshot       — all KPIs with provenance badges
  B) Data Gaps / Requests    — missing data callouts w/ upload workflows
  C) Field Operations        — target vs actual doors/contacts
  D) Resource Status         — planned vs actual budget by category
  E) Risk Monitor            — color-coded risk cards

Input forms (embedded in panel B):
  - Field Results upload/form
  - Volunteer Tracking log form
  - Budget Actuals form
  - Contact/ID Results form
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Optional

import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _g(d: dict, *keys, default=None) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def _load_json(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _find_latest_json(directory: Path, pattern: str) -> Optional[dict]:
    try:
        matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return json.loads(matches[0].read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _find_latest_csv(directory: Path, pattern: str) -> Optional[pd.DataFrame]:
    try:
        matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return pd.read_csv(matches[0])
    except Exception:
        pass
    return None


def _load_campaign_config() -> dict:
    try:
        import yaml
        cfg_path = BASE_DIR / "config" / "campaign_config.yaml"
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


# ── Badge helper (inline to avoid import issues) ──────────────────────────────
BADGE_CSS = {
    "REAL":      ("🟢", "#D1FAE5", "#065F46", "#6EE7B7"),
    "SIMULATED": ("🔵", "#DBEAFE", "#1E40AF", "#93C5FD"),
    "ESTIMATED": ("🟡", "#FEF3C7", "#92400E", "#FCD34D"),
    "MISSING":   ("🔴", "#FEE2E2", "#991B1B", "#FCA5A5"),
}


def _badge(stype: str) -> str:
    icon, bg, color, border = BADGE_CSS.get(stype.upper(), BADGE_CSS["MISSING"])
    return (f'<span style="background:{bg};color:{color};border:1px solid {border};'
            f'border-radius:4px;padding:1px 6px;font-size:0.72rem;font-weight:700;'
            f'margin-left:4px">{icon} {stype}</span>')


def _src_icon(stype: str) -> str:
    return BADGE_CSS.get(stype.upper(), BADGE_CSS["MISSING"])[0]


# ── Main render ───────────────────────────────────────────────────────────────

# ── Main render ───────────────────────────────────────────────────────────────

def render_war_room(data: dict) -> None:
    """Render the Campaign War Room page."""
    from ui.components.alerts import render_alert
    from ui.components.metric_card import render_metric_card
    from ui.components.empty_state import render_empty_state
    from ui.theme import apply_chart_theme

    st.markdown("<h1 class='page-title'>War Room Live Operations</h1>", unsafe_allow_html=True)
    st.caption("Central command for daily tracking, field adjustments, and risk mitigation.")

    # Load all War Room data
    cfg = _load_campaign_config()
    daily_status = _find_latest_json(BASE_DIR / "derived" / "war_room", "*__daily_status.json")
    data_requests_payload = _find_latest_json(BASE_DIR / "derived" / "war_room", "*__data_requests.json")
    provenance_data = _find_latest_json(BASE_DIR / "derived" / "provenance", "*__metric_provenance.json")
    forecast_df = _find_latest_csv(BASE_DIR / "derived" / "war_room", "*__forecast_update_comparison.csv")
    risk_df = _find_latest_csv(BASE_DIR / "derived" / "strategy", "*__risk_analysis.csv")
    budget_df = _find_latest_csv(BASE_DIR / "derived" / "strategy", "*__budget_allocation.csv")

    # Load Performance (Prompt 18)
    perf_health = _find_latest_json(BASE_DIR / "derived" / "performance", "*__campaign_health.json")
    perf_drift = _find_latest_csv(BASE_DIR / "derived" / "performance", "*__forecast_drift.csv")
    perf_scenarios = _find_latest_csv(BASE_DIR / "derived" / "performance", "*__recovery_scenarios.csv")
    perf_actions = _find_latest_json(BASE_DIR / "derived" / "performance", "*__leverage_actions.json")

    try:
        from engine.war_room.runtime_loader import get_runtime_summary
        runtime = get_runtime_summary(cfg)
    except Exception as e:
        runtime = {"presence": {}, "metrics": {}, "has_any": False}

    # ── Alerts ───────────────────────────────────────────────────────────────
    if data_requests_payload:
        critical_count = data_requests_payload.get("critical_count", 0)
        high_count = data_requests_payload.get("high_count", 0)
        if critical_count > 0:
            render_alert("critical", f"{critical_count} critical data gap(s) detected — see Data Requests.")
        elif high_count > 0:
            render_alert("warning", f"{high_count} high-priority data gap(s) — see Data Requests.")
        else:
            render_alert("success", "No critical data gaps. War Room is fully operational.")
    else:
        render_alert("warning", "No War Room data found. Run pipeline after Campaign Setup.")

    # ── Quick KPI Row ───────────────────────────────────────────────────────
    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    if daily_status:
        fp = daily_status.get("field_pace", {})
        vs = daily_status.get("volunteer_status", {})
        bs = daily_status.get("budget_status", {})
        
        with c1:
            pace = fp.get('pace_pct')
            render_metric_card("Field Pace", f"{pace:.0f}%" if pace else "—", "Of weekly target", 
                               fp.get('source_type', 'MISSING'), 
                               "success" if pace and pace > 90 else "warning")
        with c2:
            vol = vs.get('pace_pct')
            render_metric_card("Volunteer Pace", f"{vol:.0f}%" if vol else "—", "Shifts completed", 
                               vs.get('source_type', 'MISSING'), 
                               "success" if vol and vol > 90 else "danger")
        with c3:
            burn = bs.get('burn_pct')
            render_metric_card("Budget Burn", f"{burn:.0f}%" if burn else "—", "Total spend utilized", 
                               bs.get('source_type', 'MISSING'), "info")
        with c4:
            days = daily_status.get("days_to_election", "—")
            render_metric_card("Election Day", f"{days} days", "Keep pushing", None, "info")

    st.markdown("---")

    # ── 5 Core Tabs ────────────────────────────────────────────────────────
    tab_status, tab_perf, tab_gaps, tab_team, tab_risks = st.tabs([
        "Today / This Week", "Forecast Drift & Recovery", "Data Requests", "Team & Operations", "Risk Monitor"
    ])

    with tab_status:
        st.subheader("Current Week Operations")
        pc1, pc2 = st.columns(2)
        with pc1:
            if runtime.get("has_any"):
                field = runtime.get("field_results")
                if field is not None and not field.empty:
                    st.markdown("**Daily Field Results**")
                    try:
                        import plotly.express as px
                        if "date" in field.columns and "doors_knocked" in field.columns:
                            fig = px.bar(field, x="date", y="doors_knocked", title="Doors Knocked (Past 7 Days)", color_discrete_sequence=["#1F4E79"])
                            fig = apply_chart_theme(fig)
                            fig.update_layout(height=300)
                            st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.dataframe(field, use_container_width=True, hide_index=True)
                else:
                    render_empty_state("No Field Data", "Upload field results to track knocking pace.", "🚪", "Use the Data Requests tab")
            else:
                render_empty_state("No Operations Data", "Start by logging field or volunteer actuals.", "🚪", "Move to Data Requests tab to upload.")
                
        with pc2:
            st.markdown("**Campaign Health Status**")
            if perf_health:
                chi = perf_health.get("chi_score", 0.0)
                status = perf_health.get("status", "UNKNOWN")
                chi_color = "success" if status == "STRONG" else ("danger" if status == "CRITICAL" else "warning")
                render_alert(chi_color, f"Campaign Health Index: {status} ({chi:.2f})")
                render_alert("info", f"Doors Pace: {perf_health.get('doors_health')} | Calls Pace: {perf_health.get('calls_health')}")
            else:
                render_empty_state("No Performance Health", "Run the pipeline with real data to compute CHI.")

    with tab_perf:
        st.subheader("Forecast Drift & Recovery Scenarios")
        st.caption("Reconciles planned strategy vs. actual operations to predict systemic drift.")
        d1, d2 = st.columns(2)
        with d1:
            if perf_drift is not None and not perf_drift.empty:
                try:
                    import plotly.express as px
                    fig = px.bar(perf_drift, x="metric", y="pct_deviation", color="type", title="Operational Drift Variance", text_auto=".1%")
                    fig = apply_chart_theme(fig)
                    st.plotly_chart(fig, use_container_width=True)
                except Exception:
                    st.dataframe(perf_drift, use_container_width=True)
            else:
                render_empty_state("No Drift Found", "Forecast drift requires ongoing operational data.", "📈", "Log field data first.")
        with d2:
            if perf_actions:
                st.markdown("**Recommended Leverage Actions**")
                for a in perf_actions.get("actions", [])[:3]:
                    render_alert("warning", f"{a.get('program')}: {a.get('recommendation')}")
            else:
                st.info("No immediate recovery actions recommended.")
                
            if perf_scenarios is not None and not perf_scenarios.empty:
                st.markdown("**Simulated Recovery Programs**")
                st.dataframe(perf_scenarios, use_container_width=True, hide_index=True)

    with tab_gaps:
        st.subheader("Critical Data Requests")
        st.caption("The engine needs this to improve strategy accuracy.")
        if data_requests_payload and data_requests_payload.get("requests", []):
            for req in data_requests_payload.get("requests", []):
                priority = req.get("priority", "low")
                a_type = "critical" if priority == "critical" else ("warning" if priority == "high" else "info")
                render_alert(a_type, f"**{req.get('title')}** - {req.get('why_needed')}")
        else:
            render_empty_state("All Cleared", "No critical data gaps. War Room is operational.", "✅")

    with tab_team:
        try:
            from ui.dashboard.team_view import render_team_view
            from engine.auth.auth_manager import AuthManager
            if "auth_manager" in st.session_state and "current_user_id" in st.session_state:
                am = st.session_state["auth_manager"]
                user = am.get_user(st.session_state["current_user_id"])
                render_team_view(data, am, user)
        except Exception as e:
            render_alert("critical", f"Team activity unavailable: {e}")

    with tab_risks:
        st.subheader("Risk Monitor")
        if risk_df is not None and not risk_df.empty:
            if "level" in risk_df.columns:
                for lvl in ["HIGH", "MEDIUM"]:
                    subset = risk_df[risk_df["level"] == lvl]
                    a_color = "critical" if lvl == "HIGH" else "warning"
                    for _, row in subset.iterrows():
                        render_alert(a_color, f"**{row.get('risk')}** - Mitigate: {row.get('mitigation')}")
        else:
            render_empty_state("No Detected Risks", "Systems within normal parameters.", "🛡️")
