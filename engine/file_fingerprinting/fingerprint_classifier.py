"""
engine/file_fingerprinting/fingerprint_classifier.py — Prompt 25A.3

Election file type classifier.

Algorithm:
  1. Load fingerprint_rules.yaml
  2. Receive a ParsedHeader from header_parser
  3. For each rule, compute match score:
       required_header hits  → score += confidence_weight * (hits / required_count) * 0.60
       optional_header hits  → score += 0.10 per hit (max 0.20)
       numeric_pattern hits  → score += 0.10
       precinct ID detected  → score += 0.10 if rule expects precinct_level
  4. Return ClassificationResult with best match
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RULES_PATH = BASE_DIR / "engine" / "file_fingerprinting" / "fingerprint_rules.yaml"

_rules_cache: Optional[dict] = None


def _load_rules() -> dict:
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache
    if not RULES_PATH.exists():
        log.warning("[CLASSIFIER] fingerprint_rules.yaml not found")
        _rules_cache = {}
        return _rules_cache
    try:
        _rules_cache = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:
        log.error(f"[CLASSIFIER] Failed to load rules: {e}")
        _rules_cache = {}
    return _rules_cache


@dataclass
class ClassificationResult:
    """Result of fingerprint classification."""
    file_path: str
    file_hash: str
    file_type: str                   # rule key (e.g. 'statement_of_vote') or 'unknown'
    display_name: str                # human label e.g. 'Statement of Vote'
    confidence: float                # 0.0 – 1.0
    matching_headers: list[str]      # normalized headers that matched
    missing_required: list[str]      # required headers not found
    optional_hits: list[str]         # optional headers that matched
    precinct_format: Optional[str]   # e.g. '0400***'
    precinct_level: bool
    contest_level: bool
    sheet_name: Optional[str]
    row_count: int
    col_count: int
    all_scores: dict[str, float] = field(default_factory=dict)  # score per rule for debugging


def classify_file(parsed_header) -> ClassificationResult:
    """
    Classify an election file based on its parsed header.

    Args:
        parsed_header: ParsedHeader from header_parser.parse_spreadsheet_headers()

    Returns:
        ClassificationResult
    """
    from engine.file_fingerprinting.header_parser import ParsedHeader

    ph: ParsedHeader = parsed_header
    norm_headers = set(ph.normalized_headers)

    # If parse failed, return unknown immediately
    if ph.parse_error or not ph.normalized_headers:
        return ClassificationResult(
            file_path=ph.file_path, file_hash=ph.file_hash,
            file_type="parse_error", display_name="Parse Error",
            confidence=0.0, matching_headers=[], missing_required=[],
            optional_hits=[], precinct_format=ph.precinct_format,
            precinct_level=False, contest_level=False,
            sheet_name=ph.sheet_name, row_count=ph.row_count, col_count=ph.col_count,
            all_scores={},
        )

    rules_dict = _load_rules()
    file_types = rules_dict.get("file_types", {})

    best_type = "unknown"
    best_display = "Unknown File Type"
    best_score = 0.0
    best_matching: list[str] = []
    best_missing: list[str] = []
    best_optional: list[str] = []
    all_scores: dict[str, float] = {}

    for rule_key, rule in file_types.items():
        required = [r.lower().strip() for r in rule.get("required_headers", [])]
        optional = [o.lower().strip() for o in rule.get("optional_headers", [])]
        min_match = rule.get("min_required_match", len(required))
        weight    = float(rule.get("confidence_weight", 0.80))
        rule_precinct = rule.get("precinct_level", False)

        # Score required headers
        req_hits     = [r for r in required if _fuzzy_header_match(r, norm_headers)]
        req_missing  = [r for r in required if not _fuzzy_header_match(r, norm_headers)]
        req_fraction = len(req_hits) / max(len(required), 1)

        # Only consider if we meet the minimum match threshold
        if len(req_hits) < min_match:
            all_scores[rule_key] = 0.0
            continue

        score = weight * req_fraction * 0.60

        # Optional headers
        opt_hits = [o for o in optional if _fuzzy_header_match(o, norm_headers)]
        opt_bonus = min(0.20, len(opt_hits) * 0.05)
        score += opt_bonus

        # Numeric pattern bonus
        if ph.numeric_columns and rule.get("numeric_patterns"):
            score += 0.10

        # Precinct column bonus
        if ph.precinct_column and rule_precinct:
            score += 0.10
        elif not ph.precinct_column and not rule_precinct:
            score += 0.05  # small bonus for correct absence

        score = round(min(score, 0.99), 4)
        all_scores[rule_key] = score

        if score > best_score:
            best_score = score
            best_type = rule_key
            best_display = rule.get("display_name", rule_key)
            best_matching = req_hits
            best_missing = req_missing
            best_optional = opt_hits

    return ClassificationResult(
        file_path=ph.file_path,
        file_hash=ph.file_hash,
        file_type=best_type,
        display_name=best_display,
        confidence=best_score,
        matching_headers=best_matching,
        missing_required=best_missing,
        optional_hits=best_optional,
        precinct_format=ph.precinct_format,
        precinct_level=file_types.get(best_type, {}).get("precinct_level", False),
        contest_level=file_types.get(best_type, {}).get("contest_level", False),
        sheet_name=ph.sheet_name,
        row_count=ph.row_count,
        col_count=ph.col_count,
        all_scores=all_scores,
    )


def _fuzzy_header_match(pattern: str, normalized_headers: set[str]) -> bool:
    """
    Match a rule pattern against the set of normalized file headers.

    Matching strategies (in order):
    1. Exact match after normalization
    2. Pattern is a substring of any header
    3. All words in pattern appear in any single header
    """
    pattern = pattern.lower().strip()
    pattern_words = set(pattern.split())

    for h in normalized_headers:
        # Exact match
        if pattern == h:
            return True
        # Substring match
        if pattern in h:
            return True
        # All words in header
        header_words = set(h.split())
        if pattern_words and pattern_words.issubset(header_words):
            return True

    return False
