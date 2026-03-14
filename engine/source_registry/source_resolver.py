"""
engine/source_registry/source_resolver.py — Prompt 25A

Source Resolver.

When the system needs to find an election result file or geometry file,
the resolver is the first call — registry-first, then generic discovery fallback.

This is the primary interface for archive_ingest.py, file_registry_pipeline.py,
and the missing data assistant.
"""
from __future__ import annotations

import logging
from typing import Optional

from engine.source_registry.source_registry import (
    find_contest_sources,
    find_geometry_sources,
    load_contest_registry,
    load_geometry_registry,
)

log = logging.getLogger(__name__)

# Thresholds
HIGH_CONFIDENCE_THRESHOLD  = 0.80   # Use directly
MEDIUM_CONFIDENCE_THRESHOLD = 0.55   # Present to user for confirmation
LOW_CONFIDENCE_THRESHOLD   = 0.35   # Include in fallback list only


class ResolverResult:
    """Structured result returned by the source resolver."""

    def __init__(
        self,
        query: dict,
        high_confidence:  list[dict],
        medium_confidence: list[dict],
        low_confidence:   list[dict],
        fallback_required: bool,
    ):
        self.query             = query
        self.high_confidence   = high_confidence
        self.medium_confidence = medium_confidence
        self.low_confidence    = low_confidence
        self.fallback_required  = fallback_required

    @property
    def best(self) -> Optional[dict]:
        """Return the single best source, or None."""
        if self.high_confidence:
            return self.high_confidence[0]
        if self.medium_confidence:
            return self.medium_confidence[0]
        return None

    @property
    def has_known_source(self) -> bool:
        return bool(self.high_confidence or self.medium_confidence)

    def to_dict(self) -> dict:
        return {
            "query":              self.query,
            "high_confidence":    self.high_confidence,
            "medium_confidence":  self.medium_confidence,
            "low_confidence":     self.low_confidence,
            "fallback_required":  self.fallback_required,
            "best_source_id":     self.best.get("source_id") if self.best else None,
        }

    def __repr__(self):
        return (
            f"ResolverResult(best={self.best.get('source_id') if self.best else None}, "
            f"high={len(self.high_confidence)}, med={len(self.medium_confidence)}, "
            f"fallback={self.fallback_required})"
        )


# ── Contest Resolution ────────────────────────────────────────────────────────

def resolve_contest_source(
    state: str,
    county: Optional[str] = None,
    year: Optional[int] = None,
    election_type: Optional[str] = None,
    contest_name: Optional[str] = None,
    auto_ingest_only: bool = False,
) -> ResolverResult:
    """
    Registry-first resolution for an election result source.

    Behavior:
    1. Checks registry for known, high-confidence sources
    2. If high-confidence found → return it (no fallback needed)
    3. If medium-confidence found → return it with fallback_required=False,
       but flag that user confirmation is advised
    4. If only low-confidence → set fallback_required=True
    5. If no registry match → set fallback_required=True

    Args:
        state: Two-letter state code
        county: County name (optional)
        year: Election year (optional)
        election_type: "general", "primary", "special", etc.
        contest_name: Optional contest / measure name
        auto_ingest_only: If True, filter to sources where auto_ingest_allowed=True

    Returns:
        ResolverResult with tiered matches
    """
    query = dict(
        state=state, county=county, year=year,
        election_type=election_type, contest_name=contest_name,
    )

    candidates = find_contest_sources(
        state=state,
        county=county,
        year=year,
        election_type=election_type,
        contest_name=contest_name,
        min_confidence=0.0,
    )

    if auto_ingest_only:
        candidates = [c for c in candidates if c.get("auto_ingest_allowed", False)]

    high   = [c for c in candidates if c["_match_score"] >= HIGH_CONFIDENCE_THRESHOLD]
    medium = [c for c in candidates if MEDIUM_CONFIDENCE_THRESHOLD <= c["_match_score"] < HIGH_CONFIDENCE_THRESHOLD]
    low    = [c for c in candidates if c["_match_score"] < MEDIUM_CONFIDENCE_THRESHOLD]

    fallback_required = not bool(high or medium)

    # Official-status prioritization within each tier
    for tier in [high, medium, low]:
        tier.sort(key=lambda x: (
            x.get("official_status", "unknown") in ["certified", "official"],
            x["_match_score"],
        ), reverse=True)

    result = ResolverResult(
        query=query,
        high_confidence=high,
        medium_confidence=medium,
        low_confidence=low,
        fallback_required=fallback_required,
    )

    log.info(
        f"[RESOLVER] Contest resolve({state}, {county}, {year}, {election_type}) → "
        f"high={len(high)}, med={len(medium)}, low={len(low)}, "
        f"fallback={fallback_required}"
    )
    return result


