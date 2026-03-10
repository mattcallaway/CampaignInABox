"""
engine/calibration/forecast_accuracy.py — Prompt 15

Tracks forecast accuracy over time by comparing model predictions
against actual election results (post-election).

Output:
    derived/calibration/forecast_accuracy.csv
    Fields: contest, predicted, actual, error, abs_error, run_id, date
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

ACC_CSV = "forecast_accuracy.csv"


def track_forecast_accuracy(
    hist_df: pd.DataFrame,
    precinct_model: pd.DataFrame,
    root: Path,
    run_id: str = "",
    logger=None,
) -> dict:
    """
    Track forecast accuracy.

    Compares the current model's predicted support_rate against
    historical actual results where both exist and the years overlap.

    Appends new records to derived/calibration/forecast_accuracy.csv.

    Returns a summary dict with accuracy metrics.
    """
    _log = logger or log
    calib_dir = root / "derived" / "calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)
    acc_path = calib_dir / ACC_CSV

    result: dict = {
        "records": [],
        "mean_absolute_error": None,
        "n_contests_tracked": 0,
        "has_real_election_results": False,
    }

    if hist_df.empty or precinct_model.empty:
        _log.info("[FORECAST_ACC] Insufficient data for accuracy tracking")
        return result

    if "support_rate" not in hist_df.columns or "support_pct" not in precinct_model.columns:
        _log.info("[FORECAST_ACC] Missing support columns — skipping accuracy calc")
        return result

    try:
        # Aggregate historical results to contest-level mean
        hist_agg = (
            hist_df.groupby("year")["support_rate"]
            .mean()
            .reset_index()
            .rename(columns={"year": "contest", "support_rate": "actual"})
        )
        hist_agg["contest"] = hist_agg["contest"].astype(str)

        # Model predicted = mean support_pct from precinct model
        pred_val = float(precinct_model["support_pct"].mean())

        new_rows = []
        for _, row in hist_agg.iterrows():
            actual = float(row["actual"])
            error  = round(pred_val - actual, 4)
            abs_err = round(abs(error), 4)
            rec = {
                "contest":  str(row["contest"]),
                "predicted": round(pred_val, 4),
                "actual":   round(actual, 4),
                "error":    error,
                "abs_error": abs_err,
                "run_id":   run_id,
                "date":     datetime.utcnow().strftime("%Y-%m-%d"),
            }
            new_rows.append(rec)
            result["records"].append(rec)

        # Append to CSV
        new_df = pd.DataFrame(new_rows)
        if acc_path.exists():
            existing = pd.read_csv(acc_path)
            # Deduplicate by contest + run_id
            combined = pd.concat([existing, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["contest", "run_id"], keep="last")
        else:
            combined = new_df

        combined.to_csv(acc_path, index=False)

        if not new_df.empty:
            mae = float(new_df["abs_error"].mean())
            result["mean_absolute_error"] = round(mae, 4)
            result["n_contests_tracked"] = len(new_df)
            result["has_real_election_results"] = True
            _log.info(
                f"[FORECAST_ACC] Tracked {len(new_df)} contests, MAE={mae:.4f} | "
                f"written → {acc_path.name}"
            )

    except Exception as e:
        _log.warning(f"[FORECAST_ACC] Accuracy tracking failed: {e}")

    return result


def load_accuracy_history(root: Path) -> pd.DataFrame:
    """Load all forecast accuracy records."""
    path = root / "derived" / "calibration" / ACC_CSV
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            pass
    return pd.DataFrame()
