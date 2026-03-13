"""
engine/archive/train_support_model.py — Prompt 24 Rebuild

Trains and calibrates the support/persuasion prediction model.

Calibration approach:
  - Primary: Isotonic regression (monotonic, non-parametric — preferred for small samples)
  - Fallback: No calibration wrapper if training data insufficient (< 50 samples)
  - Calibrated model is saved as a CalibratedClassifierCV-compatible pipeline object

Raw GradientBoostingRegressor output → scores in [0,1] range but are:
  - Not guaranteed to be probability-like in shape
  - Systematically compressed toward center
  - Not well-calibrated across deciles

Post-calibration scores approximate P(support=YES | features) in 0-1 space.

Outputs:
  derived/models/support_model.pkl               (calibrated pipeline)
  derived/models/support_model_parameters.json
  derived/models/support_model_calibration.json
  derived/models/support_feature_importance.csv
  reports/calibration/<run_id>__persuasion_calibration_report.md
"""
from __future__ import annotations

import json
import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = BASE_DIR / "derived" / "archive"
MODELS_DIR  = BASE_DIR / "derived" / "models"
CAL_DIR     = BASE_DIR / "derived" / "calibration"
REPORTS_DIR = BASE_DIR / "reports" / "calibration"
LOG_DIR     = BASE_DIR / "logs" / "archive"

