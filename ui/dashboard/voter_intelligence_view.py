"""
ui/dashboard/voter_intelligence_view.py — Prompt 11

Voter Intelligence page for the Campaign Intelligence Dashboard.
Shows voter universe breakdown, propensity distribution, and calibration status.
Gracefully shows an informative empty state when no voter file is loaded.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_universe_data(data: dict):
    """Attempt to load voter universe CSV from derived outputs."""
    run_id = data.get("run_id", "")
    if not run_id:
        return None

    universe_dir = BASE_DIR / "derived" / "voter_universes"
    if not universe_dir.exists():
        return None

    # Find matching file for this run
    matches = sorted(universe_dir.glob(f"{run_id}__universes.csv"))
    if not matches:
        # Fall back to most recent
        all_files = sorted(universe_dir.glob("*__universes.csv"))
        if all_files:
            matches = [all_files[-1]]

    if not matches:
        return None

    try:
        import pandas as pd
        return pd.read_csv(matches[0])
    except Exception:
        return None


def _load_calibration_params() -> dict | None:
    """Load calibration parameters if they exist."""
    cal_path = BASE_DIR / "derived" / "calibration" / "model_parameters.json"
    if not cal_path.exists():
        return None
    import json
    with open(cal_path, encoding="utf-8") as f:
        return json.load(f)


def _load_download_status() -> dict | None:
    """Load the historical election download status."""
    status_path = BASE_DIR / "data" / "elections" / "CA" / "Sonoma" / "download_status.json"
    if not status_path.exists():
        return None
    import json
    with open(status_path, encoding="utf-8") as f:
        return json.load(f)


def render_voter_intelligence(data: dict) -> None:
    """Main render function for the Voter Intelligence dashboard page."""
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0F4C75 0%,#1B6CA8 100%);
         border-radius:14px;padding:24px 32px;margin-bottom:24px;color:white'>
      <h1 style='margin:0;color:white;font-size:2rem'>🧠 Voter Intelligence</h1>
      <p style='margin:6px 0 0 0;color:#BAE6FD;font-size:1rem'>
        Voter universe analysis · Model calibration · Historical context
      </p>
    </div>""", unsafe_allow_html=True)

    # ── Calibration Status Card ────────────────────────────────────────────────
    cal_params = _load_calibration_params()
    with st.container():
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("📐 Model Calibration Status")
            if cal_params:
                status = cal_params.get("calibration_status", "prior_only")
                confidence = cal_params.get("calibration_confidence", "none")
                n_elections = cal_params.get("n_elections", 0)

                conf_color = {"high": "#059669", "medium": "#D97706",
                              "low": "#DC2626", "none": "#6B7280"}.get(confidence, "#6B7280")
                status_icon = {"calibrated": "✅", "prior_only": "⚠️"}.get(status, "ℹ️")

                st.markdown(
                    f"<div style='background:#F1F5F9;border-radius:10px;padding:16px;border-left:4px solid {conf_color}'>"
                    f"<b>{status_icon} Status:</b> {status.replace('_', ' ').title()}&nbsp;&nbsp;"
                    f"<b>Confidence:</b> <span style='color:{conf_color};font-weight:700'>"
                    f"{confidence.upper()}</span>&nbsp;&nbsp;"
                    f"<b>Elections used:</b> {n_elections}"
                    f"</div>", unsafe_allow_html=True
                )
                if cal_params.get("note"):
                    st.info(cal_params["note"])

                # Parameter table
                param_rows = []
                for key, label in [
                    ("turnout_lift_per_contact_mean", "Turnout lift / contact"),
                    ("turnout_lift_per_contact_sd", "Turnout lift SD"),
                    ("persuasion_lift_per_contact_mean", "Persuasion lift / contact"),
                    ("persuasion_lift_per_contact_sd", "Persuasion lift SD"),
                ]:
                    if key in cal_params:
                        param_rows.append({"Parameter": label, "Value": f"{cal_params[key]:.5f}"})
                if param_rows:
                    import pandas as pd
                    st.dataframe(pd.DataFrame(param_rows), use_container_width=True, hide_index=True)
            else:
                st.info(
                    "**No calibration data yet.** Run the pipeline to attempt historical election "
                    "download and calibration. You can also place historical `detail.xls` files in "
                    "`data/elections/CA/Sonoma/<year>/` to enable calibration."
                )

        with c2:
            st.subheader("📅 Historical Elections")
            dl_status = _load_download_status()
            if dl_status:
                present = dl_status.get("years_already_present", [])
                downloaded = dl_status.get("years_downloaded", [])
                failed = dl_status.get("years_failed", [])
                for y in sorted(set(present + downloaded + failed)):
                    if y in present or y in downloaded:
                        st.markdown(f"✅ {y}")
                    else:
                        st.markdown(f"⬜ {y} — [download manually]({dl_status.get('manual_download_links', {}).get('Sonoma County ROV', '#')})")
            else:
                st.info("Run the pipeline to check for historical elections.")

    st.markdown("---")

    # ── Voter Universe Section ────────────────────────────────────────────────
    st.subheader("🎯 Voter Universe Breakdown")
    universe_df = _load_universe_data(data)

    if universe_df is None or universe_df.empty:
        st.warning(
            "**No voter file loaded.** To enable voter universe analysis:\n\n"
            "1. Place a voter file (CSV, TSV, or Parquet) in `data/voters/CA/Sonoma/`\n"
            "2. Run the pipeline — the `LOAD_VOTER_FILE` and `BUILD_VOTER_UNIVERSES` "
            "steps will run automatically\n"
            "3. Return to this page to see the universe breakdown\n\n"
            "Supported voter file formats: L2, Aristotle, CA Secretary of State exports. "
            "Column names are auto-detected."
        )
        _show_voter_file_instructions()
        return

    # Render universe data
    import pandas as pd
    try:
        import plotly.express as px
        _has_plotly = True
    except ImportError:
        _has_plotly = False

    # Summary KPIs
    total_voters = int(universe_df["total_voters"].sum()) if "total_voters" in universe_df.columns else 0
    n_precincts = len(universe_df)

    kb1, kb2, kb3, kb4 = st.columns(4)
    kb1.metric("Total Voters (on file)", f"{total_voters:,}")
    kb2.metric("Precincts with Data", f"{n_precincts:,}")
    if "avg_propensity" in universe_df.columns:
        avg_prop = universe_df["avg_propensity"].mean()
        kb3.metric("Avg Propensity Score", f"{avg_prop:.2f}")
    if "persuadable_count" in universe_df.columns:
        n_persuadable = int(universe_df["persuadable_count"].sum())
        kb4.metric("Persuadable Voters", f"{n_persuadable:,}")

    st.markdown("---")

    # Universe summary table
    universe_labels = {
        "high_propensity": "🟢 High Propensity",
        "low_propensity": "🔴 Low Propensity",
        "persuadable": "🟡 Persuadable",
        "base_supporters": "🔵 Base Supporters",
        "likely_opposition": "⚪ Likely Opposition",
        "other": "◻️ Other",
    }
    summary_rows = []
    for key, label in universe_labels.items():
        cnt_col = f"{key}_count"
        pct_col = f"{key}_pct"
        if cnt_col in universe_df.columns:
            total_n = int(universe_df[cnt_col].sum())
            avg_pct = universe_df[pct_col].mean() if pct_col in universe_df.columns else 0
            summary_rows.append({
                "Universe": label,
                "Total Voters": f"{total_n:,}",
                "% of Electorate": f"{avg_pct*100:.1f}%",
            })
    if summary_rows:
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    # Bar chart by precinct (top 20)
    st.subheader("📊 Universe Distribution by Precinct (Top 20)")
    count_cols = [f"{k}_count" for k in universe_labels.keys() if f"{k}_count" in universe_df.columns]
    if count_cols and _has_plotly:
        top20 = universe_df.nlargest(20, "total_voters") if "total_voters" in universe_df.columns else universe_df.head(20)
        chart_df = top20[["canonical_precinct_id"] + count_cols].copy()
        chart_df = chart_df.rename(columns={c: c.replace("_count", "").replace("_", " ").title()
                                             for c in count_cols})
        chart_melted = chart_df.melt(id_vars="canonical_precinct_id", var_name="Universe", value_name="Count")
        fig = px.bar(
            chart_melted,
            x="canonical_precinct_id",
            y="Count",
            color="Universe",
            title="Voter Universe Breakdown by Precinct",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(xaxis_title="Precinct", yaxis_title="Voter Count",
                          showlegend=True, height=400)
        st.plotly_chart(fig, use_container_width=True)

    # Propensity distribution
    if "avg_propensity" in universe_df.columns and _has_plotly:
        st.subheader("📈 Propensity Score Distribution")
        fig2 = px.histogram(
            universe_df,
            x="avg_propensity",
            nbins=20,
            title="Distribution of Average Precinct Propensity Score",
            color_discrete_sequence=["#2563EB"],
            labels={"avg_propensity": "Avg Propensity Score (0=never votes, 1=always votes)"},
        )
        fig2.update_layout(height=300)
        st.plotly_chart(fig2, use_container_width=True)

    # Raw data
    with st.expander("🔍 View Raw Universe Data"):
        st.dataframe(universe_df, use_container_width=True)
        csv = universe_df.to_csv(index=False)
        st.download_button("⬇️ Download Universe CSV", csv,
                           f"voter_universes_{data.get('run_id','latest')}.csv", "text/csv")


def _show_voter_file_instructions():
    """Show detailed instructions for loading a voter file."""
    with st.expander("📖 How to load a voter file"):
        st.markdown("""
### Voter File Setup

Place a voter file in the local-only directory (never committed to GitHub):
```
data/voters/CA/Sonoma/voter_file_2025.csv
```

**Supported formats:** CSV, TSV, Parquet

**Required columns** (auto-detected, common names accepted):
| Field | Accepted Column Names |
|-------|----------------------|
| Precinct | `precinct`, `PRECINCT`, `Precinct_ID`, `srprec` |
| Party | `party`, `PartyCode`, `Parties_Description` |
| Vote History | columns starting with `vote_history_`, `VH_`, or `Election_` |
| Age | `age`, `Age`, `Calculated_Age` |

**Optional columns:** gender, ethnicity, language, mail_ballot_status

**Note:** Address columns and voter IDs are automatically stripped from all committed outputs.
Only aggregated precinct-level statistics are ever written to `derived/voter_universes/`.
        """)
