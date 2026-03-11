"""
ui/dashboard/political_intelligence_view.py — Prompt 17

Political Intelligence Dashboard — 4 panels:
  1. Poll Tracker        — poll trend + weighted average + CI band
  2. Registration Trends — party registration shift + new voter rate
  3. Ballot Return Monitor — daily returns + return rate + projection
  4. Demographic Insights — education, income, persuasion opportunities

  + Intelligence Fusion panel — S_adj = S_model + α·P + β·D + γ·R + δ·M

Reads from:
  derived/intelligence/poll_average.json
  derived/intelligence/polling_normalized.csv
  derived/intelligence/registration_summary.json
  derived/intelligence/registration_trends.csv
  derived/intelligence/ballot_returns_summary.json
  derived/intelligence/ballot_returns_daily.csv
  derived/intelligence/precinct_demographics.csv
  derived/intelligence/support_adjustment.json
  derived/intelligence/macro_environment.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import streamlit as st
import pandas as pd

BASE_DIR  = Path(__file__).resolve().parent.parent.parent
INTEL_DIR = BASE_DIR / "derived" / "intelligence"


def _rj(name: str) -> dict:
    p = INTEL_DIR / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _rc(name: str) -> pd.DataFrame:
    p = INTEL_DIR / name
    if p.exists():
        try:
            return pd.read_csv(p)
        except Exception:
            pass
    return pd.DataFrame()


def _badge(label: str, color: str = "#4A90D9") -> str:
    return (
        f"<span style='background:{color};color:#fff;padding:2px 8px;"
        f"border-radius:4px;font-size:0.75rem;font-weight:600'>{label}</span>"
    )


def _source_badge(source_type: str) -> str:
    colors = {
        "EXTERNAL":  "#16A34A",
        "REAL":      "#16A34A",
        "ESTIMATED": "#D97706",
        "SIMULATED": "#6B7280",
        "MISSING":   "#EF4444",
    }
    return _badge(source_type, colors.get(source_type.upper(), "#6B7280"))


def render_political_intelligence(data: dict) -> None:
    st.markdown("# 🧭 Political Intelligence")
    st.markdown("*External signals from polls, registration trends, ballot returns, and macro environment.*")
    st.divider()

    # ── Load all intelligence data ─────────────────────────────────────────────
    poll_avg    = _rj("poll_average.json")
    reg_summary = _rj("registration_summary.json")
    br_summary  = _rj("ballot_returns_summary.json")
    macro_env   = _rj("macro_environment.json")
    adj         = _rj("support_adjustment.json")
    polls_df    = _rc("polling_normalized.csv")
    reg_df      = _rc("registration_trends.csv")
    br_daily    = _rc("ballot_returns_daily.csv")
    demo_df     = _rc("precinct_demographics.csv")

    has_any = any([
        poll_avg.get("poll_average") is not None,
        reg_summary.get("has_registration_data"),
        br_summary.get("has_ballot_return_data"),
        macro_env.get("has_macro_data"),
    ])

    # ── Top-level fusion metrics ───────────────────────────────────────────────
    _render_fusion_header(adj)

    st.divider()

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab_polls, tab_reg, tab_ballot, tab_demo, tab_macro = st.tabs([
        "📊 Poll Tracker",
        "📋 Registration Trends",
        "🗳️ Ballot Returns",
        "👥 Demographics",
        "🌐 Macro Environment",
    ])

    with tab_polls:
        _render_poll_tracker(poll_avg, polls_df)

    with tab_reg:
        _render_registration(reg_summary, reg_df)

    with tab_ballot:
        _render_ballot_returns(br_summary, br_daily)

    with tab_demo:
        _render_demographics(demo_df, adj)

    with tab_macro:
        _render_macro(macro_env)

    if not has_any:
        st.info(
            "🧭 **No intelligence data loaded yet.**\n\n"
            "To activate this layer, add files to:\n"
            "- `data/intelligence/polling/` — CSV, XLSX, or JSON poll files\n"
            "- `data/intelligence/registration/` — registration snapshot CSVs\n"
            "- `data/intelligence/ballot_returns/` — daily return report CSVs\n"
            "- `data/intelligence/macro/` — macro signal JSON/CSV\n\n"
            "Then rerun the pipeline. The intelligence fusion engine will update your "
            "adjusted support estimate and strategy recommendations."
        )


# ── Fusion Header ─────────────────────────────────────────────────────────────

def _render_fusion_header(adj: dict) -> None:
    st.markdown("### 🧮 Intelligence Fusion Summary")
    if not adj:
        st.caption("No adjustment computed yet. Run pipeline to activate.")
        return

    baseline  = adj.get("model_support_baseline", 0)
    adjusted  = adj.get("adjusted_support", baseline)
    delta     = adj.get("intelligence_adjustment", 0.0)
    impact    = adj.get("impact", "NEUTRAL")
    src_type  = adj.get("source_type", "SIMULATED")
    n_polls   = adj.get("n_polls", 0)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Baseline Support (Model)", f"{baseline:.1%}")
    col2.metric(
        "🧭 Intelligence Adjustment",
        f"{delta:+.2%}",
        delta=f"{impact}",
        delta_color="normal" if delta >= 0 else "inverse",
    )
    col3.metric("🎯 Adjusted Support", f"{adjusted:.1%}",
                delta=f"{delta:+.2%} vs baseline",
                delta_color="normal" if delta >= 0 else "inverse")
    col4.metric("📡 Polls Included", n_polls)

    st.markdown(
        f"**Signal Source:** {_source_badge(src_type)} &nbsp; "
        f"**Impact:** {_badge('↑ POSITIVE','#16A34A') if delta > 0.005 else (_badge('↓ NEGATIVE','#EF4444') if delta < -0.005 else _badge('→ NEUTRAL','#6B7280'))}",
        unsafe_allow_html=True
    )

    # Contributions breakdown
    contribs = adj.get("contributions", {})
    if contribs:
        w = adj.get("weights", {})
        rows = [
            {"Signal": "Polling (α)", "Weight": w.get("alpha_polling", 0.60), "Raw Signal": contribs.get("polling_signal", 0), "Contribution": contribs.get("polling_signal", 0) * w.get("alpha_polling", 0.60)},
            {"Signal": "Demographic (β)", "Weight": w.get("beta_demographic", 0.15), "Raw Signal": contribs.get("demographic_signal", 0), "Contribution": contribs.get("demographic_signal", 0) * w.get("beta_demographic", 0.15)},
            {"Signal": "Registration (γ)", "Weight": w.get("gamma_registration", 0.20), "Raw Signal": contribs.get("registration_signal", 0), "Contribution": contribs.get("registration_signal", 0) * w.get("gamma_registration", 0.20)},
            {"Signal": "Macro (δ)", "Weight": w.get("delta_macro", 0.05), "Raw Signal": contribs.get("macro_signal", 0), "Contribution": contribs.get("macro_signal", 0) * w.get("delta_macro", 0.05)},
        ]
        df_c = pd.DataFrame(rows)
        for col in ["Raw Signal", "Contribution"]:
            df_c[col] = df_c[col].map(lambda x: f"{x:+.4%}")
        st.dataframe(df_c, use_container_width=True, hide_index=True)


# ── Tab 1: Poll Tracker ───────────────────────────────────────────────────────

def _render_poll_tracker(poll_avg: dict, polls_df: pd.DataFrame) -> None:
    st.markdown("### 📊 Poll Tracker")
    pa = poll_avg.get("poll_average")

    if pa is None:
        st.info("No polling data loaded. Add CSV/XLSX/JSON poll files to `data/intelligence/polling/`")
        _show_polling_format()
        return

    ci_lo = poll_avg.get("confidence_interval_low", pa - 0.03)
    ci_hi = poll_avg.get("confidence_interval_high", pa + 0.03)
    n     = poll_avg.get("n_polls", 0)
    src   = poll_avg.get("source_type", "SIMULATED")

    col1, col2, col3 = st.columns(3)
    col1.metric("🗳️ Poll Average (Support)", f"{pa:.1%}")
    col2.metric("📏 95% Confidence Interval", f"{ci_lo:.1%} – {ci_hi:.1%}")
    col3.metric("📊 Polls Used", n)
    st.markdown(f"**Provenance:** {_source_badge(src)} &nbsp;&nbsp; **Latest:** {poll_avg.get('latest_poll_date', '—')}", unsafe_allow_html=True)
    st.markdown("")

    # Win threshold indicator
    win_threshold = 0.50
    if pa >= win_threshold:
        st.success(f"✅ Poll average ({pa:.1%}) is **above** the 50% win threshold.")
    else:
        st.warning(f"⚠️ Poll average ({pa:.1%}) is **below** the 50% win threshold.")

    st.divider()

    # Individual polls table
    if not polls_df.empty:
        st.markdown("#### Individual Polls")
        show_cols = [c for c in ["pollster", "field_date_end", "sample_size", "support_percent", "oppose_percent", "undecided_percent", "geography"] if c in polls_df.columns]
        if show_cols:
            display = polls_df[show_cols].copy()
            for col in ["support_percent", "oppose_percent", "undecided_percent"]:
                if col in display.columns:
                    display[col] = display[col].map(lambda x: f"{x:.1%}" if pd.notna(x) else "")
            st.dataframe(display, use_container_width=True, hide_index=True)

    # Polls used in average
    polls_used = poll_avg.get("polls_used", [])
    if polls_used:
        st.markdown("#### Polls in Weighted Average")
        wd = pd.DataFrame(polls_used)
        if "support" in wd.columns:
            wd["support"] = wd["support"].map(lambda x: f"{x:.1%}")
        st.dataframe(wd, use_container_width=True, hide_index=True)


def _show_polling_format() -> None:
    st.markdown("#### Expected Polling File Format")
    st.code("""pollster,field_date_start,field_date_end,sample_size,population,support_percent,oppose_percent,undecided_percent,geography
