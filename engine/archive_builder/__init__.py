# engine/archive_builder/__init__.py — Prompt 25
"""
Historical Election Archive Builder

Public API:
  from engine.archive_builder import run_archive_build, ArchiveBuildResult
  from engine.archive_builder import scan_all_sources
  from engine.archive_builder import classify_candidate_file
"""
from engine.archive_builder.archive_builder import run_archive_build, ArchiveBuildResult
from engine.archive_builder.source_scanner import scan_all_sources, PageScanResult
from engine.archive_builder.file_discovery import discover_files_from_page, CandidateFile
from engine.archive_builder.archive_classifier import classify_candidate_file, ClassifiedFile
from engine.archive_builder.archive_ingestor import ingest_classified_file
from engine.archive_builder.archive_registry import (
    register_election, list_elections, get_election, registry_summary
)

__all__ = [
    "run_archive_build", "ArchiveBuildResult",
    "scan_all_sources", "PageScanResult",
    "discover_files_from_page", "CandidateFile",
    "classify_candidate_file", "ClassifiedFile",
    "ingest_classified_file",
    "register_election", "list_elections", "get_election", "registry_summary",
]
