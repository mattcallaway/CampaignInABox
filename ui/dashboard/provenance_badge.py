"""
ui/dashboard/provenance_badge.py — Prompt 14

Helper functions for rendering data provenance badges in the Streamlit UI.

Provenance types:
  REAL      — Green  — from actual campaign runtime data
  SIMULATED — Blue   — from model simulation / Monte Carlo
  ESTIMATED — Yellow — from heuristics / prior assumptions
  MISSING   — Red    — required but not present

Usage:
    from ui.dashboard.provenance_badge import badge, metric_with_badge, legend

    st.markdown(f"Win Probability: **42%** {badge('SIMULATED')}", unsafe_allow_html=True)
    metric_with_badge("Turn Probability", "42%", "SIMULATED")
"""
from __future__ import annotations

import streamlit as st
from typing import Any, Optional

# ── Badge style constants ─────────────────────────────────────────────────────
BADGE_STYLES: dict[str, dict] = {
    "REAL": {
        "icon": "🟢",
        "label": "REAL",
        "bg":    "#D1FAE5",
        "color": "#065F46",
        "border": "#6EE7B7",
        "description": "Actual campaign data",
    },
    "SIMULATED": {
        "icon": "🔵",
        "label": "SIMULATED",
        "bg":    "#DBEAFE",
        "color": "#1E40AF",
        "border": "#93C5FD",
        "description": "Model / Monte Carlo",
    },
    "ESTIMATED": {
        "icon": "🟡",
        "label": "ESTIMATED",
        "bg":    "#FEF3C7",
        "color": "#92400E",
        "border": "#FCD34D",
        "description": "Heuristic / prior assumption",
    },
    "MISSING": {
        "icon": "🔴",
        "label": "MISSING",
        "bg":    "#FEE2E2",
        "color": "#991B1B",
        "border": "#FCA5A5",
        "description": "Required but not present",
    },
}


def badge(source_type: str, compact: bool = False) -> str:
    """
    Return an HTML badge span for the given provenance source_type.

    Args:
        source_type: "REAL" | "SIMULATED" | "ESTIMATED" | "MISSING"
        compact: if True, show only icon (no label text)

    Returns: HTML string (requires unsafe_allow_html=True)
    """
    style = BADGE_STYLES.get(source_type.upper(), BADGE_STYLES["MISSING"])
    icon  = style["icon"]
    label = "" if compact else f" {style['label']}"
    bg    = style["bg"]
    color = style["color"]
    border = style["border"]
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {border};'
        f'border-radius:4px;padding:1px 6px;font-size:0.72rem;font-weight:600;'
        f'letter-spacing:0.03em;margin-left:4px;white-space:nowrap">'
        f'{icon}{label}</span>'
    )


def metric_with_badge(
    label: str,
    value: Any,
    source_type: str,
    delta: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """
    Render a Streamlit metric with a provenance badge inline.
    Uses st.metric with a badge appended to the label.
    """
    style = BADGE_STYLES.get(source_type.upper(), BADGE_STYLES["MISSING"])
    badge_html = badge(source_type)
    full_label = f"{label}"

    # Streamlit metric doesn't support HTML labels; use a combination instead
    with st.container():
        st.metric(label=full_label, value=str(value) if value is not None else "—", delta=delta)
        st.markdown(
            f'<div style="margin-top:-14px;margin-bottom:4px">'
            f'{badge_html}'
            + (f' <span style="color:#6B7280;font-size:0.78rem">{notes}</span>' if notes else "")
            + "</div>",
            unsafe_allow_html=True,
        )


def legend() -> None:
    """Render the data status legend as compact colored chips."""
    items = " &nbsp; ".join(
        f'<span style="background:{s["bg"]};color:{s["color"]};border:1px solid {s["border"]};'
        f'border-radius:4px;padding:2px 8px;font-size:0.75rem;font-weight:600">'
        f'{s["icon"]} {s["label"]}</span>'
        for s in BADGE_STYLES.values()
    )
    st.markdown(
        f'<div style="margin-bottom:8px"><b style="font-size:0.8rem">Data Provenance:</b> {items}</div>',
        unsafe_allow_html=True,
    )


def provenance_summary_card(provenance_data: Optional[dict]) -> None:
    """Render a compact provenance summary card from provenance JSON data."""
    if not provenance_data:
        st.caption("No provenance data available.")
        return

    summary = provenance_data.get("summary", {})
    total = sum(summary.values()) or 1
    war_room_ready = provenance_data.get("war_room_ready", False)

    status_color = "#065F46" if war_room_ready else "#92400E"
    status_text  = "War Room Ready ✅" if war_room_ready else "Needs Real Data ⚠️"

    cols = st.columns(5)
    for i, (stype, count) in enumerate(summary.items()):
        style = BADGE_STYLES.get(stype, {})
        pct   = count / total * 100
        with cols[i]:
            st.markdown(
                f'<div style="text-align:center;background:{style.get("bg","#F8FAFC")};'
                f'border:1px solid {style.get("border","#E2E8F0")};border-radius:8px;padding:8px 4px">'
                f'<div style="font-size:1.4rem">{style.get("icon","⬜")}</div>'
                f'<div style="font-weight:700;color:{style.get("color","#374151")}">{count}</div>'
                f'<div style="font-size:0.72rem;color:{style.get("color","#6B7280")}">{stype}</div>'
                f'<div style="font-size:0.65rem;color:#6B7280">{pct:.0f}%</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    with cols[4]:
        st.markdown(
            f'<div style="text-align:center;background:#F8FAFC;border:1px solid #E2E8F0;'
            f'border-radius:8px;padding:8px 4px">'
            f'<div style="font-size:0.75rem;font-weight:600;color:{status_color};margin-top:8px">'
            f'{status_text}</div></div>',
            unsafe_allow_html=True,
        )
