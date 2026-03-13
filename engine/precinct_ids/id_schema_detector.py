"""
engine/precinct_ids/id_schema_detector.py — Prompt 25A.4

Precinct ID schema detector.

Inspects a column of precinct ID values and infers the likely schema family
from id_rules.yaml. Outputs a SchemaDetectionResult with:
  - detected schema key
  - boundary type
  - confidence
  - warnings for mixed-schema columns
  - per-row schema assignments

Safety principle:
  Mixed-schema columns cannot be auto-normalized and are marked as
  MIXED_SCHEMA. Cross-jurisdiction matching is never attempted here.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
RULES_PATH = BASE_DIR / "engine" / "precinct_ids" / "id_rules.yaml"

_rules_cache: Optional[dict] = None


def _load_rules() -> dict:
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache
    try:
        _rules_cache = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:
        log.error(f"[SCHEMA_DETECTOR] Failed to load id_rules.yaml: {e}")
        _rules_cache = {}
    return _rules_cache


@dataclass
class RowSchemaResult:
    """Schema classification for a single precinct ID value."""
    raw_value:   str
    schema_key:  str      # rule key or 'unknown'
    boundary_type: str
    confidence:  float
    matched_pattern: Optional[str]


@dataclass
class SchemaDetectionResult:
    """Result of schema detection for an entire column of precinct IDs."""
    column_name: str
    sample_size: int
    dominant_schema: str         # most common schema key
    dominant_boundary_type: str
    schema_confidence: float     # fraction of rows matching dominant schema
    is_mixed: bool               # True if >1 schema families detected
    schema_distribution: dict[str, int]   # {schema_key: count}
    warnings: list[str]
    row_results: list[RowSchemaResult]
    requires_crosswalk: bool
    cross_jurisdiction_safe: bool


def detect_schema_for_value(raw_value: str) -> RowSchemaResult:
    """
    Detect the schema for a single precinct ID value.

    Returns RowSchemaResult with 'unknown' if no pattern matches.
    Never attempts cross-jurisdiction resolution.
    """
    rules = _load_rules()
    schemas = rules.get("schemas", {})
    v = str(raw_value).strip()
    v_lower = v.lower()

    best_key = "unknown"
    best_boundary = "UNKNOWN"
    best_conf = 0.0
    best_pattern = None

    for schema_key, schema in schemas.items():
        patterns = schema.get("regex_patterns", [])
        for pat in patterns:
            try:
                if re.match(pat, v_lower, re.IGNORECASE):
                    base_conf = float(schema.get("confidence_base", 0.50))
                    if base_conf > best_conf:
                        best_conf = base_conf
                        best_key = schema_key
                        best_boundary = schema.get("boundary_type", "UNKNOWN")
                        best_pattern = pat
            except re.error:
                pass

    return RowSchemaResult(
        raw_value=v,
        schema_key=best_key,
        boundary_type=best_boundary,
        confidence=best_conf,
        matched_pattern=best_pattern,
    )


def detect_column_schema(
    values: list[str],
    column_name: str = "precinct",
    sample_limit: int = 200,
) -> SchemaDetectionResult:
    """
    Detect the schema for a column of precinct ID values.

    Args:
        values:       list of raw precinct ID strings
        column_name:  name of the source column (for reporting)
        sample_limit: max rows to inspect (first N)

    Returns:
        SchemaDetectionResult describing the column's schema profile
    """
    rules = _load_rules()
    schemas_rules = rules.get("schemas", {})

    sample = [str(v).strip() for v in values[:sample_limit] if v and str(v).strip()]
    if not sample:
        return SchemaDetectionResult(
            column_name=column_name, sample_size=0,
            dominant_schema="unknown", dominant_boundary_type="UNKNOWN",
            schema_confidence=0.0, is_mixed=False,
            schema_distribution={}, warnings=["No non-empty values in column"],
            row_results=[], requires_crosswalk=True, cross_jurisdiction_safe=False,
        )

    row_results: list[RowSchemaResult] = [detect_schema_for_value(v) for v in sample]

    # Count schema distribution
    distribution: dict[str, int] = {}
    for rr in row_results:
        distribution[rr.schema_key] = distribution.get(rr.schema_key, 0) + 1

    n = len(row_results)
    dominant_schema = max(distribution, key=distribution.get)  # type: ignore[arg-type]
    dominant_count  = distribution[dominant_schema]
    schema_confidence = dominant_count / n

    # Determine if mixed (more than one schema family with >5% share)
    non_trivial_schemas = {k for k, c in distribution.items() if c / n >= 0.05}
    is_mixed = len(non_trivial_schemas) > 1

    warnings: list[str] = []
    if is_mixed:
        schema_names = ", ".join(non_trivial_schemas)
        warnings.append(
            f"MIXED_SCHEMA detected in column '{column_name}': "
            f"schemas present = [{schema_names}]. Cannot auto-normalize."
        )
    if dominant_schema == "unknown" or schema_confidence < 0.60:
        warnings.append(
            f"LOW_CONFIDENCE schema detection for '{column_name}': "
            f"dominant={dominant_schema} conf={schema_confidence:.2f}. "
            f"Manual review required."
        )

    schema_info = schemas_rules.get(dominant_schema, {})
    requires_crosswalk = schema_info.get("requires_crosswalk", True) or is_mixed
    cross_jurisdiction_safe = schema_info.get("cross_jurisdiction_safe", False) and not is_mixed

    dominant_boundary = (
        row_results[0].boundary_type if row_results else "UNKNOWN"
    )
    # Use mode boundary type from dominant schema rows
    boundary_counts: dict[str, int] = {}
    for rr in row_results:
        if rr.schema_key == dominant_schema:
            boundary_counts[rr.boundary_type] = boundary_counts.get(rr.boundary_type, 0) + 1
    if boundary_counts:
        dominant_boundary = max(boundary_counts, key=boundary_counts.get)  # type: ignore[arg-type]

    return SchemaDetectionResult(
        column_name=column_name,
        sample_size=n,
        dominant_schema=dominant_schema,
        dominant_boundary_type=dominant_boundary,
        schema_confidence=round(schema_confidence, 4),
        is_mixed=is_mixed,
        schema_distribution=distribution,
        warnings=warnings,
        row_results=row_results,
        requires_crosswalk=requires_crosswalk,
        cross_jurisdiction_safe=cross_jurisdiction_safe,
    )
