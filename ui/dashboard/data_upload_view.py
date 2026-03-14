"""
ui/dashboard/data_upload_view.py — Contest Data Upload (Prompt 31.5 Overhaul)

Canonical upload flow for campaign contest files:
  - Smart defaults from active campaign config
  - Tag-on-intake: user sets state/county/year/slug/file-type BEFORE saving
  - Saves to canonical path: data/contests/<state>/<county>/<year>/<slug>/raw/<file>
  - Writes intake manifest to .../manifests/primary_result_file.json
  - Shows existing contests at page top for context

Safe path: data/contests/<state>/<county>/<year>/<slug>/raw/
Legacy paths (data/CA/counties/, data/votes/) are NO LONGER used.
"""
from __future__ import annotations

import io
import json
import datetime
import shutil
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Canonical contest root
CONTESTS_DIR = BASE_DIR / "data" / "contests"

US_STATES = ["CA", "TX", "FL", "NY", "AZ", "GA", "PA", "NV", "WI", "MI"]

CURRENT_YEAR = datetime.datetime.now().year
YEAR_OPTIONS = [CURRENT_YEAR + 1, CURRENT_YEAR, CURRENT_YEAR - 1,
                CURRENT_YEAR - 2, CURRENT_YEAR - 3, CURRENT_YEAR - 4]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_active_campaign() -> dict:
    """Read active_campaign.yaml for smart defaults."""
    try:
        import yaml
        p = BASE_DIR / "config" / "active_campaign.yaml"
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _scan_existing_contests() -> list[dict]:
    """Return list of contests already in data/contests/."""
    found = []
    if not CONTESTS_DIR.exists():
        return found
    for state_dir in sorted(CONTESTS_DIR.iterdir()):
        if not state_dir.is_dir():
            continue
        for county_dir in sorted(state_dir.iterdir()):
            if not county_dir.is_dir():
                continue
            for year_dir in sorted(county_dir.iterdir()):
                if not year_dir.is_dir():
                    continue
                for slug_dir in sorted(year_dir.iterdir()):
                    if not slug_dir.is_dir():
                        continue
                    raw_dir = slug_dir / "raw"
                    files = list(raw_dir.glob("*.xlsx")) + list(raw_dir.glob("*.xls")) + list(raw_dir.glob("*.csv")) if raw_dir.exists() else []
                    found.append({
                        "state":  state_dir.name,
                        "county": county_dir.name,
                        "year":   year_dir.name,
                        "slug":   slug_dir.name,
                        "files":  [f.name for f in files],
                        "path":   str(slug_dir.relative_to(BASE_DIR)),
                        "has_manifest": (slug_dir / "manifests" / "primary_result_file.json").exists(),
                    })
    return found


def _write_manifest(raw_file: Path, state: str, county: str, year: str,
                    slug: str, file_type: str, notes: str) -> None:
    """Write/update the primary_result_file.json manifest."""
    manifests_dir = raw_file.parent.parent / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "state": state,
        "county": county,
        "year": year,
        "contest_slug": slug,
        "file_type": file_type,
        "filename": raw_file.name,
        "canonical_path": str(raw_file.relative_to(BASE_DIR)),
        "notes": notes,
        "ingested_at": datetime.datetime.now().isoformat(),
    }
    manifest_path = manifests_dir / "primary_result_file.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _write_contest_metadata(slug_dir: Path, state: str, county: str,
                             year: str, slug: str) -> None:
    """Write contest_metadata.json if not present."""
    manifests_dir = slug_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    meta_path = manifests_dir / "contest_metadata.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps({
            "state": state, "county": county,
            "year": year, "slug": slug,
            "created_at": datetime.datetime.now().isoformat(),
        }, indent=2), encoding="utf-8")


# ── Main render ───────────────────────────────────────────────────────────────

