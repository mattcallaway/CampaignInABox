"""
ui/dashboard/data_explorer.py — Prompt 9

Generic dataset viewer with sorting, filtering, and CSV export.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd


DATASETS = {
    "Precinct Model":     "precinct_model",
    "Precinct Universes": "precinct_universes",
    "Top Targets":        "top_targets",
    "Simulation Results": "simulation_results",
    "Scenario Forecasts": "scenario_forecasts",
    "Field Plan":         "field_plan",
    "Join Guard":         "join_guard_csv",
    "Integrity Repairs":  "repair_csv",
}


def render_explorer(data: dict) -> None:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0F172A,#1E293B);
         border-radius:12px;padding:18px 28px;margin-bottom:20px;color:white'>
      <h2 style='margin:0;color:white'>🗄️ Data Explorer</h2>
      <p style='margin:4px 0 0 0;color:#94A3B8'>
        Browse, sort, filter and export any pipeline dataset
      </p>
    </div>""", unsafe_allow_html=True)

    # ── Dataset selector ──────────────────────────────────────────────────────
    dataset_name = st.selectbox(
        "Select dataset",
        list(DATASETS.keys()),
        key="explorer_dataset",
    )
    key = DATASETS[dataset_name]
    df: pd.DataFrame = data.get(key, pd.DataFrame())

    if df.empty:
        st.warning(f"No data for `{dataset_name}`. Run the pipeline to generate outputs.")
        return

    st.markdown(f"**{len(df):,}** rows · **{len(df.columns)}** columns")

    # ── Column filter ─────────────────────────────────────────────────────────
    with st.expander("📌 Column Selector", expanded=False):
        all_cols = df.columns.tolist()
        selected_cols = st.multiselect("Show columns", all_cols, default=all_cols, key="explorer_cols")
        if selected_cols:
            df = df[selected_cols]

    # ── Text search ───────────────────────────────────────────────────────────
    search = st.text_input("🔍 Search (filters all text columns)", key="explorer_search", placeholder="e.g. Precinct 05...")
    if search:
        mask = df.apply(lambda col: col.astype(str).str.contains(search, case=False, na=False)).any(axis=1)
        df = df[mask]
        st.markdown(f"**{len(df):,}** matching rows")

    # ── Numeric range sliders for key columns ─────────────────────────────────
    num_cols = df.select_dtypes("number").columns.tolist()
    if num_cols:
        with st.expander("📊 Numeric Filters", expanded=False):
            for nc in num_cols[:5]:  # max 5 sliders
                mn, mx = float(df[nc].min()), float(df[nc].max())
                if mn < mx:
                    rng = st.slider(nc, mn, mx, (mn, mx), key=f"exp_{nc}")
                    df = df[df[nc].between(*rng)]

    # ── Sort ──────────────────────────────────────────────────────────────────
    col_sort, col_asc = st.columns([3, 1])
    sort_col  = col_sort.selectbox("Sort by", ["(none)"] + df.columns.tolist(), key="explorer_sort")
    sort_asc  = col_asc.checkbox("Ascending", value=True, key="explorer_asc")
    if sort_col != "(none)":
        df = df.sort_values(sort_col, ascending=sort_asc)

    # ── Dataframe display ─────────────────────────────────────────────────────
    st.dataframe(df.head(2000), use_container_width=True, hide_index=True)
    if len(df) > 2000:
        st.caption(f"Showing first 2,000 of {len(df):,} rows.")

    # ── Export ────────────────────────────────────────────────────────────────
    st.download_button(
        f"⬇️ Export {dataset_name}",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"{key}_export.csv",
        mime="text/csv",
        key="explorer_export",
    )

    # ── Summary stats ─────────────────────────────────────────────────────────
    with st.expander("📈 Summary Statistics"):
        st.dataframe(df.describe(include="all").T, use_container_width=True)
