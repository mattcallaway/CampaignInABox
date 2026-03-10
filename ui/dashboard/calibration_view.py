"""
ui/dashboard/calibration_view.py — Prompt 15

Calibration Dashboard — 3 panels:
  1. Calibration Status  — active/prior_only, sources, data coverage
  2. Parameter Estimates — turnout lift, persuasion lift, baseline turnout
  3. Forecast Accuracy   — predicted vs actual results chart & table

Reads from:
  derived/calibration/calibration_summary.json (latest run)
  derived/calibration/turnout_parameters.json
  derived/calibration/persuasion_parameters.json
  derived/calibration/turnout_lift_parameters.json
  derived/calibration/forecast_accuracy.csv
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CALIB_DIR = BASE_DIR / "derived" / "calibration"


def _rj(name: str) -> dict:
    p = CALIB_DIR / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _badge(label: str, color: str = "#4A90D9") -> str:
    return (
        f"<span style='background:{color};color:#fff;padding:2px 8px;"
        f"border-radius:4px;font-size:0.75rem;font-weight:bold'>{label}</span>"
    )


def _status_badge(status: str) -> str:
    colors = {
        "active": "#16A34A",
        "prior_only": "#D97706",
        "none": "#6B7280",
    }
    labels = {
        "active": "✅ ACTIVE",
        "prior_only": "🟡 PRIOR ONLY",
        "none": "❌ None",
    }
    return _badge(labels.get(status, status.upper()), colors.get(status, "#6B7280"))


def _confidence_badge(conf: str) -> str:
    colors = {"high": "#16A34A", "medium": "#D97706", "low": "#EF4444", "none": "#6B7280"}
    return _badge(conf.upper(), colors.get(conf, "#6B7280"))


def render_calibration(data: dict) -> None:
    st.markdown("# 📐 Model Calibration")
    st.markdown("*How campaign intelligence learns from elections and field results.*")
    st.divider()

    # ── Load calibration data ─────────────────────────────────────────────────
    summary = _rj("calibration_summary.json")
    turnout_p = _rj("turnout_parameters.json")
    persuasion_p = _rj("persuasion_parameters.json")
    lift_p = _rj("turnout_lift_parameters.json")

    acc_path = CALIB_DIR / "forecast_accuracy.csv"
    acc_df = pd.DataFrame()
    if acc_path.exists():
        try:
            acc_df = pd.read_csv(acc_path)
        except Exception:
            pass

    no_calib = not summary
    if no_calib:
        st.info(
            "📐 **No calibration data yet.** Run the full pipeline to generate "
            "calibration parameters. Place historical election files in "
            "`data/elections/CA/<county>/<year>/detail.xls` for best accuracy."
        )
        # Show parameter defaults
        _render_default_params()
        return

    # ── Tab layout ────────────────────────────────────────────────────────────
    tab_status, tab_params, tab_accuracy = st.tabs([
        "📊 Calibration Status",
        "🎯 Parameter Estimates",
        "🎯 Forecast Accuracy",
    ])

    with tab_status:
        _render_status(summary)

    with tab_params:
        _render_parameters(turnout_p, persuasion_p, lift_p, summary)

    with tab_accuracy:
        _render_accuracy(acc_df, summary)


# ── Panel 1: Status ───────────────────────────────────────────────────────────

def _render_status(summary: dict) -> None:
    status = summary.get("calibration_status", "prior_only")
    confidence = summary.get("calibration_confidence", "none")
    sources = summary.get("calibration_sources", [])
    run_id = summary.get("run_id", "—")

    st.markdown(f"### Calibration Status &nbsp; {_status_badge(status)}", unsafe_allow_html=True)
    st.markdown(
        f"**Confidence:** &nbsp; {_confidence_badge(confidence)} &nbsp; "
        f"&nbsp; **Run:** `{run_id[:20] if run_id != '—' else '—'}`",
        unsafe_allow_html=True
    )
    st.markdown("")

    col1, col2, col3 = st.columns(3)
    with col1:
        n_elec = summary.get("n_historical_elections", 0)
        n_rec  = summary.get("n_historical_records", 0)
        icon = "✅" if "historical_elections" in sources else "❌"
        st.metric(label=f"{icon} Historical Elections", value=n_elec,
                  help="Number of historical election years parsed.")
        if n_rec:
            st.caption(f"{n_rec:,} precinct-year records")

    with col2:
        gotv = summary.get("gotv_universe_size", 0)
        pers = summary.get("persuasion_universe_size", 0)
        icon = "✅" if "voter_turnout_history" in sources else "❌"
        st.metric(label=f"{icon} Voter Intelligence", value=f"{gotv + pers:,}",
                  help="GOTV + persuasion universe voters with propensity scores.")
        if gotv or pers:
            st.caption(f"GOTV: {gotv:,} | Persuasion: {pers:,}")

    with col3:
        icon = "✅" if summary.get("runtime_has_data") else "❌"
        st.metric(label=f"{icon} Runtime Field Data",
                  value="Available" if summary.get("runtime_has_data") else "Not yet",
                  help="Live field results from War Room.")

    st.divider()
    st.markdown("#### Data Sources Required")
    st.markdown("""
