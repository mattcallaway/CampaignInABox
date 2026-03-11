"""
engine/intelligence/macro_environment.py — Prompt 17

Import and store macro political environment signals.

Signals that affect baseline support:
    presidential_approval  — % approving the sitting president
    generic_ballot_dem     — generic congressional ballot Dem advantage
    state_approval         — governor or state approval rating
    economic_index         — composite economic conditions (-1.0 to 1.0)
    inflation_rate         — annual CPI inflation (%)
    right_track_pct        — % thinking country on right track

Inputs:
    data/intelligence/macro/ — JSON or CSV files with signal values

Output:
    derived/intelligence/macro_environment.json

Provenance: EXTERNAL (sourced) | ESTIMATED (modeled) | SIMULATED (default)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

MACRO_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "intelligence" / "macro"
DERIVED   = Path(__file__).resolve().parent.parent.parent / "derived" / "intelligence"

# Default priors (national averages — neutral baseline)
_DEFAULTS = {
    "presidential_approval": 0.44,
    "generic_ballot_dem":    0.02,   # +2 Dem generic ballot advantage
    "state_approval":        None,
    "economic_index":        0.0,    # neutral
    "inflation_rate":        0.035,  # ~3.5% CPI
    "right_track_pct":       0.30,   # 30% right track (historically bearish)
}

# How much each macro signal shifts baseline support (tuned empirically)
_MACRO_WEIGHTS = {
    "presidential_approval": 0.05,   # +5pp alignment if approval ≥ 0.50
    "generic_ballot_dem":    1.0,    # direct: +X pp Dem means +X pp for Dem-aligned measures
    "economic_index":        0.03,   # stronger economy = slight incumbent bonus
    "right_track_pct":       0.04,   # more optimism = slight incumbency/mainstream bonus
}


def _read_macro_file(path: Path) -> dict:
    """Read a macro signal file (JSON or flat CSV key-value)."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    elif suffix in (".csv", ".xlsx"):
        try:
            df = pd.read_csv(path) if suffix == ".csv" else pd.read_excel(path)
            # Support both wide format (one column per signal) and
            # long format (signal, value columns)
            if "signal" in df.columns and "value" in df.columns:
                return dict(zip(df["signal"].str.lower(), df["value"]))
            else:
                # Wide: take first row
                row = df.iloc[0].to_dict()
                return {k.lower().replace(" ", "_"): v for k, v in row.items()}
        except Exception as e:
            log.warning(f"[MACRO] Could not parse {path.name}: {e}")
            return {}
    return {}


def load_macro_environment(logger=None) -> dict:
    """
    Load all macro signal files and compute environment score.
    Returns summary dict and writes macro_environment.json.
    """
    _log = logger or log
    DERIVED.mkdir(parents=True, exist_ok=True)

    # Start with defaults
    signals = dict(_DEFAULTS)
    sources = []

    for path in sorted(MACRO_DIR.glob("*")):
        if path.name.startswith(".") or ".gitkeep" in path.name:
            continue
        data = _read_macro_file(path)
        if data:
            for k, v in data.items():
                clean_k = k.lower().replace(" ", "_")
                if clean_k in signals or clean_k in _MACRO_WEIGHTS:
                    try:
                        signals[clean_k] = float(v)
                    except (ValueError, TypeError):
                        pass
            sources.append(path.name)
            _log.info(f"[MACRO] Loaded macro signals from {path.name}: {list(data.keys())}")

    # Compute composite macro score (+/- from neutral)
    macro_score = 0.0
    signal_contributions = {}

    pres_approval = signals.get("presidential_approval", _DEFAULTS["presidential_approval"])
    if pres_approval is not None:
        # Measures/candidates aligned with president get a boost if president is popular
        contrib = _MACRO_WEIGHTS["presidential_approval"] * (float(pres_approval) - 0.45)
        signal_contributions["presidential_approval"] = round(contrib, 5)
        macro_score += contrib

    generic = signals.get("generic_ballot_dem", _DEFAULTS["generic_ballot_dem"])
    if generic is not None:
        # Generic ballot converts roughly 1:1 for Dem-aligned measures
        contrib = _MACRO_WEIGHTS["generic_ballot_dem"] * float(generic)
        signal_contributions["generic_ballot_dem"] = round(contrib, 5)
        macro_score += contrib

    econ = signals.get("economic_index", _DEFAULTS["economic_index"])
    if econ is not None:
        contrib = _MACRO_WEIGHTS["economic_index"] * float(econ)
        signal_contributions["economic_index"] = round(contrib, 5)
        macro_score += contrib

    right_track = signals.get("right_track_pct", _DEFAULTS["right_track_pct"])
    if right_track is not None:
        contrib = _MACRO_WEIGHTS["right_track_pct"] * (float(right_track) - 0.30)
        signal_contributions["right_track_pct"] = round(contrib, 5)
        macro_score += contrib

    has_data = len(sources) > 0

    result = {
        "generated_at": datetime.utcnow().isoformat(),
        "has_macro_data": has_data,
        "signals": {k: v for k, v in signals.items() if v is not None},
        "signal_contributions": signal_contributions,
        "macro_environment_score": round(macro_score, 5),
        "source_type": "EXTERNAL" if has_data else "SIMULATED",
        "sources": sources,
        "note": (
            f"Macro signals from {len(sources)} file(s) — score={macro_score:+.4f}"
            if has_data else
            "Using default macro environment (neutral). Add signals to data/intelligence/macro/"
        ),
    }

    (DERIVED / "macro_environment.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    _log.info(f"[MACRO] Environment score={macro_score:+.5f} | sources={sources}")
    return result


def load_macro_environment_result() -> dict:
    path = DERIVED / "macro_environment.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}
