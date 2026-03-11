"""
ui/dashboard/strategy_view.py — Prompt 13 (upgraded)

Campaign Strategy dashboard page. Shows:
  - Vote Path (base/persuasion/GOTV breakdown with waterfall chart)
  - Budget Allocation (donut chart by program)
  - Field Plan Timeline (weekly canvassing table)
  - Risk Analysis (color-coded risk cards)
  - Export bundle download button

Gracefully degrades when strategy outputs are missing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STRATEGY_DIR = BASE_DIR / "derived" / "strategy"
REPORTS_DIR  = BASE_DIR / "reports" / "strategy"


# ── Data Loaders ──────────────────────────────────────────────────────────────

def _load_latest_csv(directory: Path, pattern: str):
    try:
        import pandas as pd
        matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return pd.read_csv(matches[0])
    except Exception:
        pass
    return None


def _load_latest_json(directory: Path, pattern: str) -> Optional[dict]:
    try:
        matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            with open(matches[0], encoding="utf-8") as f:
                return json.load(f)
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


def _g(d: dict, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


# ── Main Page ─────────────────────────────────────────────────────────────────

# ── Main Page ─────────────────────────────────────────────────────────────────

def render_strategy(data: dict) -> None:
    """Render the Campaign Strategy dashboard page."""
    from ui.components.alerts import render_alert
    from ui.components.metric_card import render_metric_card
    from ui.theme import apply_chart_theme

    st.markdown("<h1 class='page-title'>Strategic Plan</h1>", unsafe_allow_html=True)
    st.caption("Executive strategy, vote path math, and recommended field allocations.")

    cfg = _load_campaign_config()
    contest_name = _g(cfg, "campaign", "contest_name", default="Campaign")

    vote_path_df = _load_latest_csv(STRATEGY_DIR, "*__vote_path.csv")
    budget_df    = _load_latest_csv(STRATEGY_DIR, "*__budget_allocation.csv")
    field_df     = _load_latest_csv(STRATEGY_DIR, "*__field_strategy.csv")
    risk_df      = _load_latest_csv(STRATEGY_DIR, "*__risk_analysis.csv")

    has_strategy = vote_path_df is not None

    if not has_strategy:
        render_alert("warning", "No strategy outputs found. Run the pipeline first.")
        return

    import pandas as pd
    try:
        import plotly.express as px
        import plotly.graph_objects as go
        _has_plotly = True
    except ImportError:
        _has_plotly = False

    vp = vote_path_df.iloc[0].to_dict() if vote_path_df is not None and not vote_path_df.empty else {}

    # ── Executive Strategy Summary Cards ──────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        win_number = int(vp.get('win_number', 0))
        render_metric_card("Win Number", f"{win_number:,}", "Required for victory", "ESTIMATED", "info")
    with k2:
        cov_rate = float(vp.get('coverage_rate', 0))
        c_status = "success" if cov_rate >= 1.0 else ("warning" if cov_rate >= 0.85 else "danger")
        render_metric_card("Path Coverage", f"{cov_rate:.1%}", "Identified voters", None, c_status)
    with k3:
        target_margin = float(_g(cfg,'targets','win_margin',default=0.04))
        render_metric_card("Target Margin", f"+{target_margin:.1%}", "Strategic objective", None, "info")
    with k4:
        total_b = _g(cfg,'budget','total_budget',default=0)
        render_metric_card("Budget Total", f"${total_b:,}", "Available resources", None, "info")

    st.markdown("---")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Executive Report", "Vote Path", "Budget & Resources", "Field Targets", "Export Bundle"
    ])

    with tab1:
        st.subheader("Strategy Report")
        report_files = sorted(REPORTS_DIR.glob("*__campaign_strategy.md"), key=lambda p: p.stat().st_mtime, reverse=True) if REPORTS_DIR.exists() else []
        if report_files:
            latest = report_files[0]
            st.markdown(f"<div class='secondary-block' style='font-size:0.95rem; line-height:1.6;'>{latest.read_text(encoding='utf-8')}</div>", unsafe_allow_html=True)
        else:
            render_alert("info", "No strategy report markdown found.")
            
    with tab2:
        st.subheader("Vote Path Math")
        col_chart, col_table = st.columns([3, 2])
        base_votes   = int(vp.get("base_votes", 0))
        pers_votes   = int(vp.get("persuasion_votes_needed", 0))
        gotv_votes   = int(vp.get("gotv_votes_needed", 0))
        cumulative   = int(vp.get("cumulative_total", 0))

        with col_chart:
            if _has_plotly:
                fig = go.Figure(go.Waterfall(
                    orientation="v", measure=["relative", "relative", "relative", "total"],
                    x=["Base Committed", "Persuasion", "GOTV", "Projected"],
                    y=[base_votes, pers_votes, gotv_votes, 0],
                    decreasing=dict(marker_color="#EF4444"), increasing=dict(marker_color="#2E8B57"),
                    totals=dict(marker_color="#1F4E79"),
                    text=[f"{base_votes:,}", f"+{pers_votes:,}", f"+{gotv_votes:,}", f"{cumulative:,}"],
                    textposition="outside",
                ))
                fig.add_hline(y=win_number, line_dash="dash", line_color="#DC2626", annotation_text=f"Win Number: {win_number:,}")
                fig = apply_chart_theme(fig)
                fig.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        with col_table:
            rows = [
                {"Metric": "Expected Voters", "Count": f"{int(vp.get('expected_voters', 0)):,}"},
                {"Metric": "Win Number", "Count": f"{win_number:,}"},
                {"Metric": "Base Committed", "Count": f"{base_votes:,}"},
                {"Metric": "Persuasion Target", "Count": f"{pers_votes:,}"},
                {"Metric": "GOTV Target", "Count": f"{gotv_votes:,}"},
                {"Metric": "Projected Total", "Count": f"{cumulative:,}"},
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("Resource Allocation")
        if budget_df is not None and not budget_df.empty and _has_plotly:
            c_p, c_t = st.columns([3, 2])
            with c_p:
                fig_pie = px.pie(budget_df, values="budget", names="program", hole=0.5,
                                 color_discrete_sequence=["#1F4E79", "#3C78D8", "#8E7CC3", "#D9A441"])
                fig_pie = apply_chart_theme(fig_pie)
                st.plotly_chart(fig_pie, use_container_width=True)
            with c_t:
                b_disp = budget_df.copy()
                b_disp["budget"] = b_disp["budget"].apply(lambda x: f"${int(x):,}")
                b_disp["pct"] = b_disp["pct"].apply(lambda x: f"{float(x):.1%}")
                st.dataframe(b_disp, use_container_width=True, hide_index=True)
        else:
            render_alert("info", "Budget allocation data missing.")

    with tab4:
        st.subheader("Field Plan & Turfs")
        if field_df is not None and not field_df.empty:
            if "week" in field_df.columns and _has_plotly:
                fig_bar = px.bar(field_df, x="week", y=["persuasion_doors", "gotv_doors"], 
                                 title="Weekly Knocking Plan", barmode="stack",
                                 color_discrete_sequence=["#8E7CC3", "#3C78D8"])
                fig_bar = apply_chart_theme(fig_bar)
                st.plotly_chart(fig_bar, use_container_width=True)
            st.dataframe(field_df, use_container_width=True, hide_index=True)
        else:
            render_alert("info", "Field plan data missing.")

    with tab5:
        st.subheader("Export Strategy Bundle")
        if report_files:
            latest = report_files[0]
            st.download_button("📄 Download Markdown Report", data=latest.read_bytes(), file_name=latest.name, mime="text/markdown")
        else:
            render_alert("info", "Generate strategy report to enable export.")
