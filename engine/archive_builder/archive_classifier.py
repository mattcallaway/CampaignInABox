"""
engine/archive_builder/archive_classifier.py — Prompt 25

File validation and classification layer.

Responsibilities:
  1. Run fingerprint engine on each candidate file
  2. Run precinct schema detection (if precinct column found)
  3. Validate file structure (shape, vote ranges, duplicate precincts)
  4. Assign ClassifiedFile result with archive_ready=True/False

Confidence thresholds:
  ≥ 0.85 fingerprint → auto-processable (still requires join validation)
  < 0.85 fingerprint → user review required
  archive_ready requires ALL: fingerprint, validation, join ≥ thresholds

Validation flags (must be clean to ingest):
  - negative_vote_counts
  - duplicate_precinct_rows
  - invalid_turnout (>100%)
  - no_numeric_columns
  - empty_file
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Confidence thresholds
FINGERPRINT_AUTO_THRESHOLD  = 0.85  # auto-process without user review
ARCHIVE_READY_MIN_CONFIDENCE = 0.80  # minimum overall confidence to auto-ingest

BLOCKING_STATUSES = {"AMBIGUOUS", "NO_MATCH", "BLOCKED_CROSS_JURISDICTION"}


@dataclass
class ValidationResult:
    """File structure validation outcome."""
    valid: bool
    row_count: int
    col_count: int
    has_numeric_cols: bool
    has_precinct_col: bool
    negative_vote_counts: bool
    duplicate_precinct_rows: bool
    invalid_turnout: bool
    warnings: list[str]
    errors: list[str]


@dataclass
class ClassifiedFile:
    """Full classification and validation result for a candidate file."""
    # Source info
    local_path: str
    source_url: str
    source_id: str
    state: str
    county: str
    year: Optional[int]
    election_type: Optional[str]

    # Fingerprint
    fingerprint_type: str         # statement_of_vote | precinct_results | ...
    fingerprint_display: str
    fingerprint_confidence: float
    fingerprint_requires_review: bool    # True if conf < 0.85

    # Precinct
    precinct_schema: Optional[str]       # mprec | short_precinct | ...
    precinct_boundary_type: str
    schema_confidence: float
    schema_is_mixed: bool

    # Validation
    validation: ValidationResult

    # Join
    join_archive_ready_fraction: float   # fraction of rows that safely joined
    join_statuses: dict                  # {status: count}

    # Overall
    overall_confidence: float
    archive_ready: bool
    requires_user_review: bool
    review_reasons: list[str]

    # Provenance
    classified_at: str


def _validate_file(path: Path, state: str, county: str) -> ValidationResult:
    """
    Validate file structure using pandas.
    Checks: shape, numeric columns, precinct detection, vote sanity.
    """
    warnings: list[str] = []
    errors: list[str] = []

    try:
        import pandas as pd
        import numpy as np

        ext = path.suffix.lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(path, nrows=2000)
        elif ext in (".csv", ".tsv"):
            sep = "\t" if ext == ".tsv" else ","
            df = pd.read_csv(path, sep=sep, nrows=2000, low_memory=False)
        else:
            return ValidationResult(
                valid=False, row_count=0, col_count=0,
                has_numeric_cols=False, has_precinct_col=False,
                negative_vote_counts=False, duplicate_precinct_rows=False,
                invalid_turnout=False,
                warnings=[], errors=[f"Unsupported format: {ext}"],
            )

        if df.empty:
            return ValidationResult(
                valid=False, row_count=0, col_count=len(df.columns),
                has_numeric_cols=False, has_precinct_col=False,
                negative_vote_counts=False, duplicate_precinct_rows=False,
                invalid_turnout=False,
                warnings=[], errors=["File is empty"],
            )

        rows, cols = df.shape
        cols_lower = [str(c).lower().strip() for c in df.columns]

        # Detect precinct column
        precinct_keywords = ["precinct", "prec", "srprec", "mprec", "district"]
        has_precinct = any(any(pk in col for pk in precinct_keywords) for col in cols_lower)

        # Detect numeric columns
        num_cols = df.select_dtypes(include="number").columns.tolist()
        has_numeric = len(num_cols) > 0

        # Check for negative vote counts in numeric columns
        neg_votes = False
        if has_numeric:
            for nc in num_cols:
                col_vals = pd.to_numeric(df[nc], errors="coerce").dropna()
                if (col_vals < 0).any():
                    neg_votes = True
                    warnings.append(f"Negative values in column '{nc}'")

        # Check duplicate precinct rows
        dup_precincts = False
        if has_precinct:
            prec_cols = [c for c in df.columns if any(pk in str(c).lower() for pk in precinct_keywords)]
            if prec_cols:
                dupes = df[prec_cols[0]].duplicated().sum()
                if dupes > 0:
                    dup_precincts = True
                    warnings.append(f"{dupes} duplicate precinct rows")

        # Check invalid turnout (column named 'turnout' > 1.0 if fractional, or > 100 if pct)
        bad_turnout = False
        for col in df.columns:
            if "turnout" in str(col).lower():
                vals = pd.to_numeric(df[col], errors="coerce").dropna()
                if not vals.empty:
                    # Could be 0–1 or 0–100
                    if vals.max() > 100.0:
                        bad_turnout = True
                        warnings.append(f"Turnout column '{col}' has values > 100")
                    elif vals.max() > 1.0:
                        pass  # percentage 0–100 — okay
                    elif (vals > 1.0).any():
                        bad_turnout = True
                        warnings.append(f"Turnout column '{col}' has fractional values > 1.0")

        if not has_numeric:
            errors.append("No numeric columns detected — cannot be an election results file")

        valid = has_numeric and not errors
        return ValidationResult(
            valid=valid, row_count=rows, col_count=cols,
            has_numeric_cols=has_numeric, has_precinct_col=has_precinct,
            negative_vote_counts=neg_votes, duplicate_precinct_rows=dup_precincts,
            invalid_turnout=bad_turnout, warnings=warnings, errors=errors,
        )

    except Exception as e:
        return ValidationResult(
            valid=False, row_count=0, col_count=0,
            has_numeric_cols=False, has_precinct_col=False,
            negative_vote_counts=False, duplicate_precinct_rows=False,
            invalid_turnout=False,
            warnings=[], errors=[f"Parse error: {e}"],
        )


def classify_candidate_file(
    candidate,       # CandidateFile from file_discovery
    state: str,
    county: str,
    boundary_type: str = "MPREC",
    canonical_index: Optional[set] = None,
) -> ClassifiedFile:
    """
    Fully classify a candidate election file:
      1. Fingerprint → file type and confidence
      2. Schema detection → precinct ID format
      3. File validation → structure checks
      4. Safe join → fraction of rows that normalize safely
      5. Overall confidence and archive_ready decision

    Args:
        candidate:       CandidateFile from file_discovery
        state:           state code (CA)
        county:          county name (Sonoma)
        boundary_type:   expected MPREC | SRPREC
        canonical_index: optional set of known canonical precinct IDs

    Returns:
        ClassifiedFile
    """
    from datetime import datetime
    from engine.file_fingerprinting.fingerprint_engine import classify as fp_classify
    from engine.precinct_ids.id_schema_detector import detect_column_schema
    from engine.precinct_ids.safe_join_engine import join_batch

    local_path = candidate.local_path
    source_url = candidate.url

    if not local_path or not Path(local_path).exists():
        # Cannot classify without a local file
        review_reasons = ["File not staged locally — cannot fingerprint"]
        return ClassifiedFile(
            local_path=local_path or "", source_url=source_url,
            source_id=candidate.source_id, state=state, county=county,
            year=candidate.year, election_type=candidate.election_type,
            fingerprint_type="file_not_found", fingerprint_display="Not Found",
            fingerprint_confidence=0.0, fingerprint_requires_review=True,
            precinct_schema=None, precinct_boundary_type=boundary_type,
            schema_confidence=0.0, schema_is_mixed=False,
            validation=ValidationResult(
                valid=False, row_count=0, col_count=0,
                has_numeric_cols=False, has_precinct_col=False,
                negative_vote_counts=False, duplicate_precinct_rows=False,
                invalid_turnout=False, warnings=[], errors=["File not found"],
            ),
            join_archive_ready_fraction=0.0, join_statuses={},
            overall_confidence=0.0, archive_ready=False,
            requires_user_review=True, review_reasons=review_reasons,
            classified_at=datetime.now().isoformat(),
        )

    path = Path(local_path)
    review_reasons: list[str] = []

    # ── 1. Fingerprint ────────────────────────────────────────────────────────
    fp = fp_classify(path, source_url=source_url, use_cache=True)
    fp_requires_review = fp.confidence < FINGERPRINT_AUTO_THRESHOLD
    if fp_requires_review:
        review_reasons.append(
            f"Low fingerprint confidence: {fp.confidence:.2f} < {FINGERPRINT_AUTO_THRESHOLD}"
        )
    if fp.file_type in ("unknown", "parse_error", "file_not_found"):
        review_reasons.append(f"Unclassified file type: {fp.file_type}")

    # ── 2. File validation ────────────────────────────────────────────────────
    validation = _validate_file(path, state, county)
    if not validation.valid:
        review_reasons.extend(validation.errors)
    if validation.negative_vote_counts:
        review_reasons.append("Negative vote counts detected")
    if validation.invalid_turnout:
        review_reasons.append("Invalid turnout values (>100%)")

    # ── 3. Precinct schema detection ─────────────────────────────────────────
    precinct_schema: Optional[str] = None
    schema_confidence = 0.0
    schema_is_mixed = False
    precincts_for_join: list[str] = []

    if validation.has_precinct_col and path.exists():
        try:
            import pandas as pd
            ext = path.suffix.lower()
            if ext in (".xlsx", ".xls"):
                df = pd.read_excel(path, nrows=500)
            else:
                df = pd.read_csv(path, nrows=500, low_memory=False)

            prec_cols = [c for c in df.columns
                         if any(pk in str(c).lower()
                                for pk in ["precinct", "prec", "srprec", "mprec"])]
            if prec_cols:
                series = df[prec_cols[0]].dropna().astype(str).tolist()
                schema_result = detect_column_schema(series, prec_cols[0])
                precinct_schema = schema_result.dominant_schema
                schema_confidence = schema_result.schema_confidence
                schema_is_mixed = schema_result.is_mixed
                precincts_for_join = series[:200]

                if schema_is_mixed:
                    review_reasons.append("Mixed precinct ID schema detected")
        except Exception as e:
            log.warning(f"[CLASSIFIER] Schema detection failed for {path.name}: {e}")
            review_reasons.append(f"Schema detection error: {e}")

    # ── 4. Safe join ─────────────────────────────────────────────────────────
    join_archive_ready_fraction = 0.0
    join_statuses: dict = {}

    if precincts_for_join and not schema_is_mixed:
        try:
            batch = join_batch(
                precincts_for_join, state, county, boundary_type,
                canonical_index=canonical_index,
                run_id=None,   # don't write review queue files during classification
            )
            join_statuses = {
                "EXACT_MATCH":                batch.exact_matches,
                "CROSSWALK_MATCH":            batch.crosswalk_matches,
                "NORMALIZED_MATCH":           batch.normalized_matches,
                "AMBIGUOUS":                  batch.ambiguous,
                "NO_MATCH":                   batch.no_matches,
                "BLOCKED_CROSS_JURISDICTION": batch.blocked_cross_jurisdiction,
            }
            join_archive_ready_fraction = batch.archive_ready_fraction
            if join_archive_ready_fraction < 0.50:
                review_reasons.append(
                    f"Low precinct join rate: {join_archive_ready_fraction:.1%} archive-ready"
                )
        except Exception as e:
            log.warning(f"[CLASSIFIER] Join engine failed for {path.name}: {e}")
            review_reasons.append(f"Join engine error: {e}")
    elif not validation.has_precinct_col:
        # Non-precinct file (ballot measure summary, etc.) — join not applicable
        join_archive_ready_fraction = 1.0

    # ── 5. Overall confidence ─────────────────────────────────────────────────
    components = [
        fp.confidence * 0.40,                  # file type confidence (40%)
        (1.0 if validation.valid else 0.0) * 0.30,  # structure validity (30%)
        join_archive_ready_fraction * 0.20,    # join success (20%)
        schema_confidence * 0.10,              # precinct schema (10%)
    ]
    overall_confidence = round(sum(components), 4)

    archive_ready = (
        overall_confidence >= ARCHIVE_READY_MIN_CONFIDENCE
        and validation.valid
        and not schema_is_mixed
        and fp.file_type not in ("unknown", "parse_error", "file_not_found")
        and len(review_reasons) == 0
    )

    requires_review = not archive_ready or len(review_reasons) > 0

    log.info(
        f"[CLASSIFIER] {path.name}: type={fp.file_type} "
        f"fp_conf={fp.confidence:.2f} overall={overall_confidence:.2f} "
        f"archive_ready={archive_ready}"
    )

    return ClassifiedFile(
        local_path=local_path, source_url=source_url,
        source_id=candidate.source_id, state=state, county=county,
        year=candidate.year, election_type=candidate.election_type,
        fingerprint_type=fp.file_type, fingerprint_display=fp.display_name,
        fingerprint_confidence=fp.confidence, fingerprint_requires_review=fp_requires_review,
        precinct_schema=precinct_schema, precinct_boundary_type=boundary_type,
        schema_confidence=schema_confidence, schema_is_mixed=schema_is_mixed,
        validation=validation,
        join_archive_ready_fraction=join_archive_ready_fraction,
        join_statuses=join_statuses,
        overall_confidence=overall_confidence,
        archive_ready=archive_ready,
        requires_user_review=requires_review,
        review_reasons=review_reasons,
        classified_at=datetime.now().isoformat(),
    )
