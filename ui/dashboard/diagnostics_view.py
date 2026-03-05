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


def render_diagnostics(data: dict) -> None:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#1E293B,#334155);
         border-radius:12px;padding:18px 28px;margin-bottom:20px;color:white'>
      <h2 style='margin:0;color:white'>🔬 System Diagnostics</h2>
      <p style='margin:4px 0 0 0;color:#CBD5E1'>
        Post-run audit · Join guard · Integrity checks · Artifact status
      </p>
    </div>""", unsafe_allow_html=True)

    audit  = data.get("post_audit", {})
    jg_csv = data.get("join_guard_csv", pd.DataFrame())
    rep    = data.get("repair_csv", pd.DataFrame())
    val_md = data.get("validation_md", "")
    qa_md  = data.get("qa_md", "")

    # ── System health banner ──────────────────────────────────────────────────
    health = audit.get("system_health", "UNKNOWN") if audit else "UNKNOWN"
    clr    = _color(health)
    st.markdown(
        f"<div style='background:{clr}15;border-left:6px solid {clr};"
        f"border-radius:10px;padding:16px 22px;margin-bottom:18px'>"
        f"<span style='font-size:1.8rem'>{_badge(health)}</span>"
        f" <span style='font-size:1.3rem;font-weight:700;color:{clr}'>System Health: {health}</span>"
        f"<br><small style='color:#64748B'>Run: <code>{audit.get('run_id','—')}</code>"
        f" · Contest: <code>{audit.get('contest_id','—')}</code></small>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── 4-metric row ──────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        _stat_card("Geometry",
                   audit.get("geometry_status", "UNKNOWN") if audit else "UNKNOWN")
    with col2:
        _stat_card("Join Guard",
                   audit.get("join_guard_status", "UNKNOWN") if audit else "UNKNOWN")
    with col3:
        repairs = audit.get("integrity_repairs_count", 0) if audit else 0
        c = "#16A34A" if repairs == 0 else "#D97706"
        st.markdown(
            f"<div style='background:white;border:1px solid #E2E8F0;border-radius:10px;"
            f"padding:16px 20px;border-top:4px solid {c}'>"
            f"<div style='font-size:0.8rem;color:#64748B'>Integrity Repairs</div>"
            f"<div style='font-size:1.6rem;font-weight:700;color:{c}'>{repairs}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col4:
        missing = audit.get("missing_artifacts", []) if audit else []
        mc = "#16A34A" if not missing else "#D97706"
        st.markdown(
            f"<div style='background:white;border:1px solid #E2E8F0;border-radius:10px;"
            f"padding:16px 20px;border-top:4px solid {mc}'>"
            f"<div style='font-size:0.8rem;color:#64748B'>Missing Artifacts</div>"
            f"<div style='font-size:1.6rem;font-weight:700;color:{mc}'>{len(missing)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Detail tabs ───────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Audit Report", "🔗 Join Guard", "🔧 Integrity Repairs",
        "📄 Validation", "✅ QA Report"
    ])

    with tab1:
        if audit:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**System health:** `{audit.get('system_health','—')}`")
                st.markdown(f"**Join guard:** `{audit.get('join_guard_status','—')}`")
                st.markdown(f"**Geometry:** `{audit.get('geometry_status','—')}`")
                st.markdown(f"**Prompt:** `{audit.get('prompt','—')}`")
                st.markdown(f"**Model version:** `{audit.get('model_version','—')}`")
            with c2:
                st.markdown(f"**Strategy pack:** {'✅' if audit.get('strategy_pack_generated') else '❌'}")
                st.markdown(f"**Simulation results:** {'✅' if audit.get('simulation_results_generated') else '❌'}")
                st.markdown(f"**Repairs:** `{audit.get('integrity_repairs_count', 0)}`")
                if missing:
                    st.warning(f"Missing: {', '.join(missing)}")
            if audit.get("warnings"):
                st.warning("**Warnings:**\n" + "\n".join(f"- {w}" for w in audit["warnings"]))
            if audit.get("errors"):
                st.error("**Errors:**\n" + "\n".join(f"- {e}" for e in audit["errors"]))
        else:
            st.info("Post-run audit not yet generated. Run the pipeline first.")

    with tab2:
        if jg_csv.empty:
            st.info("Join guard CSV not found.")
        else:
            for _, row in jg_csv.iterrows():
                s = str(row.get("status", "PASS"))
                clr2 = _color(s)
                st.markdown(
                    f"<div style='border-left:4px solid {clr2};padding:10px 16px;margin:6px 0;"
                    f"background:white;border-radius:6px'>"
                    f"{_badge(s)} <strong>{row.get('join_name','?')}</strong>"
                    f" — Left: {row.get('left_rows',0)}, Right: {row.get('right_rows',0)},"
                    f" Matched: {row.get('matched_rows',0)}, Unmatched: {row.get('left_unmatched',0)}"
                    f" ({row.get('unmatched_pct',0):.1f}%)"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    with tab3:
        if rep.empty:
            st.success("✅ No integrity repairs on record.")
        else:
            crit = rep[rep.get("repair_type", pd.Series()) == "CRITICAL_NO_REPAIR"] if "repair_type" in rep.columns else pd.DataFrame()
            repaired = rep[rep.get("repair_type", pd.Series()) != "CRITICAL_NO_REPAIR"] if "repair_type" in rep.columns else rep
            if not crit.empty:
                st.error(f"🔴 {len(crit)} CRITICAL rows (registered=0 with ballots>0 — not repaired)")
                st.dataframe(crit, use_container_width=True, hide_index=True)
            if not repaired.empty:
                st.warning(f"⚠️ {len(repaired)} repairs applied")
                st.dataframe(repaired, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Export Repair Log",
                               rep.to_csv(index=False).encode("utf-8"),
                               "integrity_repairs.csv", "text/csv")

    with tab4:
        if val_md:
            st.markdown(val_md)
        else:
            st.info("Validation report not found in logs/latest/.")

    with tab5:
        if qa_md:
            st.markdown(qa_md)
        else:
            st.info("QA report not found in logs/latest/.")


def _stat_card(label: str, status: str) -> None:
    clr = _color(status)
    st.markdown(
        f"<div style='background:white;border:1px solid #E2E8F0;border-radius:10px;"
        f"padding:16px 20px;border-top:4px solid {clr}'>"
        f"<div style='font-size:0.8rem;color:#64748B'>{label}</div>"
        f"<div style='font-size:1.4rem;font-weight:700;color:{clr}'>"
        f"{_badge(status)} {status.upper()}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
