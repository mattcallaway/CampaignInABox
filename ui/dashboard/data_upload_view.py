"""
ui/dashboard/data_upload_view.py — Contest Data Manager

Full data management interface for campaign contest files:
  - Browse + manage existing files (rename, delete, enable/disable)
  - Upload new files (XLS, GeoJSON, CSV)
  - Data weight + usage controls per dataset
  - Writes data_config.json alongside files for pipeline use
"""
from __future__ import annotations

import io
import json
import os
import shutil
import datetime
from pathlib import Path
from typing import Any

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent
US_STATES = ["CA", "TX", "FL", "NY", "AZ", "GA", "PA", "NV", "WI", "MI"]

CONFIG_FILE = "data_config.json"


# ── Config helpers ─────────────────────────────────────────────────────────────

def _cfg_path(contest_dir: Path) -> Path:
    return contest_dir / CONFIG_FILE


def _load_cfg(contest_dir: Path) -> dict[str, Any]:
    p = _cfg_path(contest_dir)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"files": {}, "updated_at": None}


def _save_cfg(contest_dir: Path, cfg: dict) -> None:
    cfg["updated_at"] = datetime.datetime.now().isoformat()
    _cfg_path(contest_dir).write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _file_cfg(cfg: dict, filename: str) -> dict:
    return cfg.setdefault("files", {}).setdefault(filename, {
        "enabled": True, "weight": 1.0, "notes": ""
    })


# ── Main render ────────────────────────────────────────────────────────────────

