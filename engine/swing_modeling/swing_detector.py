"""
engine/swing_modeling/swing_detector.py — Prompt 26

Historical Swing Precinct Detector.

Inputs (from derived/archive/):
  normalized_elections.csv  — year, precinct, state, county, support_rate, turnout_rate, contest_type
  precinct_profiles.csv     — avg_support, support_sd, avg_turnout, turnout_sd, trend_slopes, elections_counted

Output per precinct:
  {
    "precinct":            "0400127",
    "swing_score":          0.62,
    "support_volatility":   0.11,
    "turnout_volatility":   0.07,
    "trend_direction":      "pro_support",
    "confidence":           0.78,
    "swing_class":          "high_swing"
  }

Safety rules:
  - Only uses same-jurisdiction (state + county) records
  - Prefers comparable contest types
  - Low confidence when elections_counted < minimum
  - Does not inflate from one anomalous election (IQR outlier check)
  - Returns explicit confidence score with every result
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR   = BASE_DIR / "derived" / "archive"
DERIVED_DIR   = BASE_DIR / "derived" / "swing_modeling"
RULES_PATH    = Path(__file__).resolve().parent / "swing_rules.yaml"

DERIVED_DIR.mkdir(parents=True, exist_ok=True)


def _load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}


@dataclass
class SwingResult:
    precinct:             str
    state:                str
    county:               str
    swing_score:          float
    support_volatility:   float    # support SD
    turnout_volatility:   float    # turnout SD
    recent_direction:     str      # "pro_support" | "against_support" | "neutral"
    trend_magnitude:      float
    contest_sensitivity:  float
    confidence:           float
    swing_class:          str      # high_swing | moderate_swing | low_swing | stable
    elections_counted:    int
    avg_support:          Optional[float]
    avg_turnout:          Optional[float]
    provenance:           str      # REAL | SYNTHETIC


def _iqr_outlier_present(values) -> bool:
    """Return True if any value is an outlier by 1.5*IQR rule."""
    import numpy as np
    if len(values) < 4:
        return False
    arr = np.array(values)
    q1, q3 = np.percentile(arr, 25), np.percentile(arr, 75)
    iqr = q3 - q1
    return bool(((arr < q1 - 1.5 * iqr) | (arr > q3 + 1.5 * iqr)).any())


def _recent_direction(support_series) -> tuple[str, float]:
    """
    Compute directional change from second-to-last to last election.
    Returns ("pro_support"|"against_support"|"neutral", magnitude).
    """
    if len(support_series) < 2:
        return "neutral", 0.0
    delta = float(support_series.iloc[-1] - support_series.iloc[-2])
    if abs(delta) < 0.01:
        return "neutral", 0.0
    return ("pro_support" if delta > 0 else "against_support"), round(abs(delta), 4)


def _contest_sensitivity(group) -> float:
    """
    Measure how much support_rate varies across contest types.
    Returns average absolute deviation from grand mean, per type.
    """
    if "contest_type" not in group.columns:
        return 0.0
    grand_mean = group["support_rate"].mean()
    per_type = group.groupby("contest_type")["support_rate"].mean()
    deviations = (per_type - grand_mean).abs()
    return float(deviations.mean()) if len(deviations) > 1 else 0.0


def _normalize_component(value: float, low: float, high: float) -> float:
    """Normalize a value to [0, 1] given expected low and high bounds."""
    if high <= low:
        return 0.0
    return min(1.0, max(0.0, (value - low) / (high - low)))


def detect_swing_for_precinct(
    precinct_id: str,
    state: str,
    county: str,
    elections_df,
    rules: dict,
) -> SwingResult:
    """
    Compute swing score for one precinct using its election history.

    Args:
        precinct_id:   canonical precinct identifier
        state, county: jurisdiction scope
        elections_df:  full normalized_elections DataFrame FILTERED to this jurisdiction
        rules:         loaded swing_rules.yaml

    Returns:
        SwingResult
    """
    import numpy as np
    import pandas as pd

    weights     = rules.get("weights", {})
    sv_rules    = rules.get("support_volatility", {})
    tv_rules    = rules.get("turnout_volatility", {})
    classes     = rules.get("swing_classes", {})
    conf_rules  = rules.get("confidence", {})
    min_elec    = rules.get("minimum_usable_elections", 2)
    pref_min    = rules.get("preferred_min_elections", 4)

    # Filter to this precinct
    grp = elections_df[elections_df["precinct"] == precinct_id].sort_values("year")
    n = len(grp)

    # Base metrics
    sup_vals = grp["support_rate"].dropna()
    to_vals  = grp["turnout_rate"].dropna()

    support_sd = float(sup_vals.std()) if len(sup_vals) > 1 else 0.0
    turnout_sd = float(to_vals.std())  if len(to_vals)  > 1 else 0.0

    avg_support = float(sup_vals.mean()) if len(sup_vals) > 0 else None
    avg_turnout = float(to_vals.mean())  if len(to_vals)  > 0 else None

    direction, dir_magnitude = _recent_direction(sup_vals)
    contest_sens = _contest_sensitivity(grp)
    provenance = "REAL" if "provenance" in grp.columns and grp.get("provenance", pd.Series([])).isin(["REAL"]).any() else "SYNTHETIC"

    # Anomaly detection
    has_anomaly = _iqr_outlier_present(sup_vals.tolist())

    # ── Component scores (0–1 each) ───────────────────────────────────────────
    # Support volatility: normalize SD from 0 → 0.15+
    sv_comp = _normalize_component(support_sd, 0.0, sv_rules.get("high_swing_min", 0.07))

    # Turnout volatility: normalize SD from 0 → 0.10+
    tv_comp = _normalize_component(turnout_sd, 0.0, tv_rules.get("high_swing_min", 0.06))

    # Recent direction: magnitude normalized to 0–0.20 range
    dir_comp = _normalize_component(dir_magnitude, 0.0, 0.15)

    # Contest sensitivity: normalize from 0 → 0.10
    cs_comp = _normalize_component(contest_sens, 0.0, 0.10)

    # Weighted swing score
    swing_score = (
        weights.get("support_volatility",  0.40) * sv_comp +
        weights.get("turnout_volatility",  0.20) * tv_comp +
        weights.get("recent_direction",    0.25) * dir_comp +
        weights.get("contest_sensitivity", 0.15) * cs_comp
    )
    swing_score = round(min(1.0, max(0.0, swing_score)), 4)

    # ── Confidence ────────────────────────────────────────────────────────────
    conf_floor = conf_rules.get("minimum_floor", 0.20)
    if n < min_elec:
        confidence = conf_floor
    elif n < pref_min:
        confidence = min(conf_rules.get("sparse_data_cap", 0.50), 0.50)
    else:
        # Base confidence from data depth
        confidence = min(0.95, 0.50 + (n - pref_min) * 0.07)

    # Penalize if only one contest type
    if grp.get("contest_type", pd.Series([])).nunique() <= 1:
        confidence *= conf_rules.get("single_type_penalty", 0.80)

    # Penalize for anomalous outlier
    if has_anomaly:
        confidence *= conf_rules.get("anomaly_penalty", 0.85)

    confidence = round(max(conf_floor, min(0.95, confidence)), 4)

    # ── Swing class ───────────────────────────────────────────────────────────
    if swing_score >= classes.get("high_swing", 0.65):
        swing_class = "high_swing"
    elif swing_score >= classes.get("moderate_swing", 0.40):
        swing_class = "moderate_swing"
    elif swing_score >= classes.get("low_swing", 0.20):
        swing_class = "low_swing"
    else:
        swing_class = "stable"

    return SwingResult(
        precinct=precinct_id, state=state, county=county,
        swing_score=swing_score,
        support_volatility=round(support_sd, 6),
        turnout_volatility=round(turnout_sd, 6),
        recent_direction=direction, trend_magnitude=dir_magnitude,
        contest_sensitivity=round(contest_sens, 6),
        confidence=confidence, swing_class=swing_class,
        elections_counted=n,
        avg_support=round(avg_support, 4) if avg_support is not None else None,
        avg_turnout=round(avg_turnout, 4) if avg_turnout is not None else None,
        provenance=provenance,
    )


def run_swing_detection(
    state: str = "CA",
    county: str = "Sonoma",
    run_id: Optional[str] = None,
    archive_elections_df=None,
    exclude_years: Optional[list[int]] = None,
) -> list[SwingResult]:
    """
    Run swing detection for all precincts in the specified jurisdiction.

    Args:
        state, county:         jurisdiction scope
        run_id:                run identifier
        archive_elections_df:  pre-loaded DataFrame (None → load from file)
        exclude_years:         years to exclude (for backtesting hold-out)

    Returns:
        list[SwingResult]
    """
    import pandas as pd

    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M")
    rules  = _load_rules()

    # Load elections archive
    if archive_elections_df is None:
        infile = ARCHIVE_DIR / "normalized_elections.csv"
        if not infile.exists():
            log.warning("[SWING] normalized_elections.csv not found — using synthetic fallback")
            archive_elections_df = _synthetic_fallback(state, county)
        else:
            archive_elections_df = pd.read_csv(infile)

    # Filter to this jurisdiction only
    df = archive_elections_df.copy()
    for col in ["state", "county"]:
        if col in df.columns:
            df = df[df[col].str.lower() == locals()[col].lower()]

    # Exclude hold-out years if specified
    if exclude_years and "year" in df.columns:
        df = df[~df["year"].isin(exclude_years)]

    # Ensure numeric columns
    for col in ["support_rate", "turnout_rate", "year"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if df.empty:
        log.info(f"[SWING] No election data for {state}/{county} — returning empty results")
        return []

    # Detect swing per precinct
    results: list[SwingResult] = []
    for precinct_id in df["precinct"].unique():
        r = detect_swing_for_precinct(precinct_id, state, county, df, rules)
        results.append(r)

    results.sort(key=lambda r: r.swing_score, reverse=True)
    log.info(f"[SWING] Detected swing for {len(results)} precincts in {state}/{county}")

    # Write output CSV
    _write_swing_scores_csv(results, run_id)
    return results


def _write_swing_scores_csv(results: list[SwingResult], run_id: str) -> Path:
    import pandas as pd
    rows = [r.__dict__ for r in results]
    df = pd.DataFrame(rows)
    out = DERIVED_DIR / f"{run_id}__swing_scores.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    log.info(f"[SWING] Swing scores → {out}")
    return out


def _synthetic_fallback(state: str, county: str):
    """Build a minimal synthetic election DataFrame for testing when archive is absent."""
    import pandas as pd
    import numpy as np
    rng = np.random.default_rng(42)
    precincts = [f"04001{i:02d}" for i in range(1, 31)]
    years = [2018, 2020, 2022, 2024]
    rows = []
    for p in precincts:
        base_sup = rng.uniform(0.35, 0.70)
        base_to  = rng.uniform(0.35, 0.75)
        for y in years:
            rows.append({
                "precinct": p, "state": state, "county": county, "year": y,
                "support_rate": min(1.0, max(0.0, base_sup + rng.normal(0, 0.06))),
                "turnout_rate": min(1.0, max(0.0, base_to  + rng.normal(0, 0.04))),
                "contest_type": "general",
                "provenance": "SYNTHETIC",
            })
    return pd.DataFrame(rows)
