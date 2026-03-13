"""
ui/dashboard/source_registry_view.py — Prompt 25A / 25A.1

Source Registry Dashboard Page.

Shows all known contest and geometry sources with verification status,
confidence scoring, domain tier, and approval controls.
Prompt 25A.1 additions: Domain, Verified badge, Source Origin, Confidence Reason columns.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st


def render_source_registry(data: dict) -> None:
    """Render the Source Registry management page."""
    st.title("🗂️ Source Registry")
    st.markdown(
        "Manage known election result and geometry data sources. "
        "The registry is the first lookup layer for archive building and file discovery."
    )

    # ── Load Registry ─────────────────────────────────────────────────────────
    try:
        from engine.source_registry.source_registry import (
            load_contest_registry,
            load_geometry_registry,
        )
        from engine.source_registry.source_registry_updates import (
            approve_source,
            reject_source,
            mark_preferred,
            add_alias,
            add_notes,
        )
    except ImportError as e:
        st.error(f"Source registry module not found: {e}")
        return

    contest_sources  = load_contest_registry()
    geometry_sources = load_geometry_registry()

    # ── Run verification on all sources (offline/fast mode — no HTTP) ─────────
    _verified_cache: dict = {}
    try:
        from engine.source_registry.source_verifier import verify_source
        from engine.source_registry.confidence_engine import recalculate_source_confidence
        for src in contest_sources + geometry_sources:
            vr = verify_source(src, skip_http=True)
            rec = recalculate_source_confidence(src, vr)
            _verified_cache[src.get("source_id", "")] = rec
    except Exception:
        pass  # Verification optional — UI still works without it

    def _get_verified_rec(src: dict) -> dict:
        return _verified_cache.get(src.get("source_id", ""), src)

    # ── Summary Metrics ──────────────────────────────────────────────────────
    approved_contest  = sum(1 for s in contest_sources  if s.get("user_approved"))
    approved_geometry = sum(1 for s in geometry_sources if s.get("user_approved"))
    total_sources = len(contest_sources) + len(geometry_sources)
    total_approved = approved_contest + approved_geometry
    total_verified = sum(1 for r in _verified_cache.values() if r.get("verified"))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Contest Sources", len(contest_sources))
    c2.metric("Geometry Sources", len(geometry_sources))
    c3.metric("Verified", total_verified, delta=f"{total_verified}/{total_sources}")
    c4.metric("Approved", total_approved)
    c5.metric("Coverage", _coverage_label(total_sources))

    st.divider()

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_contest, tab_geo, tab_add = st.tabs([
        "🗳️ Contest Sources",
        "🗺️ Geometry Sources",
        "➕ Add Manual Source",
    ])

    # ─── Contest Sources Tab ─────────────────────────────────────────────────
    with tab_contest:
        st.subheader("Election Result Sources")

        # Filters
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            county_filter = st.selectbox(
                "Filter by County",
                ["All"] + sorted({s.get("county", "statewide") or "statewide" for s in contest_sources}),
                key="reg_county_filter",
            )
        with col_f2:
            year_filter = st.selectbox(
                "Filter by Year",
                ["All"] + sorted({str(s.get("year", "")) for s in contest_sources if s.get("year")}, reverse=True),
                key="reg_year_filter",
            )
        with col_f3:
            approval_filter = st.radio(
                "Approval Status", ["All", "Approved", "Unapproved"],
                horizontal=True, key="reg_approval_filter",
            )
        with col_f4:
            show_suspicious = st.toggle("Show Suspicious Sources Only", value=False, key="show_suspicious")

        # Apply filters
        filtered = list(contest_sources)
        if county_filter != "All":
            filtered = [s for s in filtered if (s.get("county") or "statewide") == county_filter]
        if year_filter != "All":
            filtered = [s for s in filtered if str(s.get("year", "")) == year_filter]
        if approval_filter == "Approved":
            filtered = [s for s in filtered if s.get("user_approved")]
        elif approval_filter == "Unapproved":
            filtered = [s for s in filtered if not s.get("user_approved")]
        if show_suspicious:
            filtered = [s for s in filtered
                        if not _get_verified_rec(s).get("verified", True)]

        st.caption(f"Showing {len(filtered)} of {len(contest_sources)} contest sources")

        for src in filtered:
            sid = src.get("source_id", "unknown")
            rec = _get_verified_rec(src)
            approved = src.get("user_approved", False)
            badge = "✅" if approved else "⬜"
            conf = rec.get("confidence_recalculated", src.get("confidence_default", 0.0))
            conf_orig = src.get("confidence_default", conf)
            verified = rec.get("verified", True)
            domain = rec.get("domain", "") or ""
            domain_tier = rec.get("domain_tier", "")
            origin = rec.get("source_origin", src.get("source_origin", "seeded_official"))

            # Color coding: green=verified official, yellow=unverified/discovered, red=invalid/suspicious
            if verified and domain_tier in ("gov_tier", "official_tier"):
                ver_badge = ":green[✅ Verified Official]"
            elif verified and domain_tier == "academic_tier":
                ver_badge = ":blue[✅ Verified Academic]"
            elif verified:
                ver_badge = ":yellow[⚠️ User Approved]"
            else:
                ver_badge = ":red[❌ Unverified]"

            conf_color = "🟢" if conf >= 0.90 else ("🟡" if conf >= 0.70 else "🔴")
            conf_changed = abs(conf - conf_orig) > 0.001
            conf_display = f"{conf:.2f}" + (f" *(was {conf_orig:.2f})*" if conf_changed else "")

            with st.expander(
                f"{badge} {conf_color} **{sid}** — {src.get('official_status','?')} | conf={conf_display}",
                expanded=False,
            ):
                col_a, col_b = st.columns([3, 1])

                with col_a:
                    # Verification status row
                    st.markdown(f"**Verification:** {ver_badge}  |  **Domain:** `{domain or 'local/no URL'}`  |  **Tier:** `{domain_tier}`")
                    st.markdown(f"**Source Origin:** `{origin}`")
                    if rec.get("confidence_reason"):
                        st.caption(f"Confidence reason: {rec['confidence_reason']}")
                    st.markdown(f"**Jurisdiction:** {src.get('state','?')}, {src.get('county','statewide')}")
                    st.markdown(f"**Year:** {src.get('year', 'any')}  |  **Type:** {src.get('election_type', 'any')}  |  **Source:** `{src.get('source_kind','?')}`")
                    if src.get("page_url") or src.get("base_url"):
                        url = src.get("page_url") or src.get("base_url")
                        st.markdown(f"**URL:** [{url[:60]}...]({url})")
                    if src.get("file_patterns"):
                        st.markdown(f"**File patterns:** `{', '.join(src['file_patterns'])}`")
                    if src.get("notes"):
                        st.caption(str(src["notes"])[:200])

                with col_b:
                    if not approved:
                        if st.button("✅ Approve", key=f"approve_{sid}", use_container_width=True):
                            if approve_source(sid, notes="Approved via Source Registry UI"):
                                st.success(f"Approved: {sid}")
                                st.rerun()
                    else:
                        if st.button("❌ Reject", key=f"reject_{sid}", use_container_width=True):
                            if reject_source(sid, notes="Rejected via Source Registry UI"):
                                st.warning(f"Rejected: {sid}")
                                st.rerun()

                    # Add alias
                    alias_input = st.text_input(
                        "Add alias", key=f"alias_{sid}", placeholder="e.g. Prop 50"
                    )
                    if st.button("Add Alias", key=f"alias_btn_{sid}", use_container_width=True):
                        if alias_input.strip():
                            add_alias(sid, alias_input.strip())
                            st.success("Alias added")
                            st.rerun()

                    # Notes
                    note_input = st.text_area(
                        "Add note", key=f"note_{sid}", height=60, placeholder="Optional note..."
                    )
                    if st.button("Save Note", key=f"note_btn_{sid}", use_container_width=True):
                        if note_input.strip():
                            add_notes(sid, note_input.strip())
                            st.success("Note saved")

    # ─── Geometry Sources Tab ─────────────────────────────────────────────────
    with tab_geo:
        st.subheader("Geometry & Crosswalk Sources")

        boundary_filter = st.selectbox(
            "Filter by Boundary Type",
            ["All"] + sorted({s.get("boundary_type", "unknown") for s in geometry_sources}),
            key="geo_boundary_filter",
        )

        geo_filtered = list(geometry_sources)
        if boundary_filter != "All":
            geo_filtered = [s for s in geo_filtered if s.get("boundary_type") == boundary_filter]

        for src in geo_filtered:
            sid = src.get("source_id", "unknown")
            rec = _get_verified_rec(src)
            preferred = src.get("preferred", False)
            approved  = src.get("user_approved", False)
            badge_pref = "⭐" if preferred else "  "
            badge_appr = "✅" if approved else "⬜"
            conf = rec.get("confidence_recalculated", src.get("confidence_default", 0.0))
            conf_orig = src.get("confidence_default", conf)
            verified = rec.get("verified", True)
            domain = rec.get("domain", "") or ""
            domain_tier = rec.get("domain_tier", "")
            origin = rec.get("source_origin", src.get("source_origin", "seeded_official"))
            conf_changed = abs(conf - conf_orig) > 0.001
            conf_display = f"{conf:.2f}" + (f" *(was {conf_orig:.2f})*" if conf_changed else "")

            if verified and domain_tier in ("gov_tier", "official_tier"):
                ver_badge = ":green[✅ Verified Official]"
            elif verified and domain_tier == "academic_tier":
                ver_badge = ":blue[✅ Verified Academic]"
            elif not domain:
                ver_badge = ":yellow[📁 Local File]"
            else:
                ver_badge = ":red[❌ Unverified]"

            with st.expander(
                f"{badge_appr} {badge_pref} **{sid}** — {src.get('boundary_type','?')} | conf={conf_display}",
                expanded=False,
            ):
                col_a, col_b = st.columns([3, 1])

                with col_a:
                    st.markdown(f"**Verification:** {ver_badge}  |  **Domain:** `{domain or 'local/no URL'}`  |  **Tier:** `{domain_tier}`")
                    st.markdown(f"**Source Origin:** `{origin}`")
                    if rec.get("confidence_reason"):
                        st.caption(f"Confidence reason: {rec['confidence_reason']}")
                    st.markdown(f"**State:** {src.get('state')} | **County:** {src.get('county', 'statewide')}")
                    st.markdown(f"**Boundary type:** `{src.get('boundary_type')}` | **Source:** `{src.get('source_kind')}`")
                    if src.get("id_field_name"):
                        st.markdown(f"**ID field:** `{src['id_field_name']}` | **Name field:** `{src.get('name_field_name','?')}`")
                    if src.get("crosswalk_targets"):
                        st.markdown(f"**Crosswalk:** {' <-> '.join(src['crosswalk_targets'])}")
                    if src.get("page_url") or src.get("base_url"):
                        url = src.get("page_url") or src.get("base_url")
                        st.markdown(f"**URL:** [{url[:60]}...]({url})")
                    if src.get("notes"):
                        st.caption(str(src["notes"])[:200])

                with col_b:
                    if not preferred:
                        if st.button("⭐ Set Preferred", key=f"pref_{sid}", use_container_width=True):
                            mark_preferred(sid)
                            st.success("Marked preferred")
                            st.rerun()

                    if not approved:
                        if st.button("✅ Approve", key=f"geo_approve_{sid}", use_container_width=True):
                            approve_source(sid, notes="Approved via Source Registry UI")
                            st.success("Approved")
                            st.rerun()
                    else:
                        if st.button("❌ Reject", key=f"geo_reject_{sid}", use_container_width=True):
                            reject_source(sid, notes="Rejected via Source Registry UI")
                            st.warning("Rejected")
                            st.rerun()

    # ─── Add Manual Source Tab ────────────────────────────────────────────────
    with tab_add:
        st.subheader("Add Manual Source")
        st.info(
            "Use this form to register a source that is not in the seeded registry. "
            "Manual sources are saved to `config/source_registry/local_overrides.yaml`."
        )

        source_type = st.radio("Source type", ["Contest", "Geometry"], horizontal=True)

        with st.form(key="add_manual_source_form"):
            col1, col2 = st.columns(2)

            with col1:
                new_sid             = st.text_input("Source ID*", placeholder="ca_sonoma_2025_prop50_special")
                new_state           = st.text_input("State*", value="CA")
                new_county          = st.text_input("County", value="Sonoma")
                new_source_kind     = st.selectbox("Source Kind*", [
                    "county_registrar", "state_sos", "electionstats_database",
                    "clarity_enr", "document_archive", "manual_upload", "data_vendor",
                ])
                new_official_status = st.selectbox("Official Status*", [
                    "certified", "official", "preliminary", "estimated", "unofficial", "unknown",
                ])
                new_confidence      = st.slider("Default Confidence", 0.0, 1.0, 0.80, 0.05)

            with col2:
                new_url    = st.text_input("Page URL", placeholder="https://...")
                new_year   = st.number_input("Year", min_value=2000, max_value=2040, value=2024, step=1)
                new_elec_type = st.selectbox("Election Type", [
                    "general", "primary", "special", "runoff", "recall", "consolidated", "presidential", ""
                ])
                new_contest_name = st.text_input("Contest Name", placeholder="Measure B — Parks")
                new_auto_ingest  = st.checkbox("Auto-ingest allowed", value=False)
                new_req_confirm  = st.checkbox("Requires confirmation", value=True)
                new_notes        = st.text_area("Notes", height=80)

            submitted = st.form_submit_button("➕ Add to Registry")

        if submitted:
            if not new_sid.strip():
                st.error("Source ID is required.")
            else:
                entry = {
                    "source_id":           new_sid.strip(),
                    "state":               new_state.strip().upper(),
                    "county":              new_county.strip() or None,
                    "source_kind":         new_source_kind,
                    "official_status":     new_official_status,
                    "confidence_default":  float(new_confidence),
                    "auto_ingest_allowed": new_auto_ingest,
                    "requires_confirmation": new_req_confirm,
                    "user_approved":       True,
                    "notes":               new_notes.strip() or None,
                }
                if new_url.strip():
                    entry["page_url"] = new_url.strip()
                if new_year:
                    entry["year"] = int(new_year)
                if new_elec_type:
                    entry["election_type"] = new_elec_type
                if new_contest_name.strip():
                    entry["contest_name"] = new_contest_name.strip()

                from engine.source_registry.source_registry_updates import (
                    add_manual_contest_source, add_manual_geometry_source,
                )
                if source_type == "Contest":
                    ok = add_manual_contest_source(entry)
                else:
                    ok = add_manual_geometry_source(entry)

                if ok:
                    st.success(f"✅ Source `{new_sid}` added to local_overrides.yaml")
                    # Force reload next time
                    from engine.source_registry import source_registry as sr
                    sr._contest_registry  = None
                    sr._geometry_registry = None
                else:
                    st.error("Failed to save source.")

    st.divider()

    # ── Registry Diagnostics ─────────────────────────────────────────────────
    with st.expander("🔍 Registry Diagnostics & Repair", expanded=False):
        col_diag1, col_diag2 = st.columns(2)
        with col_diag1:
            if st.button("Generate Registry Report", key="run_reg_report", use_container_width=True):
                with st.spinner("Generating source registry diagnostics…"):
                    try:
                        from engine.source_registry.source_registry_report import run_registry_report
                        from datetime import datetime
                        run_id = datetime.now().strftime("%Y%m%d__%H%M")
                        summary = run_registry_report(run_id=run_id)
                        st.success(
                            f"Registry report: {summary['contest_sources']} contest, "
                            f"{summary['geometry_sources']} geometry sources. "
                            f"Coverage: **{summary['registry_coverage']}**"
                        )
                        st.info(f"Report: `{summary['report_path']}`")
                    except Exception as e:
                        st.error(f"Error generating report: {e}")

        with col_diag2:
            if st.button("Run Registry Repair (Confidence Audit)", key="run_reg_repair", use_container_width=True):
                with st.spinner("Running confidence recalculation and suspicious source scan…"):
                    try:
                        from engine.source_registry.registry_repair import run_registry_repair
                        from datetime import datetime
                        run_id = datetime.now().strftime("%Y%m%d__%H%M")
                        repair_summary = run_registry_repair(run_id=run_id, skip_http=True)
                        st.success(
                            f"Repair complete: {repair_summary['total_sources']} sources | "
                            f"Verified: {repair_summary['verified_sources']} | "
                            f"Suspicious: {repair_summary['suspicious_entries']} | "
                            f"Coverage: **{repair_summary['registry_coverage']}**"
                        )
                        st.info(f"Report: `{repair_summary['report_path']}`")
                        if repair_summary['suspicious_entries'] > 0:
                            st.warning(f"{repair_summary['suspicious_entries']} suspicious sources found — see report.")
                    except Exception as e:
                        st.error(f"Error running repair: {e}")


def _coverage_label(total: int) -> str:
    if total >= 10:
        return "Strong"
    elif total >= 5:
        return "Good"
    elif total >= 1:
        return "Partial"
    return "None"
