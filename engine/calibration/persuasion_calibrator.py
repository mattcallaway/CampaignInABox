"""
engine/calibration/persuasion_calibrator.py — Prompt 15

Estimates persuasion lift per contact from:
  1. Campaign runtime contact results (Prompt 14 War Room field data)
  2. Historical ballot measure support variance
  3. Prior from config

Output:
    derived/calibration/persuasion_parameters.json
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Hardcoded prior (evidence-based literature value)
PRIOR_PERSUASION_LIFT = 0.006   # 0.6 pp per contact
PRIOR_PERSUASION_VARIANCE = 0.003


def calibrate_persuasion(
    hist_df: pd.DataFrame,
    runtime: dict,
    vi_summary: dict,
    root: Path,
    logger=None,
) -> dict:
    """
    Estimate persuasion_lift_per_contact.

    Strategy:
      1. If runtime contact ID results exist (Prompt 14), derive observed
         persuasion rate from support_ids / total_contacts.
      2. Else if historical data: estimate from ballot measure support
         variance across years (proxy for persuadability).
      3. Else: return prior.

    Returns dict (also writes persuasion_parameters.json).
    """
    _log = logger or log
    out: dict = {
        "method": "prior",
        "persuasion_lift_per_contact": PRIOR_PERSUASION_LIFT,
        "persuasion_variance": PRIOR_PERSUASION_VARIANCE,
        "confidence": "none",
        "notes": "Using prior (0.6pp/contact). Enter field contact results to calibrate.",
    }

    calib_dir = root / "derived" / "calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)

    # ── Strategy 1: Runtime contact results ───────────────────────────────────
    runtime_metrics = runtime.get("metrics", {})
    contact_results = runtime.get("contact_results")
    if contact_results is not None and not (
        isinstance(contact_results, pd.DataFrame) and contact_results.empty
    ):
        try:
            df = contact_results if isinstance(contact_results, pd.DataFrame) else pd.DataFrame(contact_results)
            if "contacts" in df.columns and "supporters_count" in df.columns:
                total_contacts = df["contacts"].sum()
                total_support  = df["supporters_count"].sum()
                total_persuadable = df.get("persuadables_count", pd.Series([0])).sum() if "persuadables_count" in df.columns else 0

                if total_contacts > 0 and (total_support + total_persuadable) > 0:
                    # Persuasion lift = fraction of contacts that resulted in supporter/persuadable ID
                    obs_lift = float((total_support + total_persuadable) / total_contacts)
                    # Cap at plausible range
                    obs_lift = min(max(obs_lift, 0.001), 0.25)

                    out.update({
                        "method": "runtime_observed",
                        "persuasion_lift_per_contact": round(obs_lift, 5),
                        "persuasion_variance": round(PRIOR_PERSUASION_VARIANCE, 5),
                        "total_contacts_observed": int(total_contacts),
                        "total_supporters_id": int(total_support),
                        "confidence": "medium" if total_contacts > 100 else "low",
                        "notes": f"Observed from {int(total_contacts)} real contacts.",
                    })
                    _log.info(
                        f"[PERSUASION_CAL] Runtime observed lift={obs_lift:.5f} "
                        f"from {int(total_contacts)} contacts"
                    )
                    out_path = calib_dir / "persuasion_parameters.json"
                    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
                    return out
        except Exception as e:
            _log.debug(f"[PERSUASION_CAL] Runtime parsing failed: {e}")

    # ── Strategy 2: Historical support variance ────────────────────────────────
    if not hist_df.empty and "support_rate" in hist_df.columns:
        valid = hist_df["support_rate"].dropna()
        if len(valid) > 5:
            # Inter-election variance in support is a proxy for persuadability ceiling
            support_variance = float(valid.std())
            # Persuasion lift ~= 10% of natural swing per contact (conservative)
            estimated_lift = round(min(support_variance * 0.1, 0.05), 5)
            n_elec = hist_df["year"].nunique()

            out.update({
                "method": "historical_variance",
                "persuasion_lift_per_contact": estimated_lift,
                "persuasion_variance": round(support_variance * 0.05, 5),
                "observed_support_variance": round(support_variance, 4),
                "n_elections": n_elec,
                "confidence": "low",
                "notes": (
                    f"Estimated from {n_elec} historical elections. "
                    "Enter field contact results to improve confidence."
                ),
            })
            _log.info(
                f"[PERSUASION_CAL] Historical-derived lift={estimated_lift:.5f}, "
                f"support_variance={support_variance:.4f}"
            )

    out_path = calib_dir / "persuasion_parameters.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    _log.info(f"[PERSUASION_CAL] Written → {out_path.name}")
    return out
