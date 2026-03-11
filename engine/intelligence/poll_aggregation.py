"""
engine/intelligence/poll_aggregation.py — Prompt 17

Combine multiple polls into a weighted average estimate.

Weight formula (multiplicative):
    w_i = sample_weight × recency_weight × quality_weight

    sample_weight  = sqrt(sample_size) / max(sqrt(sample_sizes))
    recency_weight = exp(-λ × days_since_field)  where λ = 0.05
    quality_weight = pollster_quality_rating (default 1.0, range 0.5–1.5)

Rolling average:
    ŝ = Σ(w_i × s_i) / Σ(w_i)

Output:
    derived/intelligence/poll_average.json

Provenance: EXTERNAL (if any real polls), SIMULATED (if synthetic only)
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

DERIVED_DIR = Path(__file__).resolve().parent.parent.parent / "derived" / "intelligence"

# Decay constant for recency weighting (higher = faster decay)
_LAMBDA = 0.05

# Default pollster quality ratings (can be extended via pollster_quality.yaml)
_DEFAULT_QUALITY: dict[str, float] = {
    "internal": 0.7,
    "campaign": 0.7,
    "cbs": 1.2,
    "nyt": 1.2,
    "nbc": 1.2,
    "abc": 1.2,
    "fox": 1.1,
    "quinnipiac": 1.3,
    "emerson": 1.1,
    "suvey_usa": 1.1,
    "university": 1.1,
}


def _recency_weight(field_date_end: str, reference_date: Optional[date] = None) -> float:
    """Exponential decay by days since field end date."""
    ref = reference_date or date.today()
    try:
        fde = pd.to_datetime(field_date_end).date()
        days_ago = max((ref - fde).days, 0)
        return math.exp(-_LAMBDA * days_ago)
    except Exception:
        return 0.5


def _sample_weight(sample_size: float, max_sample: float) -> float:
    """Square-root scaled sample weight."""
    if max_sample <= 0 or pd.isna(sample_size):
        return 0.5
    return math.sqrt(max(sample_size, 0)) / math.sqrt(max(max_sample, 1))


def _quality_weight(pollster: str) -> float:
    """Look up pollster quality rating."""
    if pd.isna(pollster):
        return 1.0
    p_lower = str(pollster).lower()
    for key, rating in _DEFAULT_QUALITY.items():
        if key in p_lower:
            return rating
    return 1.0


def compute_poll_average(
    polls_df: pd.DataFrame,
    reference_date: Optional[date] = None,
    logger=None,
) -> dict:
    """
    Compute weighted poll average from normalized polling DataFrame.

    Returns a dict with poll_average, confidence intervals, and provenance.
    Writes derived/intelligence/poll_average.json.
    """
    _log = logger or log
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.utcnow().isoformat()

    result: dict = {
        "generated_at": now_iso,
        "poll_average": None,
        "poll_average_oppose": None,
        "poll_average_undecided": None,
        "n_polls": 0,
        "n_polls_weighted": 0.0,
        "confidence_interval_low": None,
        "confidence_interval_high": None,
        "source_type": "SIMULATED",
        "latest_poll_date": None,
        "polls_used": [],
        "method": "weighted_average",
        "note": "No polling data available.",
    }

    if polls_df.empty or "support_percent" not in polls_df.columns:
        _log.info("[POLL_AGG] No polls to aggregate — returning None")
        (DERIVED_DIR / "poll_average.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        return result

    valid = polls_df[polls_df["support_percent"].notna()].copy()
    if valid.empty:
        _log.info("[POLL_AGG] All polls have null support_percent")
        (DERIVED_DIR / "poll_average.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        return result

    max_sample = valid["sample_size"].dropna().max() if "sample_size" in valid.columns else 1000

    weights = []
    for _, row in valid.iterrows():
        sw = _sample_weight(row.get("sample_size", 400), max_sample)
        rw = _recency_weight(row.get("field_date_end", row.get("field_date_start", "")), reference_date)
        qw = _quality_weight(row.get("pollster", ""))
        w = sw * rw * qw
        weights.append(max(w, 0.01))

    valid = valid.copy()
    valid["_weight"] = weights
    total_w = sum(weights)

    avg_support = float(np.average(valid["support_percent"], weights=valid["_weight"]))
    avg_oppose  = (
        float(np.average(valid["oppose_percent"], weights=valid["_weight"]))
        if "oppose_percent" in valid.columns and valid["oppose_percent"].notna().any()
        else None
    )
    avg_undecided = (
        float(np.average(valid["undecided_percent"], weights=valid["_weight"]))
        if "undecided_percent" in valid.columns and valid["undecided_percent"].notna().any()
        else None
    )

    # Margin of error as weighted std dev approximation
    if len(valid) > 1:
        variance = float(np.average(
            (valid["support_percent"] - avg_support) ** 2,
            weights=valid["_weight"]
        ))
        std = math.sqrt(variance)
        ci_low  = round(max(avg_support - 1.96 * std, 0), 4)
        ci_high = round(min(avg_support + 1.96 * std, 1), 4)
    else:
        # Single poll: use textbook MOE
        n = valid["sample_size"].iloc[0] if "sample_size" in valid.columns else 400
        n = n if pd.notna(n) and n > 0 else 400
        moe = 1 / math.sqrt(n)
        ci_low  = round(max(avg_support - moe, 0), 4)
        ci_high = round(min(avg_support + moe, 1), 4)

    has_real = (
        "source_type" in valid.columns
        and (valid["source_type"] == "EXTERNAL").any()
    )

    polls_used = []
    for _, row in valid.iterrows():
        polls_used.append({
            "pollster": str(row.get("pollster", "Unknown")),
            "date": str(row.get("field_date_end", row.get("field_date_start", ""))),
            "support": round(float(row["support_percent"]), 4),
            "n": int(row.get("sample_size", 0) or 0),
            "weight": round(row["_weight"], 4),
        })

    latest_date = str(valid["field_date_end"].max()) if "field_date_end" in valid.columns else None

    result.update({
        "poll_average": round(avg_support, 4),
        "poll_average_oppose": round(avg_oppose, 4) if avg_oppose is not None else None,
        "poll_average_undecided": round(avg_undecided, 4) if avg_undecided is not None else None,
        "n_polls": len(valid),
        "n_polls_weighted": round(total_w, 3),
        "confidence_interval_low": ci_low,
        "confidence_interval_high": ci_high,
        "source_type": "EXTERNAL" if has_real else "SIMULATED",
        "latest_poll_date": latest_date,
        "polls_used": polls_used,
        "note": (
            f"Weighted average of {len(valid)} poll(s). "
            f"Confidence: {'EXTERNAL' if has_real else 'SIMULATED'}."
        ),
    })

    (DERIVED_DIR / "poll_average.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    _log.info(
        f"[POLL_AGG] Average={avg_support:.3f} ± [{ci_low:.3f},{ci_high:.3f}] "
        f"from {len(valid)} polls (type={result['source_type']})"
    )
    return result


def load_poll_average() -> dict:
    """Load saved poll average JSON."""
    path = DERIVED_DIR / "poll_average.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}