Sonoma Survey,2026-01-15,2026-01-17,400,LV,0.52,0.41,0.07,Sonoma County
UC Survey,2026-02-01,2026-02-03,600,RV,0.49,0.43,0.08,Statewide""", language="csv")


# ── Tab 2: Registration Trends ────────────────────────────────────────────────

def _render_registration(reg_summary: dict, reg_df: pd.DataFrame) -> None:
    st.markdown("### 📋 Voter Registration Trends")

    if not reg_summary.get("has_registration_data"):
        st.info("No registration data. Add snapshot CSVs to `data/intelligence/registration/`")
        return

    col1, col2, col3 = st.columns(3)
    growth = reg_summary.get("registration_growth")
    partisan = reg_summary.get("net_partisan_score")
    total = reg_summary.get("latest_total_registered")

    col1.metric(
        "📈 Registration Growth",
        f"{growth:+.1%}" if growth is not None else "N/A",
        delta="vs earliest snapshot",
        delta_color="normal" if (growth or 0) >= 0 else "inverse",
    )
    col2.metric(
        "🎭 Net Partisan Score (D - R)",
        f"{partisan:+.1%}" if partisan is not None else "N/A",
        help="Positive = more Democrats than Republicans registered"
    )
    col3.metric(
        "📊 Total Registered",
        f"{int(total):,}" if total else "N/A"
    )

    party_shift = reg_summary.get("party_shift")
    if party_shift is not None:
        if party_shift > 0.01:
            st.success(f"📈 Registration shifting **+{party_shift:.2%}** toward Democrats since earliest snapshot.")
        elif party_shift < -0.01:
            st.warning(f"📉 Registration shifting **{party_shift:.2%}** toward Republicans since earliest snapshot.")
        else:
            st.info("📊 Registration composition is essentially stable since earliest snapshot.")

    st.caption(reg_summary.get("note", ""))

    if not reg_df.empty and "snapshot_date" in reg_df.columns and "total_registered" in reg_df.columns:
        st.markdown("#### Registration Over Time")
        chart_df = reg_df[["snapshot_date", "total_registered"]].copy()
        chart_df["snapshot_date"] = pd.to_datetime(chart_df["snapshot_date"], errors="coerce")
        chart_df = chart_df.sort_values("snapshot_date").set_index("snapshot_date")
        st.line_chart(chart_df, height=200)


# ── Tab 3: Ballot Returns ─────────────────────────────────────────────────────

def _render_ballot_returns(br_summary: dict, br_daily: pd.DataFrame) -> None:
    st.markdown("### 🗳️ Ballot Return Monitor")

    if not br_summary.get("has_ballot_return_data"):
        st.info("No ballot return data. Add aggregate daily return reports to `data/intelligence/ballot_returns/`")
        st.warning("⚠️ **Security:** Only aggregate return counts. Do NOT add individual voter files.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📬 Total Returned", f"{int(br_summary.get('total_returned') or 0):,}")
    col2.metric("📤 Total Issued", f"{int(br_summary.get('total_issued') or 0):,}")
    rr = br_summary.get("return_rate")
    col3.metric("📈 Return Rate", f"{rr:.1%}" if rr else "N/A")
    pt = br_summary.get("projected_turnout")
    col4.metric("🔭 Projected Turnout", f"{pt:.1%}" if pt else "N/A")

    adv = br_summary.get("partisan_advantage")
    if adv is not None:
        if adv > 0.03:
            st.success(f"🗳️ Democrats returning ballots at a **+{adv:.1%}** advantage.")
        elif adv < -0.03:
            st.warning(f"🗳️ Republicans returning ballots at a **+{abs(adv):.1%}** advantage.")
        else:
            st.info("📊 Partisan return parity — no significant advantage for either side.")

    if not br_daily.empty:
        st.markdown("#### Daily Return Trend")
        if "report_date" in br_daily.columns and "ballots_returned" in br_daily.columns:
            try:
                chart_df = br_daily[["report_date", "ballots_returned"]].copy()
                chart_df["report_date"] = pd.to_datetime(chart_df["report_date"], errors="coerce")
                chart_df = chart_df.sort_values("report_date").set_index("report_date")
                st.bar_chart(chart_df, height=200)
            except Exception:
                st.dataframe(br_daily, use_container_width=True, hide_index=True)


# ── Tab 4: Demographics ───────────────────────────────────────────────────────

def _render_demographics(demo_df: pd.DataFrame, adj: dict) -> None:
    st.markdown("### 👥 Demographic Insights")

    if demo_df.empty:
        st.info("No demographic data. Add Census ACS or precinct demographic CSVs to `data/intelligence/demographics/`")
        return

    n_precincts = len(demo_df)
    col1, col2, col3 = st.columns(3)

    if "pct_college_or_higher" in demo_df.columns:
        avg_edu = demo_df["pct_college_or_higher"].mean()
        col1.metric("🎓 Avg. College+ Rate", f"{avg_edu:.1%}")

    if "median_income" in demo_df.columns:
        avg_inc = demo_df["median_income"].mean()
        col2.metric("💰 Avg. Median Income", f"${avg_inc:,.0f}")

    if "homeownership_rate" in demo_df.columns:
        avg_own = demo_df["homeownership_rate"].mean()
        col3.metric("🏘️ Avg. Homeownership", f"{avg_own:.1%}")

    st.caption(f"{n_precincts:,} precincts with demographic data.")

    demo_adj = adj.get("contributions", {}).get("demographic_signal")
    if demo_adj is not None:
        st.markdown(f"**Education adjustment to support:** `{demo_adj:+.4%}`")
        if demo_adj > 0.005:
            st.success("📚 Above-average education rates suggest a slight positive tailwind.")
        elif demo_adj < -0.005:
            st.warning("📚 Below-average education rates suggest a slight headwind.")

    # Show sample data
    show_cols = [c for c in ["canonical_precinct_id", "pct_college_or_higher",
                              "median_income", "homeownership_rate"] if c in demo_df.columns]
    if show_cols:
        st.dataframe(demo_df[show_cols].head(20), use_container_width=True, hide_index=True)


# ── Tab 5: Macro Environment ──────────────────────────────────────────────────

def _render_macro(macro_env: dict) -> None:
    st.markdown("### 🌐 Macro Political Environment")
    signals = macro_env.get("signals", {})
    contributions = macro_env.get("signal_contributions", {})
    macro_score = macro_env.get("macro_environment_score", 0.0)
    src = macro_env.get("source_type", "SIMULATED")

    st.markdown(
        f"**Overall Macro Score:** `{macro_score:+.4f}` &nbsp; {_source_badge(src)}",
        unsafe_allow_html=True
    )
    if not macro_env.get("has_macro_data"):
        st.info("Using default neutral macro environment. Add signal files to `data/intelligence/macro/`")

    if macro_score > 0.02:
        st.success("🌊 Macro environment is **favorable** — national conditions help your side.")
    elif macro_score < -0.02:
        st.warning("🌊 Macro environment is **unfavorable** — national headwinds present.")
    else:
        st.info("🌊 Macro environment is **neutral** — minimal national impact on local race.")

    # Signal table
    if signals:
        rows = []
        for k, v in signals.items():
            if v is not None:
                rows.append({
                    "Signal": k.replace("_", " ").title(),
                    "Value": f"{v:.3f}" if isinstance(v, float) else str(v),
                    "Contribution": f"{contributions.get(k, 0):+.5f}",
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("#### Add Macro Signals")
    st.markdown("Create `data/intelligence/macro/signals.json`:")
    st.code("""{
  "presidential_approval": 0.44,
  "generic_ballot_dem": 0.02,
  "economic_index": -0.1,
  "right_track_pct": 0.30,
  "inflation_rate": 0.035
}""", language="json")
