"""
ui/dashboard/pipeline_runner_view.py

Run Pipeline & Archive Builder dashboard page.
Allows triggering the modeling pipeline and archive builder from the UI
with live log streaming and results display.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _discover_contests() -> list[dict]:
    """
    Return list of contests discoverable in the system.

    Priority:
      1. Canonical contest structure (data/contests/) via ContestResolver — P28
      2. Legacy trees as read-only fallback (labelled with LEGACY PATH warning)
    """
    contests: list[dict] = []
    seen: set[str] = set()

    def _add(county, state, year, slug, has_votes, label_suffix=""):
        key = f"{state}/{county}/{year}/{slug}"
        if key in seen:
            return
        seen.add(key)
        label = f"{county} / {year} / {slug}" + ("" if has_votes else " ⚠️ no votes") + label_suffix
        contests.append({"label": label, "county": county, "state": state,
                          "year": year, "slug": slug, "has_votes": has_votes})

    # ── 1. Canonical path (ContestResolver, P28) ─────────────────────────────
    try:
        from engine.contest_data.contest_resolver import ContestResolver
        resolver = ContestResolver(BASE_DIR)
        for c in resolver.list_all_contests():
            _add(c["county"], c["state"], c["year"], c["contest_slug"],
                 has_votes=c["has_primary"])
    except Exception:
        pass  # resolver not yet importable — fall through

    # ── 2. Legacy fallback: votes/{year}/{state}/{county}/{slug}/ ─────────────
    votes_root = BASE_DIR / "votes"
    if votes_root.exists():
        for year_dir in sorted(votes_root.iterdir(), reverse=True):
            if not year_dir.is_dir(): continue
            year = year_dir.name
            for state_dir in year_dir.iterdir():
                if not state_dir.is_dir(): continue
                state = state_dir.name
                for county_dir in state_dir.iterdir():
                    if not county_dir.is_dir(): continue
                    county = county_dir.name
                    for contest_dir in county_dir.iterdir():
                        if not contest_dir.is_dir(): continue
                        slug = contest_dir.name
                        has_votes = any((contest_dir / f).exists()
                                        for f in ["detail.xlsx", "detail.xls", "detail.csv"])
                        _add(county, state, year, slug, has_votes,
                             " ⚠️ LEGACY — re-upload via Data Manager")

    # ── 3. Legacy fallback: data/elections/{state}/{county}/{slug}/ ───────────
    elections_root = BASE_DIR / "data" / "elections"
    if elections_root.exists():
        for state_dir in elections_root.iterdir():
            if not state_dir.is_dir(): continue
            state = state_dir.name
            for county_dir in state_dir.iterdir():
                if not county_dir.is_dir(): continue
                county = county_dir.name
                for contest_dir in county_dir.iterdir():
                    if not contest_dir.is_dir(): continue
                    slug = contest_dir.name
                    xlsx = list(contest_dir.glob("*.xlsx")) + list(contest_dir.glob("*.xls"))
                    year = "unknown"
                    for x in xlsx:
                        import re as _re
                        m = _re.search(r"(20\d{2})", x.name)
                        if m: year = m.group(1); break
                    _add(county, state, year, slug, bool(xlsx),
                         " ⚠️ LEGACY — re-upload via Data Manager")

    # ── 4. Legacy fallback: data/{state}/counties/{county}/votes/ ────────────
    data_root = BASE_DIR / "data"
    if data_root.exists():
        for state_dir in data_root.iterdir():
            if not state_dir.is_dir() or state_dir.name in ("contests", "elections", "uploads"): continue
            state = state_dir.name
            counties_dir = state_dir / "counties"
            if not counties_dir.exists(): continue
            for county_dir in counties_dir.iterdir():
                if not county_dir.is_dir(): continue
                county = county_dir.name
                votes_dir = county_dir / "votes"
                if not votes_dir.exists(): continue
                for year_dir in votes_dir.iterdir():
                    if not year_dir.is_dir(): continue
                    year = year_dir.name
                    for contest_dir in year_dir.iterdir():
                        if not contest_dir.is_dir(): continue
                        slug = contest_dir.name
                        has_votes = any((contest_dir / f).exists()
                                        for f in ["detail.xlsx", "detail.xls", "detail.csv"])
                        _add(county, state, year, slug, has_votes,
                             " ⚠️ LEGACY — re-upload via Data Manager")

    return sorted(contests, key=lambda c: (c["county"], c["year"], c["slug"]))


def _stream_process(cmd: list[str], log_box, stop_event: threading.Event) -> int:

    """Run a subprocess and write output to a Streamlit text area line by line."""
    lines: list[str] = []
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(BASE_DIR),
    )
    try:
        for raw_line in proc.stdout:
            if stop_event.is_set():
                proc.terminate()
                break
            line = raw_line.rstrip()
            lines.append(line)
            log_box.code("\n".join(lines[-200:]), language=None)  # keep last 200 lines
        proc.wait()
    except Exception:
        proc.kill()
    return proc.returncode


def _latest_run_log() -> str:
    """Read the most recent run log file, returns content or empty string."""
    log_dir = BASE_DIR / "logs" / "latest"
    if not log_dir.exists():
        return ""
    logs = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if logs:
        try:
            return logs[0].read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
    return ""


# ── Main view ─────────────────────────────────────────────────────────────────

def render_pipeline_runner(data: dict) -> None:
    st.markdown("<h1 class='page-title'>▶️ Pipeline Runner</h1>", unsafe_allow_html=True)
    st.caption("Trigger the modeling pipeline or archive builder directly from the dashboard.")

    tab_pipeline, tab_archive, tab_logs = st.tabs([
        "🔬 Modeling Pipeline",
        "🏛️ Archive Builder",
        "📋 Latest Run Log",
    ])

    # ─── TAB 1: Modeling Pipeline ────────────────────────────────────────────
    with tab_pipeline:
        st.subheader("Election Modeling Pipeline")
        st.info(
            "Runs the full 24-step modeling pipeline: geography validation → vote allocation → "
            "precinct modeling → scoring → field plans → forecasts → strategy.",
            icon="ℹ️",
        )

        contests = _discover_contests()
        col1, col2 = st.columns([3, 2])

        with col1:
            st.markdown("#### Contest Selection")
            if contests:
                contest_labels = ["— select —"] + [c["label"] for c in contests]
                chosen_label = st.selectbox("Select contest", contest_labels, key="pl_contest_sel")
                chosen = next((c for c in contests if c["label"] == chosen_label), None)
            else:
                chosen = None
                st.warning("No contests found. Upload election data first via Data Manager.")

            # Manual override fields
            with st.expander("Override / manual entry", expanded=(chosen is None)):
                pl_state  = st.text_input("State", value=chosen["state"]  if chosen else "CA",  key="pl_state")
                pl_county = st.text_input("County", value=chosen["county"] if chosen else "",    key="pl_county")
                pl_year   = st.text_input("Year",   value=chosen["year"]   if chosen else "2024", key="pl_year")
                pl_slug   = st.text_input("Contest slug", value=chosen["slug"] if chosen else "", key="pl_slug",
                                          placeholder="e.g. nov2024_general")
                pl_detail = st.text_input("Override detail.xlsx path (optional)", key="pl_detail",
                                          placeholder="votes/2024/CA/Sonoma/nov2024_general/detail.xlsx")
                pl_staging = st.text_input("Staging directory (optional)", key="pl_staging")

        with col2:
            st.markdown("#### Options")
            pl_method = st.selectbox("Membership method", ["auto", "crosswalk", "area_weighted"], key="pl_method")
            pl_mode   = st.selectbox("Contest mode", ["auto", "measure", "candidate"], key="pl_mode")
            pl_commit = st.checkbox("Git commit outputs", value=False, key="pl_commit")

            st.divider()
            st.markdown("#### Quick flags")
            pl_check_only = st.checkbox("Structure check only (--check-structure)", key="pl_check")
            pl_ingest_only = st.checkbox("Ingest only (--ingest-only)", key="pl_ingest")

        st.divider()

        # Build command
        state  = pl_state  or (chosen["state"]  if chosen else "CA")
        county = pl_county or (chosen["county"] if chosen else "")
        year   = pl_year   or (chosen["year"]   if chosen else "")
        slug   = pl_slug   or (chosen["slug"]   if chosen else "")

        cmd = [sys.executable, "scripts/run_pipeline.py"]
        if pl_check_only:
            cmd += ["--check-structure"]
        elif pl_ingest_only:
            cmd += ["--ingest-only"]
            if pl_staging:
                cmd += ["--staging-dir", pl_staging]
        else:
            if not (state and county and year and slug):
                st.error("Fill in State, County, Year, and Contest Slug before running.")
                st.stop()
            cmd += [
                "--state", state,
                "--county", county,
                "--year", year,
                "--contest-slug", slug,
                "--membership-method", pl_method,
                "--contest-mode", pl_mode,
            ]
            if pl_detail:
                cmd += ["--detail-path", pl_detail]
            if pl_staging:
                cmd += ["--staging-dir", pl_staging]
            if not pl_commit:
                cmd += ["--no-commit"]

        st.code(" ".join(cmd), language="bash")

        run_btn = st.button("▶️ Run Modeling Pipeline", type="primary",
                            use_container_width=True, key="pl_run_btn")

        if run_btn:
            st.markdown("---")
            stop_event = threading.Event()
            log_placeholder = st.empty()
            log_placeholder.code("Starting pipeline…", language=None)
            stop_btn_col, _ = st.columns([1, 4])
            with stop_btn_col:
                if st.button("⛔ Stop", key="pl_stop"):
                    stop_event.set()

            start_ts = datetime.now()
            with st.spinner("Pipeline running…"):
                rc = _stream_process(cmd, log_placeholder, stop_event)
            elapsed = (datetime.now() - start_ts).seconds

            if stop_event.is_set():
                st.warning(f"⚠️ Pipeline was stopped after {elapsed}s.")
            elif rc == 0:
                st.success(f"✅ Pipeline completed in {elapsed}s.")
                st.cache_data.clear()
            else:
                st.error(f"❌ Pipeline exited with code {rc} after {elapsed}s. Check log below.")

    # ─── TAB 2: Archive Builder ───────────────────────────────────────────────
    with tab_archive:
        st.subheader("Election Archive Builder (Prompt 25B/25C)")
        st.info(
            "Runs the archive discovery pipeline: source scanning → page discovery → "
            "directory prediction (P25C) → file extraction → classification → ingestion.",
            icon="ℹ️",
        )

        ab_col1, ab_col2 = st.columns([3, 2])
        with ab_col1:
            ab_state  = st.text_input("State", value="CA", key="ab_state")
            ab_county = st.text_input("County", value="Sonoma", key="ab_county")

        with ab_col2:
            ab_online = st.checkbox("Online mode (live HTTP probes)", value=True, key="ab_online")
            ab_dry    = st.checkbox("Dry run (no file downloads)", value=False, key="ab_dry")

        # Check that archive_builder is importable
        ab_cmd = [
            sys.executable, "-m", "engine.archive_builder.archive_builder",
            "--state", ab_state or "CA",
            "--county", ab_county or "Sonoma",
        ]
        if not ab_online:
            ab_cmd += ["--offline"]
        if ab_dry:
            ab_cmd += ["--dry-run"]

        st.code(" ".join(ab_cmd), language="bash")

        ab_run_btn = st.button("🏛️ Run Archive Builder", type="primary",
                               use_container_width=True, key="ab_run_btn")

        if ab_run_btn:
            st.markdown("---")
            ab_stop = threading.Event()
            ab_log  = st.empty()
            ab_log.code("Starting archive builder…", language=None)

            start_ts = datetime.now()
            with st.spinner("Archive builder running…"):
                rc = _stream_process(ab_cmd, ab_log, ab_stop)
            elapsed = (datetime.now() - start_ts).seconds

            if rc == 0:
                st.success(f"✅ Archive builder completed in {elapsed}s.")
                # Surface the latest reports
                rpt_dir = BASE_DIR / "reports" / "archive_builder"
                if rpt_dir.exists():
                    latest = sorted(rpt_dir.glob("*archive_discovery_report.json"),
                                    key=lambda p: p.stat().st_mtime, reverse=True)
                    if latest:
                        import json
                        try:
                            summary = json.loads(latest[0].read_text(encoding="utf-8"))
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Predicted Dirs", summary.get("predicted_directories", 0))
                            c2.metric("Confirmed Dirs", summary.get("directories_confirmed", 0))
                            c3.metric("Files Found",    summary.get("files_found", 0))
                            st.caption(f"Report: `{latest[0].name}`")
                        except Exception:
                            pass
            else:
                st.error(f"❌ Archive builder exited with code {rc} after {elapsed}s.")

        # Show latest archive report (always)
        st.divider()
        st.markdown("#### Latest Archive Discovery Report")
        rpt_dir = BASE_DIR / "reports" / "archive_builder"
        if rpt_dir.exists():
            latest_md = sorted(rpt_dir.glob("*archive_discovery_report.md"),
                               key=lambda p: p.stat().st_mtime, reverse=True)
            if latest_md:
                txt = latest_md[0].read_text(encoding="utf-8", errors="replace")
                st.markdown(txt)
                st.caption(f"File: `{latest_md[0].name}`")
            else:
                st.info("No archive reports yet. Run the Archive Builder above.")
        else:
            st.info("No reports directory found.")

    # ─── TAB 3: Latest Run Log ────────────────────────────────────────────────
    with tab_logs:
        st.subheader("Latest Run Log")

        log_dir = BASE_DIR / "logs" / "latest"
        run_logs = []
        if log_dir.exists():
            run_logs = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)

        if not run_logs:
            st.info("No run logs found. Run the pipeline to generate logs.")
        else:
            log_names = [p.name for p in run_logs[:10]]
            selected_log = st.selectbox("Select log", log_names, key="log_sel")
            selected_path = log_dir / selected_log

            if st.button("🔄 Refresh", key="log_refresh"):
                st.rerun()

            try:
                content = selected_path.read_text(encoding="utf-8", errors="replace")
                # Colour-code: step headers, OK, WARN, FAIL
                lines_out = []
                for line in content.splitlines():
                    u = line.upper()
                    if "HARD_FAIL" in u or "ERROR" in u or "❌" in line:
                        lines_out.append(f"🔴 {line}")
                    elif "WARN" in u or "⚠️" in line or "SKIP" in u:
                        lines_out.append(f"🟡 {line}")
                    elif "STEP_DONE" in u or "✅" in line or "PASS" in u:
                        lines_out.append(f"🟢 {line}")
                    else:
                        lines_out.append(f"   {line}")

                st.code("\n".join(lines_out), language=None)

                # Summary metrics from log
                n_done = sum(1 for l in content.splitlines() if "STEP_DONE" in l.upper())
                n_skip = sum(1 for l in content.splitlines() if "STEP_SKIP" in l.upper())
                n_fail = sum(1 for l in content.splitlines() if "HARD_FAIL" in l.upper() or "ERROR" in l.upper())
                m1, m2, m3 = st.columns(3)
                m1.metric("Steps Done", n_done)
                m2.metric("Steps Skipped", n_skip)
                m3.metric("Errors", n_fail)

            except Exception as e:
                st.error(f"Could not read log: {e}")
