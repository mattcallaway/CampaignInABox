"""
ui/dashboard/jurisdiction_view.py — Prompt 19

Generates the Multi-Jurisdiction dashboard tab to view aggregate strategy,
forecasts, and comparisons across multiple counties/districts in the campaign.
"""
from __future__ import annotations
import streamlit as st
import pandas as pd

def render_jurisdiction_summary(data: dict):
    st.header("🌐 Jurisdiction Summary")
    st.caption("Cross-county strategy aggregation and regional forecasts")
    
    state_snap = data.get("state_summary", {})
    jurisdictions = state_snap.get("jurisdictions", [])
    mj_forecast = state_snap.get("multi_jurisdiction_forecast", {})
    
    if not jurisdictions and not mj_forecast:
        st.warning("No multi-jurisdiction data available. Run the pipeline with multiple counties (e.g. `--county Sonoma,Marin`) to generate regional strategy.")
        return
        
    st.markdown("### 🗺️ Included Jurisdictions")
    st.markdown(", ".join([f"**{j}**" for j in jurisdictions]) if jurisdictions else "Global / All")
    
    st.divider()
    
    st.markdown("### 📊 Regional Forecast Comparison")
    
    if mj_forecast:
        # Build a table comparing margins for 'baseline' and 'field_heavy'
        rows = []
        for j, scens in mj_forecast.items():
            base_margin = scens.get("baseline", {}).get("margin", 0)
            base_votes = scens.get("baseline", {}).get("support_votes", 0)
            heavy_margin = scens.get("field_heavy", {}).get("margin", 0)
            heavy_votes = scens.get("field_heavy", {}).get("support_votes", 0)
            
            rows.append({
                "Jurisdiction": j,
                "Baseline Margin": f"{base_margin:,.0f}",
                "Best Case Margin": f"{heavy_margin:,.0f}",
                "Gain (Votes)": f"{(heavy_votes - base_votes):,.0f}"
            })
            
        df_forecast = pd.DataFrame(rows)
        st.dataframe(df_forecast, use_container_width=True)
    else:
        st.info("No regional forecast simulation data found.")
        
    st.divider()
    
    # Ideally link to jurisdiction_strategy.csv here or show a quick breakdown
    # If the file is loaded in data, show it. But data_loader doesn't load it by default.
    # We can try to load it ad-hoc for the UI.
    
    import json
    from pathlib import Path
    
    st.markdown("### 📦 Resource Allocation by Jurisdiction")
    st.caption("Distribution of volunteer shifts and door targets by local geography.")
    
    run_id = state_snap.get("run_id")
    contest_id = state_snap.get("contest_id")
    
    base_dir = Path(__file__).resolve().parent.parent.parent
    alloc_path = base_dir / "derived" / "strategy_packs" / str(contest_id) / str(run_id) / "resource_allocation_by_jurisdiction.csv"
    
    if alloc_path.exists():
        alloc_df = pd.read_csv(alloc_path)
        
        # Format columns if they exist
        if "doors_to_knock" in alloc_df.columns:
            alloc_df["doors_to_knock"] = alloc_df["doors_to_knock"].apply(lambda x: f"{x:,.0f}")
        if "volunteers_needed" in alloc_df.columns:
            alloc_df["volunteers_needed"] = alloc_df["volunteers_needed"].apply(lambda x: f"{x:,.0f}")
            
        st.dataframe(alloc_df, use_container_width=True)
    else:
        st.info("No resource allocation data found for this run.")

