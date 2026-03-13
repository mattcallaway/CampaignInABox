# engine/precinct_ids/__init__.py — Prompt 25A.4
"""
Jurisdiction-Scoped Precinct ID Normalization Engine

Public API:
  from engine.precinct_ids import detect_schema, normalize_id, join_single, join_batch
"""
from engine.precinct_ids.id_schema_detector import (
    detect_schema_for_value,
    detect_column_schema,
    SchemaDetectionResult,
    RowSchemaResult,
)
from engine.precinct_ids.id_normalizer import (
    normalize_id,
    normalize_column,
    build_scoped_key,
    NormalizationResult,
)
from engine.precinct_ids.id_crosswalk_resolver import (
    resolve_via_crosswalk,
    CrosswalkResolutionResult,
)
from engine.precinct_ids.safe_join_engine import (
    join_single,
    join_batch,
    JoinResult,
    JoinBatchResult,
)

__all__ = [
    "detect_schema_for_value", "detect_column_schema",
    "SchemaDetectionResult", "RowSchemaResult",
    "normalize_id", "normalize_column", "build_scoped_key", "NormalizationResult",
    "resolve_via_crosswalk", "CrosswalkResolutionResult",
    "join_single", "join_batch", "JoinResult", "JoinBatchResult",
]
