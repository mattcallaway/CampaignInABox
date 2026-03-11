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

def render_war_room(data: dict) -> None:
    """Render the Campaign War Room page."""

    from ui.dashboard.provenance_badge import legend, provenance_summary_card

    st.markdown("""
    <div style='background:linear-gradient(135deg,#1C1917 0%,#292524 100%);
         border-radius:14px;padding:24px 32px;margin-bottom:24px;border:1px solid #78350F'>
      <h1 style='margin:0;color:#FEF3C7;font-size:2rem'>&#127914; Campaign War Room</h1>
      <p style='margin:6px 0 0 0;color:#D97706;font-size:1rem'>
        Live Ops Command Center &nbsp;&middot;&nbsp; Real-Time Decision Support
      </p>
    </div>""", unsafe_allow_html=True)

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

    # Load runtime data for form display
    try:
        from engine.war_room.runtime_loader import get_runtime_summary
        runtime = get_runtime_summary(cfg)
    except Exception as e:
        runtime = {"presence": {}, "metrics": {}, "has_any": False}

    # ── Provenance Legend ─────────────────────────────────────────────────────
    legend()

    # ── Data Status Warning ───────────────────────────────────────────────────
    if data_requests_payload:
        critical_count = data_requests_payload.get("critical_count", 0)
        high_count     = data_requests_payload.get("high_count", 0)
        if critical_count > 0:
            st.error(f"🚨 {critical_count} critical data gap(s) detected — see Data Gaps tab.")
        elif high_count > 0:
            st.warning(f"⚠️ {high_count} high-priority data gap(s). View Data Gaps tab for details.")
        else:
            st.success("✅ No critical data gaps. War Room is operational.")
    else:
        st.warning("No War Room data found. Run the pipeline after Campaign Setup to generate the War Room.")

    st.divider()

    # ── 6 Main Tabs ────────────────────────────────────────────────────────────
    tab_snap, tab_perf, tab_gaps, tab_field, tab_resource, tab_risks = st.tabs([
        "📊 Campaign Snapshot",
        "🏆 Performance & Drift",
        "🔔 Data Gaps",
        "🚪 Field Ops",
        "💰 Resources",
        "⚠️ Risks",
    ])

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab A: Campaign Snapshot
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_snap:
        st.subheader("Campaign Snapshot")

        if not daily_status:
            st.info("Run the pipeline to generate the War Room status snapshot.")
        else:
            contest = daily_status.get("contest_name", "Campaign")
            st.markdown(f"**{contest}**")

            col1, col2 = st.columns([2, 1])
            with col1:
                # KPI grid with provenance
                wp = daily_status.get("win_probability", {})
                vp = daily_status.get("vote_path", {})
                fp = daily_status.get("field_pace", {})
                vs = daily_status.get("volunteer_status", {})
                bs = daily_status.get("budget_status", {})

                k1, k2, k3 = st.columns(3)
                with k1:
                    st.markdown(
                        f"**🗳️ Win Probability**<br>"
                        f"<span style='font-size:1.8rem;font-weight:700'>{wp.get('display','—')}</span>"
                        f"{_badge(wp.get('source_type','MISSING'))}",
                        unsafe_allow_html=True,
                    )
                with k2:
                    coverage = vp.get("coverage_rate", 0)
                    color = "#065F46" if coverage >= 1.0 else "#92400E" if coverage >= 0.8 else "#991B1B"
                    st.markdown(
                        f"**📊 Vote Path Coverage**<br>"
                        f"<span style='font-size:1.8rem;font-weight:700;color:{color}'>{coverage:.1%}</span>"
                        f"{_badge(vp.get('source_type','MISSING'))}",
                        unsafe_allow_html=True,
                    )
                with k3:
                    days = daily_status.get("days_to_election")
                    weeks = daily_status.get("weeks_to_election")
                    color = "#991B1B" if (days or 0) < 30 else "#D97706" if (days or 0) < 60 else "#065F46"
                    st.markdown(
                        f"**📅 Days to Election**<br>"
                        f"<span style='font-size:1.8rem;font-weight:700;color:{color}'>"
                        f"{'—' if days is None else days}</span>"
                        f"<span style='color:#6B7280;font-size:0.85rem'> ({weeks}w)</span>",
                        unsafe_allow_html=True,
                    )
                st.divider()

                k4, k5, k6 = st.columns(3)
                with k4:
                    pace = fp.get("pace_pct")
                    pace_color = "#065F46" if (pace or 0) >= 90 else "#D97706" if (pace or 0) >= 60 else "#DC2626"
                    st.markdown(
                        f"**🚪 Field Pace**<br>"
                        f"<span style='font-size:1.5rem;font-weight:700;color:{pace_color}'>"
                        f"{'—' if pace is None else f'{pace:.0f}%'} of target</span>"
                        f"{_badge(fp.get('source_type','MISSING'))}",
                        unsafe_allow_html=True,
                    )
                with k5:
                    vol_pace = vs.get("pace_pct")
                    vol_color = "#065F46" if (vol_pace or 0) >= 90 else "#D97706" if (vol_pace or 0) >= 60 else "#DC2626"
                    st.markdown(
                        f"**🙋 Volunteer Pace**<br>"
                        f"<span style='font-size:1.5rem;font-weight:700;color:{vol_color}'>"
                        f"{'—' if vol_pace is None else f'{vol_pace:.0f}%'} of target</span>"
                        f"{_badge(vs.get('source_type','MISSING'))}",
                        unsafe_allow_html=True,
                    )
                with k6:
                    burn = bs.get("burn_pct")
                    expected = bs.get("expected_burn_pct")
                    burn_color = "#DC2626" if burn and expected and burn > expected * 1.2 else "#065F46"
                    st.markdown(
                        f"**💰 Budget Burn**<br>"
                        f"<span style='font-size:1.5rem;font-weight:700;color:{burn_color}'>"
                        f"{'—' if burn is None else f'{burn:.0f}%'} spent</span>"
                        f"{_badge(bs.get('source_type','MISSING'))}",
                        unsafe_allow_html=True,
                    )

                st.divider()
                # Vote path detail
                st.markdown("#### Vote Path Detail")
                st.markdown(
                    f"| Component | Votes | Source |"
                    f"\n|-----------|-------|--------|"
                    f"\n| Win Number | **{vp.get('win_number',0):,}** | — |"
                    f"\n| Base Committed | {vp.get('base_votes',0):,} | {_src_icon(vp.get('source_type','ESTIMATED'))} {vp.get('source_type','ESTIMATED')} |"
                    f"\n| Persuasion Needed | {vp.get('persuasion_needed',0):,} | {_src_icon(vp.get('source_type','ESTIMATED'))} {vp.get('source_type','ESTIMATED')} |"
                    f"\n| GOTV Needed | {vp.get('gotv_needed',0):,} | {_src_icon(vp.get('source_type','ESTIMATED'))} {vp.get('source_type','ESTIMATED')} |",
                    unsafe_allow_html=True,
                )

            with col2:
                st.markdown("#### Provenance Summary")
                if provenance_data:
                    provenance_summary_card(provenance_data)
                else:
                    st.caption("No provenance data yet.")

                st.divider()
                st.markdown("#### Next 72h Priorities")
                for p in daily_status.get("next_72h_priorities", [])[:4]:
                    st.markdown(f"▸ {p}")

        # Forecast comparison
        if forecast_df is not None and not forecast_df.empty:
            with st.expander("📈 Baseline vs. Runtime Forecast Comparison"):
                st.caption("Shows how real runtime data has shifted model assumptions.")
                st.dataframe(forecast_df, use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab B: Performance & Drift (Prompt 18)
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_perf:
        st.subheader("Performance Reconciliation & Forecast Drift")
        st.caption("Reconciles planned strategy vs. actual operations to predict systemic drift.")

        if not perf_health:
            st.info("No Performance Data found. Run the full pipeline (with Field Data) to generate insights.")
        else:
            chi = perf_health.get("chi_score", 0.0)
            status = perf_health.get("status", "UNKNOWN")
            
            # Health Score Header
            chi_color = "#065F46" if status == "STRONG" else "#DC2626" if status == "CRITICAL" else "#D97706"
            
            st.markdown(f"""
            <div style='background:{chi_color}11; border: 1px solid {chi_color}44; border-radius: 8px; padding: 16px; margin-bottom: 24px'>
                <h3 style='margin:0; color:{chi_color}'>Campaign Health Index: {status} ({chi:.2f})</h3>
                <p style='margin:4px 0 0 0; color:#4B5563'>Pacing: Doors ({perf_health.get('doors_health')}) | Calls ({perf_health.get('calls_health')})</p>
            </div>
            """, unsafe_allow_html=True)
            
            pc1, pc2 = st.columns(2)
            with pc1:
                st.markdown("#### Forecast Drift")
                if perf_drift is not None and not perf_drift.empty:
                    try:
                        import plotly.express as px
                        # Bar chart for pct dev
                        fig = px.bar(
                            perf_drift, x="metric", y="pct_deviation", color="type",
                            title="Operational Drift (% Variance from Plan)",
                            text_auto=".1%", template="plotly_white"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception:
                        st.dataframe(perf_drift, use_container_width=True)
                else:
                    st.caption("No drift calculations available.")

            with pc2:
                st.markdown("#### Leverage Actions & Recovery Scenarios")
                if perf_actions:
                    actions = perf_actions.get("actions", [])
                    for a in actions:
                        st.markdown(f"**{a.get('program')}:** {a.get('issue')} ➔ <br>_Recommendation_: {a.get('recommendation')}", unsafe_allow_html=True)
                
                if perf_scenarios is not None and not perf_scenarios.empty:
                    st.divider()
                    st.markdown("**Simulated Recovery Programs**")
                    st.dataframe(perf_scenarios, use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab C: Data Gaps / Requests
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_gaps:
        st.subheader("Data Gaps & Requests")
        st.caption("The engine needs this data to improve strategy accuracy. Higher priority = bigger impact.")

        requests = []
        if data_requests_payload:
            requests = data_requests_payload.get("requests", [])

        if not requests:
            st.success("✅ No data gaps detected! All major inputs are present.")
        else:
            priority_colors = {
                "critical": ("#FEF2F2", "#DC2626"),
                "high":     ("#FFF7ED", "#D97706"),
                "medium":   ("#FEFCE8", "#CA8A04"),
                "low":      ("#F0FDF4", "#16A34A"),
            }
            for req in requests:
                priority = req.get("priority", "low")
                bg, border_color = priority_colors.get(priority, ("#F8FAFC", "#E2E8F0"))
                st.markdown(f"""
                <div style='background:{bg};border-left:4px solid {border_color};
                     border-radius:8px;padding:14px;margin-bottom:10px'>
                  <b>{req.get('icon','📋')} {req.get('title','')}</b>
                  <span style='background:{border_color};color:white;border-radius:3px;
                       padding:1px 6px;font-size:0.7rem;font-weight:700;margin-left:8px'>
                    {priority.upper()}
                  </span>
                  <p style='margin:6px 0 2px 0;color:#374151'>{req.get('why_needed','')}</p>
                  <p style='margin:0;font-size:0.85rem'>
                    <b>Improves:</b> {req.get('what_it_improves','')} &nbsp;|&nbsp;
                    <b>Action:</b> {req.get('recommended_ui_action','')}
                  </p>
                </div>""", unsafe_allow_html=True)

        # ── Runtime Data Entry Forms ──────────────────────────────────────────
        st.divider()
        st.subheader("Enter Campaign Runtime Data")
        st.caption("Data entered here stays local — it is never committed to GitHub.")

        runtime_dir = BASE_DIR / "data" / "campaign_runtime" / "CA" / "Sonoma" / "prop_50_special"

        # Field Results
        with st.expander("🚪 Log Field Results", expanded=not runtime.get("presence", {}).get("field_results")):
            st.caption("Log actual canvassing results by day and turf.")
            with st.form("field_results_form", clear_on_submit=True):
                fc1, fc2 = st.columns(2)
                fr_date   = fc1.date_input("Date", value=datetime.date.today(), key="fr_date")
                fr_turf   = fc2.text_input("Turf / Region ID", placeholder="e.g. Precinct 001", key="fr_turf")
                fc3, fc4, fc5 = st.columns(3)
                fr_doors  = fc3.number_input("Doors Knocked", min_value=0, step=5, key="fr_doors")
                fr_canvassers = fc4.number_input("Canvassers", min_value=0, step=1, key="fr_canvassers")
                fr_contacts = fc5.number_input("Contacts Made", min_value=0, step=1, key="fr_contacts")
                fc6, fc7 = st.columns(2)
                fr_pers   = fc6.number_input("Persuasion Contacts", min_value=0, step=1, key="fr_pers")
                fr_gotv   = fc7.number_input("GOTV Contacts", min_value=0, step=1, key="fr_gotv")
                submitted = st.form_submit_button("💾 Save Field Results", type="primary")
                if submitted:
                    try:
                        from engine.war_room.runtime_loader import save_runtime_data
                        row = pd.DataFrame([{
                            "date": str(fr_date), "turf_id": fr_turf,
                            "doors_knocked": fr_doors, "canvasser_count": fr_canvassers,
                            "contacts_made": fr_contacts, "persuasion_contacts": fr_pers,
                            "gotv_contacts": fr_gotv,
                        }])
                        save_runtime_data(row, "field_results", cfg, append=True)
                        st.success(f"Field results saved for {fr_date}! Re-run the pipeline to update forecasts.")
                    except Exception as e:
                        st.error(f"Could not save: {e}")

            # CSV upload option
            up_file = st.file_uploader("Or upload a CSV file", type=["csv"], key="fr_upload")
            if up_file:
                try:
                    from engine.war_room.runtime_loader import save_runtime_data
                    up_df = pd.read_csv(up_file)
                    save_runtime_data(up_df, "field_results", cfg, append=True)
                    st.success(f"Uploaded {len(up_df)} field result rows.")
                except Exception as e:
                    st.error(f"Upload failed: {e}")

        # Volunteer Log
        with st.expander("🙋 Log Volunteer Shifts", expanded=not runtime.get("presence", {}).get("volunteer_log")):
            with st.form("volunteer_form", clear_on_submit=True):
                vc1, vc2 = st.columns(2)
                vl_date     = vc1.date_input("Date", value=datetime.date.today(), key="vl_date")
                vl_vols     = vc2.number_input("Volunteer Count", min_value=0, step=1, key="vl_vols")
                vc3, vc4 = st.columns(2)
                vl_shifts   = vc3.number_input("Shifts Completed", min_value=0, step=1, key="vl_shifts")
                vl_hours    = vc4.number_input("Total Hours Worked", min_value=0.0, step=0.5, key="vl_hours")
                vl_submit = st.form_submit_button("💾 Save Volunteer Log", type="primary")
                if vl_submit:
                    try:
                        from engine.war_room.runtime_loader import save_runtime_data
                        row = pd.DataFrame([{
                            "date": str(vl_date), "volunteer_count": vl_vols,
                            "shifts_completed": vl_shifts, "hours_worked": vl_hours,
                        }])
                        save_runtime_data(row, "volunteer_log", cfg, append=True)
                        st.success("Volunteer log saved!")
                    except Exception as e:
                        st.error(f"Could not save: {e}")

        # Budget Actuals
        with st.expander("💳 Log Budget Actuals", expanded=not runtime.get("presence", {}).get("budget_actuals")):
            with st.form("budget_actuals_form", clear_on_submit=True):
                ba_date     = st.date_input("Date", value=datetime.date.today(), key="ba_date")
                ba_category = st.selectbox("Category", ["Field", "Mail", "Digital", "Research", "Other"], key="ba_category")
                bac1, bac2 = st.columns(2)
                ba_planned  = bac1.number_input("Planned Spend ($)", min_value=0, step=100, key="ba_planned")
                ba_actual   = bac2.number_input("Actual Spend ($)", min_value=0, step=100, key="ba_actual")
                ba_notes    = st.text_input("Notes", placeholder="e.g. Mail drop #1", key="ba_notes")
                ba_submit = st.form_submit_button("💾 Save Budget Actuals", type="primary")
                if ba_submit:
                    try:
                        from engine.war_room.runtime_loader import save_runtime_data
                        row = pd.DataFrame([{
                            "date": str(ba_date), "category": ba_category,
                            "planned_spend": ba_planned, "actual_spend": ba_actual, "notes": ba_notes,
                        }])
                        save_runtime_data(row, "budget_actuals", cfg, append=True)
                        st.success("Budget actuals saved!")
                    except Exception as e:
                        st.error(f"Could not save: {e}")

        # Contact / ID Results
        with st.expander("📋 Log Contact / ID Results", expanded=not runtime.get("presence", {}).get("contact_results")):
            with st.form("contact_results_form", clear_on_submit=True):
                cr1, cr2 = st.columns(2)
                cr_date   = cr1.date_input("Date", value=datetime.date.today(), key="cr_date")
                cr_region = cr2.text_input("Region / Turf", placeholder="e.g. Santa Rosa SW", key="cr_region")
                cr3, cr4, cr5 = st.columns(3)
                cr_contacts = cr3.number_input("Total Contacts", min_value=0, step=1, key="cr_contacts")
                cr_support  = cr4.number_input("Supporters ID'd", min_value=0, step=1, key="cr_support")
                cr_pers     = cr5.number_input("Persuadables ID'd", min_value=0, step=1, key="cr_pers")
                cr6, cr7 = st.columns(2)
                cr_opp      = cr6.number_input("Opposition ID'd", min_value=0, step=1, key="cr_opp")
                cr_followup = cr7.number_input("Follow-up Needed", min_value=0, step=1, key="cr_followup")
                cr_submit = st.form_submit_button("💾 Save Contact Results", type="primary")
                if cr_submit:
                    try:
                        from engine.war_room.runtime_loader import save_runtime_data
                        row = pd.DataFrame([{
                            "date": str(cr_date), "region": cr_region,
                            "contacts": cr_contacts, "supporters_count": cr_support,
                            "persuadables_count": cr_pers, "opposition_count": cr_opp,
                            "follow_up_needed": cr_followup,
                        }])
                        save_runtime_data(row, "contact_results", cfg, append=True)
                        st.success("Contact results saved!")
                    except Exception as e:
                        st.error(f"Could not save: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab C: Field Operations
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_field:
        st.subheader("Field Operations Monitor")
        fp = (daily_status or {}).get("field_pace", {})

        if fp:
            col1, col2, col3 = st.columns(3)
            col1.metric("Target Doors/Week", f"{fp.get('target_doors_per_week',0):,}")
            col2.metric("Weekly Avg (Actual)", f"{fp.get('weekly_avg_doors',0):,}",
                        delta=f"{'REAL data' if fp.get('source_type')=='REAL' else 'No real data yet'}")
            col3.metric("Total Doors Knocked", f"{fp.get('actual_doors_total',0):,}")

        # Field results table
        field_results = runtime.get("field_results")
        if field_results is not None and not field_results.empty:
            st.markdown("#### Field Results Log")
            st.dataframe(field_results, use_container_width=True, hide_index=True)

            # Bar chart: doors by date
            try:
                import plotly.express as px
                door_col = next((c for c in ["doors_knocked", "doors"] if c in field_results.columns), None)
                if door_col and "date" in field_results.columns:
                    fig = px.bar(field_results, x="date", y=door_col,
                                 color="turf_id" if "turf_id" in field_results.columns else None,
                                 title="Doors Knocked by Date",
                                 color_discrete_sequence=px.colors.qualitative.Set2)
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                pass
        else:
            st.markdown(f"No field results yet. {_badge('MISSING')} — Log daily results in the **Data Gaps** tab.",
                        unsafe_allow_html=True)

        # Volunteer log
        vol_log = runtime.get("volunteer_log")
        if vol_log is not None and not vol_log.empty:
            st.markdown("#### Volunteer Log")
            st.dataframe(vol_log, use_container_width=True, hide_index=True)
            avg_vols = runtime.get("metrics", {}).get("avg_volunteers_per_week")
            if avg_vols:
                st.metric("Average Volunteers/Week", f"{avg_vols:.1f}",
                          delta=f"vs. target {_g(cfg,'volunteers','volunteers_per_week',default=10)}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab D: Resource Status
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_resource:
        st.subheader("Resource Status")
        bs = (daily_status or {}).get("budget_status", {})

        col1, col2, col3 = st.columns(3)
        total = bs.get("total_budget", 0)
        actual = bs.get("actual_spend", 0)
        burn  = bs.get("burn_pct")
        expected_burn = bs.get("expected_burn_pct")
        col1.metric("Total Budget", f"${total:,}")
        col2.metric("Actual Spend", f"${actual:,}",
                    delta=f"{burn:.0f}% burned" if burn is not None else "No actuals")
        col3.metric("Expected Burn", f"{expected_burn:.0f}%" if expected_burn else "—",
                    delta="on track" if (burn and expected_burn and abs(burn-expected_burn) < 10) else None)

        # Budget planned vs actual chart
        budget_actuals = runtime.get("budget_actuals")
        if budget_actuals is not None and not budget_actuals.empty:
            st.markdown("#### Budget Actuals by Category")
            try:
                import plotly.express as px
                agg = budget_actuals.groupby("category").agg(
                    planned=("planned_spend", "sum"),
                    actual=("actual_spend", "sum")
                ).reset_index()
                fig = px.bar(
                    agg.melt(id_vars="category", value_vars=["planned","actual"]),
                    x="category", y="value", color="variable",
                    barmode="group", title="Planned vs. Actual Spend by Category",
                    color_discrete_map={"planned": "#93C5FD", "actual": "#2563EB"},
                )
                fig.update_layout(height=320)
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.dataframe(budget_actuals, use_container_width=True, hide_index=True)
        else:
            st.markdown(f"No budget actuals. {_badge('ESTIMATED')} Showing planned budget only.", unsafe_allow_html=True)
            if budget_df is not None and not budget_df.empty:
                try:
                    import plotly.express as px
                    fig = px.pie(budget_df, values="budget", names="program",
                                 title="Planned Budget (No Actuals Yet)",
                                 hole=0.45,
                                 color_discrete_sequence=["#93C5FD","#6EE7B7","#FCD34D","#FCA5A5"])
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    pass

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab E: Risk Monitor
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_risks:
        st.subheader("Risk Monitor")

        # Live risk alerts from daily status
        top_risks = (daily_status or {}).get("top_risks", [])
        if top_risks:
            st.markdown("#### Live Risk Alerts")
            for risk in top_risks:
                st.error(f"⚠️ {risk}")
        else:
            st.success("No live risk alerts. Run the pipeline to update.")

        st.divider()

        # Structured risk analysis from pipeline
        if risk_df is not None and not risk_df.empty:
            st.markdown("#### Structured Risk Analysis")
            risk_colors = {"HIGH": "#FEF2F2", "MEDIUM": "#FFFBEB", "LOW": "#F0FDF4"}
            risk_borders = {"HIGH": "#DC2626", "MEDIUM": "#D97706", "LOW": "#16A34A"}
            risk_icons   = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

            if "level" in risk_df.columns:
                for lvl in ["HIGH", "MEDIUM", "LOW"]:
                    subset = risk_df[risk_df["level"] == lvl]
                    for _, row in subset.iterrows():
                        st.markdown(f"""
                        <div style='background:{risk_colors.get(lvl,"#F8FAFC")};
                             border-left:4px solid {risk_borders.get(lvl,"#6B7280")};
                             border-radius:8px;padding:12px;margin-bottom:8px'>
                          <b>{risk_icons.get(lvl,"⬜")} {row.get('risk','Unknown Risk')}</b>
                          <p style='margin:4px 0 2px 0'>{row.get('description','')}</p>
                          <p style='margin:0;font-size:0.85rem'><b>Mitigation:</b> {row.get('mitigation','')}</p>
                        </div>""", unsafe_allow_html=True)
            else:
                st.dataframe(risk_df, use_container_width=True, hide_index=True)

        # Data quality risks
        st.divider()
        st.markdown("#### Data Quality Risks")
        presence = runtime.get("presence", {})
        for name, key in [
            ("Field Results", "field_results"),
            ("Volunteer Data", "volunteer_log"),
            ("Budget Actuals", "budget_actuals"),
            ("Contact/ID Results", "contact_results"),
        ]:
            if presence.get(key):
                st.markdown(f"🟢 **{name}** — Real data loaded; forecasts use actual observations.")
            else:
                st.markdown(f"🔴 **{name}** — {_badge('MISSING')} Forecasts use model priors.",
                            unsafe_allow_html=True)
