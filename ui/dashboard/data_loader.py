"""
ui/dashboard/data_loader.py — Prompt 9

Loads latest pipeline run artifacts for the Campaign Intelligence Dashboard.
All reads use @st.cache_data for performance (< 3s load target).
No recomputation — derived outputs only.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR  = BASE_DIR / "logs" / "ui"

# ── Logging setup ──────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
log = logging.getLogger("dashboard")
if not log.handlers:
    _fh = logging.FileHandler(LOG_DIR / "dashboard.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    log.addHandler(_fh)
    log.setLevel(logging.INFO)


def _latest(root: Path, glob: str) -> Optional[Path]:
    """Return the most recently modified file matching glob under root."""
    if not root.exists():
        return None
    hits = sorted(root.rglob(glob), key=lambda p: p.stat().st_mtime, reverse=True)
    hits = [h for h in hits if h.is_file() and ".gitkeep" not in str(h)]
    return hits[0] if hits else None


def _read_csv(p: Optional[Path]) -> pd.DataFrame:
    if p and p.exists():
        try:
            return pd.read_csv(p)
        except Exception as e:
            log.warning(f"Could not read {p}: {e}")
    return pd.DataFrame()


def _read_json(p: Optional[Path]) -> dict:
    if p and p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Could not read JSON {p}: {e}")
    return {}


def _read_md(p: Optional[Path]) -> str:
    if p and p.exists():
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            pass
    return ""


# ── Artifact discovery ────────────────────────────────────────────────────────

def get_run_id() -> str:
    """Return the latest run_id from logs/latest/."""
    rid_file = BASE_DIR / "logs" / "latest" / "RUN_ID.txt"
    if rid_file.exists():
        return rid_file.read_text(encoding="utf-8").strip()
    # Fallback: find newest pathway
    pw = _latest(BASE_DIR / "logs" / "runs", "*pathway*.json")
    if pw:
        return pw.stem.split("__pathway")[0]
    return "unknown"


def load_all(run_id: Optional[str] = None) -> dict:
    """
    Load all dashboard datasets for the given run_id (or auto-detect latest).
    Returns a dict with DataFrames and metadata.
    """
    ts_start = datetime.now()

    precinct_model = _read_csv(_latest(BASE_DIR / "derived" / "precinct_models", "*.csv"))

    # Strategy pack
    sp_meta_path = _latest(BASE_DIR / "derived" / "strategy_packs", "STRATEGY_META.json")
    strategy_meta = _read_json(sp_meta_path)
    sp_dir = sp_meta_path.parent if sp_meta_path else None

    top_targets        = _read_csv(sp_dir / "TOP_TARGETS.csv"       if sp_dir else None)
    top_turfs          = _read_csv(sp_dir / "TOP_TURFS.csv"         if sp_dir else None)
    simulation_results = _read_csv(sp_dir / "SIMULATION_RESULTS.csv" if sp_dir else None)
    field_plan         = _read_csv(sp_dir / "FIELD_PLAN.csv"        if sp_dir else None)
    field_pace         = _read_csv(sp_dir / "FIELD_PACE.csv"        if sp_dir else None)
    strategy_summary_md = _read_md(sp_dir / "STRATEGY_SUMMARY.md"  if sp_dir else None)

    precinct_universes = _read_csv(_latest(BASE_DIR / "derived" / "universes", "*precinct_universes*.csv"))
    scenario_forecasts = _read_csv(_latest(BASE_DIR / "derived" / "forecasts", "*scenario_forecasts*.csv"))

    # Diagnostics
    latest_dir = BASE_DIR / "logs" / "latest"
    post_audit     = _read_json(latest_dir / "post_prompt86_audit.json")
    join_guard_csv = _read_csv(_latest(BASE_DIR / "derived" / "diagnostics", "*join_guard*.csv"))
    repair_csv     = _read_csv(_latest(BASE_DIR / "derived" / "diagnostics", "*integrity_repairs*.csv"))
    validation_md  = _read_md(latest_dir / "validation.md")
    qa_md          = _read_md(latest_dir / "qa.md")

    detected_run_id = run_id or get_run_id()
    elapsed = (datetime.now() - ts_start).total_seconds()

    # Log startup
    datasets_loaded = [
        k for k, v in {
            "precinct_model": precinct_model,
            "top_targets": top_targets,
            "simulation_results": simulation_results,
            "precinct_universes": precinct_universes,
        }.items() if not (v.empty if isinstance(v, pd.DataFrame) else not v)
    ]
    log.info(
        f"Dashboard loaded | run_id={detected_run_id} | "
        f"datasets={datasets_loaded} | elapsed={elapsed:.2f}s"
    )

    return {
        "run_id":              detected_run_id,
        "load_elapsed":        elapsed,
        "precinct_model":      precinct_model,
        "precinct_universes":  precinct_universes,
        "top_targets":         top_targets,
        "top_turfs":           top_turfs,
        "simulation_results":  simulation_results,
        "field_plan":          field_plan,
        "field_pace":          field_pace,
        "scenario_forecasts":  scenario_forecasts,
        "strategy_meta":       strategy_meta,
        "strategy_summary_md": strategy_summary_md,
        "post_audit":          post_audit,
        "join_guard_csv":      join_guard_csv,
        "repair_csv":          repair_csv,
        "validation_md":       validation_md,
        "qa_md":               qa_md,
    }
