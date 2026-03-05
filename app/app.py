"""
Campaign In A Box — Web UI
app/app.py

Run with:
    cd "Campaign In A Box"
    streamlit run app/app.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st
import yaml

# ── Bootstrap sys.path ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "app") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "app"))

from .lib.county_manager import (
    discover_counties, initialize_county, get_geography_status, discover_contests, read_manifest,
    ALL_CATEGORY_LABELS,
)
from .lib.upload_handler import save_geography_files, save_votes_file, save_voter_file
from .lib.pipeline_runner import run_pipeline_streaming, get_latest_run_id, read_latest_artifact
from .lib.output_browser import (
    discover_run_artifacts, discover_log_artifacts, discover_all_run_logs,
    read_file_safe, get_needs_summary,
)
from .lib.state_manager import get_stale_status, mark_pipeline_success
from .lib.archiver import list_archives
from scripts.lib.naming import normalize_county, normalize_contest_slug, generate_contest_id
from scripts.lib.hashing import _sha256_bytes

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Campaign In A Box",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Core palette */
    :root {
        --primary: #1E3A5F;
        --accent:  #2563EB;
        --success: #16A34A;
        --warn:    #D97706;
        --danger:  #DC2626;
        --bg:      #F8FAFC;
        --card:    #FFFFFF;
        --border:  #E2E8F0;
        --text:    #1E293B;
        --muted:   #64748B;
    }
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1E3A5F 0%, #0F2340 100%);
        color: white;
    }
    [data-testid="stSidebar"] .stRadio label { color: white !important; font-size: 15px; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p { color: white !important; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #CBD5E1 !important; }

    /* Main header */
    .ciab-header {
        background: linear-gradient(135deg, #1E3A5F 0%, #2563EB 100%);
        border-radius: 12px;
        padding: 20px 28px;
        margin-bottom: 24px;
        color: white;
    }
    .ciab-header h1 { color: white !important; margin: 0; font-size: 1.8rem; }
    .ciab-header p  { color: #BFDBFE !important; margin: 4px 0 0 0; }

    /* Status cards */
    .status-card {
        background: white;
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .status-present { border-left: 4px solid #16A34A; }
    .status-missing  { border-left: 4px solid #DC2626; }

    /* Log viewer */
    .log-box {
        font-family: 'Courier New', monospace;
        font-size: 12px;
        background: #0F172A;
        color: #94A3B8;
        padding: 16px;
        border-radius: 8px;
        overflow-y: auto;
        max-height: 500px;
        white-space: pre-wrap;
    }
    .log-ok   { color: #4ADE80; }
    .log-warn { color: #FBBF24; }
    .log-fail { color: #F87171; }
    .log-step { color: #60A5FA; }

    /* Metric row */
    .metric-row { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
    .metric-box {
        background: white; border: 1px solid #E2E8F0; border-radius: 10px;
        padding: 14px 20px; flex: 1; min-width: 150px; text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-val { font-size: 2rem; font-weight: 700; color: #1E3A5F; }
    .metric-lbl { font-size: 0.8rem; color: #64748B; margin-top: 4px; }

    /* Needs viewer */
    .need-missing { color: #DC2626; font-weight: 600; }
    .need-blocked  { color: #D97706; font-weight: 600; }
    .need-ok       { color: #16A34A; }

    /* Run banner */
    .run-success {
        background: #F0FDF4; border: 2px solid #16A34A;
        border-radius: 10px; padding: 16px 20px; margin: 12px 0;
    }
    .run-partial {
        background: #FFFBEB; border: 2px solid #D97706;
        border-radius: 10px; padding: 16px 20px; margin: 12px 0;
    }
    .run-fail {
        background: #FEF2F2; border: 2px solid #DC2626;
        border-radius: 10px; padding: 16px 20px; margin: 12px 0;
    }
    button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #1E3A5F, #2563EB) !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗳️ Campaign In A Box")
    st.markdown("*California Election Modeling*")
    st.divider()
    page = st.radio(
        "Navigation",
        [
            "🏛️ Jurisdiction", 
            "📤 Upload New Data", 
            "🔄 Update Center", 
            "🕰️ Version Browser",
            "▶️ Run Pipeline",
            "📊 Outputs Browser", 
            "📋 Logs & NEEDS",
            "📜 County Registry"
        ],
        label_visibility="collapsed",
    )
    st.divider()
    counties = discover_counties()
    if counties:
        st.markdown(f"**{len(counties)} counties initialized**")
        for c in counties[:8]:
            st.markdown(f"  • {c}")
        if len(counties) > 8:
            st.markdown(f"  *…and {len(counties) - 8} more*")

    run_id = get_latest_run_id()
    if run_id:
        st.divider()
        st.markdown("**Latest run:**")
        st.code(run_id, language=None)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1: JURISDICTION SELECTOR / CREATOR
# ═════════════════════════════════════════════════════════════════════════════
if page == "🏛️ Jurisdiction":
    st.markdown("""
    <div class='ciab-header'>
        <h1>🏛️ Jurisdiction Manager</h1>
        <p>Initialize and inspect California county data packs</p>
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Create / Select County")
        
        from scripts.lib.county_registry import load_county_registry
        reg = load_county_registry()
        all_counties_fmt = [f"{c['county_name']} ({c['county_fips']})" for c in reg.get_all()]
        
        existing = discover_counties()
        # Prepend visually which ones are initialized
        
        county_sel = st.selectbox(
            "Select California County", 
            ["— select —"] + all_counties_fmt,
            help="Select any of the 58 canonical CA counties."
        )
        
        if existing:
            selected_from_exists = st.selectbox(
                "Or quickly pick an initialized county", ["— select —"] + [f"{e} (initialized)" for e in existing]
            )
            if selected_from_exists != "— select —" and county_sel == "— select —":
                county_sel = selected_from_exists.replace(" (initialized)", "")
                # the input gets matched below via normalization anyway

        county_input = ""
        if county_sel != "— select —":
            county_input = county_sel.split(" (")[0]

        state = "CA"

        if county_input:
            if st.button("✅ Initialize / Verify County", type="primary", use_container_width=True):
                from scripts.lib.county_registry import normalize_county_input
                try:
                    c_record = normalize_county_input(county_input)
                    name = c_record['county_name']
                    slug = c_record['county_slug']
                    fips = c_record['county_fips']
                    
                    with st.spinner(f"Initializing {name} ({fips})…"):
                        geo_dir = initialize_county(name, state)
                    st.success(f"✅ County **{name}** verified at `{geo_dir}`\n\nCanonical Slug: `{slug}` | FIPS: `{fips}`")
                    time.sleep(1.5)
                    st.rerun()
                except ValueError as e:
                    st.error(f"❌ {e}")

    with col2:
        if county_input:
            st.subheader(f"Geography Status — {county_input}, {state}")
            status = get_geography_status(county_input, state)
            present = [k for k, v in status.items() if v]
            missing = [k for k, v in status.items() if not v]

            # Metrics
            st.markdown(f"""
            <div class='metric-row'>
                <div class='metric-box'>
                    <div class='metric-val' style='color:#16A34A'>{len(present)}</div>
                    <div class='metric-lbl'>Categories Present</div>
                </div>
                <div class='metric-box'>
                    <div class='metric-val' style='color:#DC2626'>{len(missing)}</div>
                    <div class='metric-lbl'>Categories Missing</div>
                </div>
                <div class='metric-box'>
                    <div class='metric-val'>{len(ALL_CATEGORY_LABELS)}</div>
                    <div class='metric-lbl'>Total Categories</div>
                </div>
            </div>""", unsafe_allow_html=True)

            # Category grid
            for label in ALL_CATEGORY_LABELS:
                ok = status[label]
                icon  = "✅" if ok else "❌"
                cls   = "status-present" if ok else "status-missing"
                badge = "present" if ok else "missing"
                st.markdown(
                    f"<div class='status-card {cls}'>"
                    f"{icon} <strong>{label}</strong> "
                    f"<span style='color:{'#16A34A' if ok else '#DC2626'};float:right'>{badge}</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )

            mf = read_manifest(county_input, state)
            if mf:
                st.subheader("Manifest Summary")
                st.json({
                    "canonical_geography": mf.get("canonical_geography"),
                    "categories_present":  mf.get("categories_present", []),
                    "categories_missing":  mf.get("categories_missing", []),
                    "generated_at":        mf.get("generated_at"),
                })
        else:
            st.info("👈 Enter a county name to see its status.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2: UPLOAD NEW DATA (Initial ingest)
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📤 Upload New Data":
    st.markdown("""
    <div class='ciab-header'>
        <h1>📤 Upload New Data</h1>
        <p>Initialize geography packs, election results, and voter files</p>
    </div>""", unsafe_allow_html=True)

    existing_counties = discover_counties()
    county = st.selectbox(
        "County", ["— select / type below —"] + existing_counties,
        help="Select an initialized county or type a new one below",
    )
    county_override = st.text_input("Or type county name", placeholder="e.g. Los Angeles")
    county = county_override.strip() or (county if county != "— select / type below —" else "")

    if not county:
        st.warning("Select or enter a county name above to continue.")
        st.stop()

    tab_a, tab_b, tab_c = st.tabs([
        "🗺️ A — Geography Pack", "🗳️ B — Election Results", "👥 C — Voter File"
    ])

    # ── Tab A: Geography ──────────────────────────────────────────────────────
    with tab_a:
        st.subheader(f"Upload Geography Files — {county}")
        st.markdown(
            "Upload GeoJSON, GeoPackage, Shapefile bundles, or crosswalk CSVs. "
            "Select the correct category so files are routed to the right folder."
        )

        category = st.selectbox("File category", ALL_CATEGORY_LABELS)
        is_shapefile = "Shapefile" in category

        if is_shapefile:
            st.info(
                "📦 **Shapefile bundle**: upload `.shp`, `.shx`, `.dbf` together "
                "(also `.prj`, `.cpg`, `.qix` if available). "
                "The UI will warn if required sidecar files are missing."
            )

        uploaded = st.file_uploader(
            f"Choose files for: **{category}**",
            accept_multiple_files=True,
            key=f"geo_upload_{category}",
        )

        if uploaded:
            exts = {Path(f.name).suffix.lower() for f in uploaded}
            st.write(f"**{len(uploaded)} file(s) selected:** {', '.join(f.name for f in uploaded)}")

            from app.lib.upload_handler import detect_county_from_filenames
            detected_county, method = detect_county_from_filenames([f.name for f in uploaded])
            
            target_county = county
            if detected_county and detected_county != county:
                st.info(f"🔍 **Auto-detected county:** `{detected_county}` (via {method}).")
                target_county = detected_county

            if not target_county:
                st.error("❌ Need a county to proceed. Please select/type one above, or ensure your filenames contain FIPS codes (e.g. c097_).")
            else:
                from scripts.lib.county_registry import normalize_county_input
                try:
                    c_record = normalize_county_input(target_county)
                    final_county = c_record['county_name']
                    
                    if st.button(f"💾 Save to {final_county} Geography", type="primary", use_container_width=True):
                        # Initialize county if not exist
                        initialize_county(final_county)
                        with st.spinner("Saving files…"):
                            saved, warnings = save_geography_files(uploaded, category, final_county, detection_method=method)

                        if warnings:
                            for w in warnings:
                                st.warning(f"⚠️ {w}")

                        st.success(f"✅ Saved {len(saved)} file(s) to `{category}` for **{final_county}**")
                        for rec in saved:
                            st.markdown(
                                f"  • `{rec['filename']}` — {rec['size_bytes']:,} bytes — "
                                f"sha256:`{rec['sha256'][:12]}…`"
                            )

                        # Refresh status
                        st.subheader("Updated Geography Status")
                        status = get_geography_status(final_county)
                        for label in ALL_CATEGORY_LABELS:
                            ok = status[label]
                            st.markdown(
                                f"{'✅' if ok else '❌'} **{label}**",
                                unsafe_allow_html=False,
                            )
                except ValueError as e:
                    st.error(f"❌ {e}")

    # ── Tab B: Election Results ───────────────────────────────────────────────
    with tab_b:
        st.subheader(f"Upload Election Results — {county}")

        col1, col2 = st.columns(2)
        with col1:
            year = st.text_input("Election year", value="2024", max_chars=4)
        with col2:
            detail_file = st.file_uploader(
                "detail.xlsx or detail.xls",
                type=["xlsx", "xls"],
                key="votes_upload",
            )

        if detail_file:
            # Auto-suggest contest slug from filename
            raw_slug = Path(detail_file.name).stem
            auto_slug = normalize_contest_slug(raw_slug)
            if auto_slug in ("detail", ""):
                auto_slug = f"contest_{year}"

        contest_slug = st.text_input(
            "Contest slug",
            value=auto_slug if detail_file else "",
            placeholder="e.g. nov2024_general",
            help="Used as folder name under votes/<year>/CA/<county>/",
        )

        if contest_slug:
            # Preview normalization
            canon_slug = normalize_contest_slug(contest_slug)
            if canon_slug != contest_slug:
                st.info(f"💡 Slug will be normalized to: `{canon_slug}`")
            
            try:
                _, c_slug, _ = normalize_county(county)
                cid = generate_contest_id(year, "CA", c_slug, canon_slug)
                st.caption(f"Canonical Contest ID: `{cid}`")
            except Exception:
                pass

        if detail_file and contest_slug and year:
            st.info(
                f"Will write to: `votes/{year}/CA/{county}/{contest_slug}/detail{Path(detail_file.name).suffix}`"
            )
            if st.button("💾 Save Election Results", type="primary", use_container_width=True):
                canon_slug = normalize_contest_slug(contest_slug)
                with st.spinner("Saving…"):
                    dest, cj = save_votes_file(detail_file, year, county, canon_slug)
                st.success(f"✅ Saved `{dest.name}` to `votes/{year}/CA/{county}/{canon_slug}/`")
                st.markdown(f"  • `contest.json` updated with canonical identifiers at: `{cj}`")

    # ── Tab C: Voter File ─────────────────────────────────────────────────────
    with tab_c:
        st.subheader(f"Upload Voter File — {county} (Optional)")
        st.markdown(
            "Voter files are stored in `voters/CA/<county>/` and are excluded from Git by `.gitignore`. "
            "They are marked 'optional present' in the county manifest."
        )

        voter_file = st.file_uploader(
            "Upload voter file (any format)",
            key="voter_upload",
        )
        if voter_file:
            if st.button("💾 Save Voter File", type="primary", use_container_width=True):
                dest = save_voter_file(voter_file, county)
                st.success(f"✅ Voter file saved to `{dest}`")
                st.info("📋 Voter files are gitignored and will not be committed.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 3: UPDATE CENTER (Replace & Archive)
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🔄 Update Center":
    st.markdown("""
    <div class='ciab-header'>
        <h1>🔄 Update Center</h1>
        <p>Safely replace raw files. Old versions are archived, and downstream outputs are marked stale.</p>
    </div>""", unsafe_allow_html=True)

    counties = discover_counties()
    if not counties:
        st.info("No counties initialized.")
        st.stop()

    county = st.selectbox("Select County to Update", counties)

    tab_votes, tab_geo = st.tabs(["🗳️ Update Votes", "🗺️ Update Geography"])

    # ── Update Votes ────────────────────────────────────────────────────────
    with tab_votes:
        st.subheader(f"Update Election Results — {county}")
        contests = discover_contests()
        county_contests = [c for c in contests if c["county"] == county]
        
        if not county_contests:
            st.info("No contests found for this county.")
        else:
            c_opts = [f"{c['year']} / {c['contest_slug']}" for c in county_contests]
            sel = st.selectbox("Select Contest to Update", c_opts)
            c_idx = c_opts.index(sel)
            c_data = county_contests[c_idx]
            year = c_data["year"]
            contest_slug = c_data["contest_slug"]

            votes_path = BASE_DIR / "votes" / year / "CA" / county / contest_slug / "detail.xlsx"
            if not votes_path.exists():
                votes_path = BASE_DIR / "votes" / year / "CA" / county / contest_slug / "detail.xls"

            if votes_path.exists():
                st.markdown(f"**Current File:** `{votes_path.name}`")
                sz = votes_path.stat().st_size
                st.markdown(f"**Size:** {sz:,} bytes")
                
                new_file = st.file_uploader(
                    "Upload Replacement Workbook (detail.xlsx or detail.xls)",
                    type=["xlsx", "xls"],
                    key="update_votes_upload",
                )
                
                if new_file:
                    new_data = new_file.getvalue()
                    new_sz = len(new_data)
                    new_sha = _sha256_bytes(new_data)
                    old_sha = _sha256_bytes(votes_path.read_bytes())
                    
                    st.markdown("### Update Summary")
                    st.markdown(f"- **Old size:** {sz:,} bytes")
                    st.markdown(f"- **New size:** {new_sz:,} bytes")
                    
                    if old_sha == new_sha:
                        st.warning("⚠️ The uploaded file is perfectly identical to the current file (same SHA-256 hash).")
                        
                    confirm = st.checkbox("I confirm I want to archive the old file and replace it.")
                    if confirm and st.button("Archive & Replace Votes", type="primary", use_container_width=True):
                        with st.spinner("Archiving and updating..."):
                            save_votes_file(new_file, year, county, contest_slug)
                        st.success("✅ Votes updated! Old version archived. Derived outputs marked stale.")
                        st.rerun()
            else:
                st.warning("No detail.xlsx found for this contest. Use Upload New Data to initialize it.")

    # ── Update Geography ────────────────────────────────────────────────────
    with tab_geo:
        st.subheader(f"Update Geography Files — {county}")
        category = st.selectbox("Select Category to Update", ALL_CATEGORY_LABELS, key="upd_geo_cat")
        
        mf = read_manifest(county, "CA") or {}
        cat_files = [f for f in mf.get("files", []) if f.get("category_label") == category]
        
        if not cat_files:
            st.info(f"No files currently exist for {category}. Use Upload New Data.")
        else:
            st.markdown(f"**Current Files in {category}:**")
            for cf in cat_files:
                st.markdown(f"- `{cf.get('filename')}` ({cf.get('size_bytes', 0):,} bytes)")
                
            new_geo = st.file_uploader(
                f"Upload Replacement for {category}",
                accept_multiple_files=True,
                key="update_geo_upload",
            )
            
            if new_geo:
                # new_geo can be a single file or list. Wrap in list if needed.
                if not isinstance(new_geo, list):
                    new_geo = [new_geo]
                    
                confirm_geo = st.checkbox("I confirm I want to archive the existing files in this category and replace them.")
                if confirm_geo and st.button("Archive & Replace Geography", type="primary", use_container_width=True):
                    with st.spinner("Archiving and updating..."):
                        saved, warns = save_geography_files(new_geo, category, county)
                    if warns:
                        for w in warns:
                            st.warning(f"⚠️ {w}")
                    else:
                        st.success("✅ Geography updated! Old version archived. Memberships and dependencies marked stale.")
                        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 4: VERSION BROWSER
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🕰️ Version Browser":
    st.markdown("""
    <div class='ciab-header'>
        <h1>🕰️ Version Browser</h1>
        <p>Inspect archived data versions and roll back if necessary.</p>
    </div>""", unsafe_allow_html=True)
    
    counties = discover_counties()
    county = st.selectbox("Select County to inspect archives", counties if counties else ["— none —"])
    
    if county != "— none —":
        domain = st.radio("Domain", ["Votes", "Geography"])
        
        if domain == "Votes":
            contests = discover_contests()
            c_opts = [f"{c['year']} / {c['contest_slug']}" for c in contests if c["county"] == county]
            if not c_opts:
                st.info("No contests found.")
            else:
                if c_opts:
                    sel = st.selectbox("Select Contest", c_opts)
                    if sel:
                        year = str(sel).split(" / ")[0]
                        c_slug = str(sel).split(" / ")[1]
                        archives = list_archives("votes", county, year=year, contest=c_slug)
                        
                        if not archives:
                            st.info("No archived versions found for this contest.")
                        else:
                            st.markdown(f"**Found {len(archives)} archived versions:**")
                            for arch in archives:
                                with st.expander(f"📁 Timestamp: {arch.name}"):
                                    files = list(arch.iterdir())
                                    for f in files:
                                        st.markdown(f"- `{f.name}` ({f.stat().st_size:,} bytes)")
                                    
                                    if st.button(f"Rollback to {arch.name}", key=f"rb_{arch.name}"):
                                        st.warning("Rollback functionality is scaffolded but requires UI bypass or manual replace implementation under the hood. For now, download the archive file and re-upload via Update Center.")
                                
        elif domain == "Geography":
            archives = list_archives("geography", county)
            if not archives:
                st.info("No archived versions found for this county's geography.")
            else:
                st.markdown(f"**Found {len(archives)} archived versions:**")
                for arch in archives:
                    with st.expander(f"📁 Timestamp: {arch.name}"):
                        files = list(arch.iterdir())
                        for f in files[:5]: # show up to 5
                            st.markdown(f"- `{f.name}` ({f.stat().st_size:,} bytes)")
                        if len(files) > 5:
                            st.markdown(f"- ... and {len(files)-5} more files")

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 5: RUN PIPELINE
# ═════════════════════════════════════════════════════════════════════════════
elif page == "▶️ Run Pipeline":
    st.markdown("""
    <div class='ciab-header'>
        <h1>▶️ Run Pipeline</h1>
        <p>Execute the election modeling pipeline with targeted rebuilds and streaming logs</p>
    </div>""", unsafe_allow_html=True)

    contests = discover_contests()
    counties = discover_counties()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Configure Run")

        county = st.selectbox("County", ["— select —"] + counties)
        year   = st.text_input("Year", value="2024")
        contest_slug = st.text_input("Contest slug", placeholder="e.g. nov2024_general")

        # Auto-populate from discovered contests
        if contests:
            st.markdown("**Or pick from discovered contests:**")
            contest_opts = [
                f"{c['county']} / {c['year']} / {c['contest_slug']}"
                + ("" if c["has_votes"] else " ⚠️ no votes")
                for c in contests
            ]
            chosen = st.selectbox("Discovered contests", ["— pick —"] + contest_opts)
            if chosen and chosen != "— pick —":
                try:
                    idx = contest_opts.index(str(chosen))
                    chosen_idx = int(idx) if idx is not None else 0
                    c = contests[chosen_idx]
                    county       = str(c.get("county", ""))
                    year         = str(c.get("year", ""))
                    contest_slug = str(c.get("contest_slug", ""))
                except ValueError:
                    pass

        # Override detail path
        detail_override = st.text_input(
            "Override detail.xlsx path (optional)",
            placeholder="e.g. votes/2024/CA/SAMPLE_COUNTY/MEASURE_A/detail.xlsx"
        )

        staging_dir = st.text_input(
            "Staging directory (optional)",
            placeholder="e.g. Campaign In A Box Data",
        )

    with col2:
        st.subheader("Options")
        membership = st.selectbox(
            "Membership method",
            ["auto", "crosswalk", "area_weighted"],
            help="auto: use crosswalk if available, else area_weighted",
        )
        no_commit = not st.checkbox(
            "Git commit outputs", value=False,
            help="If checked, derived outputs will be auto-committed to git",
        )

        st.divider()
        # Status badge
        if county and county != "— select —" and contest_slug:
            try:
                c_name, c_slug, c_fips = normalize_county(county)
                norm_contest = normalize_contest_slug(contest_slug)
                cid = generate_contest_id(year, "CA", c_slug, norm_contest)
                st.markdown(f"**Context Identifiers:**<br><span style='font-size: 0.9em'>County FIPS: `{c_fips}` | Contest ID: `{cid}`</span>", unsafe_allow_html=True)
            except Exception:
                pass
                
            geo_status = get_geography_status(county)
            n_present  = sum(v for v in geo_status.values())
            has_geo    = n_present > 0
            st.markdown(f"**Geo:** {'🟢' if has_geo else '🔴'} {n_present}/12 present")

            votes_path = (
                BASE_DIR / "votes" / year / "CA" / county / contest_slug / "detail.xlsx"
            )
            has_votes = votes_path.exists() or bool(detail_override)
            st.markdown(f"**Votes:** {'🟢' if has_votes else '🟡'} {'found' if has_votes else 'not found (partial run)'}")

            # Staleness Display
            ctx_key = f"CA/{county}/{year}/{contest_slug}"
            stale_info = get_stale_status(ctx_key)
            if stale_info:
                st.markdown("---")
                st.markdown("### ⚠️ Staleness Detected")
                for d, info in stale_info.items():
                    st.markdown(f"- **{d}**: stale *(reason: {info.get('reason')})*")
            else:
                if has_geo and has_votes:
                    st.markdown("---")
                    st.markdown("✅ **Everything is up to date.**")

        else:
            st.info("Select county + contest to see status.")

    st.divider()

    if county and county != "— select —" and contest_slug and year:
        col_run1, col_run2, col_run3 = st.columns(3)
        with col_run1:
            run_full = st.button("🚀 Rebuild Everything", type="primary", use_container_width=True)
        with col_run2:
            run_targets = st.button("🎯 Rebuild Targets Only", use_container_width=True)
        with col_run3:
            run_maps = st.button("🗺️ Rebuild Maps Only", use_container_width=True)

        do_run = run_full or run_targets or run_maps
        
        if do_run:
            st.markdown("---")
            log_placeholder = st.empty()
            status_placeholder = st.empty()

            log_lines: list[str] = []
            run_status = "running"

            with st.spinner("Pipeline running…"):
                gen = run_pipeline_streaming(
                    county=county,
                    year=year,
                    contest_slug=contest_slug,
                    detail_path=detail_override or None,
                    staging_dir=staging_dir or None,
                    membership_method=membership,
                    no_commit=no_commit,
                    rebuild_targets_only=run_targets,
                    rebuild_maps_only=run_maps,
                )

                for line in gen:
                    if line == "__SUCCESS__":
                        run_status = "success"
                        break
                    elif line.startswith("__FAIL__"):
                        run_status = "fail"
                        break
                    log_lines.append(line)
                    # Keep last 200 lines
                    if len(log_lines) > 200:
                        log_lines = log_lines[-200:]
                    # Colorize
                    colored = []
                    for l in log_lines[-60:]:
                        if "[STEP ]" in l and "[OK]" in l:
                            colored.append(f"<span class='log-ok'>{l}</span>")
                        elif "[WARN ]" in l or "[SKIP]" in l:
                            colored.append(f"<span class='log-warn'>{l}</span>")
                        elif "[ERROR]" in l or "[FAIL]" in l:
                            colored.append(f"<span class='log-fail'>{l}</span>")
                        elif "[STEP ]" in l:
                            colored.append(f"<span class='log-step'>{l}</span>")
                        else:
                            colored.append(l)
                    log_placeholder.markdown(
                        f"<div class='log-box'>{'<br>'.join(colored)}</div>",
                        unsafe_allow_html=True,
                    )

            # Final status banner
            run_id_now = get_latest_run_id()
            if run_status == "success":
                status_placeholder.markdown(
                    f"<div class='run-success'>✅ <strong>Pipeline succeeded!</strong>"
                    f"<br>RUN_ID: <code>{run_id_now}</code>"
                    "</div>",
                    unsafe_allow_html=True,
                )
            elif run_status == "fail":
                status_placeholder.markdown(
                    "<div class='run-fail'>❌ <strong>Pipeline failed.</strong> "
                    "See logs below for details.</div>",
                    unsafe_allow_html=True,
                )
            else:
                status_placeholder.markdown(
                    "<div class='run-partial'>🟡 <strong>Partial run</strong> (votes not yet present). "
                    "Ingestion + validation complete.</div>",
                    unsafe_allow_html=True,
                )

            # Quick-link artifacts
            log_arts = discover_log_artifacts()
            if log_arts:
                st.subheader("📎 Latest Artifacts")
                for name, path in log_arts.items():
                    content = read_file_safe(path)
                    st.download_button(
                        f"⬇️ {name}", data=content,
                        file_name=name, mime="text/plain",
                        key=f"dl_run_{name}",
                    )
    else:
        st.info("Select county, year, and contest slug above, then click Run Pipeline.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 6: OUTPUTS BROWSER
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📊 Outputs Browser":
    st.markdown("""
    <div class='ciab-header'>
        <h1>📊 Outputs Browser</h1>
        <p>Browse and download derived pipeline artifacts</p>
    </div>""", unsafe_allow_html=True)

    counties = discover_counties()
    county = st.selectbox("Select county", ["— all —"] + counties)

    browse_counties = counties if county == "— all —" else [county]

    if not browse_counties:
        st.info("No counties initialized yet. Go to 🏛️ Jurisdiction to create one.")
        st.stop()

    for c in browse_counties:
        artifacts = discover_run_artifacts(c)
        if not artifacts:
            st.markdown(f"### {c} — *no derived outputs yet*")
            continue

        st.markdown(f"### 🏛️ {c}")

        # Group by contest
        by_contest: dict[str, list] = {}
        for a in artifacts:
            by_contest.setdefault(a["contest_slug"], []).append(a)

        for contest_slug, arts in sorted(by_contest.items()):
            with st.expander(f"📁 {contest_slug} ({len(arts)} files)", expanded=True):
                # Group by type for organized display
                by_type: dict[str, list] = {}
                for a in arts:
                    by_type.setdefault(a["type"], []).append(a)

                for art_type, items in sorted(by_type.items()):
                    st.markdown(f"**{art_type.replace('_', ' ').title()}**")
                    for item in sorted(items, key=lambda x: x["name"], reverse=True):
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.text(item["name"])
                        with col2:
                            st.text(f"{item['size_bytes']:,} bytes")
                        with col3:
                            try:
                                content = item["path"].read_bytes()
                                st.download_button(
                                    "⬇️", data=content,
                                    file_name=item["name"],
                                    mime="text/csv" if item["path"].suffix == ".csv" else "application/json",
                                    key=f"dl_{c}_{contest_slug}_{item['name']}",
                                )
                            except Exception:
                                st.text("error")

    # Latest run artifacts section
    st.divider()
    st.subheader("📋 Latest Run Log Artifacts")
    log_arts = discover_log_artifacts()
    if log_arts:
        cols = st.columns(min(4, len(log_arts)))
        for i, (name, path) in enumerate(log_arts.items()):
            with cols[i % 4]:
                content = read_file_safe(path)
                st.download_button(
                    f"⬇️ {name}", data=content,
                    file_name=name, mime="text/plain",
                    key=f"latest_{name}",
                )
    else:
        st.info("No pipeline runs yet.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 7: LOGS & NEEDS VIEWER
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📋 Logs & NEEDS":
    st.markdown("""
    <div class='ciab-header'>
        <h1>📋 Logs & NEEDS Viewer</h1>
        <p>Inspect run logs, validation reports, QA checks, and missing data registry. Failures are never hidden.</p>
    </div>""", unsafe_allow_html=True)

    run_id = get_latest_run_id()
    if run_id:
        st.markdown(f"**Latest RUN_ID:** `{run_id}`")
    else:
        st.warning("No pipeline runs found.")

    tab_log, tab_val, tab_qa, tab_needs, tab_history = st.tabs([
        "📄 run.log", "✅ Validation", "🔬 QA Checks", "⚠️ NEEDS", "📚 Run History"
    ])

    # ── run.log ───────────────────────────────────────────────────────────────
    with tab_log:
        content = read_latest_artifact("run.log")
        if content:
            # Colorize log lines
            colored = []
            for line in content.splitlines():
                if "[OK]" in line and "[STEP ]" in line:
                    colored.append(f"<span class='log-ok'>{line}</span>")
                elif "[WARN ]" in line or "[SKIP]" in line:
                    colored.append(f"<span class='log-warn'>{line}</span>")
                elif "[ERROR]" in line or "[FAIL]" in line or "HARD FAIL" in line:
                    colored.append(f"<span class='log-fail'>{line}</span>")
                elif "[STEP ]" in line:
                    colored.append(f"<span class='log-step'>{line}</span>")
                else:
                    colored.append(line)
            st.markdown(
                f"<div class='log-box'>{'<br>'.join(colored)}</div>",
                unsafe_allow_html=True,
            )
            st.download_button("⬇️ Download run.log", content, "run.log", "text/plain")
        else:
            st.info("No run.log available yet.")

    # ── Validation report ─────────────────────────────────────────────────────
    with tab_val:
        content = read_latest_artifact("validation.md")
        if content:
            st.markdown(content)
            st.download_button("⬇️ Download validation.md", content, "validation_report.md", "text/markdown")
        else:
            st.info("No validation report yet.")

    # ── QA checks ─────────────────────────────────────────────────────────────
    with tab_qa:
        content = read_latest_artifact("qa.md")
        if content:
            # Highlight failures
            lines = content.splitlines()
            display_lines = []
            has_failures = any("[FAIL]" in l or "✗" in l for l in lines)
            for line in lines:
                if "[FAIL]" in line or "✗" in line:
                    display_lines.append(
                        f"<span style='color:#DC2626;font-weight:600'>{line}</span>"
                    )
                elif "[OK]" in line or "✓" in line:
                    display_lines.append(
                        f"<span style='color:#16A34A'>{line}</span>"
                    )
                else:
                    display_lines.append(line)

            if has_failures:
                st.error("⛔ QA checks have failures — see highlighted lines below.")

            st.markdown(
                "<div style='font-family:monospace;background:#F8FAFC;padding:16px;"
                "border-radius:8px;border:1px solid #E2E8F0'>"
                + "<br>".join(display_lines) + "</div>",
                unsafe_allow_html=True,
            )
            st.download_button("⬇️ Download qa.md", content, "qa_sanity_checks.md", "text/markdown")
        else:
            st.info("No QA report yet.")

    # ── NEEDS viewer ──────────────────────────────────────────────────────────
    with tab_needs:
        content = read_latest_artifact("needs.yaml")
        if content:
            try:
                needs_data = yaml.safe_load(content) or {}
            except Exception:
                needs_data = {}

            meta = needs_data.get("meta", {})
            jurisdictions = needs_data.get("jurisdictions", {})

            if meta:
                st.markdown(
                    f"**Registry last updated:** {meta.get('last_updated','N/A')}  "
                    f"| **Last RUN_ID:** `{meta.get('last_run_id','N/A')}`"
                )

            if not jurisdictions:
                st.info("No NEEDS entries recorded yet.")
            else:
                for jur_key, jur_data in jurisdictions.items():
                    needs_list = jur_data.get("needs", [])
                    n_missing  = sum(1 for n in needs_list if n.get("status") == "missing")
                    n_blocked  = sum(1 for n in needs_list if n.get("status") == "blocked")

                    with st.expander(
                        f"{'🔴' if n_missing > 0 else '🟡' if n_blocked > 0 else '🟢'} "
                        f"**{jur_key}** — {n_missing} missing, {n_blocked} blocked",
                        expanded=(n_missing > 0),
                    ):
                        if not needs_list:
                            st.success("✅ No missing data for this jurisdiction.")
                        else:
                            for need in needs_list:
                                cat = need.get("category", "unknown")
                                status_str = need.get("status", "unknown")
                                blocks = need.get("blocks", [])
                                exp_path = need.get("expected_path", "")

                                if status_str == "missing":
                                    icon = "❌"
                                    color = "#DC2626"
                                elif status_str == "blocked":
                                    icon = "⚠️"
                                    color = "#D97706"
                                else:
                                    icon = "ℹ️"
                                    color = "#2563EB"

                                st.markdown(
                                    f"<div style='padding:8px 12px;margin:4px 0;"
                                    f"border-left:3px solid {color};"
                                    f"background:#F8FAFC;border-radius:4px'>"
                                    f"{icon} <strong>{cat}</strong> "
                                    f"<code style='color:{color}'>[{status_str}]</code><br>"
                                    f"<small>blocks: {', '.join(blocks)}</small>"
                                    + (f"<br><small>expected at: <code>{exp_path}</code></small>" if exp_path else "")
                                    + "</div>",
                                    unsafe_allow_html=True,
                                )

            st.divider()
            st.download_button("⬇️ Download needs.yaml", content, "needs.yaml", "text/plain")
        else:
            st.info("No NEEDS registry recorded yet — run the pipeline first.")

    # ── Run history ───────────────────────────────────────────────────────────
    with tab_history:
        all_logs = discover_all_run_logs()
        if not all_logs:
            st.info("No historical runs found.")
        else:
            st.markdown(f"**{len(all_logs)} total runs**")
            for entry in all_logs[:20]:
                with st.expander(f"📄 `{entry['run_id']}`", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        log_content = read_file_safe(entry["log"])
                        st.download_button(
                            "⬇️ run.log", log_content,
                            file_name=f"{entry['run_id']}__run.log",
                            mime="text/plain",
                            key=f"hist_log_{entry['run_id']}",
                        )
                    with col2:
                        if entry["pathway"]:
                            pw_content = read_file_safe(entry["pathway"])
                            st.download_button(
                                "⬇️ pathway.json", pw_content,
                                file_name=f"{entry['run_id']}__pathway.json",
                                mime="application/json",
                                key=f"hist_pw_{entry['run_id']}",
                            )
                    # Quick log tail
                    tail = "\n".join(log_content.splitlines()[-15:]) if log_content else ""
                    st.code(tail, language=None)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 7: COUNTY REGISTRY
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📜 County Registry":
    st.markdown("""
    <div class='ciab-header'>
        <h1>📜 California County Registry</h1>
        <p>Canonical Single Source of Truth for CA Counties</p>
    </div>""", unsafe_allow_html=True)
    
    from scripts.lib.county_registry import load_county_registry
    reg = load_county_registry()
    counties = reg.get_all()
    
    st.markdown(f"**Registry Version:** `{reg.version}`  |  **Total Counties:** `{len(counties)}`")
    
    import pandas as pd
    df = pd.DataFrame([{
        "FIPS": c["county_fips"],
        "Name": c["county_name"],
        "Slug": c["county_slug"],
        "Aliases": ", ".join(c["aliases"])
    } for c in counties])
    
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "FIPS": st.column_config.TextColumn("FIPS", width="small"),
            "Name": st.column_config.TextColumn("Name (Title Case)", width="medium"),
            "Slug": st.column_config.TextColumn("Canonical Slug", width="medium"),
            "Aliases": st.column_config.TextColumn("Recognized Aliases", width="large"),
        }
    )
