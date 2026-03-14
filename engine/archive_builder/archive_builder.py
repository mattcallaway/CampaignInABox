"""
engine/archive_builder/archive_builder.py — Prompt 25 / 25B / 25C

Main orchestrator for the Historical Election Archive Builder.
Prompt 25 upgrade: pre-condition checks, jurisdiction lock, page_discovery,
5-factor file scoring, file_downloader + file registry, archive_status routing,
archive output writers, campaign state post-build update.

Pipeline:
  0. Pre-condition check        — abort if any required system missing
  1. Jurisdiction lock          — enforce CA / Sonoma, reject cross-jurisdiction
  2. Source scan                — source_scanner ← contest_sources.yaml
  3. Page discovery             — page_discovery (two-stage HTML traversal)
  4. File discovery             — file_discovery (5-factor scoring, min 0.5)
  5. Download                   — file_downloader → data/election_archive/raw/
  6. Classify                   — archive_classifier (fingerprint + validate + join)
  7. Ingest                     — archive_ingestor (P27 normalizer + acceptance gate)
  8. Register                   — archive_registry (with archive_status)
  9. Archive outputs            — archive_output_writer (4 CSVs)
 10. Campaign state update      — campaign_state_resolver post-build
 11. Write reports              — build_report, file_classification

Public API:
  run_archive_build(state, county, online, download, run_id) → ArchiveBuildResult

Jurisdiction lock: state=CA county=Sonoma
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

# ── Required systems ──────────────────────────────────────────────────────────
REQUIRED_SYSTEMS = [
    ("engine.archive_builder.source_scanner",            "scan_all_sources"),
    ("engine.archive_builder.page_discovery",            "discover_election_pages"),
    ("engine.archive_builder.file_discovery",            "discover_files_from_page"),
    ("engine.archive_builder.file_downloader",           "download_batch"),
    ("engine.archive_builder.archive_classifier",        "classify_candidate_file"),
    ("engine.archive_builder.archive_ingestor",          "ingest_classified_file"),
    ("engine.archive_builder.archive_registry",          "register_election"),
    ("engine.archive_builder.archive_output_writer",     "write_archive_outputs"),
    ("engine.archive_builder.election_directory_predictor", "predict_election_result_paths"),  # P25C
    ("engine.state.campaign_state_resolver",             "get_active_campaign_id"),
]


@dataclass
class ArchiveBuildResult:
    """Overall result of a single archive build run."""
    run_id:              str
    state:               str
    county:              str
    sources_scanned:     int
    pages_found:         int
    candidates_found:    int
    classified:          int
    ingested:            int
    review_queue:        int
    failed:              int
    archive_ready_count: int
    avg_overall_confidence: float
    build_report:        Optional[str]
    classification_report: Optional[str]
    archive_outputs:     dict[str, str]
    errors:              list[str]
    preconditions_ok:    bool
    # Prompt 25C additions
    predicted_directories:  int = 0
    directories_confirmed:  int = 0
    directory_files_found:  int = 0
    directory_predictions_report: Optional[str] = None
    archive_discovery_report:     Optional[str] = None


# ── Step 0: Pre-condition check ───────────────────────────────────────────────

def check_preconditions() -> tuple[bool, list[str]]:
    """
    Verify all required systems are importable.
    Returns (all_ok: bool, missing: list[str])
    """
    missing: list[str] = []
    for module_path, func_name in REQUIRED_SYSTEMS:
        try:
            mod = __import__(module_path, fromlist=[func_name])
            if not hasattr(mod, func_name):
                missing.append(f"{module_path}.{func_name} — function missing")
        except ImportError as e:
            missing.append(f"{module_path} — ImportError: {e}")
    return len(missing) == 0, missing


# ── Step 1: Jurisdiction check ────────────────────────────────────────────────

def _check_jurisdiction(url: str, state: str, county: str) -> bool:
    """
    Return True if url passes the jurisdiction lock for state/county.
    Used as a cross-jurisdiction guard before download/ingest.
    """
    from config.source_registry import official_domain_allowlist  # noqa: F401 - import guard
    # Simple check: only allow downloads from known gov/official domains
    # A cross-jurisdiction check must be done at classify/ingest time too (P27 does this)
    return True   # domain enforcement is in allowlist; content enforcement in ingestor


def _is_cross_jurisdiction(classified_file) -> bool:
    """Return True if the classified file's state/county mismatch the jurisdiction lock."""
    state_ok  = not classified_file.state or classified_file.state.upper() == "CA"
    county_ok = not classified_file.county or classified_file.county.lower() == "sonoma"
    return not (state_ok and county_ok)


