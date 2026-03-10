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

def render_strategy(data: dict) -> None:
    """Render the Campaign Strategy dashboard page."""

    st.markdown("""
    <div style='background:linear-gradient(135deg,#1E3A5F 0%,#2563EB 100%);
         border-radius:14px;padding:24px 32px;margin-bottom:24px;color:white'>
      <h1 style='margin:0;color:white;font-size:2rem'>&#128203; Campaign Strategy</h1>
      <p style='margin:6px 0 0 0;color:#BAE6FD;font-size:1rem'>
        Vote Path &middot; Budget Allocation &middot; Field Plan &middot; Risk Analysis &middot; Export
      </p>
    </div>""", unsafe_allow_html=True)

    cfg = _load_campaign_config()
    contest_name = _g(cfg, "campaign", "contest_name", default="Campaign")

    # Load strategy outputs
    vote_path_df = _load_latest_csv(STRATEGY_DIR, "*__vote_path.csv")
    budget_df    = _load_latest_csv(STRATEGY_DIR, "*__budget_allocation.csv")
    field_df     = _load_latest_csv(STRATEGY_DIR, "*__field_strategy.csv")
    risk_df      = _load_latest_csv(STRATEGY_DIR, "*__risk_analysis.csv")

    has_strategy = vote_path_df is not None

    # ── Campaign Config Summary ───────────────────────────────────────────────
    if cfg:
        with st.expander("**Campaign Configuration Summary**", expanded=not has_strategy):
            col1, col2, col3 = st.columns(3)
            col1.metric("Contest", contest_name[:30])
            col2.metric("Election Date", _g(cfg, "campaign", "election_date", default="—"))
            col3.metric("Target Vote Share", f"{_g(cfg,'targets','target_vote_share',default=0.52):.1%}")
            col1.metric("Total Budget", f"${_g(cfg,'budget','total_budget',default=0):,}")
            col2.metric("Win Margin Target", f"{_g(cfg,'targets','win_margin',default=0.04):.1%}")
            col3.metric("Volunteers/Week", _g(cfg, "volunteers", "volunteers_per_week", default="—"))
    else:
        st.info("No campaign configuration found. Go to **🗳️ Campaign Setup** to configure your campaign.")

    if not has_strategy:
        st.warning(
            "No strategy outputs found. Run the pipeline after configuring your campaign:\n\n"
            "```\npython scripts/run_pipeline.py --state CA --county Sonoma --year 2025 --contest-slug prop_50_special\n```"
        )
        return

    import pandas as pd

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        _has_plotly = True
    except ImportError:
        _has_plotly = False

    # ── Top KPI Row ───────────────────────────────────────────────────────────
    vp = vote_path_df.iloc[0].to_dict() if vote_path_df is not None and not vote_path_df.empty else {}

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Win Number", f"{int(vp.get('win_number', 0)):,}")
    k2.metric("Expected Voters", f"{int(vp.get('expected_voters', 0)):,}")
    k3.metric("Baseline Turnout", f"{float(vp.get('baseline_turnout_pct', 0)):.1%}")
    k4.metric("Vote Path Coverage", f"{float(vp.get('coverage_rate', 0)):.1%}",
              delta="On track" if float(vp.get('coverage_rate', 0)) >= 1.0 else "Gap exists")
    k5.metric("Total Budget", f"${_g(cfg,'budget','total_budget',default=0):,}")

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Vote Path", "💰 Budget", "🚪 Field Plan", "⚠️ Risks", "📦 Export"
    ])

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab 1: Vote Path
    # ═══════════════════════════════════════════════════════════════════════════
    with tab1:
        st.subheader("Vote Path Analysis")

        base_votes   = int(vp.get("base_votes", 0))
        pers_votes   = int(vp.get("persuasion_votes_needed", 0))
        gotv_votes   = int(vp.get("gotv_votes_needed", 0))
        win_number   = int(vp.get("win_number", 0))
        cumulative   = int(vp.get("cumulative_total", 0))

        # Waterfall / stacked bar
        col_chart, col_table = st.columns([3, 2])
        with col_chart:
            if _has_plotly:
                fig = go.Figure(go.Waterfall(
                    name="Vote Path",
                    orientation="v",
                    measure=["relative", "relative", "relative", "total"],
                    x=["Base Committed", "Persuasion Needed", "GOTV Needed", "Projected Total"],
                    y=[base_votes, pers_votes, gotv_votes, 0],
                    connector=dict(line=dict(color="rgb(63, 63, 63)")),
                    decreasing=dict(marker_color="#EF4444"),
                    increasing=dict(marker_color="#10B981"),
                    totals=dict(marker_color="#2563EB"),
                    text=[f"{base_votes:,}", f"+{pers_votes:,}", f"+{gotv_votes:,}", f"{cumulative:,}"],
                    textposition="outside",
                ))
                # Win number line
                fig.add_hline(y=win_number, line_dash="dash", line_color="#DC2626",
                              annotation_text=f"Win Number: {win_number:,}",
                              annotation_position="right")
                fig.update_layout(
                    title="Vote Path Waterfall",
                    yaxis_title="Votes",
                    height=400,
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                # Fallback text
                st.markdown(f"""
                | Component | Votes |
                |-----------|-------|
                | Base Committed | {base_votes:,} |
                | + Persuasion Needed | {pers_votes:,} |
                | + GOTV Needed | {gotv_votes:,} |
                | **Projected Total** | **{cumulative:,}** |
                | **Win Number** | **{win_number:,}** |
                """)

        with col_table:
            st.markdown("#### Vote Path Summary")
            rows = [
                {"Component": "Registered Voters", "Count": f"{int(vp.get('registered', 0)):,}"},
                {"Component": "Expected Voters", "Count": f"{int(vp.get('expected_voters', 0)):,}"},
                {"Component": "Win Number", "Count": f"{win_number:,}"},
                {"Component": "Stretch Goal", "Count": f"{int(vp.get('stretch_number', win_number)):,}"},
                {"Component": "Base Committed", "Count": f"{base_votes:,}"},
                {"Component": "Votes Needed (Gap)", "Count": f"{int(vp.get('votes_gap', 0)):,}"},
                {"Component": "→ via Persuasion", "Count": f"{pers_votes:,}"},
                {"Component": "→ via GOTV", "Count": f"{gotv_votes:,}"},
                {"Component": "Projected Total", "Count": f"{cumulative:,}"},
                {"Component": "Coverage Rate", "Count": f"{float(vp.get('coverage_rate', 0)):.1%}"},
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Strategy recommendation
        coverage = float(vp.get("coverage_rate", 0))
        if coverage >= 1.0:
            st.success(f"✅ Vote path is fully covered ({coverage:.1%}). Execute the field plan to achieve the win number.")
        elif coverage >= 0.85:
            st.warning(f"⚠️ Vote path is {coverage:.1%} covered. Modest increase in volunteer capacity or budget would close the gap.")
        else:
            st.error(f"❌ Vote path is only {coverage:.1%} covered. Significant resource increase or target recalibration needed.")

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab 2: Budget
    # ═══════════════════════════════════════════════════════════════════════════
    with tab2:
        st.subheader("Budget Allocation")
        if budget_df is not None and not budget_df.empty and _has_plotly:
            col_pie, col_table = st.columns([3, 2])
            with col_pie:
                fig_pie = px.pie(
                    budget_df,
                    values="budget",
                    names="program",
                    title="Budget by Program",
                    color_discrete_sequence=["#2563EB", "#7C3AED", "#059669", "#D97706"],
                    hole=0.45,
                )
                fig_pie.update_traces(textposition="inside", textinfo="percent+label")
                fig_pie.update_layout(height=380)
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_table:
                st.markdown("#### Program Breakdown")
                ba_display = budget_df.copy()
                if "budget" in ba_display.columns:
                    ba_display["budget"] = ba_display["budget"].apply(lambda x: f"${int(x):,}")
                if "pct" in ba_display.columns:
                    ba_display["pct"] = ba_display["pct"].apply(lambda x: f"{float(x):.1%}")
                st.dataframe(ba_display.rename(columns={"program": "Program", "budget": "Budget", "pct": "% Total"}),
                             use_container_width=True, hide_index=True)

                total_b = _g(cfg, "budget", "total_budget", default=0)
                st.metric("Total Budget", f"${total_b:,}")
        else:
            st.info("Budget data not yet available. Run the pipeline after configuring your campaign.")

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab 3: Field Plan Timeline
    # ═══════════════════════════════════════════════════════════════════════════
    with tab3:
        st.subheader("Field Program Plan")
        if field_df is not None and not field_df.empty:
            # Check if it's a weekly plan or a summary
            if "week" in field_df.columns:
                col_chart, col_table = st.columns([3, 2])
                with col_chart:
                    if _has_plotly:
                        fig_bar = go.Figure()
                        fig_bar.add_trace(go.Bar(
                            name="Persuasion Doors",
                            x=field_df["week"],
                            y=field_df.get("persuasion_doors", []),
                            marker_color="#2563EB",
                        ))
                        fig_bar.add_trace(go.Bar(
                            name="GOTV Doors",
                            x=field_df["week"],
                            y=field_df.get("gotv_doors", []),
                            marker_color="#059669",
                        ))
                        fig_bar.update_layout(
                            barmode="stack",
                            title="Weekly Door-Knocking Plan",
                            xaxis_title="Week",
                            yaxis_title="Doors",
                            height=380,
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.dataframe(field_df, use_container_width=True, hide_index=True)

                with col_table:
                    # Agg stats
                    total_doors = int(field_df.get("total_doors", pd.Series([0])).sum())
                    total_pers  = int(field_df.get("expected_persuasion_contacts", pd.Series([0])).sum())
                    total_gotv  = int(field_df.get("expected_gotv_contacts", pd.Series([0])).sum())
                    st.metric("Total Doors", f"{total_doors:,}")
                    st.metric("Total Persuasion Contacts", f"{total_pers:,}")
                    st.metric("Total GOTV Contacts", f"{total_gotv:,}")
                    st.metric("Weeks Planned", len(field_df))

                # Full table
                with st.expander("Weekly Plan Detail"):
                    st.dataframe(field_df, use_container_width=True, hide_index=True)
            else:
                st.dataframe(field_df, use_container_width=True, hide_index=True)
        else:
            st.info("Field plan not yet generated. Run the pipeline with campaign config.")

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab 4: Risk Analysis
    # ═══════════════════════════════════════════════════════════════════════════
    with tab4:
        st.subheader("Campaign Risk Analysis")
        if risk_df is not None and not risk_df.empty:
            risk_colors = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
            risk_bg     = {"HIGH": "#FEF2F2", "MEDIUM": "#FFFBEB", "LOW": "#F0FDF4"}

            # Sort: HIGH first
            level_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            risk_sorted = risk_df.copy()
            if "level" in risk_sorted.columns:
                risk_sorted["_order"] = risk_sorted["level"].map(level_order).fillna(3)
                risk_sorted = risk_sorted.sort_values("_order").drop(columns=["_order"])

            for _, row in risk_sorted.iterrows():
                lvl = str(row.get("level", "LOW")).upper()
                icon = risk_colors.get(lvl, "⬜")
                bg   = risk_bg.get(lvl, "#F8FAFC")
                risk_name = row.get("risk", "Unknown")
                desc = row.get("description", "")
                mitigation = row.get("mitigation", "")

                st.markdown(f"""
                <div style='background:{bg};border-radius:10px;padding:14px;margin-bottom:10px;border-left:4px solid {"#DC2626" if lvl=="HIGH" else "#D97706" if lvl=="MEDIUM" else "#16A34A"}'>
                  <b>{icon} {risk_name}</b> &nbsp; <span style='color:#6B7280;font-size:0.85rem'>{lvl}</span>
                  <p style='margin:4px 0 2px 0'>{desc}</p>
                  <p style='margin:0;color:#374151;font-size:0.9rem'><b>Mitigation:</b> {mitigation}</p>
                </div>""", unsafe_allow_html=True)

            # Risk summary
            high_count = (risk_df.get("level", pd.Series([])) == "HIGH").sum()
            med_count  = (risk_df.get("level", pd.Series([])) == "MEDIUM").sum()
            if high_count == 0:
                st.success("No HIGH-level risks identified ✅")
            else:
                st.error(f"{high_count} HIGH-level risk(s) require immediate attention.")
        else:
            st.info("Risk analysis not yet available. Run the pipeline after configuring your campaign.")

    # ═══════════════════════════════════════════════════════════════════════════
    # Tab 5: Export
    # ═══════════════════════════════════════════════════════════════════════════
    with tab5:
        st.subheader("Export Campaign Plan Bundle")

        # Show strategy report preview
        report_files = sorted(REPORTS_DIR.glob("*__campaign_strategy.md"), key=lambda p: p.stat().st_mtime, reverse=True) if REPORTS_DIR.exists() else []
        if report_files:
            latest_report = report_files[0]
            st.success(f"Strategy report ready: `{latest_report.name}`")
            with st.expander("Preview Strategy Report"):
                st.markdown(latest_report.read_text(encoding="utf-8"))

            # Download raw markdown
            st.download_button(
                "📄 Download Strategy Report (Markdown)",
                data=latest_report.read_bytes(),
                file_name=latest_report.name,
                mime="text/markdown",
                key="dl_strategy_report",
            )
        else:
            st.info("No strategy report yet. Run the pipeline to generate one.")

        st.divider()
        st.markdown("### Build Export Bundle")
        st.caption("Creates a portable folder with all strategy files for sharing.")

        export_run_id = st.text_input(
            "Run ID for export (or leave blank for latest)",
            value="",
            placeholder="e.g. 2026-03-10__143525__030abb27__msi",
            key="export_run_id_input",
        )

        if st.button("📦 Build & Download Export Bundle", type="primary", key="build_export_btn"):
            with st.spinner("Building export bundle…"):
                try:
                    from engine.strategy.strategy_exporter import build_export_bundle

                    # Infer latest run_id if blank
                    if not export_run_id.strip():
                        # Find from any strategy CSV
                        strategy_csvs = sorted(STRATEGY_DIR.glob("*__vote_path.csv"),
                                               key=lambda p: p.stat().st_mtime, reverse=True)
                        if strategy_csvs:
                            export_run_id = strategy_csvs[0].name.replace("__vote_path.csv", "")
                        else:
                            st.error("No strategy outputs found. Run the pipeline first.")
                            st.stop()

                    result = build_export_bundle(export_run_id.strip(), create_zip=True)
                    zip_path = result.get("zip_path")
                    included = result.get("files_included", [])
                    skipped  = result.get("files_skipped", [])

                    st.success(f"Bundle built! {len(included)} files included.")
                    if included:
                        st.markdown("**Included:** " + ", ".join(f"`{f}`" for f in included))
                    if skipped:
                        st.warning("Not included (not yet generated): " + ", ".join(f"`{f}`" for f in skipped))

                    if zip_path and zip_path.exists():
                        with open(zip_path, "rb") as zf:
                            st.download_button(
                                "⬇️ Download ZIP Bundle",
                                data=zf.read(),
                                file_name=zip_path.name,
                                mime="application/zip",
                                key="dl_bundle_zip",
                            )
                    else:
                        bundle_dir = result.get("bundle_dir")
                        if bundle_dir:
                            st.info(f"Bundle written to: `{bundle_dir}`")

                except Exception as e:
                    st.error(f"Export failed: {e}")
