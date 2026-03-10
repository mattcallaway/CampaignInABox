"""
ui/dashboard/voter_intelligence_view.py — Prompt 11/12 (upgraded)

Voter Intelligence page for the Campaign Intelligence Dashboard.

Prompt 12 upgrade:
  - TPS (Turnout Propensity Score) distribution histogram
  - PS (Persuasion Score) distribution histogram
  - Targeting quadrant scatter plot (TPS vs PS, color-coded by quadrant)
  - Upgraded universe breakdown with Prompt 12 universes
  - Top precincts table filterable by universe type
  - GOTV / Persuasion target summary

Gracefully shows an informative empty state when no voter file is loaded.
"""
from __future__ import annotations

from pathlib import Path
import json

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Data Loaders ──────────────────────────────────────────────────────────────

def _load_csv(directory: Path, pattern: str):
    """Load the most-recent matching CSV, return None if missing."""
    try:
        import pandas as pd
        matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return pd.read_csv(matches[0])
    except Exception:
        pass
    return None


def _load_universe_data():
    return _load_csv(BASE_DIR / "derived" / "voter_universes", "*__universes.csv")

def _load_tps_data():
    return _load_csv(BASE_DIR / "derived" / "voter_models", "*__precinct_turnout_scores.csv")

def _load_ps_data():
    return _load_csv(BASE_DIR / "derived" / "voter_models", "*__precinct_persuasion_scores.csv")

def _load_quadrant_data():
    return _load_csv(BASE_DIR / "derived" / "voter_segments", "*__targeting_quadrants.csv")

def _load_precinct_metrics():
    return _load_csv(BASE_DIR / "derived" / "voter_models", "*__precinct_voter_metrics.csv")

def _load_calibration_params():
    cal_path = BASE_DIR / "derived" / "calibration" / "model_parameters.json"
    if not cal_path.exists():
        return None
    with open(cal_path, encoding="utf-8") as f:
        return json.load(f)

def _load_download_status():
    status_path = BASE_DIR / "data" / "elections" / "CA" / "Sonoma" / "download_status.json"
    if not status_path.exists():
        return None
    with open(status_path, encoding="utf-8") as f:
        return json.load(f)


# ── Page: Voter Intelligence ──────────────────────────────────────────────────