# ── Geometry Resolution ───────────────────────────────────────────────────────

def resolve_geometry_source(
    state: str,
    county: Optional[str] = None,
    boundary_type: Optional[str] = None,
) -> ResolverResult:
    """
    Registry-first resolution for a geometry or crosswalk source.

    Returns tiered ResolverResult, preferred sources first within each tier.
    """
    query = dict(state=state, county=county, boundary_type=boundary_type)

    candidates = find_geometry_sources(
        state=state,
        county=county,
        boundary_type=boundary_type,
    )

    # For geometry, score is just confidence_default (no match_score added by registry)
    # Add a synthetic _match_score for consistency with contest tier logic
    for c in candidates:
        c.setdefault("_match_score", c.get("confidence_default", 0.5))

    high   = [c for c in candidates if c["_match_score"] >= HIGH_CONFIDENCE_THRESHOLD]
    medium = [c for c in candidates if MEDIUM_CONFIDENCE_THRESHOLD <= c["_match_score"] < HIGH_CONFIDENCE_THRESHOLD]
    low    = [c for c in candidates if c["_match_score"] < MEDIUM_CONFIDENCE_THRESHOLD]

    # Preferred flag sorts within tiers
    for tier in [high, medium, low]:
        tier.sort(key=lambda x: (x.get("preferred", False), x["_match_score"]), reverse=True)

    fallback_required = not bool(high or medium)

    result = ResolverResult(
        query=query,
        high_confidence=high,
        medium_confidence=medium,
        low_confidence=low,
        fallback_required=fallback_required,
    )

    log.info(
        f"[RESOLVER] Geometry resolve({state}, {county}, {boundary_type}) → "
        f"high={len(high)}, med={len(medium)}, low={len(low)}"
    )
    return result


# ── Quick Helpers ─────────────────────────────────────────────────────────────

def get_best_contest_source(
    state: str,
    county: Optional[str] = None,
    year: Optional[int] = None,
    election_type: Optional[str] = None,
) -> Optional[dict]:
    """Returns the single best match, or None if no high/medium match."""
    result = resolve_contest_source(state=state, county=county, year=year, election_type=election_type)
    return result.best


def get_best_geometry_source(
    state: str,
    county: Optional[str] = None,
    boundary_type: Optional[str] = None,
) -> Optional[dict]:
    """Returns the single best geometry match, or None."""
    result = resolve_geometry_source(state=state, county=county, boundary_type=boundary_type)
    return result.best


def summarize_registry_coverage(state: str, county: Optional[str] = None) -> dict:
    """
    Summarize what sources are available in the registry for a given jurisdiction.
    Returns a coverage dict suitable for campaign_state.json.
    """
    contest_sources  = find_contest_sources(state=state, county=county)
    geometry_sources = find_geometry_sources(state=state, county=county)

    approved_contest  = sum(1 for s in contest_sources if s.get("user_approved"))
    approved_geometry = sum(1 for s in geometry_sources if s.get("user_approved"))

    # Simple coverage rating
    total = len(contest_sources) + len(geometry_sources)
    if total >= 10:
        coverage = "strong"
    elif total >= 5:
        coverage = "good"
    elif total >= 1:
        coverage = "partial"
    else:
        coverage = "none"

    return {
        "contest_sources":   len(contest_sources),
        "geometry_sources":  len(geometry_sources),
        "approved_sources":  approved_contest + approved_geometry,
        "registry_coverage": coverage,
    }