def render_upload() -> None:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0F766E,#0D9488);
         border-radius:12px;padding:18px 28px;margin-bottom:20px;color:white'>
      <h2 style='margin:0;color:white'>📂 Upload Contest Data</h2>
      <p style='margin:4px 0 0 0;color:#CCFBF1'>
        Tag your file on the way in — state, county, year, contest slug, and type are set before saving.
      </p>
    </div>""", unsafe_allow_html=True)

    # ── Existing contests panel ───────────────────────────────────────────────
    existing = _scan_existing_contests()
    if existing:
        with st.expander(f"📁 Existing contests ({len(existing)} found) — click to see what's already loaded", expanded=False):
            for c in existing:
                files_str = ", ".join(c["files"]) if c["files"] else "_(no raw files yet)_"
                manifest_badge = "✅" if c["has_manifest"] else "⚠️ no manifest"
                st.markdown(
                    f"**{c['state']} / {c['county']} / {c['year']} / `{c['slug']}`** "
                    f"— {manifest_badge}  \n"
                    f"📄 {files_str}  \n"
                    f"<small style='color:#64748b'>`{c['path']}`</small>",
                    unsafe_allow_html=True,
                )
                st.markdown("<hr style='margin:6px 0;border-color:#e2e8f0'>", unsafe_allow_html=True)
    else:
        st.info("No contests loaded yet. Upload your first file below.")

    st.divider()

    # ── File type selector ────────────────────────────────────────────────────
    st.markdown("### Step 1 — What are you uploading?")
    file_type_label = st.radio(
        "File type",
        ["📊 Election Results (XLSX / XLS)",
         "🗺️ Precinct Geometry (GeoJSON)",
         "🗂️ Voter File / Crosswalk / Other (CSV)"],
        horizontal=True,
        key="up_file_type",
        label_visibility="collapsed",
    )

    st.divider()

    if "Election Results" in file_type_label:
        _upload_results_flow()
    elif "GeoJSON" in file_type_label:
        _upload_geojson_flow()
    else:
        _upload_csv_flow()


# ── Election results flow ─────────────────────────────────────────────────────

def _upload_results_flow():
    """Full tag-on-intake flow for election result workbooks."""
    st.markdown("### Step 2 — Choose your file")
    up = st.file_uploader(
        "Upload election results workbook (.xlsx or .xls)",
        type=["xlsx", "xls"],
        key="up_results_file",
    )

    if not up:
        st.caption("Accepted: Statement of Votes Cast, Canvass Report, Detail Export, etc.")
        return

    # ── File preview ─────────────────────────────────────────────────────────
    try:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(up.getvalue()), sheet_name=0, nrows=5)
        with st.expander("🔍 File preview (first 5 rows)", expanded=True):
            st.caption(f"{len(df.columns)} columns: `{list(df.columns)[:10]}`")
            st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Can't preview: {e}")

    st.divider()
    st.markdown("### Step 3 — Tag this file before saving")
    st.caption("These tags determine where the file is saved and how the pipeline finds it.")

    # Pre-fill from active campaign
    ac = _load_active_campaign()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        ac_state = ac.get("state", "CA")
        default_state_idx = US_STATES.index(ac_state) if ac_state in US_STATES else 0
        state = st.selectbox("State *", US_STATES, index=default_state_idx, key="up_state")
    with col2:
        county = st.text_input("County *", value=ac.get("county", ""), key="up_county",
                               placeholder="e.g. Sonoma").strip()
    with col3:
        ac_year = int(ac.get("year", CURRENT_YEAR))
        safe_year = ac_year if ac_year in YEAR_OPTIONS else CURRENT_YEAR
        year = st.selectbox("Election Year *", YEAR_OPTIONS,
                            index=YEAR_OPTIONS.index(safe_year), key="up_year")
    with col4:
        slug = st.text_input("Contest Slug *", value=ac.get("contest_slug", ""), key="up_slug",
                             placeholder="e.g. nov2025_special",
                             help="URL-safe name: month+year+type, e.g. nov2025_general").strip()

    col5, col6 = st.columns(2)
    with col5:
        file_subtype = st.selectbox(
            "File subtype",
            ["canvass", "detail", "statement_of_votes", "totals", "other"],
            key="up_subtype",
            help="How this file is used by the pipeline",
        )
    with col6:
        save_name = st.text_input("Save as filename", value=up.name, key="up_save_name")

    notes = st.text_input("Provenance note (optional)", key="up_notes",
                          placeholder="e.g. 'Sonoma ROV official canvass 2025-11-05'")

    # ── Destination preview ───────────────────────────────────────────────────
    if county and slug:
        dest = CONTESTS_DIR / state / county / str(year) / slug / "raw" / save_name.strip()
        st.markdown(
            f"<div style='background:#0f172a;border-radius:8px;padding:10px 16px;margin:10px 0;"
            f"font-size:0.85rem;color:#94a3b8'>📁 Will save to:<br>"
            f"<b style='color:#38bdf8'>{dest.relative_to(BASE_DIR)}</b></div>",
            unsafe_allow_html=True,
        )

        # ── Save button ───────────────────────────────────────────────────────
        if not slug:
            st.warning("Fill in Contest Slug before saving.")
        else:
            if st.button("💾 Save & Register", type="primary", key="up_save_results",
                         use_container_width=False):
                _do_save_results(up, state, county, str(year), slug,
                                 file_subtype, save_name.strip(), notes)
    else:
        if not county:
            st.warning("Fill in County.")
        if not slug:
            st.warning("Fill in Contest Slug  (e.g. `nov2025_general`)")


def _do_save_results(up, state: str, county: str, year: str, slug: str,
                     file_subtype: str, save_name: str, notes: str) -> None:
    raw_dir = CONTESTS_DIR / state / county / year / slug / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / save_name

    # Check for existing and warn
    if dest.exists():
        st.warning(f"⚠️ `{save_name}` already exists — it will be overwritten.")

    dest.write_bytes(up.getvalue())
    _write_manifest(dest, state, county, year, slug, file_subtype, notes)
    _write_contest_metadata(CONTESTS_DIR / state / county / year / slug,
                            state, county, year, slug)

    st.success(f"✅ Saved → `{dest.relative_to(BASE_DIR)}`")
    st.success("✅ Manifest written — pipeline can now find this file automatically.")
    st.info(
        f"**Next step:** Go to **▶️ Pipeline Runner** and run with:\n\n"
        f"`--state {state} --county {county} --year {year} --contest-slug {slug}`"
    )
    st.balloons()
    # Clear uploader state
    st.session_state.pop("up_results_file", None)


# ── GeoJSON flow ──────────────────────────────────────────────────────────────

def _upload_geojson_flow():
    """GeoJSON is county-level — saved to data/CA/counties/Sonoma/geography/precinct_shapes/."""
    st.markdown("### Step 2 — Choose your GeoJSON file")
    st.caption("GeoJSON precinct boundaries are **county-level** — they apply to all election years.")
    up = st.file_uploader("Upload precinct boundary file (.geojson)", type=["geojson", "json"],
                          key="up_geo_file")
    if not up:
        return

    try:
        gj = json.loads(up.getvalue())
        st.info(f"ℹ️ {len(gj.get('features', []))} precinct features detected.")
    except Exception as e:
        st.error(f"Invalid GeoJSON: {e}"); return

    st.divider()
    st.markdown("### Step 3 — Tag this file")

    ac = _load_active_campaign()
    col1, col2 = st.columns(2)
    with col1:
        ac_state = ac.get("state", "CA")
        default_state_idx = US_STATES.index(ac_state) if ac_state in US_STATES else 0
        state = st.selectbox("State *", US_STATES, index=default_state_idx, key="up_geo_state")
    with col2:
        county = st.text_input("County *", value=ac.get("county", ""), key="up_geo_county",
                               placeholder="e.g. Sonoma").strip()

    fname = up.name if up.name.endswith(".geojson") else up.name.replace(".json", ".geojson")
    save_name = st.text_input("Save as filename", value=fname, key="up_geo_name")

    if county:
        geo_dir = BASE_DIR / "data" / state / "counties" / county / "geography" / "precinct_shapes" / "MPREC_GeoJSON"
        dest = geo_dir / save_name.strip()
        st.markdown(
            f"<div style='background:#0f172a;border-radius:8px;padding:10px 16px;margin:10px 0;"
            f"font-size:0.85rem;color:#94a3b8'>📁 Will save to:<br>"
            f"<b style='color:#38bdf8'>{dest.relative_to(BASE_DIR)}</b></div>",
            unsafe_allow_html=True,
        )
        if st.button("💾 Save GeoJSON", type="primary", key="up_save_geo"):
            geo_dir.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(up.getvalue())
            st.success(f"✅ Saved → `{dest.relative_to(BASE_DIR)}`")
            st.info("Geometry will be picked up automatically on next pipeline run.")
            st.session_state.pop("up_geo_file", None)
    else:
        st.warning("Fill in County.")


# ── CSV / Voter / Crosswalk flow ──────────────────────────────────────────────

def _upload_csv_flow():
    """CSV uploads: voter file (year-level) or crosswalk (county-level)."""
    st.markdown("### Step 2 — What kind of CSV is this?")
    purpose = st.selectbox(
        "File purpose",
        ["Voter File", "Crosswalk", "Supplemental"],
        key="up_csv_purpose",
        help="Voter files are year-level. Crosswalks are county-level.",
    )

    up = st.file_uploader("Upload CSV file", type=["csv"], key="up_csv_file")
    if not up:
        return

    try:
        import pandas as pd
        df = pd.read_csv(io.BytesIO(up.getvalue()), nrows=5)
        with st.expander("🔍 Preview", expanded=True):
            st.caption(f"{len(df.columns)} columns: `{list(df.columns)[:10]}`")
            st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Can't preview: {e}")

    st.divider()
    st.markdown("### Step 3 — Tag this file")

    ac = _load_active_campaign()
    col1, col2 = st.columns(2)
    with col1:
        ac_state = ac.get("state", "CA")
        default_state_idx = US_STATES.index(ac_state) if ac_state in US_STATES else 0
        state = st.selectbox("State *", US_STATES, index=default_state_idx, key="up_csv_state")
    with col2:
        county = st.text_input("County *", value=ac.get("county", ""), key="up_csv_county",
                               placeholder="e.g. Sonoma").strip()

    if purpose == "Voter File":
        ac_year = int(ac.get("year", CURRENT_YEAR))
        safe_year = ac_year if ac_year in YEAR_OPTIONS else CURRENT_YEAR
        year = st.selectbox("Election Year *", YEAR_OPTIONS,
                            index=YEAR_OPTIONS.index(safe_year), key="up_csv_year")
        target = BASE_DIR / "data" / state / "counties" / county / "voters" / str(year) if county else None
    elif purpose == "Crosswalk":
        year = None
        target = BASE_DIR / "data" / state / "counties" / county / "geography" / "crosswalks" if county else None
    else:
        year = None
        target = BASE_DIR / "data" / state / "counties" / county / "supplemental" if county else None

    save_name = st.text_input("Save as filename", value=up.name, key="up_csv_name")

    if county and target:
        dest = target / save_name.strip()
        st.markdown(
            f"<div style='background:#0f172a;border-radius:8px;padding:10px 16px;margin:10px 0;"
            f"font-size:0.85rem;color:#94a3b8'>📁 Will save to:<br>"
            f"<b style='color:#38bdf8'>{dest.relative_to(BASE_DIR)}</b></div>",
            unsafe_allow_html=True,
        )
        if st.button("💾 Save", type="primary", key="up_save_csv"):
            target.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(up.getvalue())
            st.success(f"✅ Saved → `{dest.relative_to(BASE_DIR)}`")
            st.session_state.pop("up_csv_file", None)
    else:
        if not county:
            st.warning("Fill in County.")
