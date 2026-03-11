"""
ui/dashboard/data_manager_view.py — Prompt 17.5

The core UI for Campaign In A Box Data Intake.
- Upload dropzone + Classification
- File Registry Management Table (Rename, Relabel, Archive)
- Missing Data & Source Finder reporting
"""
import io
import json
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

from engine.data_intake.data_intake_manager import FileRegistryManager

def _badge(prov: str) -> str:
    color = "gray"
    if prov == "REAL":
        color = "green"
    elif prov == "EXTERNAL":
        color = "blue"
    elif prov == "ESTIMATED":
        color = "orange"
    elif prov == "SIMULATED":
        color = "violet"
    elif prov == "MISSING":
        color = "red"
    return f":{color}[**{prov}**]"

def _preview_file(file_path: Path):
    """Show inline preview of the file before uploading."""
    ext = file_path.suffix.lower()
    if ext in (".csv", ".tsv"):
        try:
            df = pd.read_csv(file_path, nrows=10)
            st.dataframe(df, use_container_width=True)
            st.caption(f"Detected {len(df.columns)} columns.")
        except Exception as e:
            st.error(f"Error reading CSV preview: {e}")
    elif ext in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(file_path, nrows=10)
            st.dataframe(df, use_container_width=True)
        except Exception:
            st.warning("Could not preview Excel file.")
    elif ext in (".geojson", ".json"):
        try:
            txt = file_path.read_text(encoding="utf-8")
            st.json(txt[:2000] + ("..." if len(txt) > 2000 else ""))
        except Exception:
            pass
    elif ext in (".md", ".txt"):
        try:
            st.text(file_path.read_text(encoding="utf-8")[:1000])
        except Exception:
            pass
    else:
        st.info(f"Binary or non-previewable format ({ext}).")

