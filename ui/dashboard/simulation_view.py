"""
ui/dashboard/simulation_view.py — Prompt 9

Monte Carlo simulation results viewer with Plotly charts.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd


def render_simulation(data: dict) -> None:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#7C2D12,#DC2626);
         border-radius:12px;padding:18px 28px;margin-bottom:20px;color:white'>
      <h2 style='margin:0;color:white'>🔬 Simulation Results</h2>
      <p style='margin:4px 0 0 0;color:#FEE2E2'>Monte Carlo outcome distributions</p>
    </div>""", unsafe_allow_html=True)

    try:
        import plotly.express as px
        import plotly.graph_objects as go
    except ImportError:
        st.error("Plotly not installed. Run: `pip install plotly`")
        return

    sim = data.get("simulation_results", pd.DataFrame())
    forecasts = data.get("scenario_forecasts", pd.DataFrame())

    if sim.empty and forecasts.empty:
        st.warning("No simulation data found. Run the pipeline to generate SIMULATION_RESULTS.csv.")
        return

    # Use whichever has data
    df = sim if not sim.empty else forecasts

    if df.empty:
        st.warning("Simulation data is empty.")
        return

    st.markdown(f"**{len(df)}** simulation rows loaded")

    # ── Detect available columns ────────────────────────────────────────────
    has_margin   = any(c in df.columns for c in ["margin", "vote_margin", "net_margin"])
    has_turnout  = any(c in df.columns for c in ["turnout_rate", "turnout_pct", "expected_turnout"])
    has_win      = any(c in df.columns for c in ["win_probability", "win", "outcome"])
    has_scenario = "scenario" in df.columns

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Outcome Distribution", "📈 Turnout Scenarios", "📉 Scatter", "📋 Raw Data"])

    with tab1:
        # Win probability card
        if has_win:
            win_col = next(c for c in ["win_probability", "win", "outcome"] if c in df.columns)
            win_pct = df[win_col].mean() * 100 if df[win_col].dtype != object else (df[win_col] == "WIN").mean() * 100
            color = "#16A34A" if win_pct >= 60 else ("#D97706" if win_pct >= 45 else "#DC2626")
            st.markdown(
                f"<div style='background:{color}18;border:2px solid {color};border-radius:12px;"
                f"padding:20px 28px;margin-bottom:16px;text-align:center'>"
                f"<div style='font-size:0.85rem;color:#64748B;text-transform:uppercase;font-weight:600'>Win Probability</div>"
                f"<div style='font-size:3rem;font-weight:800;color:{color}'>{win_pct:.0f}%</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # Scenario breakdown bar chart
        if has_scenario:
            scenario_grp = df.groupby("scenario").size().reset_index(name="count")
            fig = px.bar(scenario_grp, x="scenario", y="count",
                         title="Scenario Distribution",
                         color="scenario",
                         height=320)
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Margin histogram
        margin_col = next((c for c in ["margin", "vote_margin", "net_margin"] if c in df.columns), None)
        if margin_col:
            fig = px.histogram(df, x=margin_col,
                               title="Vote Margin Distribution",
                               nbins=30, height=320,
                               color_discrete_sequence=["#2563EB"])
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        turnout_col = next((c for c in ["turnout_rate", "turnout_pct", "expected_turnout"] if c in df.columns), None)
        if turnout_col and has_scenario:
            fig = px.line(
                df.sort_values("scenario"),
                x=df.index, y=turnout_col,
                color="scenario" if has_scenario else None,
                title="Turnout by Scenario",
                height=400,
                markers=True,
            )
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
        elif turnout_col:
            fig = px.line(df, y=turnout_col, title="Turnout Rate", height=350,
                          color_discrete_sequence=["#059669"])
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No turnout rate column found in simulation results.")

    with tab3:
        # Persuasion vs Turnout scatter
        x_col = next((c for c in ["turnout_rate", "turnout_pct"] if c in df.columns), None)
        y_col = next((c for c in ["support_pct", "yes_rate", "persuasion_potential"] if c in df.columns), None)
        if x_col and y_col:
            fig = px.scatter(
                df, x=x_col, y=y_col,
                color="scenario" if has_scenario else None,
                title=f"{y_col.replace('_',' ').title()} vs {x_col.replace('_',' ').title()}",
                opacity=0.65, height=420,
                trendline="ols" if len(df) < 5000 else None,
            )
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Generic numeric scatter with first two numeric cols
            num_cols = df.select_dtypes("number").columns.tolist()
            if len(num_cols) >= 2:
                fig = px.scatter(df, x=num_cols[0], y=num_cols[1],
                                 title=f"{num_cols[1]} vs {num_cols[0]}", height=400)
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Not enough numeric columns for scatter plot.")

    with tab4:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Export Simulation Results",
            df.to_csv(index=False).encode("utf-8"),
            "simulation_results.csv", "text/csv",
        )
