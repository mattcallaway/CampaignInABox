"""
ui/dashboard/archive_view.py
Dashboard view for Historical Archive & Trend Analysis.
"""
import streamlit as st
import pandas as pd
from pathlib import Path
from ui.components.cards import metric_card

def render_archive_view(state: dict):
    st.markdown("<h2 class='page-header'>Historical Election Archive</h2>", unsafe_allow_html=True)
    st.markdown("<p class='subtext'>Review historical precinct behavior, train baseline models, and calibrate forecasts based on prior elections.</p>", unsafe_allow_html=True)
    
    archive = state.get("archive_summary", {})
    if not archive:
        st.warning("No historical archive data available. Please run the archive ingestion pipeline.")
        return
        
    cols = st.columns(4)
    with cols[0]:
        metric_card("Total Elections", archive.get("total_elections", 0), "Contests")
    with cols[1]:
        metric_card("Years Covered", f"{len(archive.get('years_covered', []))} Years", "-")
    with cols[2]:
        metric_card("Precinct Records", archive.get("total_precinct_records", 0), "Data points")
    with cols[3]:
        model_status = "Active" if state.get("historical_models_active") else "Inactive"
        metric_card("Models", model_status, "Support & Turnout")
        
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<h3 class='section-header'>Similar Historical Contests</h3>", unsafe_allow_html=True)
        similar = state.get("similar_elections", [])
        if similar:
            df = pd.DataFrame(similar)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No similar contest data available.")
            
    with c2:
        st.markdown("<h3 class='section-header'>Historical Coverage</h3>", unsafe_allow_html=True)
        types = archive.get("contest_types_present", [])
        st.write("Contains data across the following contest types:")
        for t in types:
            st.markdown(f"- **{t}**")
