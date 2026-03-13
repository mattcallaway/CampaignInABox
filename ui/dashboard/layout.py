"""
ui/dashboard/layout.py — Prompt 20.7
Overview / Campaign Summary command center page.
"""
import streamlit as st
from ui.components.metric_card import render_metric_card
from ui.components.alerts import render_alert

def render_overview(data: dict) -> None:
    meta = data.get("strategy_meta", {})
    topline = meta.get("topline_metrics", {})
    rec = meta.get("recommended_strategy", {})
    snap = data.get("state_snapshot", {})  # Assume state metadata could be passed here, or derived
    
    st.markdown("<h1 class='page-title'>Campaign Command Overview</h1>", unsafe_allow_html=True)
    st.caption("Strategic snapshot and top-level executive summary")

    # ── Primary Summary Cards ──────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    
    with c1:
        wp = (topline.get("win_probability") or 0) * 100
        render_metric_card(
            title="Win Probability",
            value=f"{wp:.1f}%",
            subtitle="Current modeled forecast",
            provenance="SIMULATED",
            status="success" if wp > 50 else "warning"
        )
        
    with c2:
        health = snap.get("risk_level", "UNKNOWN") if snap else "UNKNOWN"
        h_color = "success" if health == "LOW" else ("warning" if health == "MEDIUM" else "danger")
        render_metric_card(
            title="Campaign Health",
            value=health,
            subtitle="Overall risk assessment",
            status=h_color
        )
        
    with c3:
        win_num = topline.get("win_number") or 0
        render_metric_card(
            title="Votes Needed",
            value=f"{win_num:,}",
            subtitle="Path to victory target",
            provenance="ESTIMATED",
            status="info"
        )
        
    st.write("")
    c4, c5, c6 = st.columns(3)
    
    with c4:
        budget = 250000  # Placeholder, should come from finance module if exists
        render_metric_card(
            title="Budget Remaining",
            value=f"${budget:,}",
            subtitle="Estimated capacity",
            provenance="ESTIMATED"
        )
        
    with c5:
        doors = meta.get("estimated_doors", 0)
        render_metric_card(
            title="Doors Planned",
            value=f"{doors:,}",
            subtitle="Target vs Actual: 0",
            provenance="ESTIMATED"
        )
        
    with c6:
        vols = meta.get("estimated_volunteers", 0)
        render_metric_card(
            title="Volunteers Needed",
            value=f"{vols:,}",
            subtitle="Active currently: 0",
            provenance="ESTIMATED"
        )

    # ── Secondary Blocks: Risks & Recommendations ─────────────────────────────
    st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
    r1, r2 = st.columns([1, 1])
    
    with r1:
        st.markdown("<div class='secondary-block'>", unsafe_allow_html=True)
        st.markdown("<h3 class='section-header'>🚨 Top Campaign Risks</h3>", unsafe_allow_html=True)
        # Mocking top risks based on existing logic
        if not data.get("field_data"):
            render_alert("critical", "No real field data uploaded yet. Operations relying on models.")
        if wp < 50:
            render_alert("warning", f"Win probability is critically low at {wp:.1f}%")
        render_alert("info", "Volunteer pace hasn't been established.")
        st.markdown("</div>", unsafe_allow_html=True)

    with r2:
        st.markdown("<div class='secondary-block'>", unsafe_allow_html=True)
        st.markdown("<h3 class='section-header'>💡 Strategic Recommendations</h3>", unsafe_allow_html=True)
        if isinstance(rec, dict) and rec:
            render_alert("success", f"Focus: {rec.get('focus_desc', '—')}")
            prio = rec.get("priority_regions", [])
            if prio:
                render_alert("info", f"Prioritize jurisdictions: {', '.join(str(p) for p in prio[:3])}")
            render_alert("warning", f"Model Strategy: {rec.get('strategy_mode', '—')}")
        elif isinstance(rec, str):
            render_alert("success", f"Focus: {rec}")
        else:
            render_alert("warning", "No recommendations available yet. Run the pipeline.")
        st.markdown("</div>", unsafe_allow_html=True)
