"""
engine/source_registry/source_registry.py — Prompt 25A

Source Registry Loader.

The source registry is the first lookup layer for election data discovery.
Before running web search or asking a user for a file, the system should
call this module to find known high-confidence sources.

Usage:
    from engine.source_registry.source_registry import (
        load_contest_registry,
        load_geometry_registry,
        find_contest_sources,
        find_geometry_sources,
    )
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REGISTRY_DIR = BASE_DIR / "config" / "source_registry"

CONTEST_REGISTRY_PATH  = REGISTRY_DIR / "contest_sources.yaml"
GEOMETRY_REGISTRY_PATH = REGISTRY_DIR / "geometry_sources.yaml"
LOCAL_OVERRIDES_PATH   = REGISTRY_DIR / "local_overrides.yaml"

# Cache
_contest_registry:  Optional[list[dict]] = None
_geometry_registry: Optional[list[dict]] = None


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_contest_registry(force_reload: bool = False) -> list[dict]:
    """
    Load the contest source registry (seeded + local overrides merged).
    Returns a list of source dicts, each matching the schema in source_registry_schema.yaml.
    """
    global _contest_registry
    if _contest_registry is not None and not force_reload:
        return _contest_registry

    sources: list[dict] = []

    # Seeded registry
    if CONTEST_REGISTRY_PATH.exists():
        try:
            data = yaml.safe_load(CONTEST_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
            sources = list(data.get("sources", []))
            log.info(f"[SOURCE_REGISTRY] Loaded {len(sources)} seeded contest sources")
        except Exception as e:
            log.warning(f"[SOURCE_REGISTRY] Could not load contest registry: {e}")

    # Local overrides (user-approved sources + manual additions)
    sources = _apply_overrides(sources, "manual_contest_sources")

    _contest_registry = sources
    return _contest_registry


def load_geometry_registry(force_reload: bool = False) -> list[dict]:
    """
    Load the geometry source registry (seeded + local overrides merged).
    """
    global _geometry_registry
    if _geometry_registry is not None and not force_reload:
        return _geometry_registry

    sources: list[dict] = []

    if GEOMETRY_REGISTRY_PATH.exists():
        try:
            data = yaml.safe_load(GEOMETRY_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
            sources = list(data.get("sources", []))
            log.info(f"[SOURCE_REGISTRY] Loaded {len(sources)} seeded geometry sources")
        except Exception as e:
            log.warning(f"[SOURCE_REGISTRY] Could not load geometry registry: {e}")

    sources = _apply_overrides(sources, "manual_geometry_sources")

    _geometry_registry = sources
    return _geometry_registry


def _apply_overrides(sources: list[dict], manual_key: str) -> list[dict]:
    """
    Apply local_overrides.yaml:
    1. Merge `approved_updates` (updates fields on existing source_ids)
    2. Append `manual_key` entries (new sources only)
    """
    if not LOCAL_OVERRIDES_PATH.exists():
        return sources

    try:
        overrides = yaml.safe_load(LOCAL_OVERRIDES_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:
        log.warning(f"[SOURCE_REGISTRY] Could not load local_overrides.yaml: {e}")
        return sources

    # Apply field updates to existing sources
    approved_updates = overrides.get("approved_updates", []) or []
    update_map = {u["source_id"]: u for u in approved_updates if "source_id" in u}

    merged = []
    for src in sources:
        sid = src.get("source_id")
        if sid in update_map:
            updated = {**src, **update_map.pop(sid)}
            merged.append(updated)
        else:
            merged.append(src)

    # Append any manual sources not in the seeded registry
    for entry in (overrides.get(manual_key, []) or []):
        sid = entry.get("source_id")
        if sid and not any(s.get("source_id") == sid for s in merged):
            merged.append(entry)

    return merged


# ── Finders ──────────────────────────────────────────────────────────────────

def find_contest_sources(
    state: str,
    county: Optional[str] = None,
    year: Optional[int] = None,
    election_type: Optional[str] = None,
    contest_name: Optional[str] = None,
    min_confidence: float = 0.0,
) -> list[dict]:
    """
    Find contest sources matching the given criteria.
    Returns sources sorted by score (descending), filtering by min_confidence.

    Args:
        state: Two-letter state code (e.g. "CA")
        county: County name (optional)
        year: Election year (optional)
        election_type: "general", "primary", "special", etc.
        contest_name: Contest or measure name — matched against contest_name and contest_aliases
        min_confidence: Minimum confidence_default to include (0.0 = all)
    """
    sources = load_contest_registry()

    results = []
    for src in sources:
        score = score_registry_match(
            src, state=state, county=county, year=year,
            election_type=election_type, contest_name=contest_name,
        )
        if score is not None and src.get("confidence_default", 0) >= min_confidence:
            results.append({**src, "_match_score": round(score, 4)})

    results.sort(key=lambda x: x["_match_score"], reverse=True)
    log.info(
        f"[SOURCE_REGISTRY] find_contest_sources({state}, {county}, {year}, {election_type}) "
        f"→ {len(results)} matches"
    )
    return results


def find_geometry_sources(
    state: str,
    county: Optional[str] = None,
    boundary_type: Optional[str] = None,
    preferred_only: bool = False,
) -> list[dict]:
    """
    Find geometry sources matching the given criteria.
    Returns sources sorted by confidence_default (descending).
    """
    sources = load_geometry_registry()

    results = []
    for src in sources:
        if src.get("state", "").upper() != state.upper():
            continue
        if county and src.get("county") and src["county"].lower() != county.lower():
            continue
        if boundary_type and src.get("boundary_type", "").lower() != boundary_type.lower():
            continue
        if preferred_only and not src.get("preferred", False):
            continue
        results.append(src)

    results.sort(key=lambda x: x.get("confidence_default", 0.0), reverse=True)
    log.info(
        f"[SOURCE_REGISTRY] find_geometry_sources({state}, {county}, {boundary_type}) "
        f"→ {len(results)} matches"
    )
    return results


def score_registry_match(
    source: dict,
    state: str,
    county: Optional[str] = None,
    year: Optional[int] = None,
    election_type: Optional[str] = None,
    contest_name: Optional[str] = None,
) -> Optional[float]:
    """
    Score a registry entry against search criteria.
    Returns a float (higher is better) or None if the source is disqualified.

    Scoring rules:
    - Must match state (exact, case-insensitive) — disqualify if no match
    - County match adds weight (statewide sources still match county searches)
    - Year match adds weight; year mismatch within 2 years reduces weight
    - Election type match adds weight
    - Contest name / alias match adds weight
    - Multiply by confidence_default at the end
    """
    # State check (required)
    if source.get("state", "").upper() != state.upper():
        return None

    score = 1.0  # base score

    # County
    src_county = (source.get("county") or "").lower()
    if county:
        q_county = county.lower()
        if src_county == q_county:
            score += 0.40
        elif src_county == "":
            # Statewide source — partial match
            score += 0.10
        else:
            # Wrong county
            return None
    elif src_county == "":
        score += 0.05  # statewide source, county unspecified in query

    # Year
    src_year = source.get("year")
    if year and src_year:
        if isinstance(src_year, list):
            if year in src_year:
                score += 0.30
            elif any(abs(year - y) <= 2 for y in src_year):
                score += 0.10
        else:
            if src_year == year:
                score += 0.30
            elif abs(src_year - year) <= 2:
                score += 0.10
    elif year and not src_year:
        # Registry entry covers any year (e.g. county_registrar generic)
        score += 0.05

    # Election type
    src_et = (source.get("election_type") or "").lower()
    if election_type and src_et:
        if src_et == election_type.lower():
            score += 0.20
        else:
            score -= 0.10  # wrong type, mild penalization

    # Contest name / alias
    if contest_name:
        src_name = (source.get("contest_name") or "").lower()
        aliases = [a.lower() for a in (source.get("contest_aliases") or [])]
        q = contest_name.lower()
        if q in src_name or src_name in q:
            score += 0.20
        elif any(q in a or a in q for a in aliases):
            score += 0.15

    # Multiply by source confidence
    score *= source.get("confidence_default", 0.5)

    return max(0.0, score)


def get_source_by_id(source_id: str, source_type: str = "contest") -> Optional[dict]:
    """
    Retrieve a single source entry by its source_id.

    Args:
        source_id: The unique source identifier
        source_type: "contest" or "geometry"
    """
    if source_type == "geometry":
        sources = load_geometry_registry()
    else:
        sources = load_contest_registry()

    for src in sources:
        if src.get("source_id") == source_id:
            return src
    return None
