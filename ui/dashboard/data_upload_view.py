"""
ui/dashboard/data_upload_view.py — Contest Data Upload

Allows campaign staff to upload election data files for a specific contest
directly through the browser UI.

Files supported:
  - detail.xlsx / detail.xls  → data/CA/counties/<County>/votes/<year>/<slug>/
  - *.geojson                 → data/CA/counties/<County>/geography/precinct_shapes/MPREC_GeoJSON/
  - *.csv (voter file)        → data/CA/counties/<County>/voters/<year>/
"""
from __future__ import annotations

import io
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# States supported (expand as needed)
US_STATES = ["CA", "TX", "FL", "NY", "AZ", "GA", "PA", "NV", "WI", "MI"]


def render_upload() -> None:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0F766E,#0D9488);
         border-radius:12px;padding:18px 28px;margin-bottom:20px;color:white'>
      <h2 style='margin:0;color:white'>📂 Contest Data Upload</h2>
      <p style='margin:4px 0 0 0;color:#CCFBF1'>
        Upload election results, geometry, or voter files for a contest
      </p>
    </div>""", unsafe_allow_html=True)

    st.info(
        "Files are saved directly into the `data/` directory structure. "
        "After uploading, run the pipeline to process them."
    )

    # ── Contest selector ──────────────────────────────────────────────────────
    st.subheader("1️⃣ Identify the Contest")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        state = st.selectbox("State", US_STATES, index=0, key="upload_state")
    with col2:
        county = st.text_input("County", value="Sonoma", key="upload_county").strip()
    with col3:
        year = st.selectbox("Year", [2026, 2025, 2024, 2023, 2022], index=2, key="upload_year")
    with col4:
        slug = st.text_input("Contest Slug", value="nov2024_general", key="upload_slug",
                             help="e.g. nov2024_general, jun2024_primary").strip()

    if not county or not slug:
        st.warning("Please fill in County and Contest Slug to continue.")
        return

    # Derived paths
    contest_dir   = BASE_DIR / "data" / state / "counties" / county / "votes" / str(year) / slug
    geo_dir       = BASE_DIR / "data" / state / "counties" / county / "geography" / "precinct_shapes" / "MPREC_GeoJSON"
    voter_dir     = BASE_DIR / "data" / state / "counties" / county / "voters" / str(year)

    # Show target paths
    with st.expander("📁 Target directory paths", expanded=False):
        st.code(f"Results workbook → {contest_dir / 'detail.xlsx'}")
        st.code(f"GeoJSON          → {geo_dir / '<filename>.geojson'}")
        st.code(f"Voter file (CSV) → {voter_dir / '<filename>.csv'}")

    st.markdown("---")

    # ── File upload tabs ──────────────────────────────────────────────────────
    st.subheader("2️⃣ Upload Files")
    tab1, tab2, tab3 = st.tabs(["📊 Election Results (XLS/XLSX)", "🗺️ Geometry (GeoJSON)", "🗂️ Other (CSV)"])

    with tab1:
        _upload_results(contest_dir, state, county, year, slug)

    with tab2:
        _upload_geojson(geo_dir, state, county)

    with tab3:
        _upload_csv(voter_dir, state, county, year)

    st.markdown("---")

    # ── Run pipeline button ───────────────────────────────────────────────────
    st.subheader("3️⃣ Run Pipeline")
    st.markdown(
        f"After uploading files, run the pipeline to process this contest:"
    )
    st.code(
        f"python scripts/run_pipeline.py "
        f"--state {state} --county {county} "
        f"--contest-slug {slug} --year {year}",
        language="bash",
    )

    if st.button("▶️ Run Pipeline Now", type="primary", use_container_width=False, key="run_pipe_btn"):
        _run_pipeline(state, county, slug, year)


def _upload_results(contest_dir: Path, state: str, county: str, year: int, slug: str) -> None:
    """Upload detail.xlsx / detail.xls election results workbook."""
    st.markdown(
        "Upload the election results workbook. "
        "It must contain a sheet with columns: **Precinct, Registered, BallotsCast, Yes (or FOR), No (or AGAINST)**."
    )

    # Show existing file status
    existing_xlsx = contest_dir / "detail.xlsx"
    existing_xls  = contest_dir / "detail.xls"
    if existing_xlsx.exists():
        sz = existing_xlsx.stat().st_size
        st.success(f"✅ `detail.xlsx` already present ({sz:,} bytes) — uploading will overwrite it.")
    elif existing_xls.exists():
        sz = existing_xls.stat().st_size
        st.info(f"ℹ️ `detail.xls` found ({sz:,} bytes) — you can upload `.xlsx` to replace it.")
    else:
        st.warning("⚠️ No results file found yet for this contest.")

    uploaded = st.file_uploader(
        "Choose detail.xlsx or detail.xls",
        type=["xlsx", "xls"],
        key="upload_results_file",
    )

    if uploaded is not None:
        # Validate it looks like a real workbook
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(uploaded.getvalue()), sheet_name=0, nrows=5)
            st.markdown(f"**Preview** — {len(df.columns)} columns detected: `{list(df.columns)}`")
            st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Could not preview file: {e}. The file may still be valid — proceed to save if you're sure.")

        col_save, col_cancel = st.columns([1, 3])
        with col_save:
            if st.button("💾 Save to contest directory", key="save_results_btn", type="primary"):
                contest_dir.mkdir(parents=True, exist_ok=True)
                # Always save as .xlsx regardless of input extension
                out_path = contest_dir / "detail.xlsx"
                out_path.write_bytes(uploaded.getvalue())
                st.success(f"✅ Saved → `{out_path.relative_to(BASE_DIR)}`")
                st.balloons()


def _upload_geojson(geo_dir: Path, state: str, county: str) -> None:
    """Upload precinct GeoJSON file for mapping."""
    st.markdown(
        "Upload a GeoJSON file containing precinct boundaries. "
        "The file should have a precinct ID field (e.g. `MPREC_ID`, `precinct`, `GEOID`)."
    )

    existing = list(geo_dir.glob("*.geojson")) if geo_dir.exists() else []
    if existing:
        for f in existing:
            st.success(f"✅ `{f.name}` already present ({f.stat().st_size:,} bytes)")
    else:
        st.warning("⚠️ No GeoJSON files found for this county.")

    uploaded = st.file_uploader(
        "Choose a .geojson file",
        type=["geojson", "json"],
        key="upload_geo_file",
    )

    if uploaded is not None:
        # Quick sanity check
        import json as _json
        try:
            gj = _json.loads(uploaded.getvalue())
            feat_count = len(gj.get("features", []))
            st.info(f"ℹ️ GeoJSON contains **{feat_count}** features.")
        except Exception as e:
            st.error(f"Not valid GeoJSON: {e}")
            return

        fname = uploaded.name if uploaded.name.endswith(".geojson") else uploaded.name.replace(".json", ".geojson")

        if st.button("💾 Save GeoJSON", key="save_geo_btn", type="primary"):
            geo_dir.mkdir(parents=True, exist_ok=True)
            out_path = geo_dir / fname
            out_path.write_bytes(uploaded.getvalue())
            st.success(f"✅ Saved → `{out_path.relative_to(BASE_DIR)}`")


def _upload_csv(voter_dir: Path, state: str, county: str, year: int) -> None:
    """Upload a generic CSV file (voter file, crosswalk, etc.)."""
    st.markdown("Upload a CSV file — voter file, crosswalk, or any supplemental data.")

    file_type = st.radio("File purpose", ["Voter File", "Crosswalk (MPREC↔SRPREC)", "Other"],
                         horizontal=True, key="upload_csv_type")

    if file_type == "Voter File":
        target_dir = voter_dir
    elif file_type == "Crosswalk (MPREC↔SRPREC)":
        target_dir = BASE_DIR / "data" / state / "counties" / county / "crosswalks"
    else:
        target_dir = BASE_DIR / "data" / state / "counties" / county / "supplemental"

    uploaded = st.file_uploader("Choose a .csv file", type=["csv"], key="upload_csv_file")

    if uploaded is not None:
        try:
            import pandas as pd
            df = pd.read_csv(io.BytesIO(uploaded.getvalue()), nrows=5)
            st.markdown(f"**Preview** — {len(df.columns)} columns: `{list(df.columns)}`")
            st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Could not preview CSV: {e}")

        if st.button("💾 Save CSV", key="save_csv_btn", type="primary"):
            target_dir.mkdir(parents=True, exist_ok=True)
            out_path = target_dir / uploaded.name
            out_path.write_bytes(uploaded.getvalue())
            st.success(f"✅ Saved → `{out_path.relative_to(BASE_DIR)}`")


def _run_pipeline(state: str, county: str, slug: str, year: int) -> None:
    """Launch pipeline as a subprocess and stream output."""
    import subprocess, sys
    st.markdown("**Running pipeline…** (this may take 1–2 minutes)")
    cmd = [
        sys.executable, "scripts/run_pipeline.py",
        "--state", state,
        "--county", county,
        "--contest-slug", slug,
        "--year", str(year),
        "--no-commit",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            cwd=str(BASE_DIR),
        )
        if result.returncode == 0:
            st.success("✅ Pipeline completed successfully!")
        else:
            st.error("❌ Pipeline returned non-zero exit code.")
        with st.expander("Pipeline output"):
            st.code(result.stdout[-5000:] if len(result.stdout) > 5000 else result.stdout)
        if result.stderr:
            with st.expander("Stderr"):
                st.code(result.stderr[-2000:])
    except subprocess.TimeoutExpired:
        st.error("Pipeline timed out after 5 minutes.")
    except Exception as e:
        st.error(f"Failed to run pipeline: {e}")
