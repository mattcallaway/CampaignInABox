# engine/file_fingerprinting/__init__.py — Prompt 25A.3
"""
Election File Fingerprinting Engine

Public API:
  from engine.file_fingerprinting import classify, classify_batch, generate_fingerprint_report
"""
from engine.file_fingerprinting.fingerprint_engine import (
    classify,
    classify_batch,
    generate_fingerprint_report,
)
from engine.file_fingerprinting.fingerprint_classifier import ClassificationResult
from engine.file_fingerprinting.header_parser import ParsedHeader, parse_spreadsheet_headers

__all__ = [
    "classify",
    "classify_batch",
    "generate_fingerprint_report",
    "ClassificationResult",
    "ParsedHeader",
    "parse_spreadsheet_headers",
]
