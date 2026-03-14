"""
engine/precinct_ids/join_quality.py — Prompt 29

Computes join quality metrics for a contest file's precinct join results.
Answers: what % of contest rows joined to geometry? Are crosswalks working?
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from engine.precinct_ids.join_outcomes import (
    EXACT_GEOMETRY_MATCH, EXACT_CROSSWALK_MATCH, NORMALIZED_MATCH,
    MULTI_STEP_CROSSWALK_MATCH, AMBIGUOUS_SOURCE_COLUMN, AMBIGUOUS_TARGET_COLUMN,
    IDENTITY_FALLBACK_USED, NO_MATCH_AFTER_NORMALIZATION,
    BLOCKED_CROSS_JURISDICTION, GEOMETRY_KEY_MISSING,
    SUCCESS_OUTCOMES, FAILURE_OUTCOMES, REVIEW_REQUIRED_OUTCOMES,
)

log = logging.getLogger(__name__)


@dataclass
class JoinQualityReport:
    run_id:             str
    state:              str
    county:             str
    contest_slug:       str
    contest_file:       str

    total_contest_rows:     int
    unique_raw_ids:         int
    exact_geometry_matches: int
    exact_crosswalk_matches: int
    normalized_matches:     int
    multi_step_matches:     int
    identity_fallbacks:     int
    ambiguous_ids:          int
    no_match_count:         int
    blocked_count:          int
    geometry_key_missing:   int

    total_joined:           int
    total_unjoined:         int
    pct_joined:             float
    pct_rendered:           float   # conservative: joined / total
    pct_blocked:            float

    crosswalks_loaded:      int
    crosswalk_detection_failures: int

    quality_verdict:        str     # "GOOD" | "PARTIAL" | "POOR" | "FAILED"
    quality_notes:          list[str]


def compute_join_quality(
    run_id:             str,
    state:              str,
    county:             str,
    contest_slug:       str,
    contest_file:       str,
    outcome_counts:     dict[str, int],  # {outcome_constant: count}
    unique_raw_ids:     int,
    crosswalks_loaded:  int,
    crosswalk_detection_failures: int,
) -> JoinQualityReport:
    """
    Build a JoinQualityReport from aggregated outcome counts.

    Args:
        outcome_counts: dict mapping join_outcome constant → count of rows
    """
    def _c(k: str) -> int:
        return outcome_counts.get(k, 0)

    exact_geo   = _c(EXACT_GEOMETRY_MATCH)
    exact_xwalk = _c(EXACT_CROSSWALK_MATCH)
    norm_match  = _c(NORMALIZED_MATCH)
    multi_step  = _c(MULTI_STEP_CROSSWALK_MATCH)
    identity_fb = _c(IDENTITY_FALLBACK_USED)
    ambiguous   = _c(AMBIGUOUS_SOURCE_COLUMN) + _c(AMBIGUOUS_TARGET_COLUMN)
    no_match    = _c(NO_MATCH_AFTER_NORMALIZATION)
    blocked     = _c(BLOCKED_CROSS_JURISDICTION)
    geo_missing = _c(GEOMETRY_KEY_MISSING)

    total_joined   = exact_geo + exact_xwalk + norm_match + multi_step
    total_rows     = sum(outcome_counts.values())
    total_unjoined = total_rows - total_joined

    pct_joined  = round(total_joined / max(total_rows, 1) * 100, 2)
    pct_blocked = round(blocked / max(total_rows, 1) * 100, 2)

    # Quality verdict
    notes: list[str] = []
    if identity_fb > 0:
        notes.append(f"⚠️  IDENTITY_FALLBACK_USED on {identity_fb} rows — crosswalk not loaded correctly")
    if crosswalk_detection_failures > 0:
        notes.append(f"⚠️  {crosswalk_detection_failures} crosswalk file(s) could not detect source/target columns")
    if pct_joined >= 85:
        verdict = "GOOD"
    elif pct_joined >= 50:
        verdict = "PARTIAL"
        notes.append(f"Only {pct_joined}% joined — check crosswalk files and column mappings")
    elif pct_joined > 0:
        verdict = "POOR"
        notes.append(f"Very low join rate ({pct_joined}%) — likely crosswalk or normalization failure")
    else:
        verdict = "FAILED"
        notes.append("0% join rate — no precinct IDs matched geometry. Check contest schema and crosswalks.")

    if crosswalks_loaded == 0:
        notes.append("No crosswalks loaded — identity mapping was used for all rows")

    return JoinQualityReport(
        run_id=run_id, state=state, county=county,
        contest_slug=contest_slug, contest_file=contest_file,
        total_contest_rows=total_rows, unique_raw_ids=unique_raw_ids,
        exact_geometry_matches=exact_geo, exact_crosswalk_matches=exact_xwalk,
        normalized_matches=norm_match, multi_step_matches=multi_step,
        identity_fallbacks=identity_fb, ambiguous_ids=ambiguous,
        no_match_count=no_match, blocked_count=blocked,
        geometry_key_missing=geo_missing,
        total_joined=total_joined, total_unjoined=total_unjoined,
        pct_joined=pct_joined, pct_rendered=pct_joined,
        pct_blocked=pct_blocked,
        crosswalks_loaded=crosswalks_loaded,
        crosswalk_detection_failures=crosswalk_detection_failures,
        quality_verdict=verdict,
        quality_notes=notes,
    )


def write_quality_report(report: JoinQualityReport, output_dir: Path) -> Path:
    """Write join quality report as JSON. Returns path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report.run_id}__join_quality.json"
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    log.info(f"[QUALITY] {report.quality_verdict} — {report.pct_joined}% joined — written to {path.name}")
    return path
