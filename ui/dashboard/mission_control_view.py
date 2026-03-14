"""
ui/dashboard/mission_control_view.py — Prompt 31.5

Campaign Mission Control — the primary workflow orchestration dashboard.
Provides a 7-stage workflow overview, system readiness panel, next-action
guidance, and direct navigation shortcuts to all existing pages.

This is an OVERLAY layer — it does not modify any other page.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)

# ── Helper: navigate to another page ─────────────────────────────────────────
def _nav_to(page_id: str):
    st.session_state["active_page"] = page_id
    st.rerun()


# ── Helper: status badge HTML ─────────────────────────────────────────────────
def _badge(text: str, color: str = "#444") -> str:
    return (
        f"<span style='background:{color};color:#fff;border-radius:4px;"
        f"padding:2px 8px;font-size:0.78rem;font-weight:600'>{text}</span>"
    )


def _status_color(s: str) -> str:
    s = s.upper()
    if any(x in s for x in ("OK", "PRESENT", "SUCCESS", "READY", "YES", "DONE")):
        return "#1a7340"
    if any(x in s for x in ("WARN", "PARTIAL", "REVIEW", "LIMITED")):
        return "#b45309"
    if any(x in s for x in ("FAIL", "MISSING", "NO", "NOT", "UNKNOWN", "CRASH")):
        return "#9b1c1c"
    return "#374151"


# ── Load Prompt 31 diagnostics ────────────────────────────────────────────────
def _load_readiness(base_dir: Path):
    try:
        from engine.diagnostics.system_readiness import evaluate_system_state
        return evaluate_system_state(base_dir)
    except Exception as exc:
        logger.debug(f"[MC] readiness error: {exc}")
        return None


def _load_guidance(base_dir: Path):
    try:
        from engine.ui.user_guidance import evaluate_guidance
        return evaluate_guidance(base_dir)
    except Exception as exc:
        logger.debug(f"[MC] guidance error: {exc}")
        return None


def _load_detected_files(base_dir: Path):
    try:
        from engine.ingestion.contest_file_watcher import scan_for_new_contest_files
        return scan_for_new_contest_files(base_dir)
    except Exception as exc:
        logger.debug(f"[MC] watcher error: {exc}")
        return []


def _load_pipeline_suggestions(base_dir: Path):
    try:
        from engine.ingestion.auto_pipeline_runner import suggest_pipeline_runs
        return suggest_pipeline_runs(base_dir)
    except Exception as exc:
        logger.debug(f"[MC] suggestions error: {exc}")
        return []


def _load_latest_run(base_dir: Path) -> Optional[dict]:
    runs_dir = base_dir / "reports" / "pipeline_runs"
    if not runs_dir.exists():
        return None
    run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()])
    if not run_dirs:
        # Check for run summary JSONs written by observer
        return None
    latest = run_dirs[-1]
    json_path = latest / "pipeline_summary.json"
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Fallback: build minimal summary from directory name
    return {"run_id": latest.name, "overall": "UNKNOWN", "contest_slug": "?"}


def _load_flow_findings(base_dir: Path) -> list[dict]:
    analysis_path = base_dir / "reports" / "ui_analysis" / "user_flow_analysis.md"
    findings = []
    if analysis_path.exists():
        text = analysis_path.read_text(encoding="utf-8")
        # Extract finding titles from markdown headers
        for line in text.splitlines():
            if line.startswith("### ") and ("🔴" in line or "🟡" in line):
                # Strip leading '### N. 🔴 🔧 Title'
                parts = line.lstrip("# ").split(".", 1)
                title = parts[-1].strip() if len(parts) > 1 else line.lstrip("# ")
                findings.append({"title": title})
    return findings[:3]  # Show top 3


# ── Campaign context ─────────────────────────────────────────────────────────-
def _get_campaign_ctx(data: dict) -> dict:
    return {
        "name": data.get("campaign_name", "Unknown Campaign"),
        "contest": data.get("contest_id", "—"),
        "state": data.get("state", "—"),
        "county": data.get("county", "—"),
        "stage": data.get("campaign_stage", "Planning"),
        "status": data.get("campaign_status", "Active"),
    }


# ── Main render ───────────────────────────────────────────────────────────────
def render_mission_control(data: dict):
    base_dir = Path(data.get("base_dir", "."))

    # Custom CSS for Mission Control
    st.markdown("""
    <style>
    .mc-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 12px;
        padding: 20px 28px;
        margin-bottom: 20px;
        color: #f8fafc;
        border: 1px solid #334155;
    }
    .mc-header h1 { margin: 0; font-size: 1.6rem; letter-spacing: -0.5px; }
    .mc-header p  { margin: 4px 0 0; color: #94a3b8; font-size:0.9rem; }
    .mc-stage {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
        transition: border-color 0.2s;
    }
    .mc-stage:hover { border-color: #60a5fa; }
    .mc-stage-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 4px;
    }
    .mc-stage-sub { color: #94a3b8; font-size: 0.82rem; margin-top: 4px; }
    .mc-next-action {
        background: linear-gradient(135deg, #1a4731 0%, #166534 100%);
        border: 1px solid #22c55e;
        border-radius: 10px;
        padding: 16px 20px;
        color: #86efac;
        margin-bottom: 18px;
    }
    .mc-next-action strong { color: #4ade80; font-size: 1.0rem; }
    .mc-readiness {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 18px;
    }
    .mc-kv { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px solid #1e293b; }
    .mc-kv:last-child { border-bottom: none; }
    .mc-kv-key { color: #94a3b8; font-size:0.85rem; }
    .mc-kv-val { font-size:0.85rem; font-weight:600; color:#f1f5f9; }
    .mc-run-box {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius:10px;
        padding: 14px 18px;
        color:#cbd5e1;
        font-size:0.85rem;
    }
    .mc-insight {
        background:#1c1917;
        border-left: 3px solid #f59e0b;
        padding: 8px 14px;
        border-radius: 0 8px 8px 0;
        margin: 6px 0;
        font-size: 0.83rem;
        color: #fcd34d;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Campaign context ─────────────────────────────────────────────────────
    ctx = _get_campaign_ctx(data)

    st.markdown(f"""
    <div class="mc-header">
      <h1>🎯 Campaign Mission Control</h1>
      <p>
        <b>{ctx['name']}</b> &nbsp;·&nbsp;
        {ctx['state']} / {ctx['county']} &nbsp;·&nbsp;
        Stage: <b>{ctx['stage']}</b> &nbsp;·&nbsp;
        <span style='color:#4ade80;font-weight:600'>{ctx['status']}</span>
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Load all diagnostics (cached for this render) ─────────────────────────
    with st.spinner("Loading system state…"):
        readiness   = _load_readiness(base_dir)
        guidance    = _load_guidance(base_dir)
        det_files   = _load_detected_files(base_dir)
        suggestions = _load_pipeline_suggestions(base_dir)
        latest_run  = _load_latest_run(base_dir)
        ux_findings = _load_flow_findings(base_dir)

    # ── Layout: left main + right sidebar ────────────────────────────────────
    col_main, col_right = st.columns([3, 1.4])

    # ═══════════════════════════════════════════════════════════════════════════
    # RIGHT COLUMN — System Status snapshot
    # ═══════════════════════════════════════════════════════════════════════════
    with col_right:

        # System Readiness
        st.markdown("### 🩺 System Readiness")
        if readiness:
            overall_color = {"READY": "#1a7340", "PARTIAL": "#b45309", "NOT_READY": "#9b1c1c"}.get(readiness.overall, "#444")
            st.markdown(_badge(readiness.overall, overall_color), unsafe_allow_html=True)
            st.markdown('<div class="mc-readiness">', unsafe_allow_html=True)
            for chk in readiness.checks:
                sc = _status_color(chk.status)
                st.markdown(
                    f'<div class="mc-kv">'
                    f'<span class="mc-kv-key">{chk.name}</span>'
                    f'<span class="mc-kv-val" style="color:{sc}">{chk.status}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Readiness engine unavailable.")

        st.divider()

        # Latest Pipeline Run
        st.markdown("### 🔄 Latest Pipeline Run")
        if latest_run:
            overall = latest_run.get("overall", "UNKNOWN")
            color = _status_color(overall)
            st.markdown(f'<div class="mc-run-box">', unsafe_allow_html=True)
            st.markdown(
                f"**{latest_run.get('contest_slug', '?')}**  "
                f"{_badge(overall, color)}",
                unsafe_allow_html=True,
            )
            if latest_run.get("rows_loaded"):
                st.markdown(f"Rows: `{latest_run['rows_loaded']:,}`")
            if latest_run.get("precinct_join_rate") is not None:
                rate = latest_run["precinct_join_rate"]
                st.markdown(f"Join rate: `{rate:.1%}`")
            if latest_run.get("archive_built") is not None:
                ab = "✅ Yes" if latest_run["archive_built"] else "⏳ No"
                st.markdown(f"Archive: {ab}")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="mc-run-box">No pipeline runs recorded yet.</div>', unsafe_allow_html=True)

        st.divider()

        # Quick Nav
        st.markdown("### 🔗 Quick Navigation")
        nav_buttons = [
            ("📤 Upload Data",         "📂 Upload Contest Data"),
            ("▶️ Run Pipeline",        "▶️ Pipeline Runner"),
            ("🗺️ Precinct Map",       "🗺️ Precinct Map"),
            ("🗃️ Archive",            "🏛️ Historical Archive"),
            ("🔬 Simulations",         "🔬 Simulations"),
            ("📋 Strategy",            "📋 Strategy"),
            ("🩺 Diagnostics",         "🩺 Diagnostics"),
        ]
        for label, pid in nav_buttons:
            if st.button(label, key=f"mc_nav_{pid}", use_container_width=True):
                _nav_to(pid)

    # ═══════════════════════════════════════════════════════════════════════════
    # LEFT COLUMN — Next Action + 7 Stages
    # ═══════════════════════════════════════════════════════════════════════════
    with col_main:

        # ── Next Recommended Action ───────────────────────────────────────────
        if guidance and guidance.items:
            top = guidance.items[0]
            icon = {"CRITICAL": "🚨", "IMPORTANT": "⚠️", "INFO": "ℹ️", "OK": "✅"}.get(top.priority, "•")
            st.markdown(f"""
            <div class="mc-next-action">
              <strong>{icon} Next Recommended Action</strong><br>
              <span style='color:#d1fae5;font-size:0.95rem'>{top.action}</span><br>
              <span style='color:#86efac;font-size:0.8rem'>📍 {top.where_in_ui}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="mc-next-action">
              <strong>✅ All checks passed</strong><br>
              <span style='color:#d1fae5'>System appears ready for normal operation.</span>
            </div>
            """, unsafe_allow_html=True)

        # ── Workflow progress bar ─────────────────────────────────────────────
        st.markdown("#### Campaign Workflow")
        stages_short = ["Setup", "Data", "Analysis", "Modeling", "Strategy", "War Room", "Tools"]
        prog_cols = st.columns(len(stages_short))
        for i, (col, stage) in enumerate(zip(prog_cols, stages_short)):
            with col:
                color = "#22c55e" if i == 1 else "#334155"  # highlight current stage
                st.markdown(
                    f"<div style='text-align:center;background:{color};border-radius:6px;"
                    f"padding:4px;font-size:0.72rem;color:#f1f5f9'>{stage}</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        # ─────────────────────────────────────────────────────────────────────
        # STAGE 1 — Campaign Setup
        # ─────────────────────────────────────────────────────────────────────
        with st.expander("1️⃣  Campaign Setup", expanded=False):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**Active Campaign:** {ctx['name']}")
                st.markdown(f"**Contest:** `{ctx['contest']}`")
                st.markdown(f"**Area:** {ctx['state']} / {ctx['county']}")
                st.markdown(f"**Stage:** {ctx['stage']}  |  **Status:** {ctx['status']}")
                if ctx["contest"] in ("—", "", None):
                    st.warning("No active contest configured. Go to Campaign Admin to create one.")
                else:
                    st.success("Campaign context loaded.")
            with col_b:
                if st.button("⚙️ Campaign Admin", key="mc_s1_admin", use_container_width=True):
                    _nav_to("🏛️ Campaign Admin")
                if st.button("🗳️ Setup", key="mc_s1_setup", use_container_width=True):
                    _nav_to("🗳️ Campaign Setup")

        # ─────────────────────────────────────────────────────────────────────
        # STAGE 2 — Data Ingestion  ← most prominent
        # ─────────────────────────────────────────────────────────────────────
        # Determine readiness
        files_present = bool(det_files)
        pipeline_ready = any(s.auto_run_eligible for s in suggestions) if suggestions else False
        pipeline_ran   = bool(latest_run)

        s2_status = "❌ No Data" if not files_present else ("✅ Ready" if pipeline_ran else "⚠️ Pipeline Needed")
        s2_color  = _status_color(s2_status)

        with st.expander(f"2️⃣  Data Ingestion — {s2_status}", expanded=True):
            st.markdown(
                f'<div style="background:#0f172a;border-radius:8px;padding:14px 18px;margin-bottom:10px">'
                f'<b style="color:#f1f5f9">⭐ This is the most critical stage.</b><br>'
                f'<span style="color:#94a3b8;font-size:0.85rem">'
                f'Upload your election results file here, then run the pipeline. '
                f'Everything else (map, archive, simulations, strategy) requires this to succeed.'
                f'</span></div>',
                unsafe_allow_html=True,
            )
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**Contest files detected:** {len(det_files)}")
                if det_files:
                    for f in det_files[:4]:
                        status_badge = _badge(f.status, _status_color(f.status))
                        st.markdown(
                            f"📄 `{f.filename}` · `{f.contest_slug}/{f.year}` "
                            f"· {status_badge}",
                            unsafe_allow_html=True,
                        )
                else:
                    st.warning("No contest files found in canonical paths.")

                # Pipeline suggestion
                if suggestions:
                    for sug in suggestions[:2]:
                        if sug.suggestion == "ALREADY_RUN":
                            st.success(f"✅ Pipeline already run for `{sug.contest_slug}`")
                        elif sug.suggestion == "RUN_PIPELINE":
                            st.info(f"⚡ Ready to run pipeline for `{sug.contest_slug}` — {sug.reason[:80]}")
                        elif sug.suggestion == "REVIEW_FIRST":
                            st.warning(f"📋 Review needed for `{sug.contest_slug}` — {sug.reason[:80]}")

                # Pipeline run status
                if latest_run:
                    overall = latest_run.get("overall", "UNKNOWN")
                    color = _status_color(overall)
                    st.markdown(
                        f"**Last run:** `{latest_run.get('contest_slug', '?')}` — "
                        f"{_badge(overall, color)}",
                        unsafe_allow_html=True,
                    )
                else:
                    st.info("No pipeline runs recorded yet. Upload data then run the pipeline.")

            with col_b:
                if st.button("📤 Upload Data", key="mc_s2_upload", use_container_width=True, type="primary"):
                    _nav_to("📂 Upload Contest Data")
                if st.button("📂 File Registry", key="mc_s2_registry", use_container_width=True):
                    _nav_to("📂 Data Manager")
                if st.button("▶️ Run Pipeline", key="mc_s2_pipeline", use_container_width=True):
                    _nav_to("▶️ Pipeline Runner")

        # ─────────────────────────────────────────────────────────────────────
        # STAGE 3 — Historical Analysis
        # ─────────────────────────────────────────────────────────────────────
        archive_present = readiness and any(
            c.name == "Archive" and c.status not in ("NOT BUILT", "MISSING", "UNKNOWN")
            for c in readiness.checks
        ) if readiness else False

        s3_status = "✅ Archive Built" if archive_present else "⏳ Not Built"
        with st.expander(f"3️⃣  Historical Analysis — {s3_status}", expanded=not archive_present):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                if archive_present:
                    st.success("Archive is present. Historical analysis is available.")
                else:
                    st.warning(
                        "Archive not yet built.\n\n"
                        "**Reason:** Pipeline has not completed the ARCHIVE_INGEST step for this contest.\n\n"
                        "**Next step:** Run the pipeline in Stage 2, then return here."
                    )
                if readiness:
                    for chk in readiness.checks:
                        if chk.name in ("Archive", "Precinct Join Rate", "Model Calibration"):
                            color = _status_color(chk.status)
                            st.markdown(f"**{chk.name}:** {_badge(chk.status, color)}", unsafe_allow_html=True)
            with col_b:
                if st.button("🗃️ Archive", key="mc_s3_archive", use_container_width=True):
                    _nav_to("🏛️ Historical Archive")
                if st.button("🗺️ Precinct Map", key="mc_s3_map", use_container_width=True):
                    _nav_to("🗺️ Precinct Map")
                if st.button("📐 Calibration", key="mc_s3_cal", use_container_width=True):
                    _nav_to("📐 Calibration")

        # ─────────────────────────────────────────────────────────────────────
        # STAGE 4 — Targeting & Modeling
        # ─────────────────────────────────────────────────────────────────────
        model_ready = readiness and any(
            c.name == "Model Calibration" and c.status in ("OK", "PRESENT")
            for c in readiness.checks
        ) if readiness else False

        s4_status = "✅ Calibrated" if model_ready else ("⚠️ Partial" if archive_present else "⏳ Pending")
        with st.expander(f"4️⃣  Targeting & Modeling — {s4_status}", expanded=False):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**Model Calibration:** {_badge(s4_status, _status_color(s4_status))}", unsafe_allow_html=True)
                if archive_present:
                    st.info("Archive is present — calibration can run. Check Calibration page.")
                else:
                    st.warning("Targeting requires archive data. Complete Stage 3 first.")
                hist_count = 1 if archive_present else 0
                st.markdown(f"**Historical elections available:** {hist_count}")
            with col_b:
                if st.button("🎯 Targeting", key="mc_s4_tgt", use_container_width=True):
                    _nav_to("🎯 Targeting")
                if st.button("🔬 Simulations", key="mc_s4_sim", use_container_width=True):
                    _nav_to("🔬 Simulations")
                if st.button("⚡ Advanced Modeling", key="mc_s4_adv", use_container_width=True):
                    _nav_to("⚡ Advanced Modeling")
                if st.button("🧠 Voter Intel", key="mc_s4_vi", use_container_width=True):
                    _nav_to("🧠 Voter Intelligence")

        # ─────────────────────────────────────────────────────────────────────
        # STAGE 5 — Strategy Planning
        # ─────────────────────────────────────────────────────────────────────
        strategy_dir = base_dir / "derived" / "strategy"
        strategy_ready = strategy_dir.exists() and any(strategy_dir.rglob("*.md"))
        sims_have_data = bool(latest_run and latest_run.get("overall") == "SUCCESS")

        s5_status = "✅ Strategy Available" if strategy_ready else "⏳ Not Generated"
        with st.expander(f"5️⃣  Strategy Planning — {s5_status}", expanded=False):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                if strategy_ready:
                    st.success("Strategy documents are available.")
                else:
                    st.info(
                        "No strategy documents generated yet.\n\n"
                        "**Next step:** Run simulations, then open the Strategy page to generate a plan."
                    )
                st.markdown(f"**Simulations run:** {'✅ Yes' if sims_have_data else '⏳ No'}")
                st.markdown(f"**Optimal allocation:** {'✅ Yes' if strategy_ready else '⏳ Not generated'}")
            with col_b:
                if st.button("📋 Strategy", key="mc_s5_strat", use_container_width=True):
                    _nav_to("📋 Strategy")
                if st.button("🔬 Simulations", key="mc_s5_sim", use_container_width=True):
                    _nav_to("🔬 Simulations")
                if st.button("🧭 Pol. Intel", key="mc_s5_polintel", use_container_width=True):
                    _nav_to("🧭 Political Intelligence")

        # ─────────────────────────────────────────────────────────────────────
        # STAGE 6 — War Room Operations
        # ─────────────────────────────────────────────────────────────────────
        s6_status = "⚠️ Pre-Planning" if not strategy_ready else "✅ Operational"
        with st.expander(f"6️⃣  War Room Operations — {s6_status}", expanded=False):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**Campaign stage:** {ctx['stage']}")
                if not strategy_ready:
                    st.info(
                        "Complete Strategy Planning (Stage 5) before activating War Room monitoring."
                    )
                else:
                    st.success("Strategy is available — War Room can be activated.")
                st.markdown(f"**Operational metrics:** {'Available' if sims_have_data else 'None yet'}")
            with col_b:
                if st.button("🪖 War Room", key="mc_s6_wr", use_container_width=True):
                    _nav_to("🪖 War Room")
                if st.button("🩺 Diagnostics", key="mc_s6_diag", use_container_width=True):
                    _nav_to("🩺 Diagnostics")

        # ─────────────────────────────────────────────────────────────────────
        # STAGE 7 — Advanced Tools
        # ─────────────────────────────────────────────────────────────────────
        with st.expander("7️⃣  Advanced Tools — For power users & debugging", expanded=False):
            st.caption("🔧 These tools are for detailed inspection, modeling tuning, and debugging.")
            tool_cols = st.columns(3)
            tools = [
                ("🗄️ Data Explorer",     "🗄️ Data Explorer"),
                ("🩺 Diagnostics",        "🩺 Diagnostics"),
                ("📐 Calibration",        "📐 Calibration"),
                ("⚡ Advanced Modeling",  "⚡ Advanced Modeling"),
                ("🗂️ Source Registry",   "🗂️ Source Registry"),
                ("📊 Swing Modeling",     "📊 Swing Modeling"),
            ]
            for i, (label, pid) in enumerate(tools):
                with tool_cols[i % 3]:
                    if st.button(label, key=f"mc_s7_{i}", use_container_width=True):
                        _nav_to(pid)

        # ─────────────────────────────────────────────────────────────────────
        # UX Insights from Prompt 31 flow analyzer
        # ─────────────────────────────────────────────────────────────────────
        if ux_findings:
            st.markdown("---")
            st.markdown("#### 💡 UI Insights *(from automated flow analysis)*")
            st.caption("These are documented friction points noted for future simplification.")
            for finding in ux_findings:
                st.markdown(
                    f'<div class="mc-insight">{finding["title"]}</div>',
                    unsafe_allow_html=True,
                )

        # ─────────────────────────────────────────────────────────────────────
        # All guidance items
        # ─────────────────────────────────────────────────────────────────────
        if guidance and len(guidance.items) > 1:
            st.markdown("---")
            with st.expander("📋 All System Guidance Items", expanded=False):
                for item in guidance.items:
                    icon = {"CRITICAL": "🚨", "IMPORTANT": "⚠️", "INFO": "ℹ️", "OK": "✅"}.get(item.priority, "•")
                    st.markdown(f"**{icon} {item.title}**")
                    st.markdown(f"> {item.detail}")
                    st.caption(f"Action: {item.action}  |  Where: {item.where_in_ui}")
                    st.divider()
