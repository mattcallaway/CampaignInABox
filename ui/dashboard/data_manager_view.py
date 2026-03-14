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

    tab_upload, tab_registry, tab_precinct, tab_archive, tab_missing = st.tabs([
        "📤 Upload New File",
        "🗂️ File Registry",
        "🔎 Precinct ID Review",
        "🗃️ Election Archive",
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
            # Capture raw bytes NOW before any preview/fingerprint opens the file.
            # On Windows, openpyxl holds an exclusive lock, so we cannot
            # re-read from temp_path later. Store bytes in session_state.
            st.session_state["_upload_raw_bytes"] = uploaded_file.getvalue()

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
                form_name = st.text_input("Filename", uploaded_file.name, key="upload_filename")

            with col2:
                opts = ["REAL", "EXTERNAL", "ESTIMATED", "SIMULATED"]
                form_prov   = st.selectbox("Provenance", opts, index=opts.index(prov) if prov in opts else 1)
                form_state  = st.text_input("State Code (e.g. CA)", "CA", key="upload_state")
                form_county = st.text_input("County", "Sonoma", key="upload_county")
                form_contest = st.text_input("Contest Slug (e.g. nov2020_general)", "nov2020_general", key="upload_contest")
                form_year   = st.text_input("Year", "2020", key="upload_year")

            is_election_result = form_cat == "election_results"
            if is_election_result:
                canonical_dest = f"data/contests/{form_state}/{form_county}/{form_year}/{form_contest}/raw/{form_name}"
                render_alert("info", f"**Canonical Destination (P28):** `{canonical_dest}`")
                st.caption("Election result files are stored in the canonical contest structure and registered through ContestIntake.")
            else:
                proposed_dest = manager.propose_destination(form_name, form_cat, form_state, form_county, form_contest)
                render_alert("info", f"**Proposed Destination:** `{proposed_dest}`")

            form_notes = st.text_area("Notes (Optional)")

            if st.button("Confirm & Save File", type="primary"):
                try:
                    raw = st.session_state.get("_upload_raw_bytes")
                    if is_election_result:
                        # ── Canonical contest intake (P28) ──────────────────
                        from engine.contest_data.contest_intake import ContestIntake
                        intake = ContestIntake(PROJECT_ROOT)
                        record = intake.ingest(
                            source_file=temp_path,
                            state=form_state,
                            county=form_county,
                            year=form_year,
                            contest_slug=form_contest,
                            provenance=form_prov,
                            notes=form_notes,
                            raw_bytes=raw,
                            uploaded_by="ui_upload",
                            ingest_source="data_manager_ui",
                        )
                        dest_display = record.get("canonical_path", "")
                    else:
                        # ── Non-contest files: use legacy FileRegistryManager ─
                        record = manager.register_new_file(
                            source_file=temp_path, category=form_cat, provenance=form_prov,
                            state=form_state, county=form_county, contest_id=form_contest,
                            notes=form_notes, proposed_name=form_name,
                            raw_bytes=raw,
                        )
                        dest_display = record.get("current_path", "")
                    try:
                        if temp_path.exists():
                            temp_path.unlink()
                    except PermissionError:
                        pass
                    st.success(f"File saved to `{dest_display}` and registered!")
                    st.rerun()
                except Exception as e:
                    render_alert("critical", f"Error saving file: {e}")


    with tab_precinct:
        st.subheader("Precinct ID Review")
        st.markdown(
            "Inspect and validate precinct ID formats before archive ingestion. "
            "Ambiguous IDs are queued for review — they are **never auto-joined**."
        )

        pc1, pc2, pc3 = st.columns(3)
        p_state    = pc1.text_input("State", "CA", key="prec_state")
        p_county   = pc2.text_input("County", "Sonoma", key="prec_county")
        p_boundary = pc3.selectbox("Boundary Type", ["MPREC", "SRPREC", "CITY_PRECINCT", "UNKNOWN_LOCAL"])

        precinct_input = st.text_area(
            "Precinct IDs to validate (one per line or comma-separated)",
            placeholder="0400127\n400153\n127\nPCT-42\nSR 99",
            height=150,
        )

        if st.button("Run Precinct ID Check", type="primary") and precinct_input.strip():
            raw_ids = [
                v.strip() for line in precinct_input.splitlines()
                for v in line.split(",") if v.strip()
            ]
            try:
                from datetime import datetime as _dt
                from engine.precinct_ids.safe_join_engine import join_batch
                run_id = _dt.now().strftime("%Y%m%d__%H%M")
                batch = join_batch(raw_ids, p_state, p_county, p_boundary, run_id=run_id)

                st.markdown("#### Results")
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Total", batch.total)
                m2.metric("Exact", batch.exact_matches, delta=None)
                m3.metric("Crosswalk", batch.crosswalk_matches)
                m4.metric("Normalized", batch.normalized_matches)
                m5.metric("Ambiguous", batch.ambiguous,
                           delta=f"-{batch.ambiguous}" if batch.ambiguous else None,
                           delta_color="inverse" if batch.ambiguous else "off")
                m6.metric("Blocked", batch.blocked_cross_jurisdiction,
                           delta=f"-{batch.blocked_cross_jurisdiction}" if batch.blocked_cross_jurisdiction else None,
                           delta_color="inverse" if batch.blocked_cross_jurisdiction else "off")

                ready_pct = int(batch.archive_ready_fraction * 100)
                if ready_pct >= 90:
                    st.success(f"**Archive-ready: {ready_pct}%** — IDs are safe to join.")
                elif ready_pct >= 60:
                    st.warning(f"**Archive-ready: {ready_pct}%** — Some IDs need review.")
                else:
                    render_alert("critical", f"**Archive-ready: {ready_pct}%** — Too many ambiguous/unresolved IDs.")

                # Sample mapping table
                import pandas as _pd
                rows_df = _pd.DataFrame([{
                    "Raw ID":       r.raw_precinct,
                    "Schema":       r.detected_schema,
                    "Status":       r.join_status,
                    "Confidence":   f"{r.confidence:.2f}",
                    "Scoped Key":   r.resolved_scoped_key or "—",
                    "Reason":       r.reason[:80],
                } for r in batch.join_results])
                st.dataframe(rows_df, use_container_width=True, hide_index=True)

                # Review queue links
                if batch.ambiguous_csv:
                    from pathlib import Path as _P
                    render_alert("warning",
                        f"**{batch.ambiguous + batch.blocked_cross_jurisdiction} rows** written to review queue: "
                        f"`{_P(batch.ambiguous_csv).name}`"
                    )
                if batch.audit_report:
                    st.caption(f"Full audit: `{batch.audit_report}`")

            except Exception as e:
                render_alert("critical", f"Precinct ID check error: {e}")
        else:
            st.info("Enter precinct IDs above and click **Run Precinct ID Check** to validate.")

    with tab_archive:
        st.subheader("Election Archive")
        st.markdown(
            "Discover, classify, and ingest historical election datasets. "
            "Uses Source Registry to find official election pages, then fingerprints and validates files before archiving."
        )

        try:
            from engine.archive_builder.archive_registry import registry_summary, list_elections
            from engine.archive_builder.archive_builder import run_archive_build

            summary = registry_summary()
            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Archived Elections", summary.get("total", 0))
            a2.metric("States", len(summary.get("states", [])))
            a3.metric("Counties", len(summary.get("counties", [])))
            a4.metric("Avg Confidence", f"{summary.get('avg_confidence', 0):.1%}")

            elections = list_elections()
            if elections:
                import pandas as _pd
                df_arc = _pd.DataFrame(elections)[[
                    "election_id", "state", "county", "year", "election_type",
                    "confidence_score", "fingerprint_type", "ingestion_date",
                ]]
                st.dataframe(df_arc, use_container_width=True, hide_index=True)
            else:
                st.info("No elections archived yet. Run a scan below to discover and ingest election data.")

            st.markdown("---")
            st.markdown("#### Run Archive Scan")
            arc1, arc2 = st.columns(2)
            scan_state  = arc1.text_input("State", "CA", key="arc_state")
            scan_county = arc2.text_input("County", "Sonoma", key="arc_county")
            st.caption("Offline scan uses Source Registry metadata without making HTTP requests. Online scan discovers files from live election pages.")

            col_offline, col_online = st.columns(2)
            run_offline = col_offline.button("Run Offline Scan", type="primary")
            run_online  = col_online.button("Run Online Scan (HTTP)")

            if run_offline or run_online:
                with st.spinner("Running archive scan..."):
                    build = run_archive_build(
                        state=scan_state, county=scan_county,
                        online=run_online, download=False,
                    )
                st.markdown("#### Scan Results")
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("Sources Scanned", build.sources_scanned)
                s2.metric("Pages Found",     build.pages_found)
                s3.metric("Candidates",      build.candidates_found)
                s4.metric("Ingested",        build.ingested)

                if build.review_queue > 0:
                    render_alert("warning", f"**{build.review_queue} files** sent to review queue — check `derived/archive_review_queue/`")
                if build.errors:
                    render_alert("critical", f"**{len(build.errors)} errors** during build: {build.errors[0][:80]}")
                else:
                    st.success("Scan complete — no errors.")
                if build.build_report:
                    st.caption(f"Build report: `{build.build_report}`")
                if build.classification_report:
                    st.caption(f"Classification report: `{build.classification_report}`")

        except Exception as _arc_e:
            render_alert("critical", f"Election Archive error: {_arc_e}")

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
            # ── Normalise records for display (handles both old and new schemas) ──
            def _norm(r: dict) -> dict:
                """Return a display-friendly dict that works for both registry schemas."""
                is_canonical = bool(r.get("contest_slug") or r.get("canonical_path"))
                return {
                    "file_id":            r.get("file_id", "?"),
                    "filename":           r.get("current_filename") or r.get("canonical_filename") or r.get("original_filename", "?"),
                    "campaign_data_type": r.get("campaign_data_type") or ("election_results" if is_canonical else "unknown"),
                    "state":              r.get("state", ""),
                    "county":             r.get("county", ""),
                    "contest":            r.get("contest_id") or r.get("contest_slug", ""),
                    "year":               r.get("year", ""),
                    "provenance":         r.get("provenance", ""),
                    "status":             r.get("status") or r.get("archive_status", "ACTIVE"),
                    "last_modified":      r.get("last_modified", ""),
                    "is_canonical":       is_canonical,
                }

            norm_rows = [_norm(r) for r in registry]

            if view_status != "ALL":
                if view_status == "ACTIVE":
                    norm_rows = [r for r in norm_rows if r["status"] in ("ACTIVE", "REGISTERED")]
                else:
                    norm_rows = [r for r in norm_rows if r["status"] == view_status]

            if not norm_rows:
                render_empty_state("No Files Found", f"No {view_status.lower()} files currently exist.")
            else:
                import pandas as _pd
                disp_df = _pd.DataFrame(norm_rows)
                _display_cols = ["file_id", "filename", "campaign_data_type", "state",
                                  "county", "contest", "year", "provenance", "status", "is_canonical"]
                disp_cols = [c for c in _display_cols if c in disp_df.columns]
                st.dataframe(disp_df[disp_cols], use_container_width=True, hide_index=True)

                st.markdown("#### Manage Existing Files")
                edit_id = st.selectbox("Select File ID to Edit/Archive", disp_df["file_id"].tolist())
                if edit_id:
                    rec      = next(r for r in registry if r.get("file_id") == edit_id)
                    norm_rec = _norm(rec)
                    is_canonical = norm_rec["is_canonical"]

                    st.write(f"**Selected:** `{norm_rec['filename']}` ({norm_rec['campaign_data_type']})")
                    if is_canonical:
                        st.caption("ℹ️ This is a **canonical contest** record (P28). Only notes and archive status can be edited here.")

                    ecol1, ecol2 = st.columns(2)
                    with ecol1:
                        _cat_keys = list(manager._DESTINATION_RULES.keys())
                        _cur_cat  = norm_rec["campaign_data_type"]
                        _cat_idx  = _cat_keys.index(_cur_cat) if _cur_cat in _cat_keys else 0
                        new_cat   = st.selectbox("Change Category", _cat_keys, index=_cat_idx,
                                                  disabled=is_canonical)
                        new_name  = st.text_input("Rename File", norm_rec["filename"],
                                                   key=f"rename_{edit_id}", disabled=is_canonical)
                        if st.button("Update Metadata", disabled=is_canonical):
                            manager.update_file(file_id=edit_id, new_name=new_name, new_category=new_cat)
                            st.success("File updated successfully.")
                            st.rerun()
                        if is_canonical:
                            st.caption("Rename/category changes are managed in `data/contests/` manifests.")

                    with ecol2:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        if norm_rec["status"] != "ARCHIVED":
                            if st.button("🚨 Archive File", type="primary"):
                                if is_canonical:
                                    # For canonical records: update archive_status in canonical registry
                                    from engine.contest_data.contest_intake import ContestIntake
                                    ci = ContestIntake(root_path)
                                    ci._update_registry_record(edit_id, {"archive_status": "ARCHIVED"})
                                else:
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
