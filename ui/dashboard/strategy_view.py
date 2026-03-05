"""
ui/dashboard/strategy_view.py — Prompt 9

Strategy Pack viewer: shows STRATEGY_SUMMARY.md and key strategy outputs.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd


def render_strategy(data: dict) -> None:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#065F46,#059669);
         border-radius:12px;padding:18px 28px;margin-bottom:20px;color:white'>
      <h2 style='margin:0;color:white'>📋 Campaign Strategy</h2>
      <p style='margin:4px 0 0 0;color:#D1FAE5'>Strategy summary, field plan, and win path</p>
    </div>""", unsafe_allow_html=True)

    meta = data.get("strategy_meta", {})
    summary_md = data.get("strategy_summary_md", "")

    # ── Strategy summary ──────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["📄 Strategy Report", "🗂️ Field Plan", "🏆 Top Targets", "🗺️ Top Turfs"])

    with tab1:
        if summary_md:
            st.markdown(summary_md)
        else:
            st.info("No strategy summary found. Run the full pipeline to generate STRATEGY_SUMMARY.md.")
            # Show what we do have from meta
            if meta:
                _render_meta_fallback(meta)

    with tab2:
        fp = data.get("field_plan", pd.DataFrame())
        if fp.empty:
            st.info("Field plan not available. Run the pipeline first.")
        else:
            # Key stats
            c1, c2, c3 = st.columns(3)
            if "doors_to_knock" in fp.columns:
                c1.metric("Total Doors", f"{int(fp['doors_to_knock'].sum()):,}")
            if "volunteers_needed" in fp.columns:
                c2.metric("Volunteers Needed", f"{int(fp['volunteers_needed'].sum()):,}")
            if "weeks_required" in fp.columns:
                c3.metric("Weeks Required", f"{fp['weeks_required'].max():.0f}")

            st.dataframe(fp, use_container_width=True, hide_index=True)

            st.download_button(
                "⬇️ Export Field Plan",
                fp.to_csv(index=False).encode("utf-8"),
                "field_plan.csv", "text/csv",
            )

        pace = data.get("field_pace", pd.DataFrame())
        if not pace.empty:
            st.subheader("⏱️ Field Pace")
            import plotly.express as px
            if "week" in pace.columns and "pace_doors_per_day" in pace.columns:
                fig = px.line(pace, x="week", y="pace_doors_per_day",
                              title="Daily Door-Knock Pace by Week",
                              markers=True, height=300)
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.dataframe(pace, use_container_width=True, hide_index=True)

    with tab3:
        tt = data.get("top_targets", pd.DataFrame())
        if tt.empty:
            st.info("Top targets not available.")
        else:
            st.markdown(f"**{len(tt)}** priority precincts")
            st.dataframe(tt, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Export Top Targets",
                tt.to_csv(index=False).encode("utf-8"),
                "top_targets.csv", "text/csv",
            )

    with tab4:
        turfs = data.get("top_turfs", pd.DataFrame())
        if turfs.empty:
            st.info("Walk turf list not available.")
        else:
            st.markdown(f"**{len(turfs)}** walk turfs planned")
            st.dataframe(turfs, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Export Turfs",
                turfs.to_csv(index=False).encode("utf-8"),
                "top_turfs.csv", "text/csv",
            )


def _render_meta_fallback(meta: dict) -> None:
    st.subheader("📊 Strategy Metadata")
    for key in ["contest_id", "county", "precinct_count", "target_precincts",
                "turf_count", "estimated_doors", "estimated_volunteers",
                "simulation_runs", "model_version"]:
        val = meta.get(key, "—")
        st.markdown(f"**{key.replace('_',' ').title()}:** `{val}`")
