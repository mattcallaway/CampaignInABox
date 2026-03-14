"""
engine/precinct_ids/id_crosswalk_resolver.py — Prompt 25A.4

Official crosswalk-based precinct ID resolver.

Resolution order (strict):
  1. Exact canonical scoped key match  (confidence 0.99)
  2. Official crosswalk file match      (confidence 0.95)
  3. Deterministic same-jurisdiction normalization (confidence 0.90)
  4. FAIL CLOSED — no ambiguous resolution across jurisdictions

Safety rules:
  - Never fuzzy-match across county boundaries
  - SRPREC != MPREC without explicit crosswalk
  - City precincts != county precincts without city-county crosswalk
  - Multiple candidates with no crosswalk → AMBIGUOUS (not auto-joined)

Crosswalk sources checked (in priority order):
  1. config/source_registry/geometry_sources.yaml (local preferred=true entries)
  2. data/crosswalks/<state>/<county>/  (local validation files)
  3. derived/archive/  (project-derived crosswalk outputs)
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
CROSSWALK_DIR = BASE_DIR / "data" / "crosswalks"
DERIVED_DIR   = BASE_DIR / "derived" / "archive"


@dataclass
class CrosswalkMatch:
    """A single potential crosswalk resolution."""
    raw_id:       str
    resolved_id:  str
    scoped_key:   str
    source_file:  str
    boundary_from: str
    boundary_to:   str
    confidence:    float
    method:        str   # exact_key | crosswalk_file | derived_crosswalk


@dataclass
class CrosswalkResolutionResult:
    """Result of attempting to resolve a precinct ID via crosswalk."""
    raw_id:          str
    state:           str
    county:          str
    boundary_type_from: str
    boundary_type_to:   str
    status:          str              # EXACT_MATCH | CROSSWALK_MATCH | NO_MATCH | AMBIGUOUS | BLOCKED_CROSS_JURISDICTION
    confidence:      float
    resolved_key:    Optional[str]    # canonical scoped key if resolved
    candidates:      list[CrosswalkMatch]
    reason:          str


# ── Crosswalk file loaders ───────────────────────────────────────────────────

def _load_csv_crosswalk(path: Path) -> list[dict]:
    """Load a CSV crosswalk file as list of dicts."""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        log.warning(f"[CROSSWALK] Failed to load {path}: {e}")
        return []


def _load_json_crosswalk(path: Path) -> list[dict]:
    """Load a JSON crosswalk file as list of dicts."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("records", [])
    except Exception as e:
        log.warning(f"[CROSSWALK] Failed to load {path}: {e}")
        return []


def _find_crosswalk_files(state: str, county: str) -> list[Path]:
    """
    Find available crosswalk files for a given state/county.
    Searches:
      data/crosswalks/<state>/<county>/
      derived/archive/ (for derived crosswalks)
    """
    county_norm  = county.lower().replace(" ", "_")
    state_norm   = state.lower()
    paths: list[Path] = []

    local_dir = CROSSWALK_DIR / state_norm / county_norm
    if local_dir.exists():
        paths.extend(local_dir.glob("*.csv"))
        paths.extend(local_dir.glob("*.json"))

    if DERIVED_DIR.exists():
        for p in DERIVED_DIR.glob(f"*crosswalk*{county_norm}*"):
            paths.append(p)
        for p in DERIVED_DIR.glob(f"*{county_norm}*crosswalk*"):
            paths.append(p)

    return paths


def resolve_via_crosswalk(
    raw_id: str,
    state: str,
    county: str,
    boundary_type_from: str,
    boundary_type_to: str,
    canonical_index: Optional[set[str]] = None,
) -> CrosswalkResolutionResult:
    """
    Attempt to resolve a precinct ID using official crosswalk files.

    Args:
        raw_id:              raw precinct string (e.g. "127")
        state:               state code (CA)
        county:              county name (Sonoma)
        boundary_type_from:  source boundary (SRPREC, CITY_PRECINCT, UNKNOWN_LOCAL)
        boundary_type_to:    target boundary (MPREC)
        canonical_index:     optional set of known canonical IDs for validation

    Returns:
        CrosswalkResolutionResult — status EXACT_MATCH, CROSSWALK_MATCH,
        AMBIGUOUS, or NO_MATCH. Never BLOCKED_CROSS_JURISDICTION from this function
        (that is the caller's responsibility).
    """
    from engine.precinct_ids.id_normalizer import build_scoped_key

    raw = str(raw_id).strip()
    crosswalk_files = _find_crosswalk_files(state, county)
    candidates: list[CrosswalkMatch] = []

    for xwalk_path in crosswalk_files:
        if xwalk_path.suffix == ".csv":
            rows = _load_csv_crosswalk(xwalk_path)
        else:
            rows = _load_json_crosswalk(xwalk_path)

        for row in rows:
            # Try to match raw_id against any column value
            for col_val in row.values():
                if str(col_val).strip() == raw:
                    # Found a match — try to extract target ID
                    target_id = None
                    for candidate_col in ["mprec", "canonical_id", "srprec", "target_id"]:
                        if candidate_col in row and row[candidate_col]:
                            target_id = str(row[candidate_col]).strip()
                            break

                    if target_id:
                        key = build_scoped_key(state, county, boundary_type_to, target_id)
                        candidates.append(CrosswalkMatch(
                            raw_id=raw,
                            resolved_id=target_id,
                            scoped_key=key,
                            source_file=str(xwalk_path),
                            boundary_from=boundary_type_from,
                            boundary_to=boundary_type_to,
                            confidence=0.95,
                            method="crosswalk_file",
                        ))

    # Validate candidates against canonical index
    if canonical_index:
        candidates = [c for c in candidates if c.resolved_id in canonical_index]

    if len(candidates) == 0:
        return CrosswalkResolutionResult(
            raw_id=raw, state=state, county=county,
            boundary_type_from=boundary_type_from, boundary_type_to=boundary_type_to,
            status="NO_MATCH", confidence=0.0, resolved_key=None,
            candidates=[], reason=f"No crosswalk match found for '{raw}' in {state}|{county}",
        )

    if len(candidates) == 1:
        c = candidates[0]
        return CrosswalkResolutionResult(
            raw_id=raw, state=state, county=county,
            boundary_type_from=boundary_type_from, boundary_type_to=boundary_type_to,
            status="CROSSWALK_MATCH", confidence=c.confidence, resolved_key=c.scoped_key,
            candidates=candidates,
            reason=f"Crosswalk match via {Path(c.source_file).name}",
        )

    # Multiple candidates — ambiguous
    unique_resolved = {c.resolved_id for c in candidates}
    if len(unique_resolved) == 1:
        # All point to same ID — safe
        c = candidates[0]
        return CrosswalkResolutionResult(
            raw_id=raw, state=state, county=county,
            boundary_type_from=boundary_type_from, boundary_type_to=boundary_type_to,
            status="CROSSWALK_MATCH", confidence=0.95, resolved_key=c.scoped_key,
            candidates=candidates,
            reason=f"Consistent crosswalk match from {len(candidates)} sources",
        )

    return CrosswalkResolutionResult(
        raw_id=raw, state=state, county=county,
        boundary_type_from=boundary_type_from, boundary_type_to=boundary_type_to,
        status="AMBIGUOUS", confidence=0.20, resolved_key=None,
        candidates=candidates,
        reason=f"Ambiguous crosswalk: {len(unique_resolved)} different target IDs for '{raw}'",
    )
