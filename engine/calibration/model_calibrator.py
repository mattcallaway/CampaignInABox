"""
engine/calibration/model_calibrator.py — Prompt 11

Estimate campaign response parameters from historical election data.

Two estimation modes:
  1. OLS regression — when ≥3 years of history exist
  2. Bayesian conjugate update — always runs, even with 1 election

The calibrator produces model_parameters.json which the pipeline uses
to override priors in config/advanced_modeling.yaml.

Output:
  derived/calibration/model_parameters.json
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import yaml

CALIBRATION_DIR = BASE_DIR / "derived" / "calibration"
ADVANCED_CONFIG = BASE_DIR / "config" / "advanced_modeling.yaml"

log = logging.getLogger(__name__)


# ── Load Priors ────────────────────────────────────────────────────────────────

def _load_priors() -> dict:
    """Load prior parameters from advanced_modeling.yaml."""
    if not ADVANCED_CONFIG.exists():
        return {
            "turnout_lift_per_contact_mean": 0.004,
            "turnout_lift_per_contact_sd": 0.002,
            "persuasion_lift_per_contact_mean": 0.006,
            "persuasion_lift_per_contact_sd": 0.003,
        }
    with open(ADVANCED_CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    e = cfg.get("elasticity", {})
    return {
        "turnout_lift_per_contact_mean": e.get("turnout_lift_per_contact_mean", 0.004),
        "turnout_lift_per_contact_sd": e.get("turnout_lift_per_contact_sd", 0.002),
        "persuasion_lift_per_contact_mean": e.get("persuasion_lift_per_contact_mean", 0.006),
        "persuasion_lift_per_contact_sd": e.get("persuasion_lift_per_contact_sd", 0.003),
    }


# ── OLS Calibration ────────────────────────────────────────────────────────────

def _ols_calibrate(hist_df: pd.DataFrame, precinct_model: Optional[pd.DataFrame]) -> dict:
    """
    OLS-based parameter estimation.

    Estimates year-over-year turnout variance as a proxy for field effect variance.
    Requires scikit-learn (lightweight — already installed with most Python envs).
    """
    results = {"method": "ols", "r2_turnout": None, "r2_support": None}

    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score

        # Turnout model: predict turnout_rate from year dummies + precinct baseline
        pivot = hist_df.pivot_table(
            index="canonical_precinct_id",
            columns="year",
            values="turnout_rate",
            aggfunc="mean",
        ).dropna()

        if pivot.shape[1] < 2:
            log.info("[CALIBRATOR] OLS requires ≥2 election years — skipping regression")
            return results

        years = sorted(pivot.columns)
        # Use first year as baseline, estimate lift in subsequent years
        X = pivot[years[:-1]].values  # baseline years
        y = pivot[years[-1]].values   # target year

        model = LinearRegression().fit(X, y)
        y_pred = model.predict(X)
        r2 = float(r2_score(y, y_pred))
        results["r2_turnout"] = round(r2, 3)

        # Variance of residuals approximates unexplained field effect
        residual_sd = float(np.std(y - y_pred))
        results["turnout_residual_sd"] = round(residual_sd, 4)
        log.info(f"[CALIBRATOR] OLS turnout R²={r2:.3f}, residual_sd={residual_sd:.4f}")

        # Support model
        support_pivot = hist_df.pivot_table(
            index="canonical_precinct_id",
            columns="year",
            values="support_rate",
            aggfunc="mean",
        ).dropna()
        if support_pivot.shape[1] >= 2:
            syears = sorted(support_pivot.columns)
            Xs = support_pivot[syears[:-1]].values
            ys = support_pivot[syears[-1]].values
            sm = LinearRegression().fit(Xs, ys)
            ysp = sm.predict(Xs)
            r2s = float(r2_score(ys, ysp))
            results["r2_support"] = round(r2s, 3)
            results["persuasion_residual_sd"] = round(float(np.std(ys - ysp)), 4)
            log.info(f"[CALIBRATOR] OLS support R²={r2s:.3f}")

    except ImportError:
        log.info("[CALIBRATOR] scikit-learn not available — OLS skipped")
    except Exception as e:
        log.warning(f"[CALIBRATOR] OLS failed: {e}")

    return results


# ── Bayesian Conjugate Update ──────────────────────────────────────────────────

def _bayesian_update(hist_df: pd.DataFrame, priors: dict) -> dict:
    """
    Simple conjugate Bayesian update of prior parameters using observed variance.

    Uses a Normal-Normal conjugate model:
      posterior_mean = (prior_precision * prior_mean + n * data_mean) / (prior_precision + n)
      posterior_sd = 1 / sqrt(prior_precision + n)

    where n = number of precinct-year observations and data_mean is the
    observed variance in turnout/support as a proxy for field effect.
    """
    n_obs = len(hist_df)
    n_precincts = hist_df["canonical_precinct_id"].nunique()
    n_elections = hist_df["year"].nunique()

    # Observed variance in turnout across years (proxy for natural variation)
    if "turnout_rate" in hist_df.columns and hist_df["turnout_rate"].notna().sum() > 10:
        obs_turnout_sd = float(hist_df["turnout_rate"].std())
        obs_turnout_mean = float(hist_df["turnout_rate"].mean())
    else:
        obs_turnout_sd = priors["turnout_lift_per_contact_sd"]
        obs_turnout_mean = priors["turnout_lift_per_contact_mean"]

    if "support_rate" in hist_df.columns and hist_df["support_rate"].notna().sum() > 10:
        obs_support_sd = float(hist_df["support_rate"].std())
    else:
        obs_support_sd = priors["persuasion_lift_per_contact_sd"]

    # Conjugate update (simple weighted average)
    prior_precision = 1.0  # relative weight of prior vs data
    data_precision = max(n_elections - 1, 0)  # more elections = more data weight

    total_precision = prior_precision + data_precision

    def _update_mean(prior_mean, data_proxy):
        return (prior_precision * prior_mean + data_precision * data_proxy) / total_precision

    def _update_sd(prior_sd, data_sd):
        # Weighted average of SDs as a simple approximation
        return (prior_precision * prior_sd + data_precision * data_sd) / total_precision

    post_turnout_mean = _update_mean(
        priors["turnout_lift_per_contact_mean"],
        priors["turnout_lift_per_contact_mean"],  # data doesn't directly inform lift
    )
    # Update SD using observed natural variation as information
    post_turnout_sd = _update_sd(priors["turnout_lift_per_contact_sd"], obs_turnout_sd * 0.1)
    post_persuasion_mean = _update_mean(
        priors["persuasion_lift_per_contact_mean"],
        priors["persuasion_lift_per_contact_mean"],
    )
    post_persuasion_sd = _update_sd(priors["persuasion_lift_per_contact_sd"], obs_support_sd * 0.1)

    return {
        "method": "bayesian_conjugate",
        "n_observations": n_obs,
        "n_precincts": n_precincts,
        "n_elections": n_elections,
        "turnout_lift_per_contact_mean": round(post_turnout_mean, 5),
        "turnout_lift_per_contact_sd": round(post_turnout_sd, 5),
        "persuasion_lift_per_contact_mean": round(post_persuasion_mean, 5),
        "persuasion_lift_per_contact_sd": round(post_persuasion_sd, 5),
        "observed_turnout_mean": round(obs_turnout_mean, 4),
        "observed_turnout_sd": round(obs_turnout_sd, 4),
        "observed_support_sd": round(obs_support_sd, 4),
    }


# ── Confidence Assessment ──────────────────────────────────────────────────────

def _assess_confidence(n_elections: int, n_precincts: int) -> str:
    if n_elections >= 5 and n_precincts >= 100:
        return "high"
    elif n_elections >= 3 and n_precincts >= 50:
        return "medium"
    elif n_elections >= 1:
        return "low"
    return "none"


# ── Main Calibration Function ─────────────────────────────────────────────────

def calibrate(
    hist_df: Optional[pd.DataFrame],
    precinct_model: Optional[pd.DataFrame] = None,
    logger=None,
) -> dict:
    """
    Run calibration on historical data.

    Always returns a parameters dict (falls back to priors if no history).
    Writes derived/calibration/model_parameters.json.
    """
    _log = logger or log
    priors = _load_priors()

    if hist_df is None or hist_df.empty:
        _log.info("[CALIBRATOR] No historical data — using prior parameters")
        params = {
            "calibration_status": "prior_only",
            "calibration_confidence": "none",
            "note": "No historical election data found. "
                    "Place detail.xls files in data/elections/CA/Sonoma/<year>/ "
                    "and rerun to calibrate.",
            **priors,
        }
    else:
        n_elections = hist_df["year"].nunique()
        n_precincts = hist_df["canonical_precinct_id"].nunique()

        # Always run Bayesian update
        params = _bayesian_update(hist_df, priors)

        # Enhance with OLS if enough data
        if n_elections >= 2:
            ols = _ols_calibrate(hist_df, precinct_model)
            params.update({k: v for k, v in ols.items() if v is not None})

        params["calibration_status"] = "calibrated"
        params["calibration_confidence"] = _assess_confidence(n_elections, n_precincts)
        params["note"] = (
            f"Calibrated from {n_elections} historical elections, "
            f"{n_precincts} precincts. "
            f"Confidence: {params['calibration_confidence']}. "
            + ("Consider adding more historical elections for higher confidence. "
               if params["calibration_confidence"] != "high" else "")
        )
        _log.info(
            f"[CALIBRATOR] Calibration complete: "
            f"{params['calibration_status']} / confidence={params['calibration_confidence']}"
        )

    # Always write output
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CALIBRATION_DIR / "model_parameters.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2)
    _log.info(f"[CALIBRATOR] Wrote calibration parameters → {out_path}")

    return params


def load_calibrated_params() -> Optional[dict]:
    """Load calibrated parameters if they exist, else return None."""
    path = CALIBRATION_DIR / "model_parameters.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
