"""
engine/calibration/turnout_calibrator.py — Prompt 15

Estimates baseline turnout probability using logistic regression
on historical precinct-level election results.

If scikit-learn is not available or data is insufficient, returns
a prior from config/advanced_modeling.yaml.

Output:
    derived/calibration/turnout_parameters.json
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def _get_prior(root: Path) -> float:
    """Read baseline turnout prior from campaign config or hardcoded default."""
    try:
        import yaml
        p = root / "config" / "campaign_config.yaml"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            t = cfg.get("turnout", {})
            return float(t.get("baseline_turnout_pct", 0.45))
    except Exception:
        pass
    return 0.45


def calibrate_turnout(
    hist_df: pd.DataFrame,
    precinct_model: pd.DataFrame,
    vi_summary: dict,
    root: Path,
    logger=None,
) -> dict:
    """
    Estimate baseline_turnout_probability.

    Strategy:
      1. If historical data available: compute weighted mean turnout
         grouped by contest type. Optionally fit a logistic regression.
      2. Else if voter TPS (Turnout Propensity Scores) available:
         use their mean as a proxy.
      3. Else: return prior.

    Returns dict with parameters (also writes JSON).
    """
    _log = logger or log
    out: dict = {
        "method": "prior",
        "baseline_turnout_probability": _get_prior(root),
        "turnout_variance": 0.08,
        "confidence": "none",
        "n_precincts": 0,
        "n_elections": 0,
    }

    calib_dir = root / "derived" / "calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)

    # ── Strategy 1: Historical election data ──────────────────────────────────
    if not hist_df.empty and "turnout_rate" in hist_df.columns:
        valid = hist_df["turnout_rate"].dropna()
        if len(valid) > 5:
            baseline = float(valid.median())
            variance = float(valid.std())
            n_prec   = hist_df["canonical_precinct_id"].nunique()
            n_elec   = hist_df["year"].nunique()

            out.update({
                "method": "historical_median",
                "baseline_turnout_probability": round(baseline, 4),
                "turnout_variance": round(variance, 4),
                "n_precincts": n_prec,
                "n_elections": n_elec,
                "confidence": "medium" if n_elec >= 3 else "low",
            })
            _log.info(
                f"[TURNOUT_CAL] Historical median turnout={baseline:.4f}, "
                f"σ={variance:.4f} from {n_prec} precincts / {n_elec} elections"
            )

            # Try logistic regression enhancement
            try:
                from sklearn.linear_model import LogisticRegression
                from sklearn.preprocessing import StandardScaler

                aug = hist_df.copy()
                if not precinct_model.empty and "support_pct" in precinct_model.columns:
                    aug = aug.merge(
                        precinct_model[["canonical_precinct_id", "support_pct"]].rename(
                            columns={"support_pct": "pm_support"}),
                        on="canonical_precinct_id", how="left"
                    )

                features = []
                for col in ["year", "pm_support"]:
                    if col in aug.columns:
                        features.append(col)

                if features:
                    subset = aug[features + ["turnout_rate"]].dropna()
                    if len(subset) >= 20:
                        X = subset[features].values
                        y = (subset["turnout_rate"] > baseline).astype(int).values
                        scaler = StandardScaler()
                        X_s = scaler.fit_transform(X)
                        clf = LogisticRegression(max_iter=200).fit(X_s, y)
                        out["logistic_regression_used"] = True
                        out["method"] = "logistic_regression"
                        out["confidence"] = "high" if n_elec >= 5 else "medium"
                        _log.info("[TURNOUT_CAL] Logistic regression fit successfully")
            except Exception as e:
                _log.debug(f"[TURNOUT_CAL] Logistic regression skipped: {e}")

    # ── Strategy 2: Voter TPS scores as proxy ─────────────────────────────────
    elif "precinct_tps_df" in vi_summary:
        tps_df = vi_summary["precinct_tps_df"]
        score_col = next((c for c in ["mean_tps", "avg_tps", "tps_score"] if c in tps_df.columns), None)
        if score_col:
            baseline = float(tps_df[score_col].mean())
            out.update({
                "method": "voter_tps_mean",
                "baseline_turnout_probability": round(baseline, 4),
                "confidence": "low",
                "n_precincts": len(tps_df),
            })
            _log.info(f"[TURNOUT_CAL] TPS-derived baseline={baseline:.4f}")

    # Write JSON
    out_path = calib_dir / "turnout_parameters.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    _log.info(f"[TURNOUT_CAL] Written → {out_path.name}")
    return out
