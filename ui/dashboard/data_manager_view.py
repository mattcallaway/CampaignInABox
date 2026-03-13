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
    from ui.components.alerts import render_alert
    from ui.components.empty_state import render_empty_state
    from ui.components.badges import render_provenance_badge
    
    # Compute PROJECT_ROOT directly
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    st.markdown("<h1 class='page-title'>Data Manager</h1>", unsafe_allow_html=True)
    st.caption("Campaign data registry, file classification, and missing data tracker.")
    
    manager = FileRegistryManager(PROJECT_ROOT)
    registry = manager.load_registry()
    root_path = Path(PROJECT_ROOT)

    tab_upload, tab_registry, tab_missing = st.tabs([
        "📤 Upload New File", 
        "🗂️ File Registry", 
        "🔍 Missing Data Assistant"
    ])

    with tab_upload:
        st.subheader("Upload Campaign Files")
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

            # ── Election File Fingerprint Analysis (Prompt 25A.3) ─────────────
            st.markdown("#### 🔬 Election File Fingerprint")
            try:
                from engine.file_fingerprinting.fingerprint_engine import classify as fp_classify
                fp_result = fp_classify(temp_path, use_cache=False)

                if fp_result.file_type not in ("parse_error", "file_not_found", "unknown"):
                    conf_pct = int(fp_result.confidence * 100)
                    tier_color = "green" if conf_pct >= 85 else ("orange" if conf_pct >= 65 else "red")
                    st.success(
                        f"**{fp_result.display_name}** — "
                        f":{tier_color}[**{conf_pct}% confidence**]"
                    )
                    fp_c1, fp_c2, fp_c3, fp_c4 = st.columns(4)
                    fp_c1.metric("File Type", fp_result.display_name)
                    fp_c2.metric("Confidence", f"{conf_pct}%")
                    fp_c3.metric("Precinct Level", "✅ Yes" if fp_result.precinct_level else "❌ No")
                    fp_c4.metric("Contest Level", "✅ Yes" if fp_result.contest_level else "❌ No")

                    if fp_result.matching_headers:
                        st.caption(f"**Matched headers:** {', '.join(fp_result.matching_headers[:8])}")
                    if fp_result.precinct_format:
                        st.caption(f"**Precinct ID format:** `{fp_result.precinct_format}`")
                    if fp_result.optional_hits:
                        st.caption(f"**Optional matches:** {', '.join(fp_result.optional_hits[:6])}")

                    # Show all rule scores in expandable section
                    with st.expander("📊 All Rule Scores", expanded=False):
                        if fp_result.all_scores:
                            for rule_key, score in sorted(fp_result.all_scores.items(), key=lambda x: x[1], reverse=True):
                                bar = "█" * int(score * 20)
                                st.text(f"{rule_key:<30} {score:.3f}  {bar}")
                        else:
                            st.caption("No scores available (cached result).")
                elif fp_result.file_type == "unknown":
                    st.warning(
                        "⚠️ **Unknown file type** — could not match any election file fingerprint. "
                        "Check headers and format, or add a new rule to fingerprint_rules.yaml."
                    )
                    if fp_result.all_scores:
                        best = max(fp_result.all_scores.items(), key=lambda x: x[1])
                        st.caption(f"Closest match: `{best[0]}` at {best[1]:.2f}")
                else:
                    st.error(f"Fingerprint error: {fp_result.file_type}")
            except Exception as fp_err:
                st.caption(f"Fingerprint analysis unavailable: {fp_err}")

            classification = manager.classify_file(temp_path)
            cat  = classification["campaign_data_type"]
            prov = classification["provenance"]

            st.markdown("#### Classification & Destination")
            col1, col2 = st.columns(2)
            with col1:
                form_cat  = st.selectbox("Campaign Data Type", list(manager._DESTINATION_RULES.keys()), index=list(manager._DESTINATION_RULES.keys()).index(cat) if cat in manager._DESTINATION_RULES else 0)
                form_name = st.text_input("Filename", uploaded_file.name)
            
            with col2:
                opts = ["REAL", "EXTERNAL", "ESTIMATED", "SIMULATED"]
                form_prov = st.selectbox("Provenance", opts, index=opts.index(prov) if prov in opts else 1)
                form_state = st.text_input("State Code (e.g. CA)", "CA")
                form_county = st.text_input("County", "Sonoma")
                form_contest = st.text_input("Contest ID", "2025_prop50_special")

            proposed_dest = manager.propose_destination(form_name, form_cat, form_state, form_county, form_contest)
            render_alert("info", f"**Proposed Destination:** `{proposed_dest}`")

            form_notes = st.text_area("Notes (Optional)")

            if st.button("Confirm & Save File", type="primary"):
                try:
                    record = manager.register_new_file(
                        source_file=temp_path, category=form_cat, provenance=form_prov,
                        state=form_state, county=form_county, contest_id=form_contest,
                        notes=form_notes, proposed_name=form_name
                    )
                    if temp_path.exists(): temp_path.unlink()
                    st.success(f"File saved to `{record['current_path']}` and registered!")
                    st.rerun()
                except Exception as e:
                    render_alert("critical", f"Error saving file: {e}")

    with tab_registry:
        st.subheader("Active File Registry")
        if not registry:
            render_empty_state("No Files Uploaded", "The file registry is empty.", "🗂️", "Upload a file in the first tab.")
        else:
            df_reg = pd.DataFrame(registry)

            # ── Defensive column normalization ────────────────────────────────
            # Different writers (register_new_file, file_registry_pipeline, etc.)
            # may not include all fields. Fill missing columns with sensible defaults.
            _DEFAULT_COLS = {
                "status":             "ACTIVE",
                "last_modified":      "",
                "uploaded_at":        "",
                "file_id":            "",
                "current_filename":   "",
                "campaign_data_type": "unknown",
                "state":              "",
                "county":             "",
                "contest_id":         "",
                "provenance":         "UNKNOWN",
            }
            for col, default in _DEFAULT_COLS.items():
                if col not in df_reg.columns:
                    df_reg[col] = default
            # ── End defensive normalization ───────────────────────────────────

            view_status = st.radio("View", ["ACTIVE", "ARCHIVED", "ALL"], horizontal=True)
            if view_status != "ALL":
                if view_status == "ACTIVE":
                    df_reg = df_reg[df_reg["status"].isin(["ACTIVE", "REGISTERED"])]
                else:
                    df_reg = df_reg[df_reg["status"] == view_status]

            if df_reg.empty:
                render_empty_state("No Files Found", f"No {view_status.lower()} files currently exist.")
            else:
                # Only show columns that actually exist in the DataFrame
                _display_cols = ["file_id", "current_filename", "campaign_data_type",
                                 "state", "county", "contest_id", "provenance",
                                 "status", "last_modified"]
                disp_cols = [c for c in _display_cols if c in df_reg.columns]
                disp_df = df_reg[disp_cols]
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
                        if st.button("Update Metadata"):
                            manager.update_file(file_id=edit_id, new_name=new_name, new_category=new_cat)
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
                            render_alert("warning", "File is already archived.")

    with tab_missing:
        st.subheader("Missing Data & Source Finder")
        req_path = root_path / "derived" / "file_registry" / "latest" / "missing_data_requests.json"
        src_path = root_path / "derived" / "file_registry" / "latest" / "source_finder_recommendations.json"

        if not req_path.exists():
            render_empty_state("No Missing Data Analysis", "Run the pipeline to scan for gaps.", "🔍")
        else:
            try:
                missing_data = json.loads(req_path.read_text(encoding="utf-8"))
                reqs = missing_data.get("requests", [])
                
                if not reqs:
                    render_alert("success", "Your campaign has all required and recommended files!")
                else:
                    render_alert("warning", f"Your campaign is missing {len(reqs)} recommended files.")
                    
                    src_data = {}
                    if src_path.exists():
                        src_payload = json.loads(src_path.read_text(encoding="utf-8"))
                        for s in src_payload.get("recommendations", []):
                            src_data[s["data_type"]] = s

                    for req in reqs:
                        dt = req["data_type"]
                        prio = req["priority"]
                        a_type = "critical" if prio == "critical" else ("warning" if prio == "high" else "info")
                        
                        with st.expander(f"{dt.upper()} ({prio.upper()})"):
                            render_alert(a_type, req["why_needed"])
                            st.write(f"**Destination:** `{req['recommended_destination']}`")
                            
                            src = src_data.get(dt)
                            if src:
                                st.markdown("<div class='secondary-block'>", unsafe_allow_html=True)
                                st.markdown("##### 🌍 Source Recommendations")
                                st.write(f"**Likely Source:** {src['likely_source_type']}")
                                st.write(f"**Search Query:** `{src['search_keywords']}`")
                                for step in src["actionable_steps"]:
                                    st.markdown(f"- {step}")
                                st.markdown("</div>", unsafe_allow_html=True)
            except Exception as e:
                render_alert("critical", f"Error parsing payload: {e}")