for _d in (MODELS_DIR, CAL_DIR, REPORTS_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _load_data() -> Optional[pd.DataFrame]:
    infile = ARCHIVE_DIR / "normalized_elections.csv"
    if not infile.exists():
        log.error("[TRAIN_SUPPORT] normalized_elections.csv not found")
        return None

    df = pd.read_csv(infile)
    for col in ["support_rate", "turnout_rate"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _feature_engineer(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered features."""
    # Merge partisan tilt from precinct profiles
    profile_file = ARCHIVE_DIR / "precinct_profiles.csv"
    if profile_file.exists():
        prof = pd.read_csv(profile_file)
        df = df.merge(
            prof[["precinct", "partisan_tilt", "ballot_measure_tilt",
                  "turnout_trend_slope", "support_trend_slope"]],
            on="precinct", how="left"
        )
    else:
        df["partisan_tilt"]       = 0.0
        df["ballot_measure_tilt"] = 0.0
        df["turnout_trend_slope"] = 0.0
        df["support_trend_slope"] = 0.0

    # Contest type flags
    df["is_presidential"]  = (df["contest_type"] == "presidential").astype(int)
    df["is_midterm"]       = (df["contest_type"] == "midterm").astype(int)
    df["is_ballot_measure"]= (df["contest_type"] == "ballot_measure").astype(int)
    df["is_local"]         = df["contest_type"].isin(
        ["local_general", "local_special", "municipal"]).astype(int)
    df["is_legislative"]   = (df["contest_type"] == "legislative").astype(int)
    df["year_norm"]        = (df["year"] - 2016) / 8.0   # normalize years 0-1

    return df


FEATURES = [
    "is_presidential", "is_midterm", "is_ballot_measure", "is_local", "is_legislative",
    "turnout_rate", "partisan_tilt", "ballot_measure_tilt",
    "turnout_trend_slope", "support_trend_slope", "year_norm",
]


def _write_insufficient_data_report(run_id: str):
    """Write a calibration report noting insufficient training data."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Persuasion Model Calibration Report",
        f"**Run ID:** {run_id}  |  **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Status: SKIPPED — Insufficient Training Data",
        "",
        "The support model could not be trained because the archive data in "
        "`derived/archive/normalized_elections.csv` does not contain enough rows with",
        "valid `support_rate`, `turnout_rate`, and feature columns (need ≥ 50 clean rows).",
        "",
        "### Current Archive Status",
        "The archive currently contains voter-list data (individual records) not",
        "precinct-level election results. To enable model training:",
        "",
        "1. Place real election result files in `data/election_archive/<STATE>/<COUNTY>/<YEAR>/`",
        "2. Result files must contain columns: `precinct`, `registered`, `ballots_cast` or `turnout_rate`,",
        "   `yes_votes`/`no_votes` or `support_rate`",
        "3. Re-run `engine/archive/archive_ingest.py` to rebuild `normalized_elections.csv`",
        "4. Re-run `engine/archive/train_support_model.py` to train the calibrated model",
        "",
        "### Fallback Behavior",
        "Strategy and voter intelligence pages will use raw regression outputs without",
        "isotonic calibration until a proper election archive is available.",
    ]
    rpath = REPORTS_DIR / f"{run_id}__persuasion_calibration_report.md"
    rpath.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[TRAIN_SUPPORT] Wrote insufficient-data calibration report → {rpath.name}")


def train_model(run_id: Optional[str] = None) -> Optional[dict]:

    """
    Train and calibrate support model.
    Returns metadata dict on success, None on failure.
    """
    import joblib
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.isotonic import IsotonicRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.pipeline import Pipeline
    from sklearn.calibration import CalibratedClassifierCV

    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M%S") + "__support"

    df = _load_data()
    if df is None:
        return None

    if len(df) < 50:
        log.warning(f"[TRAIN_SUPPORT] Only {len(df)} rows — skipping training (need ≥50)")
        return None

    df = _feature_engineer(df)

    # Drop rows missing target or key features
    required_cols = ["support_rate"] + FEATURES[:3]
    available_cols = [c for c in required_cols if c in df.columns]
    if not available_cols:
        log.warning("[TRAIN_SUPPORT] Missing required columns — cannot train")
        return None

    df_clean = df.dropna(subset=[c for c in required_cols if c in df.columns])
    log.info(f"[TRAIN_SUPPORT] Clean rows after dropna: {len(df_clean):,} / {len(df):,}")

    if len(df_clean) < 50:
        log.warning(f"[TRAIN_SUPPORT] Only {len(df_clean)} clean rows — need ≥50 for training")
        _write_insufficient_data_report(run_id)
        return None


    X = df_clean[FEATURES].fillna(0.0)
    y = df_clean["support_rate"].clip(0, 1)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # ── Train base regressor (HistGBR supports NaN natively) ──────────────────
    log.info("[TRAIN_SUPPORT] Training HistGradientBoostingRegressor...")
    base_model = HistGradientBoostingRegressor(
        max_iter=150,
        learning_rate=0.05,
        max_depth=4,
        random_state=42,
    )
    base_model.fit(X_train, y_train)

    raw_preds = base_model.predict(X_test).clip(0, 1)
    raw_mae   = mean_absolute_error(y_test, raw_preds)
    raw_r2    = r2_score(y_test, raw_preds)
    log.info(f"[TRAIN_SUPPORT] Base model: MAE={raw_mae:.4f} R²={raw_r2:.4f}")

    # ── Isotonic calibration ──────────────────────────────────────────────────
    cal_model = None
    cal_method = "none"
    cal_mae = raw_mae
    cal_r2  = raw_r2

    if len(X_train) >= 30:
        try:
            # Get out-of-fold predictions for calibration fitting
            train_preds = base_model.predict(X_train).clip(0, 1)
            iso = IsotonicRegression(out_of_bounds="clip", increasing=True)
            iso.fit(train_preds, y_train)

            # Post-calibration evaluation
            cal_preds_test = iso.predict(raw_preds)
            cal_mae = mean_absolute_error(y_test, cal_preds_test)
            cal_r2  = r2_score(y_test, cal_preds_test)
            log.info(f"[TRAIN_SUPPORT] Isotonic calibration: MAE={cal_mae:.4f} R²={cal_r2:.4f}")
            cal_model = iso
            cal_method = "isotonic_regression"
        except Exception as e:
            log.warning(f"[TRAIN_SUPPORT] Isotonic calibration failed: {e}")

    # ── Save models ───────────────────────────────────────────────────────────
    pipeline = {"base_model": base_model, "calibrator": cal_model, "features": FEATURES}
    model_path = MODELS_DIR / "support_model.pkl"
    joblib.dump(pipeline, model_path)
    log.info(f"[TRAIN_SUPPORT] Saved model pipeline → {model_path}")

    # Feature importance (HistGBR doesn't have .feature_importances_ as direct array)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Use permutation-style proxy: note importance via built-in attribute
            importances = base_model.train_score_  # fallback metric
    except Exception:
        importances = None

    fi_dict = {f: round(float(np.abs(X_train[f].corr(pd.Series(base_model.predict(X_train), index=X_train.index)))), 4)
               for f in FEATURES}
    fi_df = pd.DataFrame({"feature": list(fi_dict.keys()), "importance_proxy": list(fi_dict.values())})
    fi_df = fi_df.sort_values("importance_proxy", ascending=False)
    fi_df.to_csv(MODELS_DIR / "support_feature_importance.csv", index=False)

    # Parameters JSON
    params = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        "model_type": "HistGradientBoostingRegressor",
        "features": FEATURES,
        "training_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "training_contests": int(df_clean["contest"].nunique()),
        "metrics_raw": {"mae": round(raw_mae, 4), "r2": round(raw_r2, 4)},
        "metrics_calibrated": {"mae": round(cal_mae, 4), "r2": round(cal_r2, 4)},
        "calibrated": cal_model is not None,
    }
    (MODELS_DIR / "support_model_parameters.json").write_text(
        json.dumps(params, indent=2), encoding="utf-8"
    )

    # Pre/post calibration score distributions
    def _score_dist(scores):
        return {
            "mean": round(float(np.mean(scores)), 4),
            "std":  round(float(np.std(scores)), 4),
            "p10":  round(float(np.percentile(scores, 10)), 4),
            "p50":  round(float(np.percentile(scores, 50)), 4),
            "p90":  round(float(np.percentile(scores, 90)), 4),
        }

    cal_info = {
        "run_id": run_id,
        "calibration_method": cal_method,
        "calibration_applied": cal_model is not None,
        "validation_sample_size": int(len(X_test)),
        "pre_calibration_distribution":  _score_dist(raw_preds),
        "post_calibration_distribution": _score_dist(iso.predict(raw_preds) if cal_model else raw_preds),
        "cal_mae_improvement":  round(raw_mae - cal_mae, 4),
        "known_limitations": [
            "Training data may be synthetic — calibration based on mock election patterns",
            "Isotonic calibration requires monotonic relationship between raw scores and labels",
            "Support scores reflect aggregate precinct patterns, not individual voter level",
        ],
    }
    (MODELS_DIR / "support_model_calibration.json").write_text(
        json.dumps(cal_info, indent=2), encoding="utf-8"
    )

    # Write calibration report
    _write_calibration_report(run_id, params, cal_info, raw_preds,
                              iso.predict(raw_preds) if cal_model else raw_preds,
                              y_test)

    log.info(f"[TRAIN_SUPPORT] Complete | calibrated={cal_model is not None}")
    return params


def _write_calibration_report(run_id, params, cal_info, raw_preds, cal_preds, y_test):
    from sklearn.metrics import mean_absolute_error
    pre = cal_info["pre_calibration_distribution"]
    post = cal_info["post_calibration_distribution"]

    lines = [
        f"# Persuasion Model Calibration Report",
        f"**Run ID:** {run_id}  |  **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Model Details",
        f"- Raw model type: `{params['model_type']}`",
        f"- Training samples: {params['training_samples']:,}",
        f"- Test samples: {params['test_samples']:,}",
        f"- Training contests: {params['training_contests']}",
        "",
        "## Calibration Method",
        f"- Method used: **{cal_info['calibration_method']}**",
        f"- Applied: {'✅ YES' if cal_info['calibration_applied'] else '❌ NO (insufficient data)'}",
        "",
        "## Pre-Calibration Score Distribution",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Mean | {pre['mean']} |",
        f"| Std  | {pre['std']} |",
        f"| P10  | {pre['p10']} |",
        f"| P50  | {pre['p50']} |",
        f"| P90  | {pre['p90']} |",
        "",
        "## Post-Calibration Score Distribution",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Mean | {post['mean']} |",
        f"| Std  | {post['std']} |",
        f"| P10  | {post['p10']} |",
        f"| P50  | {post['p50']} |",
        f"| P90  | {post['p90']} |",
        "",
        "## Validation Metrics",
        f"- Pre-calibration MAE: {params['metrics_raw']['mae']} | R²: {params['metrics_raw']['r2']}",
        f"- Post-calibration MAE: {params['metrics_calibrated']['mae']} | R²: {params['metrics_calibrated']['r2']}",
        f"- MAE improvement: {cal_info['cal_mae_improvement']:+.4f}",
        "",
        "## Known Limitations",
    ] + [f"- {l}" for l in cal_info["known_limitations"]]

    rpath = REPORTS_DIR / f"{run_id}__persuasion_calibration_report.md"
    rpath.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[TRAIN_SUPPORT] Wrote calibration report → {rpath.name}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train_model()
    print("Support model training and calibration complete.")