def render_upload() -> None:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0F766E,#0D9488);
         border-radius:12px;padding:18px 28px;margin-bottom:20px;color:white'>
      <h2 style='margin:0;color:white'>📂 Contest Data Manager</h2>
      <p style='margin:4px 0 0 0;color:#CCFBF1'>
        Browse · Upload · Rename · Delete · Enable/Disable · Set Weights
      </p>
    </div>""", unsafe_allow_html=True)

    # ── Contest selector ──────────────────────────────────────────────────────
    with st.container():
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            state = st.selectbox("State", US_STATES, key="dm_state")
        with col2:
            county = st.text_input("County", "Sonoma", key="dm_county").strip()
        with col3:
            year = st.selectbox("Year", [2026, 2025, 2024, 2023, 2022], index=2, key="dm_year")
        with col4:
            slug = st.text_input("Contest Slug", "nov2024_general", key="dm_slug").strip()

    if not county or not slug:
        st.warning("Fill in County and Contest Slug to continue.")
        return

    # Derived directories
    contest_dir = BASE_DIR / "data" / state / "counties" / county / "votes" / str(year) / slug
    geo_dir     = BASE_DIR / "data" / state / "counties" / county / "geography" / "precinct_shapes" / "MPREC_GeoJSON"
    voter_dir   = BASE_DIR / "data" / state / "counties" / county / "voters" / str(year)
    xwalk_dir   = BASE_DIR / "data" / state / "counties" / county / "crosswalks"

    # Config
    contest_dir.mkdir(parents=True, exist_ok=True)
    cfg = _load_cfg(contest_dir)

    st.divider()

    tab_browse, tab_upload, tab_weights, tab_run = st.tabs([
        "📁 Browse & Manage",
        "⬆️ Upload New File",
        "⚖️ Data Weights & Usage",
        "▶️ Run Pipeline",
    ])

    with tab_browse:
        _render_browse(contest_dir, geo_dir, voter_dir, xwalk_dir, cfg)

    with tab_upload:
        _render_upload(contest_dir, geo_dir, voter_dir, xwalk_dir, cfg)

    with tab_weights:
        _render_weights(contest_dir, geo_dir, voter_dir, xwalk_dir, cfg)

    with tab_run:
        _render_run(state, county, slug, year, contest_dir)


# ── Tab: Browse & Manage ───────────────────────────────────────────────────────

def _render_browse(contest_dir, geo_dir, voter_dir, xwalk_dir, cfg):
    st.subheader("📁 Browse Files")

    # Contest-scoped sections (need year + slug)
    contest_sections = {
        f"📊 Election Results  (`…/votes/{contest_dir.parent.name}/{contest_dir.name}/`)" +
        "  ⬩ *contest-specific*": (
            contest_dir, ["*.xlsx", "*.xls", "*.csv", "*.json"]
        ),
    }
    # County-level sections (shared across all contests in county)
    county_sections = {
        f"🗺️ Geometry  (`…/MPREC_GeoJSON/`)" +
        "  ⬩ *county-level — applies to all contests*": (
            geo_dir, ["*.geojson", "*.json"]
        ),
        f"🗂️ Voter Files  (`…/voters/{voter_dir.name}/`)" +
        "  ⬩ *year-level*": (
            voter_dir, ["*.csv"]
        ),
        f"🔗 Crosswalks  (`…/crosswalks/`)" +
        "  ⬩ *county-level*": (
            xwalk_dir, ["*.csv", "*.json"]
        ),
    }

    any_files = False
    for section_label, (d, globs) in {**contest_sections, **county_sections}.items():
        files = []
        if d.exists():
            for g in globs:
                files += [f for f in d.glob(g) if f.name != CONFIG_FILE]
        files = sorted(set(files))
        if not files:
            continue
        any_files = True
        with st.expander(section_label, expanded=(d == contest_dir)):
            for f in files:
                _file_row(f, contest_dir, cfg)

    if not any_files:
        st.info("No data files found. Use the **Upload** tab to add files.")

    _save_cfg(contest_dir, cfg)


def _file_row(f: Path, contest_dir: Path, cfg: dict):
    """Render one file row with rename / delete / notes controls."""
    fname = f.name
    sz    = f.stat().st_size
    mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    fc    = _file_cfg(cfg, fname)

    # Status badge
    enabled = fc.get("enabled", True)
    badge = "🟢" if enabled else "🔴"

    with st.container():
        col_name, col_meta, col_en, col_actions = st.columns([3, 2, 1, 2])

        with col_name:
            st.markdown(f"**{badge} {fname}**")
            st.caption(f"{sz:,} bytes · modified {mtime}")

        with col_meta:
            w = fc.get("weight", 1.0)
            st.caption(f"Weight: **{w:.2f}**")
            notes = fc.get("notes", "")
            if notes:
                st.caption(f"📝 {notes[:50]}")

        with col_en:
            new_en = st.toggle("On", value=enabled, key=f"en_{fname}", label_visibility="collapsed")
            if new_en != enabled:
                fc["enabled"] = new_en
                st.rerun()

        with col_actions:
            a1, a2, a3 = st.columns(3)
            with a1:
                # Download
                data = f.read_bytes()
                st.download_button("⬇️", data, file_name=fname, key=f"dl_{fname}",
                                   help="Download", use_container_width=True)
            with a2:
                # Rename
                if st.button("✏️", key=f"rename_btn_{fname}", help="Rename", use_container_width=True):
                    st.session_state[f"renaming_{fname}"] = True
            with a3:
                # Delete
                if st.button("🗑️", key=f"del_btn_{fname}", help="Delete", use_container_width=True):
                    st.session_state[f"confirm_del_{fname}"] = True

        # Rename form
        if st.session_state.get(f"renaming_{fname}"):
            new_name = st.text_input("New filename", value=fname, key=f"new_name_{fname}")
            rc1, rc2 = st.columns(2)
            with rc1:
                if st.button("✅ Save rename", key=f"save_rename_{fname}"):
                    new_name = new_name.strip()
                    if new_name and new_name != fname:
                        new_path = f.parent / new_name
                        if new_path.exists():
                            st.error(f"`{new_name}` already exists.")
                        else:
                            f.rename(new_path)
                            # Move config entry
                            if fname in cfg.get("files", {}):
                                cfg["files"][new_name] = cfg["files"].pop(fname)
                            st.success(f"Renamed → `{new_name}`")
                            del st.session_state[f"renaming_{fname}"]
                            st.rerun()
            with rc2:
                if st.button("❌ Cancel", key=f"cancel_rename_{fname}"):
                    del st.session_state[f"renaming_{fname}"]
                    st.rerun()

        # Delete confirmation
        if st.session_state.get(f"confirm_del_{fname}"):
            st.warning(f"⚠️ Delete `{fname}` permanently?")
            dc1, dc2 = st.columns(2)
            with dc1:
                if st.button("🗑️ Yes, delete", key=f"confirm_yes_{fname}", type="primary"):
                    f.unlink()
                    cfg.get("files", {}).pop(fname, None)
                    st.success(f"Deleted `{fname}`.")
                    del st.session_state[f"confirm_del_{fname}"]
                    st.rerun()
            with dc2:
                if st.button("↩️ Cancel", key=f"confirm_no_{fname}"):
                    del st.session_state[f"confirm_del_{fname}"]
                    st.rerun()

        st.markdown("<hr style='margin:4px 0;border-color:#E2E8F0'>", unsafe_allow_html=True)


# ── Tab: Upload ────────────────────────────────────────────────────────────────

def _render_upload(contest_dir, geo_dir, voter_dir, xwalk_dir, cfg):
    st.subheader("⬆️ Upload a New File")

    file_type = st.radio(
        "What are you uploading?",
        ["📊 Election Results (XLSX/XLS)", "🗺️ Precinct Geometry (GeoJSON)", "🗂️ CSV (voter file / crosswalk / other)"],
        horizontal=True, key="up_type",
    )

    if "Election Results" in file_type:
        st.caption(
            f"📌 **Contest-specific.** Will be saved to:  "
            f"`data/{contest_dir.relative_to(BASE_DIR / 'data')}/`"
        )
        _upload_results(contest_dir, cfg)

    elif "GeoJSON" in file_type:
        st.caption(
            "📌 **County-level** — GeoJSON boundaries apply to all contests in this county, "
            "not just one year or slug. Year / Contest Slug above are **ignored** for this file type."
        )
        # Geo path: state + county only — derive fresh from sidebar values
        _state = st.session_state.get("dm_state", "CA")
        _county = st.session_state.get("dm_county", "Sonoma").strip()
        _geo_dir = BASE_DIR / "data" / _state / "counties" / _county / "geography" / "precinct_shapes" / "MPREC_GeoJSON"
        st.info(f"Save location: `{_geo_dir.relative_to(BASE_DIR)}`")
        _upload_geojson(_geo_dir)

    else:
        st.caption(
            "📌 Voter files are **year-level** (all contests in a year share one voter file). "
            "Crosswalks are **county-level**. Contest Slug above is ignored for these."
        )
        _state  = st.session_state.get("dm_state",  "CA")
        _county = st.session_state.get("dm_county", "Sonoma").strip()
        _year   = st.session_state.get("dm_year",   2024)
        _voter_dir = BASE_DIR / "data" / _state / "counties" / _county / "voters" / str(_year)
        _xwalk_dir = BASE_DIR / "data" / _state / "counties" / _county / "crosswalks"
        _upload_csv(_voter_dir, _xwalk_dir)


def _upload_results(contest_dir: Path, cfg: dict):
    existing = list(contest_dir.glob("detail*.xlsx")) + list(contest_dir.glob("detail*.xls"))
    if existing:
        st.success(f"✅ `{existing[0].name}` already exists — uploading will overwrite or add alongside it.")
    else:
        st.warning("⚠️ No results workbook yet for this contest.")

    up = st.file_uploader("Choose detail.xlsx or detail.xls", type=["xlsx","xls"], key="up_results")
    if up:
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(up.getvalue()), sheet_name=0, nrows=5)
            st.caption(f"Preview — {len(df.columns)} columns: `{list(df.columns)}`")
            st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"Can't preview ({e}) — you can still save.")

        save_name = st.text_input("Save as filename", value="detail.xlsx", key="up_results_name")
        if st.button("💾 Save", key="save_results", type="primary"):
            contest_dir.mkdir(parents=True, exist_ok=True)
            out = contest_dir / save_name.strip()
            out.write_bytes(up.getvalue())
            _file_cfg(cfg, out.name)  # register in config
            _save_cfg(contest_dir, cfg)
            st.success(f"✅ Saved → `{out.relative_to(BASE_DIR)}`")
            st.balloons()


def _upload_geojson(geo_dir: Path):
    up = st.file_uploader("Choose a .geojson file", type=["geojson","json"], key="up_geo")
    if up:
        import json as _j
        try:
            gj = _j.loads(up.getvalue())
            st.info(f"ℹ️ {len(gj.get('features',[]))} features detected.")
        except Exception as e:
            st.error(f"Invalid GeoJSON: {e}"); return

        fname = up.name if up.name.endswith(".geojson") else up.name.replace(".json",".geojson")
        save_name = st.text_input("Save as filename", value=fname, key="up_geo_name")
        if st.button("💾 Save", key="save_geo", type="primary"):
            geo_dir.mkdir(parents=True, exist_ok=True)
            out = geo_dir / save_name.strip()
            out.write_bytes(up.getvalue())
            st.success(f"✅ Saved → `{out.relative_to(BASE_DIR)}`")


def _upload_csv(voter_dir: Path, xwalk_dir: Path):
    purpose = st.selectbox("File purpose", ["Voter File", "Crosswalk", "Other"], key="up_csv_pur")
    target  = voter_dir if purpose == "Voter File" else (xwalk_dir if purpose == "Crosswalk" else voter_dir.parent / "supplemental")
    up = st.file_uploader("Choose a .csv file", type=["csv"], key="up_csv")
    if up:
        import pandas as pd
        try:
            df = pd.read_csv(io.BytesIO(up.getvalue()), nrows=5)
            st.caption(f"Preview — {len(df.columns)} cols: `{list(df.columns)}`")
            st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"Can't preview: {e}")

        save_name = st.text_input("Save as filename", value=up.name, key="up_csv_name")
        if st.button("💾 Save", key="save_csv", type="primary"):
            target.mkdir(parents=True, exist_ok=True)
            out = target / save_name.strip()
            out.write_bytes(up.getvalue())
            st.success(f"✅ Saved → `{out.relative_to(BASE_DIR)}`")


# ── Tab: Weights & Usage ───────────────────────────────────────────────────────

def _render_weights(contest_dir, geo_dir, voter_dir, xwalk_dir, cfg):
    st.subheader("⚖️ Data Weights & Usage")
    st.markdown(
        "Control **which files are used** in the next pipeline run and how much weight they carry. "
        "Disabled files are skipped entirely. Weight affects blending when multiple datasets overlap.\n\n"
        "> Settings are saved to `data_config.json` in the contest directory and read by the pipeline."
    )

    # Collect all files across all relevant dirs
    all_dirs   = [contest_dir, geo_dir, voter_dir, xwalk_dir]
    all_files  = []
    for d in all_dirs:
        if d.exists():
            all_files += [f for f in d.rglob("*") if f.is_file() and f.name != CONFIG_FILE]

    if not all_files:
        st.info("No files found. Upload files first.")
        return

    changed = False
    for f in sorted(all_files):
        fname = f.name
        fc    = _file_cfg(cfg, fname)

        with st.container():
            c1, c2, c3, c4 = st.columns([3, 1, 2, 3])
            with c1:
                st.markdown(f"**{fname}**")
                st.caption(str(f.relative_to(BASE_DIR)))
            with c2:
                en = st.toggle("Use", value=fc.get("enabled", True), key=f"w_en_{fname}")
                if en != fc.get("enabled", True):
                    fc["enabled"] = en; changed = True
            with c3:
                w = st.number_input(
                    "Weight", min_value=0.0, max_value=10.0,
                    value=float(fc.get("weight", 1.0)), step=0.1,
                    key=f"w_val_{fname}",
                    help="1.0 = normal. 0 = ignored. 2.0 = double weight.",
                    disabled=not fc.get("enabled", True),
                )
                if abs(w - fc.get("weight", 1.0)) > 0.001:
                    fc["weight"] = round(w, 2); changed = True
            with c4:
                notes = st.text_input(
                    "Notes", value=fc.get("notes", ""),
                    key=f"w_notes_{fname}",
                    placeholder="e.g. 'prelim only', 'use for turnout only'",
                    label_visibility="collapsed",
                )
                if notes != fc.get("notes", ""):
                    fc["notes"] = notes; changed = True

        st.markdown("<hr style='margin:4px 0;border-color:#E2E8F0'>", unsafe_allow_html=True)

    if st.button("💾 Save weight settings", type="primary", key="save_weights"):
        _save_cfg(contest_dir, cfg)
        st.success("✅ `data_config.json` updated — weights will be applied on next pipeline run.")
    elif changed:
        _save_cfg(contest_dir, cfg)

    # Show raw config
    with st.expander("🔍 View data_config.json"):
        st.json(cfg)

    st.download_button(
        "⬇️ Download data_config.json",
        json.dumps(cfg, indent=2).encode("utf-8"),
        file_name=CONFIG_FILE, mime="application/json",
    )


# ── Tab: Run Pipeline ──────────────────────────────────────────────────────────

def _find_detail_path(contest_dir: Path, state: str, county: str, year: str, slug: str) -> Path | None:
    """
    Search for the detail.xlsx/xls in priority order:
      1. contest_dir itself (data/CA/counties/<county>/votes/<year>/<slug>/)
      2. data_config.json registered file path in contest_dir
      3. Legacy votes/<year>/<state>/<county>/<slug>/
    Returns the first Path that exists, or None.
    """
    # 1. Canonical dir
    for ext in (".xlsx", ".xls"):
        p = contest_dir / f"detail{ext}"
        if p.exists():
            return p

    # 2. data_config.json registered file
    cfg_path = contest_dir / "data_config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            for fname, finfo in cfg.get("files", {}).items():
                if finfo.get("enabled", True) and fname.lower() in ("detail.xlsx", "detail.xls"):
                    p = contest_dir / fname
                    if p.exists():
                        return p
        except Exception:
            pass

    # 3. Legacy path
    legacy = BASE_DIR / "votes" / str(year) / state / county / slug
    for ext in (".xlsx", ".xls"):
        p = legacy / f"detail{ext}"
        if p.exists():
            return p

    return None


def _render_run(state, county, slug, year, contest_dir: Path):
    st.subheader("▶️ Run Pipeline for This Contest")

    # Auto-detect the detail file
    detail_path = _find_detail_path(contest_dir, state, county, str(year), slug)

    if detail_path:
        st.success(f"✅ Election results file found: `{detail_path.relative_to(BASE_DIR)}`")
        detail_flag = f' --detail-path "{detail_path.relative_to(BASE_DIR)}"'
        detail_args = ["--detail-path", str(detail_path)]
    else:
        st.warning(
            "⚠️ No `detail.xlsx` / `detail.xls` found for this contest. "
            "Upload the election results file in the **Upload New File** tab first."
        )
        detail_flag = ""
        detail_args = []

    cmd_str = (
        f"python scripts/run_pipeline.py --state {state} --county {county} "
        f"--year {year} --contest-slug {slug}{detail_flag}"
    )
    st.code(cmd_str, language="bash")

    st.markdown(
        "After uploading or modifying files, run the pipeline to process the contest data and regenerate all outputs.\n\n"
        "_Typical runtime: ~2 minutes. Map output requires `geopandas` (optional)._"
    )

    col1, col2 = st.columns([2, 3])
    with col1:
        run_clicked = st.button(
            "▶️ Run Now",
            type="primary" if detail_path else "secondary",
            key="run_pipe",
            use_container_width=True,
            disabled=(not detail_path),
        )
    with col2:
        force_run = st.checkbox(
            "Run anyway (no election results)",
            key="force_run_chk",
            disabled=bool(detail_path),
            help="Run geo-only steps even without a detail file.",
        )

    if run_clicked or (force_run and st.button("▶️ Force Run", key="force_run_btn")):
        import subprocess, sys
        base_cmd = [
            sys.executable, "scripts/run_pipeline.py",
            "--state", state, "--county", county,
            "--year", str(year), "--contest-slug", slug,
            "--no-commit",
        ]
        if detail_args:
            base_cmd += detail_args

        with st.spinner("Running pipeline… (this may take 1–2 minutes)"):
            result = subprocess.run(
                base_cmd,
                capture_output=True, text=True, timeout=360, cwd=str(BASE_DIR),
            )

        if result.returncode == 0:
            st.success("✅ Pipeline completed successfully!")
        else:
            st.error("❌ Pipeline returned an error — see output below.")

        # Show output with key metrics highlighted
        raw_out = (result.stdout or "") + (result.stderr or "")
        step_lines = [l for l in raw_out.splitlines() if any(
            kw in l for kw in ["DONE", "SKIP", "FAIL", "ERROR", "precincts", "Run complete", "elapsed", "registered"]
        )]
        if step_lines:
            with st.expander("📊 Pipeline steps summary", expanded=True):
                st.code("\n".join(step_lines[-60:]))
        with st.expander("📄 Full pipeline output"):
            st.code(raw_out[-8000:])

    st.subheader("▶️ Run Pipeline for This Contest")
    st.markdown(
        "After uploading or modifying files, run the pipeline to process the contest data and regenerate all outputs."
    )
    st.code(
        f"python scripts/run_pipeline.py --state {state} --county {county} "
        f"--contest-slug {slug} --year {year}",
        language="bash",
    )

    if st.button("▶️ Run Now", type="primary", key="run_pipe", use_container_width=False):
        import subprocess, sys
        with st.spinner("Running pipeline… (this takes 1–2 minutes)"):
            result = subprocess.run(
                [sys.executable, "scripts/run_pipeline.py",
                 "--state", state, "--county", county,
                 "--contest-slug", slug, "--year", str(year), "--no-commit"],
                capture_output=True, text=True, timeout=300, cwd=str(BASE_DIR),
            )
        if result.returncode == 0:
            st.success("✅ Pipeline completed successfully!")
        else:
            st.error("❌ Pipeline returned an error.")
        with st.expander("Pipeline output"):
            st.code((result.stdout or "")[-6000:])
        if result.stderr:
            with st.expander("Stderr"):
                st.code(result.stderr[-2000:])