def render_voter_intelligence(data: dict) -> None:
    """Main render function for the Voter Intelligence dashboard page."""
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0F4C75 0%,#1B6CA8 100%);
         border-radius:14px;padding:24px 32px;margin-bottom:24px;color:white'>
      <h1 style='margin:0;color:white;font-size:2rem'>&#129504; Voter Intelligence</h1>
      <p style='margin:6px 0 0 0;color:#BAE6FD;font-size:1rem'>
        Turnout Propensity &amp; Persuasion Scoring &middot; Targeting Quadrants &middot; Campaign Universes
      </p>
    </div>""", unsafe_allow_html=True)

    # Load all data sources once
    tps_df      = _load_tps_data()
    ps_df       = _load_ps_data()
    quad_df     = _load_quadrant_data()
    universe_df = _load_universe_data()
    metrics_df  = _load_precinct_metrics()
    cal_params  = _load_calibration_params()
    dl_status   = _load_download_status()

    has_voter_data = any(df is not None and not df.empty for df in [tps_df, ps_df, quad_df])

    # ── Calibration Status ─────────────────────────────────────────────────────
    with st.expander("**Model Calibration Status**", expanded=not has_voter_data):
        c1, c2 = st.columns([2, 1])

        with c1:
            if cal_params:
                status = cal_params.get("calibration_status", "prior_only")
                confidence = cal_params.get("calibration_confidence", "none")
                n_elections = cal_params.get("n_elections", 0)
                conf_color = {"high": "#059669", "medium": "#D97706", "low": "#DC2626", "none": "#6B7280"}.get(confidence, "#6B7280")
                status_icon = {"calibrated": "OK", "prior_only": "Warning"}.get(status, "Info")
                st.markdown(f"""
                    <div style='background:#F1F5F9;border-radius:10px;padding:14px;border-left:4px solid {conf_color}'>
                    <b>{status_icon} Status:</b> {status.replace('_',' ').title()} &nbsp;
                    <b>Confidence:</b> <span style='color:{conf_color};font-weight:700'>{confidence.upper()}</span> &nbsp;
                    <b>Elections used:</b> {n_elections}
                    </div>""", unsafe_allow_html=True)
                if cal_params.get("note"):
                    st.info(cal_params["note"])
                # Parameter table
                import pandas as pd
                param_rows = [
                    {"Parameter": "Turnout lift / contact", "Value": f"{cal_params.get('turnout_lift_per_contact_mean', 0):.5f}"},
                    {"Parameter": "Persuasion lift / contact", "Value": f"{cal_params.get('persuasion_lift_per_contact_mean', 0):.5f}"},
                ]
                st.dataframe(pd.DataFrame(param_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No calibration data yet. Run the pipeline to calibrate.")

        with c2:
            st.markdown("**Historical Elections**")
            if dl_status:
                present = dl_status.get("years_already_present", []) + dl_status.get("years_downloaded", [])
                failed = dl_status.get("years_failed", [])
                for y in sorted(set(present + failed)):
                    if y in present:
                        st.markdown(f"OK {y}")
                    else:
                        st.markdown(f"- {y} — [manual download needed](https://www.sonomacounty.ca.gov/elected-officials-and-departments/registrar-of-voters/election-results)")
            else:
                st.caption("Run pipeline to check elections.")

    st.divider()

    # ── No voter data yet ─────────────────────────────────────────────────────
    if not has_voter_data:
        st.warning(
            "**No voter scores loaded.** Run the pipeline with a voter file to activate this page.\n\n"
            "```\n"
            "python scripts/generate_test_voter_file.py --n 5000\n"
            "python scripts/run_pipeline.py --state CA --county Sonoma --year 2025 --contest-slug prop_50_special\n"
            "```"
        )
        _show_voter_file_instructions()
        return

    import pandas as pd
    try:
        import plotly.express as px
        import plotly.graph_objects as go
        _has_plotly = True
    except ImportError:
        _has_plotly = False

    # ── KPI Row ───────────────────────────────────────────────────────────────
    total_voters = int(tps_df["total_voters"].sum()) if tps_df is not None and "total_voters" in tps_df.columns else 0
    n_precincts  = len(tps_df) if tps_df is not None else 0
    avg_tps      = float(tps_df["avg_tps"].mean()) if tps_df is not None and "avg_tps" in tps_df.columns else None
    avg_ps       = float(ps_df["avg_ps"].mean()) if ps_df is not None and "avg_ps" in ps_df.columns else None

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Voters on File", f"{total_voters:,}")
    k2.metric("Precincts with Data", f"{n_precincts:,}")
    if avg_tps is not None:
        k3.metric("Avg Turnout Propensity", f"{avg_tps:.1%}")
    if avg_ps is not None:
        k4.metric("Avg Persuasion Score", f"{avg_ps:.1%}")

    st.markdown("---")

    # ── Tab layout ────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["Targeting Quadrant", "TPS Distribution", "PS Distribution", "Universe Details"])

    # ── Tab 1: Targeting Quadrant Scatter ─────────────────────────────────────
    with tab1:
        if quad_df is not None and not quad_df.empty and _has_plotly:
            st.subheader("Targeting Quadrant Map (TPS vs PS by Precinct)")
            if "avg_tps" in quad_df.columns and "avg_ps" in quad_df.columns:
                col_for_size = "total_voters" if "total_voters" in quad_df.columns else None

                fig = go.Figure()
                quadrant_colors = {
                    "high_value":         "#7C3AED",   # purple
                    "persuasion_target":  "#2563EB",   # blue
                    "turnout_persuasion": "#059669",   # green
                    "base_voter":         "#DC2626",   # red
                    "low_priority":       "#9CA3AF",   # gray
                    "other":              "#D1D5DB",   # light gray
                }
                for q_name, q_color in quadrant_colors.items():
                    cnt_col = f"{q_name}_count"
                    if cnt_col not in quad_df.columns:
                        continue
                    q_rows = quad_df[quad_df[cnt_col] > 0]
                    if q_rows.empty:
                        continue
                    sizes = q_rows[col_for_size].clip(10, 1000) if col_for_size else 20
                    fig.add_trace(go.Scatter(
                        x=q_rows["avg_tps"], y=q_rows["avg_ps"],
                        mode="markers",
                        marker=dict(size=(sizes / sizes.max() * 30 + 5) if col_for_size else 12,
                                    color=q_color, opacity=0.7),
                        name=q_name.replace("_", " ").title(),
                        text=q_rows["canonical_precinct_id"],
                        hovertemplate="<b>Precinct:</b> %{text}<br>TPS: %{x:.2f}<br>PS: %{y:.2f}",
                    ))

                # Add quadrant dividers
                for x_thresh, y_thresh in [(0.5, 0.6)]:
                    fig.add_vline(x=x_thresh, line_dash="dash", line_color="#CBD5E1", line_width=1)
                    fig.add_hline(y=y_thresh, line_dash="dash", line_color="#CBD5E1", line_width=1)

                # Quadrant labels
                for txt, x, y in [
                    ("PERSUASION", 0.75, 0.80),
                    ("HIGH ENGAGE", 0.75, 0.30),
                    ("GOTV+PERS.", 0.20, 0.80),
                    ("LOW PRI.", 0.20, 0.30),
                ]:
                    fig.add_annotation(x=x, y=y, text=txt, showarrow=False,
                                      font=dict(size=10, color="#6B7280"),
                                      bgcolor="rgba(255,255,255,0.7)")

                fig.update_layout(
                    title="Precinct Targeting Quadrant (bubble size = voter count)",
                    xaxis_title="Turnout Propensity Score (TPS)",
                    yaxis_title="Persuasion Score (PS)",
                    xaxis=dict(range=[0, 1]), yaxis=dict(range=[0, 1]),
                    height=500, showlegend=True,
                )
                st.plotly_chart(fig, use_container_width=True)

                # Summary table
                st.subheader("Quadrant Summary")
                rows = []
                for q_name in quadrant_colors.keys():
                    cnt_col = f"{q_name}_count"
                    if cnt_col in quad_df.columns:
                        total_n = int(quad_df[cnt_col].sum())
                        if total_n > 0:
                            rows.append({"Quadrant": q_name.replace("_", " ").title(), "Voters": f"{total_n:,}"})
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("Quadrant data available but TPS/PS averages not yet computed for each precinct.")
        else:
            st.info("Run the pipeline with a voter file to generate targeting quadrant data.")

    # ── Tab 2: TPS Distribution ───────────────────────────────────────────────
    with tab2:
        if tps_df is not None and not tps_df.empty:
            st.subheader("Turnout Propensity Score (TPS) Distribution")
            c1, c2 = st.columns([2, 1])

            with c1:
                if _has_plotly and "avg_tps" in tps_df.columns:
                    fig_tps = px.histogram(
                        tps_df, x="avg_tps", nbins=25,
                        title="Precinct-Level Average TPS",
                        labels={"avg_tps": "Avg Turnout Propensity Score"},
                        color_discrete_sequence=["#2563EB"],
                    )
                    fig_tps.update_layout(height=350)
                    st.plotly_chart(fig_tps, use_container_width=True)

            with c2:
                st.markdown("**TPS Statistics**")
                for stat_col, stat_label in [("avg_tps", "Mean"), ("median_tps", "Median"),
                                              ("high_propensity_pct", "High Prop. %")]:
                    if stat_col in tps_df.columns:
                        v = tps_df[stat_col].mean()
                        st.metric(stat_label, f"{v:.1%}" if "pct" in stat_col else f"{v:.3f}")

            # GOTV target precincts
            st.subheader("Top GOTV Target Precincts (lowest TPS)")
            if "avg_tps" in tps_df.columns:
                gotv_targets = tps_df.nsmallest(20, "avg_tps")[
                    ["canonical_precinct_id", "avg_tps", "high_propensity_count", "low_propensity_count"]
                    if "high_propensity_count" in tps_df.columns else ["canonical_precinct_id", "avg_tps"]
                ]
                st.dataframe(gotv_targets, use_container_width=True, hide_index=True)
        else:
            st.info("No TPS data yet. Run the pipeline with a voter file.")

    # ── Tab 3: PS Distribution ────────────────────────────────────────────────
    with tab3:
        if ps_df is not None and not ps_df.empty:
            st.subheader("Persuasion Score (PS) Distribution")
            c1, c2 = st.columns([2, 1])

            with c1:
                if _has_plotly and "avg_ps" in ps_df.columns:
                    fig_ps = px.histogram(
                        ps_df, x="avg_ps", nbins=25,
                        title="Precinct-Level Average PS",
                        labels={"avg_ps": "Avg Persuasion Score"},
                        color_discrete_sequence=["#7C3AED"],
                    )
                    fig_ps.update_layout(height=350)
                    st.plotly_chart(fig_ps, use_container_width=True)

            with c2:
                st.markdown("**PS Statistics**")
                for stat_col, stat_label in [("avg_ps", "Mean"), ("median_ps", "Median"),
                                              ("persuadable_pct", "Persuadable %")]:
                    if stat_col in ps_df.columns:
                        v = ps_df[stat_col].mean()
                        st.metric(stat_label, f"{v:.1%}" if "pct" in stat_col else f"{v:.3f}")

            st.subheader("Top Persuasion Target Precincts (highest PS)")
            if "avg_ps" in ps_df.columns:
                pers_targets = ps_df.nlargest(20, "avg_ps")[
                    ["canonical_precinct_id", "avg_ps", "persuadable_count"]
                    if "persuadable_count" in ps_df.columns else ["canonical_precinct_id", "avg_ps"]
                ]
                st.dataframe(pers_targets, use_container_width=True, hide_index=True)
        else:
            st.info("No PS data yet. Run the pipeline with a voter file.")

    # ── Tab 4: Universe Details ───────────────────────────────────────────────
    with tab4:
        if universe_df is not None and not universe_df.empty:
            st.subheader("Campaign Universe Breakdown")
            # Universe summary
            universe_labels_12 = [
                ("high_value_persuasion",     "High-Value Persuasion"),
                ("persuasion_universe",       "Persuasion Universe"),
                ("gotv_universe",             "GOTV Universe"),
                ("base_mobilization",         "Base Mobilization"),
                ("low_turnout_persuadables",  "Low Turnout Persuadables"),
                ("likely_opposition",         "Likely Opposition"),
                ("other",                     "Other"),
            ]
            universe_labels_11 = [
                ("high_propensity",   "High Propensity"),
                ("low_propensity",    "Low Propensity"),
                ("persuadable",       "Persuadable"),
                ("base_supporters",   "Base Supporters"),
                ("likely_opposition", "Likely Opposition"),
                ("other",             "Other"),
            ]
            # Detect which version
            labels = universe_labels_12 if any(
                f"{u[0]}_count" in universe_df.columns for u in universe_labels_12
            ) else universe_labels_11

            rows, total = [], int(universe_df["total_voters"].sum()) if "total_voters" in universe_df.columns else 0
            for key, label in labels:
                cnt_col = f"{key}_count"
                if cnt_col in universe_df.columns:
                    n = int(universe_df[cnt_col].sum())
                    if n > 0:
                        rows.append({"Universe": label, "Voters": f"{n:,}", "% of File": f"{n/total*100:.1f}%" if total else "N/A"})
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            with st.expander("Raw Universe Data"):
                st.dataframe(universe_df, use_container_width=True)
                csv = universe_df.to_csv(index=False)
                st.download_button("Download Universe CSV", csv, "voter_universes.csv", "text/csv")
        else:
            st.info("No universe data yet. Run the pipeline with a voter file.")


def _show_voter_file_instructions():
    """Show instructions for loading a voter file."""
    with st.expander("How to load a voter file"):
        st.markdown("""
### Voter File Setup

Place a voter file at `data/voters/CA/Sonoma/voter_file_2025.csv`

**Supported formats:** CSV, TSV, Parquet

**Required/auto-detected columns:** precinct, party, vote_history_*, age

**Test with synthetic data:**
```
python scripts/generate_test_voter_file.py --n 5000
python scripts/run_pipeline.py ...
```

**Note:** Individual voter records are never committed to GitHub.
Only precinct-level aggregates go to `derived/`.
        """)