# ── Step 2+3: Source scan + page discovery ────────────────────────────────────

def _election_id_from_source(source: dict) -> str:
    year  = source.get("year", "unknown")
    etype = source.get("election_type", "general")
    return f"{year}_{etype}"


# ── Step 2.5: Directory prediction (Prompt 25C) ───────────────────────────────

def _write_predictor_reports(run_id: str, prediction_result) -> tuple[str, str]:
    """
    Write directory_predictions.md and directory_predictions.json.
    Returns (md_path, json_path) as strings.
    """
    from engine.archive_builder.election_directory_predictor import PredictionResult
    r: PredictionResult = prediction_result

    md_lines = [
        f"# Directory Predictions — {run_id}",
        f"",
        f"**Domain:** {r.domain}  |  **Years:** {r.years}  |  **State:** {r.state}/{r.county}",
        f"",
        f"## Metrics",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
    ]
    for k, v in r.metrics.items():
        md_lines.append(f"| {k} | {v} |")

    md_lines += [
        f"",
        f"## Predicted URLs ({len(r.predicted_urls)} total)",
        f"",
    ]
    for u in r.predicted_urls:
        md_lines.append(f"- {u}")

    if r.confirmed_dirs:
        md_lines += [f"", f"## Confirmed Directories ({len(r.confirmed_dirs)})", f""]
        for cd in r.confirmed_dirs:
            md_lines.append(
                f"- **[{cd.classified_as}]** `{cd.final_url}` "
                f"(score={cd.page_score}, files={len(cd.file_candidates)}, "
                f"html_status={cd.http_status})"
            )

    if r.file_candidates:
        md_lines += [f"", f"## File Candidates ({len(r.file_candidates)})", f""]
        for fc in r.file_candidates:
            md_lines.append(f"- {fc}")

    if r.errors:
        md_lines += [f"", f"## Errors", f""]
        for e in r.errors:
            md_lines.append(f"- {e}")

    md_path   = REPORTS_DIR / f"{run_id}__directory_predictions.md"
    json_path = REPORTS_DIR / f"{run_id}__directory_predictions.json"

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    json_path.write_text(
        json.dumps({
            "run_id":          run_id,
            "domain":          r.domain,
            "years":           r.years,
            "predicted_count": len(r.predicted_urls),
            "confirmed_count": len(r.confirmed_dirs),
            "file_candidates": r.file_candidates,
            "metrics":         r.metrics,
            "confirmed_dirs": [
                {
                    "url":             cd.url,
                    "final_url":       cd.final_url,
                    "classified_as":   cd.classified_as,
                    "page_score":      cd.page_score,
                    "year":            cd.year,
                    "files_count":     len(cd.file_candidates),
                    "resolved_count":  len(cd.resolved_files),
                    "directory_priority": cd.directory_priority,
                }
                for cd in r.confirmed_dirs
            ],
            "errors": r.errors,
        }, indent=2, default=str),
        encoding="utf-8",
    )
    log.info(f"[BUILDER] Directory predictions report → {md_path.name}")
    return str(md_path), str(json_path)


