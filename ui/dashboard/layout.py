"""
ui/dashboard/layout.py — Prompt 9

Overview / Campaign Summary page for the Campaign Intelligence Dashboard.
Displays campaign KPIs from STRATEGY_META.json.
"""
from __future__ import annotations

import streamlit as st


def render_overview(data: dict) -> None:
    meta = data.get("strategy_meta", {})
    run_id = data.get("run_id", "unknown")

    st.markdown("""
    <div style='background:linear-gradient(135deg,#1E3A5F 0%,#2563EB 100%);
         border-radius:14px;padding:24px 32px;margin-bottom:24px;color:white'>
      <h1 style='margin:0;color:white;font-size:2rem'>🗳️ Campaign Intelligence Dashboard</h1>
      <p style='margin:6px 0 0 0;color:#BFDBFE;font-size:1rem'>
        Campaign In A Box · California Election Modeling
      </p>
    </div>""", unsafe_allow_html=True)

    # Run badge
    st.markdown(
        f"<div style='background:#F1F5F9;border-radius:8px;padding:10px 16px;"
        f"font-family:monospace;font-size:0.82rem;color:#475569;margin-bottom:20px'>"
        f"📌 <strong>Run:</strong> {run_id} &nbsp;|&nbsp; "
        f"<strong>Contest:</strong> {meta.get('contest_id','—')} &nbsp;|&nbsp; "
        f"<strong>Model:</strong> v{meta.get('model_version','—')} &nbsp;|&nbsp; "
        f"⏱ Loaded in {data.get('load_elapsed',0):.2f}s"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── KPI cards ──────────────────────────────────────────────────────────────
    kpi_items = [
        ("🏘️", "Total Precincts",    meta.get("precinct_count", "—"),       "#2563EB"),
        ("🎯", "Target Precincts",   meta.get("target_precincts", "—"),     "#7C3AED"),
        ("🗺️", "Walk Turfs",         meta.get("turf_count", "—"),           "#0891B2"),
        ("🚪", "Estimated Doors",    f"{meta.get('estimated_doors',0):,}",   "#059669"),
        ("🙋", "Volunteers Needed",  meta.get("estimated_volunteers", "—"), "#D97706"),
        ("🔬", "Simulation Runs",    meta.get("simulation_runs", "—"),      "#DC2626"),
    ]

    cols = st.columns(3)
    for i, (icon, label, value, color) in enumerate(kpi_items):
        with cols[i % 3]:
            st.markdown(
                f"""<div style='background:white;border:1px solid #E2E8F0;border-radius:12px;
                    padding:20px 24px;margin-bottom:14px;
                    border-top:4px solid {color};
                    box-shadow:0 2px 8px rgba(0,0,0,0.06)'>
                  <div style='font-size:0.78rem;color:#64748B;font-weight:600;
                       text-transform:uppercase;letter-spacing:.05em'>{icon} {label}</div>
                  <div style='font-size:2rem;font-weight:800;color:{color};
                       margin-top:4px;line-height:1'>{value}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Topline metrics ────────────────────────────────────────────────────────
    topline = meta.get("topline_metrics", {})
    if topline:
        st.subheader("📊 Topline Model Metrics")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Baseline Turnout",  f"{topline.get('baseline_turnout',0)*100:.1f}%")
        c2.metric("Baseline Support",  f"{topline.get('baseline_support',0)*100:.1f}%")
        c3.metric("Win Number",        f"{topline.get('win_number',0):,}")
        c4.metric("Win Probability",   f"{topline.get('win_probability',0)*100:.0f}%" if topline.get('win_probability') is not None else "—")

    st.markdown("---")

    # ── Data sources ──────────────────────────────────────────────────────────
    pm  = data.get("precinct_model", None)
    tt  = data.get("top_targets", None)
    sim = data.get("simulation_results", None)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📂 Loaded Datasets")
        rows = [
            ("precinct_model",     pm,  len(pm) if pm is not None and not pm.empty else 0),
            ("top_targets",        tt,  len(tt) if tt is not None and not tt.empty else 0),
            ("simulation_results", sim, len(sim) if sim is not None and not sim.empty else 0),
        ]
        for name, df, n in rows:
            icon = "✅" if n > 0 else "⚠️"
            st.markdown(f"{icon} `{name}` — **{n}** rows")

    with col2:
        st.subheader("🔎 Recommended Strategy")
        rec = meta.get("recommended_strategy", {})
        if rec:
            st.markdown(f"**Mode:** `{rec.get('strategy_mode','—')}`")
            st.markdown(f"**Focus:** {rec.get('focus_desc','—')}")
            prio = rec.get("priority_regions", [])
            if prio:
                st.markdown(f"**Priority regions:** {', '.join(str(p) for p in prio[:5])}")
        else:
            st.info("Strategy recommendations not yet available — run the pipeline first.")