| Source | Location | Status |
|--------|----------|--------|
| Historical Elections | `data/elections/CA/<county>/<year>/detail.xls` | Parsed on pipeline run |
| Voter Intelligence | `derived/voter_models/` | From Prompt 12 model run |
| Field Results | `data/campaign_runtime/<state>/<county>/<slug>/field_results.csv` | Enter in War Room |
| Contact Results | `data/campaign_runtime/.../contact_results.csv` | Enter in War Room |
""")

    st.markdown("#### Confidence Scale")
    cols = st.columns(4)
    with cols[0]:
        st.markdown(f"{_badge('HIGH','#16A34A')} — ≥5 elections, ≥100 precincts", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"{_badge('MEDIUM','#D97706')} — ≥3 elections, ≥50 precincts", unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"{_badge('LOW','#EF4444')} — ≥1 election", unsafe_allow_html=True)
    with cols[3]:
        st.markdown(f"{_badge('NONE','#6B7280')} — Prior values only", unsafe_allow_html=True)


# ── Panel 2: Parameters ────────────────────────────────────────────────────────

def _render_parameters(
    turnout_p: dict, persuasion_p: dict, lift_p: dict, summary: dict
) -> None:
    st.markdown("### Calibrated Model Parameters")
    st.caption("These values feed directly into the Monte Carlo simulation and field planning engine.")
    st.markdown("")

    col1, col2, col3 = st.columns(3)

    with col1:
        val = turnout_p.get("baseline_turnout_probability", 0.45)
        method = turnout_p.get("method", "prior")
        conf = turnout_p.get("confidence", "none")
        st.metric(
            label="📈 Baseline Turnout",
            value=f"{val:.1%}",
            delta=f"{val - 0.45:+.1%} vs prior" if method != "prior" else None,
        )
        st.markdown(
            f"Method: {method} &nbsp; {_confidence_badge(conf)}",
            unsafe_allow_html=True,
        )
        if turnout_p.get("n_elections"):
            st.caption(f"From {turnout_p['n_elections']} elections, {turnout_p.get('n_precincts', 0)} precincts")

    with col2:
        val = lift_p.get("turnout_lift_per_contact", 0.06)
        method = lift_p.get("method", "prior")
        conf = lift_p.get("confidence", "none")
        st.metric(
            label="🚪 Turnout Lift / Contact",
            value=f"{val:.1%}",
            delta=f"{val - 0.06:+.1%} vs Gerber & Green prior" if method != "prior" else None,
        )
        st.markdown(
            f"Method: {method} &nbsp; {_confidence_badge(conf)}",
            unsafe_allow_html=True,
        )
        if lift_p.get("notes"):
            st.caption(lift_p["notes"][:80])

    with col3:
        val = persuasion_p.get("persuasion_lift_per_contact", 0.006)
        method = persuasion_p.get("method", "prior")
        conf = persuasion_p.get("confidence", "none")
        st.metric(
            label="💬 Persuasion Lift / Contact",
            value=f"{val:.3%}",
            delta=f"{val - 0.006:+.3%} vs prior" if method != "prior" else None,
        )
        st.markdown(
            f"Method: {method} &nbsp; {_confidence_badge(conf)}",
            unsafe_allow_html=True,
        )
        if persuasion_p.get("notes"):
            st.caption(persuasion_p["notes"][:80])

    st.divider()

    # Forecast comparison table
    st.markdown("#### Baseline vs Calibrated Forecast")
    import pandas as pd
    rows = [
        {
            "Parameter": "Baseline Turnout Probability",
            "Prior (Default)": "45.0%",
            "Calibrated": f"{turnout_p.get('baseline_turnout_probability', 0.45):.1%}",
            "Δ": f"{turnout_p.get('baseline_turnout_probability', 0.45) - 0.45:+.1%}",
            "Method": turnout_p.get("method", "prior"),
        },
        {
            "Parameter": "Turnout Lift per Contact",
            "Prior (Default)": "6.00%",
            "Calibrated": f"{lift_p.get('turnout_lift_per_contact', 0.06):.2%}",
            "Δ": f"{lift_p.get('turnout_lift_per_contact', 0.06) - 0.06:+.2%}",
            "Method": lift_p.get("method", "prior"),
        },
        {
            "Parameter": "Persuasion Lift per Contact",
            "Prior (Default)": "0.600%",
            "Calibrated": f"{persuasion_p.get('persuasion_lift_per_contact', 0.006):.3%}",
            "Δ": f"{persuasion_p.get('persuasion_lift_per_contact', 0.006) - 0.006:+.3%}",
            "Method": persuasion_p.get("method", "prior"),
        },
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.info(
        "📌 **How to improve calibration:** Add historical election files and enter "
        "field/contact results in the War Room. More real data = higher confidence.", icon="ℹ️"
    )


# ── Panel 3: Forecast Accuracy ─────────────────────────────────────────────────

def _render_accuracy(acc_df: pd.DataFrame, summary: dict) -> None:
    st.markdown("### Forecast Accuracy Tracking")
    st.caption(
        "Compares the model's predicted support rate against actual historical results. "
        "Accuracy improves as more elections are calibrated."
    )

    if acc_df.empty:
        st.info(
            "🗳️ **No accuracy records yet.** Accuracy tracking requires historical "
            "election data with both predicted and actual results. "
            "Add `detail.xls` files to `data/elections/CA/<county>/<year>/` and rerun."
        )
        return

    # Summary metrics
    mae = acc_df["abs_error"].mean() if "abs_error" in acc_df.columns else None
    n = len(acc_df)

    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Contests Tracked", n)
    if mae is not None:
        col2.metric("📏 Mean Absolute Error", f"{mae:.2%}")
        accuracy_label = "High" if mae < 0.03 else "Medium" if mae < 0.08 else "Low"
        col3.metric("🎯 Accuracy", accuracy_label)

    st.markdown("")

    # Accuracy chart
    if "actual" in acc_df.columns and "predicted" in acc_df.columns:
        try:
            chart_df = acc_df[["contest", "actual", "predicted"]].copy()
            chart_df = chart_df.set_index("contest")
            st.bar_chart(chart_df, height=250)
        except Exception:
            pass

    # Table
    display_cols = [c for c in ["contest", "predicted", "actual", "error", "abs_error", "date"] if c in acc_df.columns]
    if display_cols:
        st.dataframe(
            acc_df[display_cols].sort_values("contest", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

    st.info(
        "📌 **Accuracy improves over multiple election cycles.** "
        "Add historical detail.xls files for each election year to extend the accuracy record.", icon="ℹ️"
    )


# ── Default params display (no calibration run yet) ──────────────────────────

def _render_default_params() -> None:
    st.markdown("### Default Parameters (Prior Values)")
    st.caption("These literature-based defaults are used until calibration data is available.")
    import pandas as pd
    rows = [
        {"Parameter": "Baseline Turnout Probability", "Value": "45.0%", "Source": "Typical special election prior"},
        {"Parameter": "Turnout Lift per Contact", "Value": "6.00%", "Source": "Gerber & Green GOTV meta-analysis"},
        {"Parameter": "Persuasion Lift per Contact", "Value": "0.600%", "Source": "Campaign literature prior"},
        {"Parameter": "Turnout Variance", "Value": "8.0%", "Source": "Historical ballot measure baseline"},
        {"Parameter": "Persuasion Variance", "Value": "0.300%", "Source": "Campaign literature prior"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