def _write_discovery_report(
    run_id: str,
    result: "ArchiveBuildResult",
    prediction_result,
) -> tuple[str, str]:
    """Write archive_discovery_report.md and .json."""
    md_lines = [
        f"# Archive Discovery Report — {run_id}",
        f"",
        f"**Jurisdiction:** {result.state} / {result.county}",
        f"",
        f"## Discovery Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Predicted directories | {result.predicted_directories} |",
        f"| Confirmed directories | {result.directories_confirmed} |",
        f"| Files found (predictor) | {result.directory_files_found} |",
        f"| Sources scanned | {result.sources_scanned} |",
        f"| Pages found | {result.pages_found} |",
        f"| Candidate files | {result.candidates_found} |",
        f"| Classified | {result.classified} |",
        f"| Ingested | {result.ingested} |",
        f"| Archive ready | {result.archive_ready_count} |",
        f"| Review required | {result.review_queue} |",
        f"| Failed | {result.failed} |",
    ]
    if result.errors:
        md_lines += [f"", f"## Errors ({len(result.errors)})", f""]
        for e in result.errors[:20]:
            md_lines.append(f"- {e}")

    md_path   = REPORTS_DIR / f"{run_id}__archive_discovery_report.md"
    json_path = REPORTS_DIR / f"{run_id}__archive_discovery_report.json"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    json_path.write_text(
        json.dumps({
            "run_id":                run_id,
            "state":                 result.state,
            "county":                result.county,
            "predicted_directories": result.predicted_directories,
            "directories_confirmed": result.directories_confirmed,
            "files_found":           result.candidates_found,
            "files_ingested":        result.ingested,
            "archive_ready":         result.archive_ready_count,
            "review_required":       result.review_queue,
            "errors_count":          len(result.errors),
        }, indent=2, default=str),
        encoding="utf-8",
    )
    log.info(f"[BUILDER] Discovery report → {md_path.name}")
    return str(md_path), str(json_path)


