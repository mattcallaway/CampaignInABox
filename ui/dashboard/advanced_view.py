"""
ui/dashboard/advanced_view.py — Prompt 10

Campaign Intelligence Dashboard — Advanced Modeling page.
Displays advanced modeling outputs (no computation — read-only).
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _latest(root: Path, glob: str):
    if not root.exists():
        return None
    hits = sorted(root.rglob(glob), key=lambda p: p.stat().st_mtime, reverse=True)
    hits = [h for h in hits if h.is_file() and ".gitkeep" not in str(h)]
    return hits[0] if hits else None


def _read_csv(p) -> pd.DataFrame:
    if p and p.exists():
        try:
            return pd.read_csv(p)
        except Exception:
            pass
    return pd.DataFrame()


def _read_md(p) -> str:
    if p and p.exists():
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            pass
    return ""


def render_advanced(data: dict) -> None:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#312E81,#6D28D9);
         border-radius:12px;padding:18px 28px;margin-bottom:20px;color:white'>
      <h2 style='margin:0;color:white'>⚡ Advanced Modeling</h2>
      <p style='margin:4px 0 0 0;color:#DDD6FE'>
        Elasticity-based lift projections · Optimizer · Monte Carlo uncertainty bands
      </p>
    </div>""", unsafe_allow_html=True)

    # ── Priors-only warning banner ────────────────────────────────────────────
    st.warning(
        "⚠️ **Prior-driven proof-of-concept.** These projections use academic literature priors, "
        "not calibrated coefficients. Use relative rankings — not absolute numbers — for decisions. "
        "See the Model Card tab for full assumptions and limitations."
    )

    # ── Locate advanced modeling outputs ─────────────────────────────────────
    adv_root = BASE_DIR / "derived" / "advanced_modeling"
    scenarios_path = _latest(adv_root, "*__advanced_scenarios.csv")
    sim_sum_path   = _latest(adv_root, "*__advanced_simulation_summary.csv")
    alloc_path     = _latest(adv_root, "*__optimal_allocation.csv")
    curve_path     = _latest(adv_root, "*__allocation_curve.csv")
    mc_card_path   = _latest(BASE_DIR / "reports" / "model_cards", "*__advanced_modeling_model_card.md")

    scenarios_df = _read_csv(scenarios_path)
    sim_sum_df   = _read_csv(sim_sum_path)
    alloc_df     = _read_csv(alloc_path)
    curve_df     = _read_csv(curve_path)
    model_card   = _read_md(mc_card_path)

    if scenarios_df.empty and alloc_df.empty:
        st.info("No advanced modeling outputs found. Run the pipeline to generate advanced modeling results.")
        return

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Scenarios",
        "🏆 Win Probability Deltas",
        "🗂️ Optimal Allocation",
        "📉 Allocation Curve",
        "📋 Model Card",
    ])

    with tab1:
        _render_scenarios(scenarios_df, sim_sum_df)

    with tab2:
        _render_win_deltas(sim_sum_df)

    with tab3:
        _render_allocation(alloc_df)

    with tab4:
        _render_curve(curve_df)

    with tab5:
        if model_card:
            st.markdown(model_card)
        else:
            st.info("Model card not yet generated. Run the pipeline first.")


