"""
ui/dashboard/swing_model_view.py — Prompt 26

Swing Modeling dashboard section.

Displays:
  - Backtest status and confidence labels
  - Swing score table (high_swing / moderate_swing precincts)
  - Persuasion targets
  - Turnout targets
  - Backtest metrics (precision/recall/F1)
  - Data sufficiency warning
  - Run Swing Model button

All outputs are labeled with:
  - confidence level
  - backtest status
  - data sufficiency
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def render_swing_model_view():
    """Render the Swing Modeling & Persuasion Targeting section."""
    st.header("📊 Swing Modeling & Persuasion Targeting")
    st.markdown(
        "Backtested swing precinct detection identifying **persuasion** vs **turnout** opportunities. "
        "Each output shows confidence and backtest status — the model will not claim certainty it has not earned."
    )

    # ── Load swing adapter ────────────────────────────────────────────────────
    try:
        from engine.strategy.swing_strategy_adapter import load_swing_inputs
        swing = load_swing_inputs()
    except Exception as e:
        st.warning(f"Could not load swing model outputs: {e}")
        swing = None

    # ── Status banner ─────────────────────────────────────────────────────────
    if swing:
        status   = swing.get("backtest_status", "DISABLED_INSUFFICIENT_BACKTEST")
        avg_f1   = swing.get("avg_f1", 0.0)
        use_swing = swing.get("use_swing", False)
        rationale = swing.get("rationale", "")

        if status == "ACTIVE_VALIDATED":
            st.success(f"✅ Swing targeting **ACTIVE — VALIDATED** | Backtest F1={avg_f1:.2f} | {rationale}")
        elif status == "ACTIVE_LOW_CONFIDENCE":
            st.warning(f"⚠️ Swing targeting **ACTIVE — LOW CONFIDENCE** | F1={avg_f1:.2f} | {rationale}")
        else:
            st.error(f"🚫 Swing targeting **DISABLED — INSUFFICIENT BACKTEST DATA** | {rationale}")

        # Backtest metrics summary
        if swing.get("folds_run", 0) > 0:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Backtest Folds",    swing.get("folds_run", 0))
            m2.metric("Avg Precision",     f"{swing.get('avg_precision', 0):.2f}")
            m3.metric("Avg Recall",        f"{swing.get('avg_recall', 0):.2f}")
            m4.metric("Avg F1",            f"{avg_f1:.2f}")

        # ── Tabs ──────────────────────────────────────────────────────────────
        tab_swing, tab_persuasion, tab_turnout, tab_run = st.tabs([
            "🌀 Swing Scores", "🗣️ Persuasion Targets", "🗳️ Turnout Targets", "▶️ Run Model"
        ])

        with tab_swing:
            st.subheader("Swing Score Rankings")
            _confidence_legend()
            top = swing.get("top_swing_precincts", [])
            if top:
                df = pd.DataFrame(top)
                display_cols = [c for c in [
                    "precinct", "swing_class", "swing_score", "support_volatility",
                    "turnout_volatility", "recent_direction", "confidence", "elections_counted"
                ] if c in df.columns]
                st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
                _backtest_label(status)
            else:
                st.info("No swing scores available. Run the model below to generate scores.")

        with tab_persuasion:
            st.subheader("Persuasion Primary Targets")
            st.markdown(
                "Precincts where **avg_support is competitive (30–65%)**, support is movable, "
                "and persuasion is the primary lever."
            )
            _confidence_legend()
            targets = swing.get("persuasion_targets", [])
            if targets:
                df = pd.DataFrame(targets)
                display_cols = [c for c in [
                    "precinct", "avg_support", "support_sd", "avg_turnout",
                    "confidence", "rationale"
                ] if c in df.columns]
                st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
                _backtest_label(status)
            else:
                st.info("No persuasion targets available. Run the model to identify targets.")

        with tab_turnout:
            st.subheader("Turnout Opportunity Targets")
            st.markdown(
                "Precincts where **support is already favorable (≥52%)**, "
                "turnout is suppressed (≤55%), and turnout lift is achievable."
            )
            _confidence_legend()
            targets = swing.get("turnout_targets", [])
            if targets:
                df = pd.DataFrame(targets)
                display_cols = [c for c in [
                    "precinct", "avg_support", "avg_turnout", "turnout_sd",
                    "confidence", "rationale"
                ] if c in df.columns]
                st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
                _backtest_label(status)
            else:
                st.info("No turnout targets available. Run the model to identify opportunities.")

        with tab_run:
            st.subheader("Run Swing Model")
            r1, r2 = st.columns(2)
            run_state  = r1.text_input("State", "CA",    key="swing_state")
            run_county = r2.text_input("County", "Sonoma", key="swing_county")
            st.caption(
                "The swing model uses historical election archives (`derived/archive/normalized_elections.csv`). "
                "Run the Archive Builder first if no archive data is available."
            )

            if st.button("Run Swing Detection + Backtest", type="primary"):
                with st.spinner("Running swing detection and backtesting..."):
                    try:
                        from engine.swing_modeling.swing_detector import run_swing_detection, _synthetic_fallback
                        from engine.swing_modeling.persuasion_target_model import run_persuasion_targeting
                        from engine.swing_modeling.turnout_opportunity_model import run_turnout_targeting
                        from engine.swing_modeling.backtester import run_backtest
                        from datetime import datetime

                        ARCHIVE_CSV = BASE_DIR / "derived" / "archive" / "normalized_elections.csv"
                        if ARCHIVE_CSV.exists():
                            elections_df = pd.read_csv(ARCHIVE_CSV)
                            data_src = "real archive data"
                        else:
                            elections_df = _synthetic_fallback(run_state, run_county)
                            data_src = "synthetic fallback (no archive data found)"

                        run_id = datetime.now().strftime("%Y%m%d__%H%M")
                        swing_results = run_swing_detection(
                            state=run_state, county=run_county,
                            run_id=run_id, archive_elections_df=elections_df,
                        )
                        _ = run_persuasion_targeting(swing_results, run_id=run_id)
                        _ = run_turnout_targeting(swing_results,    run_id=run_id)
                        bt = run_backtest(elections_df, state=run_state, county=run_county, run_id=run_id)

                        st.success(
                            f"Model run complete ({data_src}). "
                            f"Detected {len(swing_results)} precincts. "
                            f"Backtest: {bt.folds_run} folds, F1={bt.avg_f1:.2f}, status={bt.backtest_status}"
                        )
                        if bt.backtest_status == "DISABLED_INSUFFICIENT_BACKTEST":
                            st.warning(bt.data_sufficiency_note)

                        st.rerun()

                    except Exception as e:
                        st.error(f"Swing model run failed: {e}")

    else:
        # No swing data at all
        st.info("No swing model outputs found. Use the **Run Model** tab above to generate swing scores.")
        with st.expander("Run Swing Model"):
            if st.button("Run (Offline / Synthetic Fallback)", type="primary"):
                with st.spinner("Running..."):
                    try:
                        from engine.swing_modeling.swing_detector import run_swing_detection, _synthetic_fallback
                        from engine.swing_modeling.backtester import run_backtest
                        from datetime import datetime
                        run_id = datetime.now().strftime("%Y%m%d__%H%M")
                        df = _synthetic_fallback("CA", "Sonoma")
                        run_swing_detection("CA", "Sonoma", run_id=run_id, archive_elections_df=df)
                        run_backtest(df, state="CA", county="Sonoma", run_id=run_id)
                        st.success("Swing model run complete (synthetic fallback). Refresh the page.")
                    except Exception as e:
                        st.error(f"Error: {e}")


def _confidence_legend():
    st.caption(
        "🟢 **High confidence** (≥6 elections) · "
        "🟡 **Medium confidence** (3–5 elections) · "
        "🔴 **Low confidence** (<3 elections) · "
        "All values are backtested against held-out historical elections."
    )


def _backtest_label(status: str):
    if status == "ACTIVE_VALIDATED":
        st.caption("✅ Backtested — predictions validated against held-out historical elections.")
    elif status == "ACTIVE_LOW_CONFIDENCE":
        st.caption("⚠️ Partially backtested — insufficient historical depth for strong validation.")
    else:
        st.caption("🚫 Not backtested — insufficient historical elections. Do not rely on these scores for decisions.")