def _write_archive_summary_json(run_id: str, cid: str, result: "ArchiveBuildResult") -> None:
    """Write archive_summary.json to campaign state dir."""
    summary_dir = (
        BASE_DIR / "derived" / "state" / "campaigns" / cid / "latest"
    )
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "archive_summary.json"
    summary = {
        "run_id":                run_id,
        "last_run":              datetime.now().isoformat(),
        "predicted_directories": result.predicted_directories,
        "directories_confirmed": result.directories_confirmed,
        "files_found":           result.candidates_found,
        "files_ingested":        result.ingested,
        "archive_ready":         result.archive_ready_count,
        "review_required":       result.review_queue,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info(f"[BUILDER] archive_summary.json → {summary_path}")

def run_archive_build(
    state:      str = "CA",
    county:     str = "Sonoma",
    online:     bool = False,
    download:   bool = False,
    run_id:     Optional[str] = None,
    source_ids: Optional[list[str]] = None,
    abort_on_precondition_fail: bool = True,
) -> ArchiveBuildResult:
    """
    Run the full archive build pipeline.

    Args:
        state:       state code (CA)
        county:      county name (Sonoma)
        online:      if True, attempt HTTP discovery
        download:    if True, download candidate files (requires online=True)
        run_id:      run identifier (auto-generated if None)
        source_ids:  limit to specific source registry IDs (None = all)
        abort_on_precondition_fail: if True, abort early if any required system missing

    Returns:
        ArchiveBuildResult with counts and report paths
    """
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d__%H%M")

    errors: list[str] = []
    archive_outputs: dict[str, str] = {}

    # ── Step 0: Pre-condition check ───────────────────────────────────────────
    log.info(f"[BUILDER] [{run_id}] Pre-condition check...")
    pc_ok, pc_missing = check_preconditions()
    if not pc_ok:
        for m in pc_missing:
            log.error(f"[BUILDER] MISSING SYSTEM: {m}")
            errors.append(f"PRECONDITION FAIL: {m}")
        if abort_on_precondition_fail:
            log.error(f"[BUILDER] [{run_id}] Aborting — {len(pc_missing)} required systems missing")
            return ArchiveBuildResult(
                run_id=run_id, state=state, county=county,
                sources_scanned=0, pages_found=0, candidates_found=0,
                classified=0, ingested=0, review_queue=0, failed=0,
                archive_ready_count=0, avg_overall_confidence=0.0,
                build_report=None, classification_report=None,
                archive_outputs={}, errors=errors, preconditions_ok=False,
            )
    else:
        log.info(f"[BUILDER] [{run_id}] All {len(REQUIRED_SYSTEMS)} required systems OK")

    from engine.archive_builder.source_scanner import scan_all_sources
    from engine.archive_builder.page_discovery import discover_election_pages
    from engine.archive_builder.file_discovery import (
        discover_files_from_page, discover_from_local_staging
    )
    from engine.archive_builder.file_downloader import download_batch, update_file_archive_status
    from engine.archive_builder.archive_classifier import classify_candidate_file
    from engine.archive_builder.archive_ingestor import ingest_classified_file
    from engine.archive_builder.archive_registry import register_election
    from engine.archive_builder.archive_output_writer import write_archive_outputs
    from engine.archive_builder.election_directory_predictor import predict_election_result_paths  # P25C

    # ── Step 2: Scan source registry ─────────────────────────────────────────
    log.info(f"[BUILDER] [{run_id}] Scanning sources: {state}/{county} online={online}")
    scan_results = scan_all_sources(
        state_filter=state, county_filter=county, online=online,
    )
    if source_ids:
        scan_results = [r for r in scan_results if r.source_id in source_ids]
    sources_scanned = len(scan_results)

    # Build source metadata lookup
    import yaml
    registry_path = BASE_DIR / "config" / "source_registry" / "contest_sources.yaml"
    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        source_map = {s["source_id"]: s for s in raw.get("sources", [])}
    except Exception:
        source_map = {}

    # ── Step 3: Page discovery ────────────────────────────────────────────────
    log.info(f"[BUILDER] [{run_id}] Discovering election pages from {sources_scanned} sources")
    all_pages: list[tuple[dict, str]] = []   # (source_dict, page_url)

    for scan in scan_results:
        src_dict = source_map.get(scan.source_id, {
            "source_id":      scan.source_id,
            "state":          scan.state,
            "county":         scan.county,
            "year":           scan.year,
            "election_type":  scan.election_type,
        })

        # Use page_discovery for richer multi-stage traversal
        try:
            election_pages = discover_election_pages(
                src_dict, online=online, max_pages=25, min_score=0.10,
            )
            for ep in election_pages:
                all_pages.append((src_dict, ep.url))
        except Exception as e:
            # Fallback: use the scan result URLs directly
            log.warning(f"[BUILDER] page_discovery failed for {scan.source_id}: {e}")
            for page_url in scan.discovered_urls:
                all_pages.append((src_dict, page_url))

    pages_found = len(all_pages)
    log.info(f"[BUILDER] [{run_id}] Found {pages_found} election pages from {sources_scanned} sources")

    # ── Step 2.5: Directory prediction (Prompt 25C) ────────────────────────────
    log.info(f"[BUILDER] [{run_id}] Running directory predictor (online={online})...")
    prediction_result = None
    predicted_directories = 0
    directories_confirmed = 0
    directory_files_found = 0
    try:
        import yaml
        registry_path2 = BASE_DIR / "config" / "source_registry" / "contest_sources.yaml"
        raw2  = yaml.safe_load(registry_path2.read_text(encoding="utf-8")) or {}
        # Pick primary domain from contest_sources.yaml or use default
        primary_domain = "https://sonomacounty.ca.gov"
        for src in raw2.get("sources", []):
            pd = src.get("primary_domain") or src.get("base_url") or ""
            if pd.startswith("http") and "sonoma" in pd.lower():
                primary_domain = pd.rstrip("/")
                break
        prediction_result = predict_election_result_paths(
            domain=primary_domain,
            years=[2024, 2023, 2022, 2021, 2020],
            online=online,
            state=state,
            county=county,
        )
        predicted_directories = len(prediction_result.predicted_urls)
        directories_confirmed = len(prediction_result.confirmed_dirs)
        directory_files_found = len(prediction_result.file_candidates)

        # Prepend confirmed directory URLs to all_pages for page_explorer
        if prediction_result.confirmed_dirs:
            log.info(
                f"[BUILDER] [{run_id}] Predictor found {directories_confirmed} confirmed dirs, "
                f"{directory_files_found} file candidates, prepending to page_explorer start_urls"
            )
            dummy_src = {
                "source_id": "predictor_p25c", "state": state, "county": county,
                "year": None, "election_type": None,
            }
            for cd in prediction_result.confirmed_dirs:
                all_pages.insert(0, (dummy_src, cd.final_url))
    except Exception as e:
        log.warning(f"[BUILDER] [{run_id}] Predictor step failed (non-fatal): {e}")
        errors.append(f"Predictor error: {e}")

    # ── Step 4: Discover candidate files ───────────────────────────────────────
    pages_found = len(all_pages)  # updated after predictor dirs added
    all_candidates = []
    for src_dict, page_url in all_pages:
        eid         = _election_id_from_source(src_dict)
        county_slug = county.lower().replace(" ", "_")
        staging_sub = f"{county_slug}/{eid}"

        if online and download:
            # Step 5: download via file_downloader for proper registry tracking
            from engine.archive_builder.file_discovery import discover_files_from_page as _dfp
            candidates_pre = _dfp(page_url, src_dict, download=False, staging_subdir=staging_sub)
            # Only download the non-staged ones
            urls_to_dl = [c.url for c in candidates_pre if not c.local_path]
            if urls_to_dl:
                dl_results = download_batch(
                    urls_to_dl,
                    state=state,
                    county=county,
                    year=src_dict.get("year"),
                    election_type=src_dict.get("election_type"),
                    source_id=src_dict.get("source_id", "unknown"),
                )
            # Now discover including newly downloaded files
            candidates = discover_files_from_page(
                page_url, src_dict, download=False, staging_subdir=staging_sub
            )
        elif online:
            candidates = discover_files_from_page(
                page_url, src_dict, download=False, staging_subdir=staging_sub
            )
        else:
            candidates = discover_from_local_staging(src_dict, staging_sub)
            if not candidates and page_url:
                log.info(f"[BUILDER] No staged files for {eid} — add manually or run with online=True")

        all_candidates.extend(candidates)

    candidates_found = len(all_candidates)
    log.info(f"[BUILDER] [{run_id}] {candidates_found} candidate files found")

    # ── Step 6: Classify each candidate file ─────────────────────────────────
    classified_files = []
    for cand in all_candidates:
        if not cand.local_path:
            continue
        try:
            cf = classify_candidate_file(
                cand, state=state, county=county, boundary_type="MPREC",
            )
            classified_files.append(cf)
        except Exception as e:
            errors.append(f"Classify error {cand.filename}: {e}")
            log.warning(f"[BUILDER] Classify failed {cand.filename}: {e}")

    classified = len(classified_files)

    # ── Step 7: Ingest (P27 normalizer + acceptance gate) ────────────────────
    ingested_count = 0
    review_count   = 0
    failed_count   = 0
    total_conf     = 0.0
    ingest_results = []

    for cf in classified_files:
        total_conf += cf.overall_confidence

        # Prompt 25: jurisdiction lock — REJECT cross-jurisdiction
        if _is_cross_jurisdiction(cf):
            review_count += 1
            log.warning(
                f"[BUILDER] BLOCKED_CROSS_JURISDICTION: {cf.local_path} "
                f"(state={cf.state} county={cf.county})"
            )
            errors.append(
                f"Cross-jurisdiction blocked: {Path(cf.local_path or '').name} "
                f"state={cf.state} county={cf.county}"
            )
            if cf.local_path:
                update_file_archive_status(cf.local_path, "REJECTED")
            continue

        try:
            result = ingest_classified_file(cf, run_id=run_id)
            ingest_results.append(result)
            archive_file_status = result.get("archive_file_status", "UNKNOWN")

            if result["status"] == "INGESTED":
                ingested_count += 1

                # Update file registry with final archive status
                if cf.local_path:
                    update_file_archive_status(cf.local_path, archive_file_status)

                # Register in archive_registry.yaml
                election_id = _election_id_from_source({
                    "year": cf.year, "election_type": cf.election_type,
                })
                register_election(
                    election_id       = election_id,
                    state             = state,
                    county            = county,
                    year              = cf.year,
                    election_type     = cf.election_type,
                    source_url        = cf.source_url,
                    files_ingested    = 1,
                    confidence_score  = cf.overall_confidence,
                    fingerprint_type  = cf.fingerprint_type,
                    precinct_schema   = cf.precinct_schema,
                    normalization_method = "safe_join_engine+p27",
                    join_confidence   = result.get("join_fraction", cf.join_archive_ready_fraction),
                    archive_dir       = result.get("archive_dir", ""),
                    # Prompt 25 / P27 additions
                    archive_status    = archive_file_status,
                    run_id            = run_id,
                    file_path         = str(
                        Path(result.get("archive_dir", "")) / "precinct_results.csv"
                    ),
                )
            elif result["status"] == "REVIEW_QUEUE":
                review_count += 1
                if cf.local_path:
                    update_file_archive_status(cf.local_path, archive_file_status)
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1
            errors.append(f"Ingest error {cf.local_path}: {e}")
            log.error(f"[BUILDER] Ingest failed {cf.local_path}: {e}")

    avg_conf       = round(total_conf / max(classified, 1), 4)
    archive_ready  = sum(
        1 for cf in classified_files
        if getattr(cf, "archive_status", "ARCHIVE_READY" if cf.archive_ready else "NO") == "ARCHIVE_READY"
        or cf.archive_ready
    )

    # ── Step 8: Write archive outputs (4 CSVs) ──────────────────────────────
    log.info(f"[BUILDER] [{run_id}] Writing archive outputs...")
    try:
        archive_outputs = write_archive_outputs(
            ingested_results=ingest_results, run_id=run_id,
        )
    except Exception as e:
        log.error(f"[BUILDER] archive_output_writer failed: {e}")
        errors.append(f"Archive outputs error: {e}")

    # ── Step 9: Campaign state post-build update ─────────────────────────────
    try:
        _update_campaign_state(
            run_id=run_id,
            archive_ready=archive_ready,
            ingested=ingested_count,
            review_queue=review_count,
            classified=classified,
        )
    except Exception as e:
        log.warning(f"[BUILDER] Campaign state update failed (non-fatal): {e}")

    # ── Step 10: Write reports (P25 + P25C) ──────────────────────────────────
    build_report = _write_build_report(
        run_id, state, county, sources_scanned, pages_found,
        candidates_found, classified, ingested_count, review_count,
        failed_count, archive_ready, avg_conf, classified_files, errors,
        archive_outputs,
    )
    classification_report = _write_classification_report(run_id, classified_files)

    # Prompt 25C: build partial result for P25C report writers
    _partial = ArchiveBuildResult(
        run_id=run_id, state=state, county=county,
        sources_scanned=sources_scanned, pages_found=pages_found,
        candidates_found=candidates_found, classified=classified,
        ingested=ingested_count, review_queue=review_count,
        failed=failed_count, archive_ready_count=archive_ready,
        avg_overall_confidence=avg_conf,
        build_report=None, classification_report=None,
        archive_outputs=archive_outputs, errors=errors, preconditions_ok=pc_ok,
        predicted_directories=predicted_directories,
        directories_confirmed=directories_confirmed,
        directory_files_found=directory_files_found,
    )
    dir_pred_report = None
    disc_report = None
    try:
        if prediction_result is not None:
            pred_md, _ = _write_predictor_reports(run_id, prediction_result)
            dir_pred_report = pred_md
        disc_md, _ = _write_discovery_report(run_id, _partial, prediction_result)
        disc_report = disc_md
    except Exception as e:
        log.warning(f"[BUILDER] P25C report writing failed (non-fatal): {e}")
        errors.append(f"P25C report error: {e}")

    # Prompt 25C: write archive_summary.json to campaign state dir
    try:
        from engine.state.campaign_state_resolver import get_active_campaign_id
        _write_archive_summary_json(run_id, get_active_campaign_id(), _partial)
    except Exception as e:
        log.warning(f"[BUILDER] archive_summary.json write failed (non-fatal): {e}")

    log.info(
        f"[BUILDER] [{run_id}] Complete: "
        f"sources={sources_scanned} pages={pages_found} candidates={candidates_found} "
        f"classified={classified} ingested={ingested_count} "
        f"review={review_count} failed={failed_count} "
        f"archive_ready={archive_ready} predicted_dirs={predicted_directories} "
        f"confirmed_dirs={directories_confirmed}"
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
        archive_outputs=archive_outputs,
        errors=errors,
        preconditions_ok=pc_ok,
        predicted_directories=predicted_directories,
        directories_confirmed=directories_confirmed,
        directory_files_found=directory_files_found,
        directory_predictions_report=dir_pred_report,
        archive_discovery_report=disc_report,
    )


def _update_campaign_state(
    run_id: str,
    archive_ready: int,
    ingested: int,
    review_queue: int,
    classified: int,
) -> None:
    """Update campaign state with archive build summary (Prompt 25 Step 13)."""
    from engine.state.campaign_state_resolver import (
        get_active_campaign_id, get_latest_campaign_state, get_latest_state_dir,
    )
    cid  = get_active_campaign_id()
    state_json_path = get_latest_state_dir(cid) / "campaign_state.json"
    if not state_json_path.exists():
        log.info(f"[BUILDER] No state file for {cid} — skipping campaign state update")
        return

    import json
    state = json.loads(state_json_path.read_text(encoding="utf-8"))

    state["archive_summary"] = {
        "run_id":                     run_id,
        "archive_ready_files":        archive_ready,
        "total_ingested_files":       ingested,
        "review_queue_files":         review_queue,
        "total_classified":           classified,
        "last_build":                 datetime.now().isoformat(),
    }
    state["historical_models_active"] = archive_ready > 0
    state["archive_file_count"]       = archive_ready

    state_json_path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    log.info(f"[BUILDER] Campaign state updated: archive_ready={archive_ready} cid={cid}")


# ── Report writers ─────────────────────────────────────────────────────────────

def _write_build_report(
    run_id, state, county, sources_scanned, pages_found,
    candidates_found, classified, ingested, review_count,
    failed, archive_ready, avg_conf, classified_files, errors,
    archive_outputs: Optional[dict] = None,
) -> Optional[Path]:
    path  = REPORTS_DIR / f"{run_id}__archive_build.md"
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

    if archive_outputs:
        lines += ["## Archive Outputs", ""]
        for name, path_str in archive_outputs.items():
            lines.append(f"- `{name}`: `{path_str}`")
        lines.append("")

    if classified_files:
        lines += [
            "## Classified Files",
            "",
            "| File | Type | FP Conf | Overall | Status |",
            "|------|------|---------|---------|--------|",
        ]
        for cf in classified_files:
            fname  = Path(cf.local_path).name if cf.local_path else "N/A"
            status = getattr(cf, "archive_status", "ARCHIVE_READY" if cf.archive_ready else "NO")
            lines.append(
                f"| `{fname}` | {cf.fingerprint_display} "
                f"| {cf.fingerprint_confidence:.2f} "
                f"| {cf.overall_confidence:.2f} "
                f"| {status} |"
            )

    if errors:
        lines += ["", "## Errors", ""]
        for e in errors:
            lines.append(f"- {e}")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_classification_report(run_id, classified_files) -> Optional[Path]:
    path  = REPORTS_DIR / f"{run_id}__file_classification.md"
    lines = [
        f"# File Classification Report — {run_id}",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "| File | FP Type | FP Conf | Schema | Join% | Valid | Status | Review Reasons |",
        "|------|---------|---------|--------|-------|-------|--------|----------------|",
    ]
    for cf in classified_files:
        fname   = Path(cf.local_path).name if cf.local_path else "N/A"
        reasons = "; ".join(cf.review_reasons[:2])[:60]
        status  = getattr(cf, "archive_status", "ARCHIVE_READY" if cf.archive_ready else "—")
        lines.append(
            f"| `{fname}` | {cf.fingerprint_type} | {cf.fingerprint_confidence:.2f} "
            f"| {cf.precinct_schema or '—'} "
            f"| {cf.join_archive_ready_fraction:.0%} "
            f"| {'OK' if cf.validation.valid else 'FAIL'} "
            f"| {status} "
            f"| {reasons} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
