"""
ui/dashboard/diagnostics_view.py — Prompt 9

System diagnostics panel — reads from engine audit artifacts.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd


def _color(status: str) -> str:
    s = str(status).upper()
    if s in ("PASS", "HEALTHY", "COMPLETE"):  return "#16A34A"
    if s in ("WARN", "DEGRADED", "SKIP"):     return "#D97706"
    if s in ("FAIL",):                         return "#DC2626"
    return "#64748B"


def _badge(status: str) -> str:
    s = str(status).upper()
    if s in ("PASS", "HEALTHY", "COMPLETE"):  return "✅"
    if s in ("WARN", "DEGRADED", "SKIP"):     return "⚠️"
    if s in ("FAIL",):                         return "❌"
    return "⏭️"


# ── Main render ───────────────────────────────────────────────────────────────

def render_diagnostics(data: dict) -> None:
    from ui.components.alerts import render_alert
    from ui.components.metric_card import render_metric_card
    from ui.components.badges import render_status_badge

    st.markdown("<h1 class='page-title'>System Diagnostics</h1>", unsafe_allow_html=True)
    st.caption("Post-run audit, integrity checks, and data artifacts.")

    audit  = data.get("post_audit", {})
    jg_csv = data.get("join_guard_csv", pd.DataFrame())
    rep    = data.get("repair_csv", pd.DataFrame())
    val_md = data.get("validation_md", "")
    qa_md  = data.get("qa_md", "")

    # ── System health banner ──────────────────────────────────────────────────
    health = audit.get("system_health", "UNKNOWN") if audit else "UNKNOWN"
    clr    = _color(health)
    
    health_box = f"""
    <div style='background:{clr}11; border-left:4px solid {clr}; border-radius:8px; padding:16px; margin-bottom:20px; color:#1A2A3A;'>
        <div style='font-size:1.4rem; font-weight:700; color:{clr}'>{_badge(health)} System Health: {health}</div>
        <div style='font-size:0.85rem; color:#5B6B7D; margin-top:4px'>Run ID: <code>{audit.get('run_id','—')}</code> | Contest: <code>{audit.get('contest_id','—')}</code></div>
    </div>
    """
    st.markdown(health_box, unsafe_allow_html=True)

    # ── High Level Cards ──────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        geo = audit.get("geometry_status", "UNKNOWN") if audit else "UNKNOWN"
        c_g = "success" if geo == "PASS" else ("warning" if geo == "WARN" else "danger")
        render_metric_card("Geometry", geo, None, None, c_g)
    with c2:
        jg = audit.get("join_guard_status", "UNKNOWN") if audit else "UNKNOWN"
        c_j = "success" if jg == "PASS" else ("warning" if jg == "WARN" else "danger")
        render_metric_card("Join Guard", jg, None, None, c_j)
    with c3:
        repairs = audit.get("integrity_repairs_count", 0) if audit else 0
        c_r = "success" if repairs == 0 else "warning"
        render_metric_card("Repairs", f"{repairs}", "Rows patched", None, c_r)
    with c4:
        missing = len(audit.get("missing_artifacts", [])) if audit else 0
        c_m = "success" if missing == 0 else "danger"
        render_metric_card("Missing Artifacts", f"{missing}", "In pipeline outputs", None, c_m)

    st.markdown("---")

    # ── Grouped Diagnostics ──────────────────────────────────────────────────
    st.markdown("### Diagnostic Groups")
    
    # Missing Inputs
    miss_stat = "PASS" if missing == 0 else "FAIL"
    with st.expander(f"Data Completeness & Missing Inputs  {_badge(miss_stat)}"):
        if missing > 0:
            for m in audit.get("missing_artifacts", []):
                render_alert("warning", f"Missing artifact: {m}")
        else:
            render_alert("success", "All required artifacts are present.")

    # Data Integrity
    int_stat = "PASS" if repairs == 0 else "WARN"
    with st.expander(f"Data Integrity & Repairs  {_badge(int_stat)}"):
        if rep.empty:
            render_alert("success", "No integrity repairs needed.")
        else:
            crit = rep[rep.get("repair_type", pd.Series()) == "CRITICAL_NO_REPAIR"] if "repair_type" in rep.columns else pd.DataFrame()
            repaired = rep[rep.get("repair_type", pd.Series()) != "CRITICAL_NO_REPAIR"] if "repair_type" in rep.columns else rep
            if not crit.empty:
                render_alert("critical", f"{len(crit)} CRITICAL rows (not repaired)")
                st.dataframe(crit, use_container_width=True, hide_index=True)
            if not repaired.empty:
                render_alert("warning", f"{len(repaired)} repairs applied")
                st.dataframe(repaired, use_container_width=True, hide_index=True)

    # Join / Geometry
    jgeo_stat = "PASS" if geo == "PASS" and jg == "PASS" else "WARN"
    with st.expander(f"Join / Geometry  {_badge(jgeo_stat)}"):
        if jg_csv.empty:
            render_alert("info", "Join guard CSV not found.")
        else:
            for _, row in jg_csv.iterrows():
                sts = str(row.get("status", "PASS"))
                clr2 = _color(sts)
                st.markdown(f"<div style='border-left:4px solid {clr2}; padding:8px 12px; margin-bottom:8px; background:#F8FBFF; border-radius:4px;'>{_badge(sts)} <b>{row.get('join_name','?')}</b> | Matched: {row.get('matched_rows',0)} | Unmatched: {row.get('left_unmatched',0)}</div>", unsafe_allow_html=True)

    # Audit & QA Reports
    with st.expander(f"Audit Results & QA Report  {_badge('PASS')}"):
        if audit.get("warnings"):
            for w in audit["warnings"]:
                render_alert("warning", w)
        if audit.get("errors"):
            for e in audit["errors"]:
                render_alert("critical", e)
        if not audit.get("warnings") and not audit.get("errors"):
            render_alert("success", "No warnings or errors in recent audit.")
        if qa_md:
            st.markdown(qa_md)
