"""
engine/utils/derived_data_reader.py — Prompt 23 Stabilization (C02 Fix)

Canonical resolver for reading derived pipeline outputs.

Replaces the duplicated _find_latest() patterns in:
  - campaign_strategy_ai.py
  - forecast_updater.py
  - state_builder.py
  - war_room modules

Design:
  - Always prefers run_id-exact match
  - Falls back to latest within contest_id
  - Never reads another contest's file
  - Raises clear warnings (never silently returns wrong data)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from engine.utils.helpers import BASE_DIR, find_latest_csv, load_json

log = logging.getLogger(__name__)

# ── Directory constants ───────────────────────────────────────────────────────

DERIVED = BASE_DIR / "derived"

# Canonical search paths for simulation/scenario data (fixes C02)
SIMULATION_SEARCH_PATHS = [
    ("derived/advanced_modeling", "**/*advanced_scenarios*.csv"),
    ("derived/simulation", "**/*.csv"),
    ("derived/forecasts", "**/*.csv"),
]


class DerivedDataReader:
    """
    Reads derived pipeline outputs with contest-aware, run_id-aware resolution.

    Usage:
        reader = DerivedDataReader(contest_id="2026_CA_sonoma_prop_50", run_id="20260312__123456__abc")
        vote_path = reader.strategy("vote_path")
        scenarios = reader.simulations()
    """

    def __init__(
        self,
        contest_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ):
        self.contest_id = contest_id
        self.run_id = run_id

    # ── Strategy outputs ──────────────────────────────────────────────────────

    def strategy(self, output_type: str) -> Optional[pd.DataFrame]:
        """
        Load a strategy output CSV.
        output_type: 'vote_path' | 'field_strategy' | 'budget_allocation' | 'risk_analysis'
        """
        pattern = f"**/*__{output_type}.csv"
        return find_latest_csv(
            DERIVED / "strategy", pattern,
            contest_id=self.contest_id, run_id=self.run_id,
        )

    # ── Simulation outputs ────────────────────────────────────────────────────

    def simulations(self) -> Optional[pd.DataFrame]:
        """
        Load simulation/scenario outputs. Searches canonical paths in priority order.
        Replaces the broken derived/scenario_forecasts/ reference (C02 fix).
        """
        # Try each search path in order
        if self.contest_id:
            # Prefer contest-specific advanced_modeling directory
            contest_dir = DERIVED / "advanced_modeling" / self.contest_id
            df = find_latest_csv(
                contest_dir, "*advanced_scenarios*.csv",
                run_id=self.run_id,
            )
            if df is not None:
                log.info(f"[READER] Loaded simulations from advanced_modeling/{self.contest_id}")
                return df

        # Walk search paths
        for rel_path, pattern in SIMULATION_SEARCH_PATHS:
            df = find_latest_csv(
                DERIVED / rel_path.replace("derived/", ""),
                pattern,
                contest_id=self.contest_id,
                run_id=self.run_id,
            )
            if df is not None:
                log.info(f"[READER] Loaded simulations from {rel_path}")
                return df

        log.warning(
            "[READER] simulations(): No scenario data found. "
            f"contest_id={self.contest_id} run_id={self.run_id}. "
            "Strategy will run without simulation comparison."
        )
        return None

    # ── Voter models ──────────────────────────────────────────────────────────

    def voter_universes(self) -> Optional[pd.DataFrame]:
        return find_latest_csv(
            DERIVED / "voter_universes", "*__universes.csv",
            contest_id=self.contest_id, run_id=self.run_id,
        )

    def targeting_quadrants(self) -> Optional[pd.DataFrame]:
        return find_latest_csv(
            DERIVED / "voter_segments", "*__targeting_quadrants.csv",
            contest_id=self.contest_id, run_id=self.run_id,
        )

    def precinct_turnout_scores(self) -> Optional[pd.DataFrame]:
        return find_latest_csv(
            DERIVED / "voter_models", "*__precinct_turnout_scores.csv",
            contest_id=self.contest_id, run_id=self.run_id,
        )

    def precinct_persuasion_scores(self) -> Optional[pd.DataFrame]:
        return find_latest_csv(
            DERIVED / "voter_models", "*__precinct_persuasion_scores.csv",
            contest_id=self.contest_id, run_id=self.run_id,
        )

    def precinct_voter_metrics(self) -> Optional[pd.DataFrame]:
        return find_latest_csv(
            DERIVED / "voter_models", "*__precinct_voter_metrics.csv",
            contest_id=self.contest_id, run_id=self.run_id,
        )

    def precinct_model(self) -> Optional[pd.DataFrame]:
        return find_latest_csv(
            DERIVED / "precinct_models", "**/*.csv",
            contest_id=self.contest_id, run_id=self.run_id,
        )

    # ── Calibration ───────────────────────────────────────────────────────────

    def calibration_params(self) -> dict:
        cal_path = DERIVED / "calibration" / "model_parameters.json"
        return load_json(cal_path)

    # ── War room ──────────────────────────────────────────────────────────────

    def vote_path_baseline(self) -> Optional[pd.DataFrame]:
        """Load most recent vote path for war room comparison."""
        return find_latest_csv(
            DERIVED / "strategy", "*__vote_path.csv",
            contest_id=self.contest_id, run_id=self.run_id,
        )

    def war_room_runtime(self) -> Optional[pd.DataFrame]:
        return find_latest_csv(
            DERIVED / "war_room", "*__forecast_update_comparison.csv",
            contest_id=self.contest_id, run_id=self.run_id,
        )

    # ── State ─────────────────────────────────────────────────────────────────

    def campaign_state(self) -> dict:
        state_dir = DERIVED / "state" / "latest"
        if not state_dir.exists():
            return {}
        candidates = sorted(
            state_dir.glob("*campaign_state.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return {}
        return load_json(candidates[0])

    # ── Manifest of inputs used ───────────────────────────────────────────────

    def resolve_all_strategy_inputs(self) -> dict:
        """
        Resolve all inputs used by the strategy engine.
        Returns a manifest dict (used for repair report).
        """
        manifest = {
            "contest_id": self.contest_id,
            "run_id": self.run_id,
            "resolved": {},
        }

        def _check(name: str, df):
            if df is None:
                manifest["resolved"][name] = {"status": "MISSING", "rows": 0}
            else:
                manifest["resolved"][name] = {"status": "LOADED", "rows": len(df)}

        _check("precinct_model",        self.precinct_model())
        _check("voter_universes",        self.voter_universes())
        _check("targeting_quadrants",    self.targeting_quadrants())
        _check("precinct_turnout_scores", self.precinct_turnout_scores())
        _check("precinct_persuasion_scores", self.precinct_persuasion_scores())
        _check("precinct_voter_metrics",  self.precinct_voter_metrics())
        _check("simulations",             self.simulations())
        manifest["calibration_params"] = "LOADED" if self.calibration_params() else "MISSING"
        return manifest
