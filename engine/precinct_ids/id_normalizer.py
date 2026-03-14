"""
engine/precinct_ids/id_normalizer.py — Prompt 25A.4

Jurisdiction-scoped precinct ID normalizer.

Inputs:
  - raw_id:          the raw precinct string
  - schema_key:      detected schema from id_schema_detector
  - state:           2-letter state code (e.g. 'CA')
  - county:          county name (e.g. 'Sonoma')
  - boundary_type:   MPREC | SRPREC | CITY_PRECINCT | UNKNOWN_LOCAL
  - expected_ids:    optional set of known valid canonical IDs in this jurisdiction
                     (for validation after normalization)

Output: NormalizationResult dataclass

Safety rules:
  - Normalization is jurisdiction-scoped. The canonical scoped key includes
    state, county, and boundary type — raw IDs are never globally valid.
  - short_precinct IDs require crosswalk; they fail closed here.
  - SRPREC cannot become MPREC without explicit crosswalk.
  - Mixed schemas always fail closed.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

SCOPED_KEY_SEP = "|"


@dataclass
class NormalizationResult:
    """Result of normalizing a single precinct ID."""
    raw_id:              str
    normalized_id:       Optional[str]    # None if normalization failed
    boundary_type:       str
    scoped_key:          Optional[str]    # None if failed
    normalization_method: str
    confidence:          float
    state:               str
    county:              str
    error:               Optional[str]    # set if normalization failed
    validated_against_index: bool         # True if normalized_id was found in expected_ids


def build_scoped_key(state: str, county: str, boundary_type: str, canonical_id: str) -> str:
    """
    Build the canonical jurisdiction-scoped precinct key.
    Format: <STATE>|<COUNTY>|<BOUNDARY_TYPE>|<CANONICAL_ID>
    Example: CA|Sonoma|MPREC|0400127
    """
    return SCOPED_KEY_SEP.join([
        state.upper().strip(),
        county.strip().title(),
        boundary_type.upper().strip(),
        canonical_id.strip(),
    ])


def _strip_prefix(raw: str) -> str:
    """Strip common prefixes: PCT, PRECINCT, SRP, SRPREC, SR, city names."""
    v = raw.strip()
    prefixes = [
        r"^(precinct|pct\.?|pct)\s*[-]?\s*",
        r"^(srprec|srp|sr)\s*[-]?\s*",
        r"^(santa\s+rosa|petaluma|rohnert\s+park|healdsburg|sonoma|windsor|cloverdale)\s*[-]?\s*",
    ]
    for pat in prefixes:
        m = re.match(pat, v, re.IGNORECASE)
        if m:
            return v[m.end():].strip()
    return v


def normalize_id(
    raw_id: str,
    schema_key: str,
    state: str,
    county: str,
    boundary_type: str,
    expected_ids: Optional[set[str]] = None,
) -> NormalizationResult:
    """
    Normalize a single precinct ID to canonical form within its jurisdiction.

    Args:
        raw_id:        raw precinct ID string
        schema_key:    schema from id_schema_detector (mprec, mprec_unpadded, etc.)
        state:         state code (CA)
        county:        county name (Sonoma)
        boundary_type: expected boundary type
        expected_ids:  optional set of known canonical IDs for validation

    Returns:
        NormalizationResult — always returns a result, never raises.
        On failure, normalized_id and scoped_key are None and error is set.
    """
    raw = str(raw_id).strip()

    def _fail(method: str, reason: str, conf: float = 0.0) -> NormalizationResult:
        return NormalizationResult(
            raw_id=raw, normalized_id=None, boundary_type=boundary_type,
            scoped_key=None, normalization_method=method, confidence=conf,
            state=state, county=county, error=reason, validated_against_index=False,
        )

    # ── Schema-specific normalization ──────────────────────────────────────────

    if schema_key == "mprec":
        # Already canonical 7-digit MPREC
        normalized = raw.zfill(7)
        conf = 0.99
        method = "preserve_leading_zero"

    elif schema_key == "mprec_unpadded":
        # 6-digit → pad to 7 digits
        normalized = raw.zfill(7)
        conf = 0.90
        method = "left_pad_zero_to_7"

    elif schema_key in ("short_precinct", "prefixed_precinct", "srprec",
                         "city_precinct", "alphanumeric_precinct"):
        # These all require crosswalk — fail closed here
        stripped = _strip_prefix(raw)
        return _fail(
            method=f"requires_crosswalk ({schema_key})",
            reason=(
                f"Schema '{schema_key}' requires an explicit crosswalk to resolve "
                f"within {state}|{county}|{boundary_type}. "
                f"Stripped form: '{stripped}'. Sent to ambiguity review queue."
            ),
            conf=0.50 if schema_key == "short_precinct" else 0.40,
        )

    else:
        # Unknown schema
        return _fail(
            method="unknown_schema",
            reason=f"Unknown schema '{schema_key}' — cannot normalize raw ID '{raw}'. Review required.",
            conf=0.0,
        )

    # ── Validate against known index (if provided) ─────────────────────────────
    validated = False
    if expected_ids:
        if normalized not in expected_ids:
            return _fail(
                method=method,
                reason=(
                    f"Normalized ID '{normalized}' not found in {state}|{county} "
                    f"jurisdiction index. Possible wrong-jurisdiction ID or mapping error."
                ),
                conf=0.30,
            )
        validated = True
        conf = min(conf, 0.99)  # validated IDs stay at schema confidence

    # ── Build scoped key ───────────────────────────────────────────────────────
    boundary = boundary_type if boundary_type != "UNKNOWN_LOCAL" else "MPREC"
    key = build_scoped_key(state, county, boundary, normalized)

    return NormalizationResult(
        raw_id=raw,
        normalized_id=normalized,
        boundary_type=boundary,
        scoped_key=key,
        normalization_method=method,
        confidence=conf,
        state=state,
        county=county,
        error=None,
        validated_against_index=validated,
    )


def normalize_column(
    raw_ids: list[str],
    schema_key: str,
    state: str,
    county: str,
    boundary_type: str,
    expected_ids: Optional[set[str]] = None,
) -> list[NormalizationResult]:
    """Normalize a full column of precinct IDs."""
    return [
        normalize_id(r, schema_key, state, county, boundary_type, expected_ids)
        for r in raw_ids
    ]
