"""
ui/dashboard/targeting_view.py — Prompt 9

Targeting list viewer with filters and CSV export.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd


# Column display names
_COL_MAP = {
    "canonical_precinct_id": "Precinct ID",
    "registered":            "Registered",
    "turnout_pct":           "Turnout Rate",
    "support_pct":           "YES %",
    "target_score":          "Target Score",
    "target_tier":           "Tier",
    "walk_priority":         "Walk Priority",
    "universe_name":         "Universe",
    "region_name":           "Region",
    "doors_to_knock":        "Doors",
}


def render_targeting(data: dict) -> None:
    st.markdown("<h1 class='page-title'>Targeting List</h1>", unsafe_allow_html=True)
    st.caption("Filter and explore precinct targeting data")

    # Try multiple sources in priority order
    df = data.get("top_targets", pd.DataFrame())
    if df.empty:
        df = data.get("precinct_model", pd.DataFrame())

    if df.empty:
        st.warning("No targeting data found. Run the pipeline first.")
        return

    # ── Sidebar / expander filters ──────────────────────────────────────────
    with st.expander("⚙️ Filters", expanded=True):
        c1, c2, c3 = st.columns(3)

        min_score = 0.0
        max_score = 1.0
        if "target_score" in df.columns:
            min_score = float(df["target_score"].min())
            max_score = float(df["target_score"].max())

        with c1:
            score_range = st.slider(
                "Target Score range",
                min_value=0.0, max_value=1.0,
                value=(min_score, max_score),
                step=0.01,
            )
        with c2:
            tier_opts = sorted(df["target_tier"].dropna().unique().tolist()) if "target_tier" in df.columns else []
            tier_sel = st.multiselect("Walk Tier", options=tier_opts, default=tier_opts)
        with c3:
            if "universe_name" in df.columns:
                uni_opts = sorted(df["universe_name"].dropna().unique().tolist())
                uni_sel = st.multiselect("Universe", options=uni_opts, default=uni_opts)
            else:
                uni_sel = []

    # Apply filters
    filt = df.copy()
    if "target_score" in filt.columns:
        filt = filt[filt["target_score"].between(*score_range)]
    if tier_sel and "target_tier" in filt.columns:
        filt = filt[filt["target_tier"].isin(tier_sel)]
    if uni_sel and "universe_name" in filt.columns:
        filt = filt[filt["universe_name"].isin(uni_sel)]

    # Display cols
    display_cols = [c for c in _COL_MAP if c in filt.columns]
    disp = filt[display_cols].copy() if display_cols else filt

    # Format numeric
    if "turnout_pct" in disp.columns:
        disp["turnout_pct"] = disp["turnout_pct"].map(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
    if "support_pct"  in disp.columns:
        disp["support_pct"]  = disp["support_pct"].map(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
    if "target_score" in disp.columns:
        disp["target_score"] = disp["target_score"].map(lambda x: f"{x:.4f}" if pd.notna(x) else "—")

    disp = disp.rename(columns=_COL_MAP)

    st.markdown(f"**{len(filt):,}** precincts matching filters &nbsp;(of {len(df):,} total)")

    st.dataframe(
        disp,
        use_container_width=True,
        hide_index=True,
    )

    # CSV export
    csv_bytes = filt.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Export filtered targeting list (CSV)",
        data=csv_bytes,
        file_name="targeting_export.csv",
        mime="text/csv",
    )