def _render_scenarios(scenarios_df: pd.DataFrame, sim_sum_df: pd.DataFrame) -> None:
    st.subheader("📊 Scenario Comparison")
    if scenarios_df.empty:
        st.info("No scenario outputs found.")
        return

    merged = scenarios_df.copy()
    if not sim_sum_df.empty and "scenario" in sim_sum_df.columns:
        mc_cols = ["scenario", "mc_net_gain_mean", "mc_net_gain_p10", "mc_net_gain_p90", "risk_band"]
        mc_cols = [c for c in mc_cols if c in sim_sum_df.columns]
        merged = merged.merge(sim_sum_df[mc_cols], on="scenario", how="left")

    # Metric cards for each scenario
    cols = st.columns(min(len(merged), 5))
    scenario_colors = {
        "baseline": "#64748B",
        "lite":     "#059669",
        "medium":   "#2563EB",
        "heavy":    "#7C3AED",
        "user_budget": "#DC2626",
    }
    for i, (_, row) in enumerate(merged.iterrows()):
        scen = row.get("scenario", "?")
        clr  = scenario_colors.get(scen, "#334155")
        gain = row.get("expected_net_gain_votes", 0)
        shifts = row.get("shifts_assigned", 0)
        risk_band = row.get("risk_band", "—")
        with cols[i % len(cols)]:
            st.markdown(
                f"<div style='background:white;border:1px solid #E2E8F0;border-radius:10px;"
                f"padding:16px;border-top:5px solid {clr};margin-bottom:10px'>"
                f"<div style='font-size:0.8rem;color:#64748B;font-weight:600;"
                f"text-transform:uppercase'>{scen}</div>"
                f"<div style='font-size:1.7rem;font-weight:800;color:{clr}'>{gain:+.1f}</div>"
                f"<div style='font-size:0.75rem;color:#94A3B8'>net votes expected</div>"
                f"<div style='font-size:0.75rem;margin-top:6px'>Shifts: {shifts}</div>"
                f"<div style='font-size:0.75rem;color:#94A3B8'>Risk band: {risk_band}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.dataframe(merged, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Export Scenarios",
                       merged.to_csv(index=False).encode("utf-8"),
                       "advanced_scenarios.csv", "text/csv")


def _render_win_deltas(sim_sum_df: pd.DataFrame) -> None:
    st.subheader("🏆 Monte Carlo Win Probability by Scenario")
    if sim_sum_df.empty:
        st.info("Monte Carlo summary not available.")
        return

    try:
        import plotly.express as px
        if "mc_net_gain_mean" in sim_sum_df.columns:
            fig = px.bar(
                sim_sum_df, x="scenario", y="mc_net_gain_mean",
                error_y=sim_sum_df.get("mc_net_gain_sd"),
                color="scenario",
                title="Expected Net Vote Gain (MC Mean ± 1 SD)",
                height=400,
                color_discrete_sequence=["#94A3B8","#059669","#2563EB","#7C3AED","#DC2626"],
            )
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # p10/p90 range chart
        if all(c in sim_sum_df.columns for c in ["mc_net_gain_p10","mc_net_gain_p90"]):
            fig2 = px.scatter(
                sim_sum_df, x="scenario", y="mc_net_gain_mean",
                error_y=(sim_sum_df["mc_net_gain_p90"] - sim_sum_df["mc_net_gain_mean"]),
                error_y_minus=(sim_sum_df["mc_net_gain_mean"] - sim_sum_df["mc_net_gain_p10"]).clip(lower=0),
                title="Uncertainty Bands (p10–p90) by Scenario",
                height=350,
            )
            fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig2, use_container_width=True)
    except ImportError:
        st.warning("Plotly not available for charts.")
        st.dataframe(sim_sum_df, use_container_width=True)


def _render_allocation(alloc_df: pd.DataFrame) -> None:
    st.subheader("🗂️ Recommended Allocation (Heavy Scenario)")
    if alloc_df.empty:
        st.info("Optimal allocation not available.")
        return

    total = alloc_df["shifts_assigned"].sum() if "shifts_assigned" in alloc_df.columns else 0
    net   = alloc_df["expected_net_gain_votes"].sum() if "expected_net_gain_votes" in alloc_df.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Shifts", f"{int(total)}")
    c2.metric("Expected Net Gain", f"{net:.1f} votes")
    c3.metric("Entities", f"{len(alloc_df)}")

    st.dataframe(alloc_df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Export Allocation",
                       alloc_df.to_csv(index=False).encode("utf-8"),
                       "optimal_allocation.csv", "text/csv")


def _render_curve(curve_df: pd.DataFrame) -> None:
    st.subheader("📉 Marginal Returns Curve")
    st.caption("Shows how each additional shift contributes less net gain than the previous one (diminishing returns).")
    if curve_df.empty:
        st.info("Allocation curve not available.")
        return

    try:
        import plotly.express as px
        if "marginal_gain_votes" in curve_df.columns:
            fig = px.line(
                curve_df, x="shift_number", y="marginal_gain_votes",
                color="entity_assigned" if "entity_assigned" in curve_df.columns else None,
                title="Marginal Vote Gain per Additional Shift",
                height=380,
            )
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.dataframe(curve_df, use_container_width=True)

    st.download_button("⬇️ Export Curve",
                       curve_df.to_csv(index=False).encode("utf-8"),
                       "allocation_curve.csv", "text/csv")