def render_data_manager(data: dict):
    from ui.dashboard.app import PROJECT_ROOT
    st.title("📂 Data Manager")
    
    manager = FileRegistryManager(PROJECT_ROOT)
    registry = manager.load_registry()

    root_path = Path(PROJECT_ROOT)

    tab_upload, tab_registry, tab_missing = st.tabs([
        "📤 Upload New File", 
        "🗂️ File Registry", 
        "🔍 Missing Data Assistant"
    ])

    with tab_upload:
        st.markdown("### Upload Campaign Files")
        st.markdown("Drop election results, voter files, crosswalks, polling, demographics, or ballot returns here.")
        
        uploaded_file = st.file_uploader("Select a file", type=["csv", "xlsx", "xls", "geojson", "zip", "md", "txt", "tsv", "json"])
        if uploaded_file:
            # Save to temporary path for classification
            temp_dir = root_path / "data" / "uploads" / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / uploaded_file.name
            temp_path.write_bytes(uploaded_file.getbuffer())

            st.markdown("#### File Preview")
            _preview_file(temp_path)

            classification = manager.classify_file(temp_path)
            cat  = classification["campaign_data_type"]
            prov = classification["provenance"]

            st.markdown("#### Classification & Destination")
            col1, col2 = st.columns(2)
            with col1:
                form_cat  = st.selectbox("Campaign Data Type", manager._DESTINATION_RULES.keys(), index=list(manager._DESTINATION_RULES.keys()).index(cat) if cat in manager._DESTINATION_RULES else 0)
                form_name = st.text_input("Filename", uploaded_file.name)
            
            with col2:
                form_prov = st.selectbox("Provenance", ["REAL", "EXTERNAL", "ESTIMATED", "SIMULATED"], index=["REAL", "EXTERNAL", "ESTIMATED", "SIMULATED"].index(prov) if prov in ["REAL", "EXTERNAL", "ESTIMATED", "SIMULATED"] else 1)
                form_state = st.text_input("State Code (e.g. CA)", "CA")
                form_county = st.text_input("County", "Sonoma")
                form_contest = st.text_input("Contest ID", "2025_prop50_special")

            proposed_dest = manager.propose_destination(form_name, form_cat, form_state, form_county, form_contest)
            st.info(f"**Proposed Destination:** `{proposed_dest}`")

            form_notes = st.text_area("Notes (Optional)")

            if st.button("Confirm & Save File", type="primary"):
                try:
                    record = manager.register_new_file(
                        source_file=temp_path,
                        category=form_cat,
                        provenance=form_prov,
                        state=form_state,
                        county=form_county,
                        contest_id=form_contest,
                        notes=form_notes,
                        proposed_name=form_name
                    )
                    # Cleanup temp
                    if temp_path.exists():
                        temp_path.unlink()
                    st.success(f"File saved to `{record['current_path']}` and registered as `{record['file_id']}`!")
                    # Force rerun to update registry view
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving file: {e}")

    with tab_registry:
        st.markdown("### Active File Registry")
        if not registry:
            st.info("The file registry is empty. Upload a file to get started.")
        else:
            # Convert string dates
            df_reg = pd.DataFrame(registry)
            
            # View toggle
            view_status = st.radio("View", ["ACTIVE", "ARCHIVED", "ALL"], horizontal=True)
            if view_status != "ALL":
                # REGISTERED is also considered active
                if view_status == "ACTIVE":
                    df_reg = df_reg[df_reg["status"].isin(["ACTIVE", "REGISTERED"])]
                else:
                    df_reg = df_reg[df_reg["status"] == view_status]

            if df_reg.empty:
                st.write(f"No {view_status.lower()} files found.")
            else:
                # Display table
                disp_df = df_reg[["file_id", "current_filename", "campaign_data_type", "state", "county", "contest_id", "provenance", "status", "last_modified", "current_path"]]
                st.dataframe(disp_df, use_container_width=True, hide_index=True)

                st.markdown("#### Manage Existing Files")
                edit_id = st.selectbox("Select File ID to Edit/Archive", disp_df["file_id"].tolist())
                
                if edit_id:
                    rec = next(r for r in registry if r["file_id"] == edit_id)
                    st.write(f"**Selected:** `{rec['current_filename']}` ({rec['campaign_data_type']})")

                    ecol1, ecol2 = st.columns(2)
                    with ecol1:
                        new_cat = st.selectbox("Change Category", list(manager._DESTINATION_RULES.keys()), index=list(manager._DESTINATION_RULES.keys()).index(rec["campaign_data_type"]))
                        new_name = st.text_input("Rename File", rec["current_filename"])
                        
                        if st.button("Update Metadata & Relocate"):
                            manager.update_file(
                                file_id=edit_id,
                                new_name=new_name,
                                new_category=new_cat
                            )
                            st.success("File updated successfully.")
                            st.rerun()

                    with ecol2:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        if rec["status"] != "ARCHIVED":
                            if st.button("🚨 Archive File", type="primary"):
                                manager.archive_file(edit_id)
                                st.success("File archived safely.")
                                st.rerun()
                        else:
                            st.warning("File is already archived.")

    with tab_missing:
        st.markdown("### Missing Data Assistant & Source Finder")
        
        req_path = root_path / "derived" / "file_registry" / "latest" / "missing_data_requests.json"
        src_path = root_path / "derived" / "file_registry" / "latest" / "source_finder_recommendations.json"

        if not req_path.exists():
            st.info("Missing Data Assistant has not run yet. Run the main pipeline (which now includes DATA_INTAKE_ANALYSIS step).")
        else:
            try:
                missing_data = json.loads(req_path.read_text(encoding="utf-8"))
                reqs = missing_data.get("requests", [])
                
                if not reqs:
                    st.success("✅ Your campaign has all required and recommended data files!")
                else:
                    st.warning(f"Your campaign is missing {len(reqs)} recommended data files.")
                    
                    src_data = {}
                    if src_path.exists():
                        src_payload = json.loads(src_path.read_text(encoding="utf-8"))
                        for s in src_payload.get("recommendations", []):
                            src_data[s["data_type"]] = s

                    for req in reqs:
                        dt = req["data_type"]
                        prio = req["priority"]
                        color = "red" if prio == "critical" else ("orange" if prio == "high" else "blue")
                        
                        with st.expander(f":{color}[**{dt.upper()}**] — Priority: {prio.upper()}"):
                            st.write(f"**Why needed:** {req['why_needed']}")
                            st.write(f"**Expected destination:** `{req['recommended_destination']}`")
                            st.write(f"**Example filename:** `{req['example_filename']}`")
                            
                            src = src_data.get(dt)
                            if src:
                                st.markdown("##### 🌍 Internet Source Finder Recommendations")
                                st.write(f"**Likely Source:** {src['likely_source_type']}")
                                st.write(f"**Search Query:** `{src['search_keywords']}`")
                                st.markdown("**Actionable Steps:**")
                                for step in src["actionable_steps"]:
                                    st.markdown(f"- {step}")
            except Exception as e:
                st.error(f"Error parsing missing data payload: {e}")
