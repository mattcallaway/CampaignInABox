"""
engine/file_fingerprinting/fingerprint_engine.py — Prompt 25A.3

Main entry-point for the election file fingerprinting system.

Orchestrates:
  1. header_parser → ParsedHeader
  2. fingerprint_classifier → ClassificationResult
  3. Cache read/write → derived/fingerprint_cache/<file_hash>.json
  4. Report generation → reports/archive_detection/<RUN_ID>__fingerprint_report.md

Public API:
  classify(file_path)               → ClassificationResult
  classify_batch(file_paths)        → list[ClassificationResult]
  generate_fingerprint_report(...)  → path to report
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

log = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
CACHE_DIR    = BASE_DIR / "derived" / "fingerprint_cache"
REPORTS_DIR  = BASE_DIR / "reports" / "archive_detection"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_path(file_hash: str) -> Path:
    return CACHE_DIR / f"{file_hash}.json"


def _read_cache(file_hash: str) -> Optional[dict]:
    p = _cache_path(file_hash)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(result, source_url: Optional[str] = None) -> None:
    """Persist ClassificationResult to fingerprint cache."""
    from engine.file_fingerprinting.fingerprint_classifier import ClassificationResult
    r: ClassificationResult = result
    data = {
        "file_path":       r.file_path,
        "file_name":       Path(r.file_path).name,
        "file_hash":       r.file_hash,
        "file_type":       r.file_type,
        "display_name":    r.display_name,
        "confidence":      r.confidence,
        "matching_headers": r.matching_headers,
        "optional_hits":   r.optional_hits,
        "precinct_format": r.precinct_format,
        "precinct_level":  r.precinct_level,
        "contest_level":   r.contest_level,
        "sheet_name":      r.sheet_name,
        "row_count":       r.row_count,
        "col_count":       r.col_count,
        "source_url":      source_url or "",
        "classified_at":   datetime.now().isoformat(),
    }
    try:
        _cache_path(r.file_hash).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning(f"[FINGERPRINT] Cache write failed for {r.file_hash}: {e}")


# ── Public API ────────────────────────────────────────────────────────────────

def classify(
    file_path: str | Path,
    source_url: Optional[str] = None,
    use_cache: bool = True,
    sheet_index: int = 0,
):
    """
    Classify an election file by its structural fingerprint.

    Args:
        file_path:  Path to the spreadsheet file
        source_url: Where the file was downloaded from (stored in cache)
        use_cache:  If True, return cached result if available
        sheet_index: Excel sheet index (default 0)

    Returns:
        ClassificationResult
    """
    from engine.file_fingerprinting.header_parser import parse_spreadsheet_headers, _file_hash
    from engine.file_fingerprinting.fingerprint_classifier import classify_file

    path = Path(file_path)
    if not path.exists():
        log.error(f"[FINGERPRINT] File not found: {path}")
        # Return an error result
        from engine.file_fingerprinting.fingerprint_classifier import ClassificationResult
        return ClassificationResult(
            file_path=str(path), file_hash="missing", file_type="file_not_found",
            display_name="File Not Found", confidence=0.0,
            matching_headers=[], missing_required=[], optional_hits=[],
            precinct_format=None, precinct_level=False, contest_level=False,
            sheet_name=None, row_count=0, col_count=0,
        )

    # Check cache
    file_hash = _file_hash(path)
    if use_cache:
        cached = _read_cache(file_hash)
        if cached:
            log.debug(f"[FINGERPRINT] Cache hit: {path.name} → {cached['file_type']}")
            # Re-hydrate as ClassificationResult
            from engine.file_fingerprinting.fingerprint_classifier import ClassificationResult
            return ClassificationResult(
                file_path=cached["file_path"],
                file_hash=cached["file_hash"],
                file_type=cached["file_type"],
                display_name=cached["display_name"],
                confidence=cached["confidence"],
                matching_headers=cached.get("matching_headers", []),
                missing_required=[],
                optional_hits=cached.get("optional_hits", []),
                precinct_format=cached.get("precinct_format"),
                precinct_level=cached.get("precinct_level", False),
                contest_level=cached.get("contest_level", False),
                sheet_name=cached.get("sheet_name"),
                row_count=cached.get("row_count", 0),
                col_count=cached.get("col_count", 0),
            )

    # Parse + classify
    parsed = parse_spreadsheet_headers(path, sheet_index=sheet_index)
    result = classify_file(parsed)

    # Write cache
    _write_cache(result, source_url=source_url)

    log.info(f"[FINGERPRINT] {path.name} → {result.display_name} (conf={result.confidence:.2f})")
    return result


def classify_batch(
    file_paths: Sequence[str | Path],
    source_url_map: Optional[dict] = None,
    use_cache: bool = True,
):
    """
    Classify a batch of files. Returns list of ClassificationResult.

    Args:
        file_paths:    Iterable of file paths
        source_url_map: dict mapping file_path string to source URL
        use_cache:     Pass through to classify()
    """
    results = []
    for fp in file_paths:
        url = (source_url_map or {}).get(str(fp))
        r = classify(fp, source_url=url, use_cache=use_cache)
        results.append(r)
    return results


def generate_fingerprint_report(
    results,
    run_id: Optional[str] = None,
) -> Path:
    """
    Generate a Markdown fingerprint report for a set of ClassificationResults.

    Returns the path to the written report.
    """
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d__%H%M")

    report_path = REPORTS_DIR / f"{run_id}__fingerprint_report.md"

    lines = [
        f"# Election File Fingerprint Report — {run_id}",
        "",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**Files analyzed:** {len(results)}",
        "",
    ]

    # Summary table
    type_counts: dict[str, int] = {}
    for r in results:
        type_counts[r.display_name] = type_counts.get(r.display_name, 0) + 1

    lines += [
        "## Summary",
        "",
        "| File Type | Count |",
        "|-----------|-------|",
    ]
    for ft, cnt in sorted(type_counts.items()):
        lines.append(f"| {ft} | {cnt} |")

    unknowns = [r for r in results if r.file_type == "unknown"]
    errors   = [r for r in results if r.file_type in ("parse_error", "file_not_found")]

    lines += [
        "",
        f"**Unknown types:** {len(unknowns)}  |  **Parse errors:** {len(errors)}",
        "",
        "## File Classification Details",
        "",
        "| File | Type | Confidence | Precinct Format | Rows | Cols |",
        "|------|------|------------|-----------------|------|------|",
    ]

    for r in results:
        fname = Path(r.file_path).name
        conf_pct = f"{r.confidence*100:.0f}%"
        pfmt = r.precinct_format or "—"
        lines.append(
            f"| `{fname}` | {r.display_name} | {conf_pct} | `{pfmt}` | {r.row_count} | {r.col_count} |"
        )

    # Unknown files section
    if unknowns:
        lines += [
            "",
            "## Unknown / Unclassified Files",
            "",
        ]
        for r in unknowns:
            fname = Path(r.file_path).name
            lines.append(f"### `{fname}`")
            lines.append(f"- **Headers:** {', '.join(r.matching_headers[:10]) or '(none parsed)'}")
            if r.all_scores:
                best_guesses = sorted(r.all_scores.items(), key=lambda x: x[1], reverse=True)[:3]
                lines.append(f"- **Top rule scores:** " + " | ".join(f"{k}={v:.2f}" for k, v in best_guesses))
            lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[FINGERPRINT] Report written: {report_path}")
    return report_path
