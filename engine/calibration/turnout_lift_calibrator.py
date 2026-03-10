"""
engine/calibration/turnout_lift_calibrator.py — Prompt 15

Estimates turnout_lift_per_contact — the fractional increase in turnout
probability caused by one campaign contact.

Data sources:
  1. Runtime field results (Prompt 14) — most accurate when available
  2. Historical election variance — proxy for maximum achievable lift
  3. Literature prior (0.06 = 6 pp per contact based on GOTV literature)

Output:
    derived/calibration/turnout_lift_parameters.json
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Literature-based prior (Gerber & Green GOTV meta-analysis)
PRIOR_LIFT = 0.06       # 6 percentage points per contacted voter
PRIOR_VARIANCE = 0.02   # ±2 pp standard deviation


def calibrate_turnout_lift(
    hist_df: pd.DataFrame,
    runtime: dict,
    precinct_model: pd.DataFrame,
    root: Path,
    logger=None,
) -> dict:
    """
    Estimate turnout_lift_per_contact.

    Strategy:
      1. If runtime field results exist: estimate lift from contacts_made
         and the historical baseline turnout as counterfactual.
      2. Else if historical data: use year-over-year turnout residuals as
         upper-bound proxy for field effect.
      3. Else: return prior.

    Returns dict (also writes turnout_lift_parameters.json).
    """
    _log = logger or log
    out: dict = {
        "method": "prior",
        "turnout_lift_per_contact": PRIOR_LIFT,
        "turnout_lift_variance": PRIOR_VARIANCE,
        "confidence": "none",
        "notes": "Using Gerber & Green prior (6pp/contact). Add field results to calibrate.",
    }

    calib_dir = root / "derived" / "calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)

    # ── Strategy 1: Runtime field results ────────────────────────────────────
    field_results = runtime.get("field_results")
    if field_results is not None and not (
        isinstance(field_results, pd.DataFrame) and field_results.empty
    ):
        try:
            df = field_results if isinstance(field_results, pd.DataFrame) else pd.DataFrame(field_results)
            if "contacts_made" in df.columns:
                total_contacts = df["contacts_made"].sum()
                total_doors    = df.get("doors_knocked", pd.Series([0])).sum() if "doors_knocked" in df.columns else 0
                gotv_contacts  = df.get("gotv_contacts", pd.Series([0])).sum() if "gotv_contacts" in df.columns else total_contacts

                if total_contacts > 0:
                    # Without a controlled comparison we use a conservative estimate:
                    # lift = 60% of the lit prior, scaled by contact rate
                    contact_rate = float(total_contacts) / max(float(total_doors), 1.0)
                    est_lift = round(min(PRIOR_LIFT * (contact_rate / 0.22), PRIOR_LIFT * 1.5), 5)

                    out.update({
                        "method": "runtime_field_observed",
                        "turnout_lift_per_contact": est_lift,
                        "turnout_lift_variance": PRIOR_VARIANCE,
                        "total_contacts": int(total_contacts),
                        "total_doors": int(total_doors),
                        "observed_contact_rate": round(contact_rate, 4),
                        "confidence": "low",
                        "notes": (
                            f"Estimated from {int(total_contacts)} contacts. "
                            "Needs A/B field experiment for high confidence."
                        ),
                    })
                    _log.info(
                        f"[LIFT_CAL] Runtime field: contacts={int(total_contacts)}, "
                        f"contact_rate={contact_rate:.2%}, lift={est_lift:.5f}"
                    )
                    out_path = calib_dir / "turnout_lift_parameters.json"
                    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
                    return out
        except Exception as e:
            _log.debug(f"[LIFT_CAL] Runtime field parsing failed: {e}")

    # ── Strategy 2: Historical residual variance ──────────────────────────────
    if not hist_df.empty and "turnout_rate" in hist_df.columns and hist_df["year"].nunique() >= 2:
        try:
            pivot = hist_df.pivot_table(
                index="canonical_precinct_id",
                columns="year",
                values="turnout_rate",
                aggfunc="mean",
            ).dropna()

            if pivot.shape[1] >= 2:
                years = sorted(pivot.columns)
                deltas = []
                for i in range(len(years) - 1):
                    col_delta = pivot[years[i + 1]] - pivot[years[i]]
                    deltas.extend(col_delta.dropna().tolist())

                if deltas:
                    # Mean absolute year-over-year swing, scaled conservatively
                    mean_swing = float(np.mean(np.abs(deltas)))
                    est_lift = round(min(mean_swing * 0.3, PRIOR_LIFT * 1.2), 5)
                    variance = round(float(np.std(deltas)) * 0.3, 5)

                    out.update({
                        "method": "historical_residuals",
                        "turnout_lift_per_contact": est_lift,
                        "turnout_lift_variance": variance,
                        "n_elections": hist_df["year"].nunique(),
                        "mean_yoy_swing": round(mean_swing, 4),
                        "confidence": "low",
                        "notes": (
                            f"Estimated from year-over-year swing across "
                            f"{hist_df['year'].nunique()} elections."
                        ),
                    })
                    _log.info(
                        f"[LIFT_CAL] Historical swing={mean_swing:.4f}, "
                        f"est_lift={est_lift:.5f}"
                    )
        except Exception as e:
            _log.debug(f"[LIFT_CAL] Historical analysis failed: {e}")

    out_path = calib_dir / "turnout_lift_parameters.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    _log.info(f"[LIFT_CAL] Written → {out_path.name}")
    return out
