"""
engine/archive_builder/archive_builder.py — Prompt 25

Main orchestrator for the Historical Election Archive Builder.

Pipeline:
  1. Scan source registry → discover election page URLs (source_scanner)
  2. For each election page → discover candidate files (file_discovery)
  3. For each candidate file:
     a. Fingerprint (archive_classifier via fingerprint_engine)
     b. Schema detection
     c. File validation
     d. Safe join
     e. Classify → ClassifiedFile
  4. Archive-ready files → archive_ingestor
  5. Non-ready files → review queue CSV
  6. Update archive_registry.yaml
  7. Write build reports

Public API:
  run_archive_build(state, county, online, download, run_id) → ArchiveBuildResult
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR  = BASE_DIR / "reports" / "archive_builder"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

ARCHIVE_CONFIDENCE_THRESHOLD = 0.80  # minimum to auto-ingest


@dataclass
class ArchiveBuildResult:
    """Overall result of a single archive build run."""
    run_id:           str
    state:            str
    county:           str
    sources_scanned:  int
    pages_found:      int
    candidates_found: int
    classified:       int
    ingested:         int
    review_queue:     int
    failed:           int
    archive_ready_count: int
    avg_overall_confidence: float
    build_report:     Optional[str]
    classification_report: Optional[str]
    errors:           list[str]


def _election_id_from_source(source: dict) -> str:
    year  = source.get("year", "unknown")
    etype = source.get("election_type", "general")
    return f"{year}_{etype}"


def run_archive_build(
    state:    str = "CA",
    county:   str = "Sonoma",
    online:   bool = False,
    download: bool = False,
    run_id:   Optional[str] = None,
    source_ids: Optional[list[str]] = None,
) -> ArchiveBuildResult:
    """
    Run the full archive build pipeline.

    Args:
        state:       state code (CA)
        county:      county name (Sonoma)
        online:      if True, attempt HTTP discovery
        download:    if True, download candidate files to staging
        run_id:      run identifier (auto-generated if None)
        source_ids:  limit to specific source registry IDs (None = all)

    Returns:
        ArchiveBuildResult with counts and report paths
    """
    from engine.archive_builder.source_scanner import scan_all_sources
    from engine.archive_builder.file_discovery import (
        discover_files_from_page, discover_from_local_staging
    )
    from engine.archive_builder.archive_classifier import classify_candidate_file
    from engine.archive_builder.archive_ingestor import ingest_classified_file
    from engine.archive_builder.archive_registry import register_election

    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d__%H%M")

    errors: list[str] = []

    # ── Step 1: Scan source registry ─────────────────────────────────────────
    log.info(f"[BUILDER] [{run_id}] Scanning sources: {state}/{county} online={online}")
    scan_results = scan_all_sources(
        state_filter=state,
        county_filter=county,
        online=online,
    )

    if source_ids:
        scan_results = [r for r in scan_results if r.source_id in source_ids]

    sources_scanned = len(scan_results)
    all_pages: list[tuple[dict, str]] = []  # (source_dict, page_url)

    # Build full source dict lookup from registry for later metadata access
    import yaml
    registry_path = BASE_DIR / "config" / "source_registry" / "contest_sources.yaml"
    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        source_map = {s["source_id"]: s for s in raw.get("sources", [])}
    except Exception:
        source_map = {}

    for scan in scan_results:
        src_dict = source_map.get(scan.source_id, {
            "source_id":   scan.source_id,
            "state":       scan.state,
            "county":      scan.county,
            "year":        scan.year,
            "election_type": scan.election_type,
        })
        for page_url in scan.discovered_urls:
            all_pages.append((src_dict, page_url))

    pages_found = len(all_pages)
    log.info(f"[BUILDER] [{run_id}] Found {pages_found} election pages from {sources_scanned} sources")

    # ── Step 2: Discover candidate files ──────────────────────────────────────
    all_candidates = []
    for src_dict, page_url in all_pages:
        eid = _election_id_from_source(src_dict)
        county_slug = county.lower().replace(" ", "_")
        staging_sub = f"{county_slug}/{eid}"

        if online and download:
            candidates = discover_files_from_page(
                page_url, src_dict, download=True, staging_subdir=staging_sub
            )
        else:
            # Offline: check if staging already has files
            candidates = discover_from_local_staging(src_dict, staging_sub)
            if not candidates and page_url:
                # No local staging — register as pending
                log.info(f"[BUILDER] No staged files for {eid} — add manually or run online")

        all_candidates.extend(candidates)

    candidates_found = len(all_candidates)
    log.info(f"[BUILDER] [{run_id}] {candidates_found} candidate files found")

    # ── Step 3: Classify each candidate file ──────────────────────────────────
    classified_files = []
    for cand in all_candidates:
        if not cand.local_path:
            continue     # not staged — skip
        try:
            cf = classify_candidate_file(
                cand,
                state=state,
                county=county,
                boundary_type="MPREC",
            )
            classified_files.append(cf)
        except Exception as e:
            errors.append(f"Classify error {cand.filename}: {e}")
            log.warning(f"[BUILDER] Classify failed {cand.filename}: {e}")

    classified = len(classified_files)

    # ── Step 4: Ingest archive-ready files ────────────────────────────────────
    ingested_count = 0
    review_count   = 0
    failed_count   = 0
    total_conf     = 0.0

    for cf in classified_files:
        total_conf += cf.overall_confidence
        try:
            result = ingest_classified_file(cf, run_id=run_id)
            if result["status"] == "INGESTED":
                ingested_count += 1
                # Register in archive registry
                register_election(
                    election_id       = _election_id_from_source({
                        "year": cf.year, "election_type": cf.election_type}),
                    state             = state,
                    county            = county,
                    year              = cf.year,
                    election_type     = cf.election_type,
                    source_url        = cf.source_url,
                    files_ingested    = 1,
                    confidence_score  = cf.overall_confidence,
                    fingerprint_type  = cf.fingerprint_type,
                    precinct_schema   = cf.precinct_schema,
                    normalization_method = "safe_join_engine",
                    join_confidence   = cf.join_archive_ready_fraction,
                    archive_dir       = result.get("archive_dir", ""),
                )
            elif result["status"] == "REVIEW_QUEUE":
                review_count += 1
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1
            errors.append(f"Ingest error {cf.local_path}: {e}")
            log.error(f"[BUILDER] Ingest failed {cf.local_path}: {e}")

    avg_conf = round(total_conf / max(classified, 1), 4)
    archive_ready = sum(1 for cf in classified_files if cf.archive_ready)

    # ── Step 5: Write reports ─────────────────────────────────────────────────
    build_report = _write_build_report(
        run_id, state, county, sources_scanned, pages_found,
        candidates_found, classified, ingested_count, review_count,
        failed_count, archive_ready, avg_conf, classified_files, errors,
    )
    classification_report = _write_classification_report(run_id, classified_files)

    log.info(
        f"[BUILDER] [{run_id}] Complete: "
        f"sources={sources_scanned} pages={pages_found} candidates={candidates_found} "
        f"classified={classified} ingested={ingested_count} "
        f"review={review_count} failed={failed_count}"
    )

    return ArchiveBuildResult(
        run_id=run_id, state=state, county=county,
        sources_scanned=sources_scanned, pages_found=pages_found,
        candidates_found=candidates_found, classified=classified,
        ingested=ingested_count, review_queue=review_count,
        failed=failed_count, archive_ready_count=archive_ready,
        avg_overall_confidence=avg_conf,
        build_report=str(build_report) if build_report else None,
        classification_report=str(classification_report) if classification_report else None,
        errors=errors,
    )


def _write_build_report(
    run_id, state, county, sources_scanned, pages_found,
    candidates_found, classified, ingested, review_count,
    failed, archive_ready, avg_conf, classified_files, errors,
) -> Optional[Path]:
    path = REPORTS_DIR / f"{run_id}__archive_build.md"
    lines = [
        f"# Archive Build Report — {run_id}",
        f"**Jurisdiction:** {state} / {county}",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Sources scanned | {sources_scanned} |",
        f"| Election pages found | {pages_found} |",
        f"| Candidate files found | {candidates_found} |",
        f"| Files classified | {classified} |",
        f"| Ingested | {ingested} |",
        f"| Sent to review queue | {review_count} |",
        f"| Failed | {failed} |",
        f"| Archive-ready | {archive_ready} |",
        f"| Avg overall confidence | {avg_conf:.3f} |",
        "",
    ]

    if classified_files:
        lines += [
            "## Classified Files",
            "",
            "| File | Type | FP Conf | Overall | Archive Ready |",
            "|------|------|---------|---------|---------------|",
        ]
        for cf in classified_files:
            fname = Path(cf.local_path).name if cf.local_path else "N/A"
            lines.append(
                f"| `{fname}` | {cf.fingerprint_display} "
                f"| {cf.fingerprint_confidence:.2f} "
                f"| {cf.overall_confidence:.2f} "
                f"| {'YES' if cf.archive_ready else 'NO'} |"
            )

    if errors:
        lines += ["", "## Errors", ""]
        for e in errors:
            lines.append(f"- {e}")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_classification_report(run_id, classified_files) -> Optional[Path]:
    path = REPORTS_DIR / f"{run_id}__file_classification.md"
    lines = [
        f"# File Classification Report — {run_id}",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "| File | FP Type | FP Conf | Schema | Join% | Valid | Review Reasons |",
        "|------|---------|---------|--------|-------|-------|----------------|",
    ]
    for cf in classified_files:
        fname = Path(cf.local_path).name if cf.local_path else "N/A"
        reasons = "; ".join(cf.review_reasons[:2])[:60]
        lines.append(
            f"| `{fname}` | {cf.fingerprint_type} | {cf.fingerprint_confidence:.2f} "
            f"| {cf.precinct_schema or '—'} "
            f"| {cf.join_archive_ready_fraction:.0%} "
            f"| {'OK' if cf.validation.valid else 'FAIL'} "
            f"| {reasons} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
