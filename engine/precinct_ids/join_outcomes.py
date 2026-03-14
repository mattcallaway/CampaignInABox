"""
engine/precinct_ids/join_outcomes.py — Prompt 29

Standardised join outcome taxonomy for all precinct normalization
and geometry join steps.

Every crosswalk, normalization, and geometry join must emit one of
these outcomes — never a silent failure.
"""
from __future__ import annotations

# ── Outcome constants ─────────────────────────────────────────────────────────

# Successful joins
EXACT_GEOMETRY_MATCH      = "EXACT_GEOMETRY_MATCH"       # raw ID matched directly to geometry key
EXACT_CROSSWALK_MATCH     = "EXACT_CROSSWALK_MATCH"      # crosswalk file produced unambiguous match
NORMALIZED_MATCH          = "NORMALIZED_MATCH"            # zero-padding / prefix strip produced match
MULTI_STEP_CROSSWALK_MATCH = "MULTI_STEP_CROSSWALK_MATCH" # multi-hop chain (e.g. SRPREC→BLK→MPREC)

# Problematic but recoverable
AMBIGUOUS_SOURCE_COLUMN   = "AMBIGUOUS_SOURCE_COLUMN"    # multiple candidate source columns; needs review
AMBIGUOUS_TARGET_COLUMN   = "AMBIGUOUS_TARGET_COLUMN"    # multiple candidate target columns; needs review
IDENTITY_FALLBACK_USED    = "IDENTITY_FALLBACK_USED"     # crosswalk detection failed; raw ID used as-is
                                                          # ⚠️ this is dangerous — map will be wrong

# Hard failures
NO_MATCH_AFTER_NORMALIZATION  = "NO_MATCH_AFTER_NORMALIZATION"  # normalization ran but ID not in geometry
BLOCKED_CROSS_JURISDICTION    = "BLOCKED_CROSS_JURISDICTION"    # refused safety: cross-county join
GEOMETRY_KEY_MISSING          = "GEOMETRY_KEY_MISSING"          # geometry file lacks expected ID column


ALL_OUTCOMES = {
    EXACT_GEOMETRY_MATCH,
    EXACT_CROSSWALK_MATCH,
    NORMALIZED_MATCH,
    MULTI_STEP_CROSSWALK_MATCH,
    AMBIGUOUS_SOURCE_COLUMN,
    AMBIGUOUS_TARGET_COLUMN,
    IDENTITY_FALLBACK_USED,
    NO_MATCH_AFTER_NORMALIZATION,
    BLOCKED_CROSS_JURISDICTION,
    GEOMETRY_KEY_MISSING,
}

SUCCESS_OUTCOMES = {
    EXACT_GEOMETRY_MATCH,
    EXACT_CROSSWALK_MATCH,
    NORMALIZED_MATCH,
    MULTI_STEP_CROSSWALK_MATCH,
}

FAILURE_OUTCOMES = {
    NO_MATCH_AFTER_NORMALIZATION,
    BLOCKED_CROSS_JURISDICTION,
    GEOMETRY_KEY_MISSING,
}

REVIEW_REQUIRED_OUTCOMES = {
    AMBIGUOUS_SOURCE_COLUMN,
    AMBIGUOUS_TARGET_COLUMN,
    IDENTITY_FALLBACK_USED,
}


def is_success(outcome: str) -> bool:
    return outcome in SUCCESS_OUTCOMES


def is_failure(outcome: str) -> bool:
    return outcome in FAILURE_OUTCOMES


def needs_review(outcome: str) -> bool:
    return outcome in REVIEW_REQUIRED_OUTCOMES
