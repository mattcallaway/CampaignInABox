"""
engine/archive_builder/file_downloader.py — Prompt 25 / Prompt 25B

Candidate file downloader with file registry integration.

Downloads candidate election data files to:
  data/election_archive/raw/<state>/<county>/<year>/

Maintains a file registry at:
  data/election_archive/file_registry.json

Safety:
  - Skips already-downloaded files (idempotent)
  - Enforces 50 KB minimum size
  - Rate-limits requests (0.5 s between downloads)
  - Never downloads non-election file types
  - Records source_url, download_timestamp, file_size, source_domain per file
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

log = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parent.parent.parent
RAW_DIR       = BASE_DIR / "data" / "election_archive" / "raw"
REGISTRY_PATH = BASE_DIR / "data" / "election_archive" / "file_registry.json"

RAW_DIR.mkdir(parents=True, exist_ok=True)
REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)

HTTP_TIMEOUT   = 20
RATE_LIMIT_S   = 0.5
MIN_FILE_SIZE  = 50 * 1024   # 50 KB

ACCEPTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv", ".zip", ".pdf"}


# ── SHA-256 hash helper ───────────────────────────────────────────

def _compute_hash(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── File Registry ─────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"schema_version": "1.0", "files": []}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": "1.0", "files": []}


def _save_registry(data: dict) -> None:
    REGISTRY_PATH.write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8",
    )


def _register_file(
    local_path: Path,
    source_url: str,
    file_size: int,
    state: str,
    county: str,
    year: Optional[int],
    election_type: Optional[str],
    source_id: str,
    download_status: str,
    file_hash: Optional[str] = None,
    page_depth: int = 0,
    candidate_score: float = 0.0,
) -> dict:
    """Add or update a file entry in the file registry."""
    reg    = _load_registry()
    files: list[dict] = reg.get("files", [])
    source_domain = urlparse(source_url).netloc

    entry = {
        "local_path":          str(local_path),
        "source_url":          source_url,
        "source_id":           source_id,
        "source_domain":       source_domain,
        "state":               state,
        "county":              county,
        "year":                year,
        "election_type":       election_type,
        "file_size":           file_size,
        "extension":           local_path.suffix.lower(),
        "download_timestamp":  datetime.now().isoformat(),
        "download_status":     download_status,
        "archive_status":      "PENDING",
        # Prompt 25B additions
        "file_hash":           file_hash or "",
        "page_depth":          page_depth,
        "candidate_score":     round(candidate_score, 3),
    }

    # Upsert by source_url
    updated = False
    for i, existing in enumerate(files):
        if existing.get("source_url") == source_url:
            files[i] = entry
            updated = True
            break
    if not updated:
        files.append(entry)

    reg["files"]        = files
    reg["last_updated"] = datetime.now().isoformat()
    _save_registry(reg)
    return entry


def update_file_archive_status(local_path: str, archive_status: str) -> None:
    """Update the archive_status of a file in the registry post-classification."""
    reg   = _load_registry()
    files = reg.get("files", [])
    for f in files:
        if f.get("local_path") == local_path:
            f["archive_status"] = archive_status
            break
    _save_registry(reg)


def get_file_registry() -> list[dict]:
    return _load_registry().get("files", [])


def registry_summary() -> dict:
    files = get_file_registry()
    total = len(files)
    staged = [f for f in files if f.get("download_status") == "staged"]
    return {
        "total_registered":  total,
        "staged":            len(staged),
        "pending":           sum(1 for f in files if f.get("download_status") == "pending"),
        "failed":            sum(1 for f in files if f.get("download_status") == "failed"),
        "archive_ready":     sum(1 for f in files if f.get("archive_status") == "ARCHIVE_READY"),
        "review_required":   sum(1 for f in files if f.get("archive_status") == "REVIEW_REQUIRED"),
        "rejected":          sum(1 for f in files if f.get("archive_status") == "REJECTED"),
        "extensions":        sorted({f.get("extension", "") for f in staged}),
    }


# ── Download ──────────────────────────────────────────────────────────────────

def _local_dest(
    state: str,
    county: str,
    year: Optional[int],
    filename: str,
) -> Path:
    """Return the canonical raw download path for a file."""
    year_str = str(year) if year else "unknown_year"
    dest_dir = RAW_DIR / state / county.replace(" ", "_") / year_str
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir / filename


def download_candidate_file(
    url: str,
    state: str = "CA",
    county: str = "Sonoma",
    year: Optional[int] = None,
    election_type: Optional[str] = None,
    source_id: str = "unknown",
    force: bool = False,
    page_depth: int = 0,
    candidate_score: float = 0.0,
) -> dict:
    """
    Download a single candidate election file.

    Returns a result dict with keys:
      status:          staged | skipped | failed | too_small | rejected_ext
      local_path:      str (or None)
      file_size:       int
      source_url:      str
      source_domain:   str
      download_timestamp: str
      error:           str (on failure)
    """
    parsed   = urlparse(url)
    filename = Path(parsed.path).name
    if not filename:
        filename = "download"
    ext = Path(filename).suffix.lower()

    # Reject non-tabular file types
    if ext not in ACCEPTED_EXTENSIONS:
        log.debug(f"[DOWNLOADER] Skipping non-tabular file: {filename}")
        return {
            "status": "rejected_ext", "local_path": None,
            "file_size": 0, "source_url": url,
            "source_domain": parsed.netloc, "error": f"Extension {ext!r} not accepted",
        }

    dest = _local_dest(state, county, year, filename)

    # ── Prompt 25B: Duplicate detection via SHA-256 ──────────────────────────
    # Before downloading, check if a file with the same URL was already registered.
    # Also check hash if dest exists.
    if not force:
        reg = _load_registry()
        existing_by_url = next(
            (f for f in reg.get("files", []) if f.get("source_url") == url), None
        )
        if existing_by_url and existing_by_url.get("download_status") == "staged":
            existing_path = Path(existing_by_url.get("local_path", ""))
            if existing_path.exists():
                log.info(f"[DOWNLOADER] DUPLICATE_URL — already staged: {filename}")
                return {
                    "status": "duplicate", "local_path": str(existing_path),
                    "file_size": existing_path.stat().st_size, "source_url": url,
                    "source_domain": parsed.netloc,
                    "download_timestamp": datetime.now().isoformat(),
                    "error": None, "file_hash": existing_by_url.get("file_hash", ""),
                    "page_depth": page_depth, "candidate_score": candidate_score,
                }

    # Already downloaded to dest path?
    if dest.exists() and not force:
        size = dest.stat().st_size
        if size >= MIN_FILE_SIZE:
            existing_hash = _compute_hash(dest)
            # Check if hash matches a known file
            reg = _load_registry()
            dup = next(
                (f for f in reg.get("files", [])
                 if f.get("file_hash") == existing_hash and f.get("source_url") != url),
                None,
            )
            if dup:
                log.warning(
                    f"[DOWNLOADER] DUPLICATE_HASH: {filename} matches {dup.get('local_path')} — skipping"
                )
                return {
                    "status": "duplicate", "local_path": dup.get("local_path"),
                    "file_size": size, "source_url": url,
                    "source_domain": parsed.netloc,
                    "download_timestamp": datetime.now().isoformat(),
                    "error": f"DUPLICATE_HASH: matches {dup.get('local_path')}",
                    "file_hash": existing_hash,
                    "page_depth": page_depth, "candidate_score": candidate_score,
                }
            log.info(f"[DOWNLOADER] Already staged: {filename} ({size:,} bytes)")
            _register_file(dest, url, size, state, county, year, election_type, source_id,
                           "staged", existing_hash, page_depth, candidate_score)
            return {
                "status": "skipped", "local_path": str(dest),
                "file_size": size, "source_url": url,
                "source_domain": parsed.netloc, "download_timestamp": datetime.now().isoformat(),
                "error": None, "file_hash": existing_hash,
                "page_depth": page_depth, "candidate_score": candidate_score,
            }

    # Download
    log.info(f"[DOWNLOADER] Downloading {url} → {dest}")
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CampaignInABox-ArchiveBuilder/1.0"},
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp, \
             dest.open("wb") as f_out:
            shutil.copyfileobj(resp, f_out)

        size = dest.stat().st_size
        if size < MIN_FILE_SIZE:
            dest.unlink(missing_ok=True)
            log.warning(f"[DOWNLOADER] File too small ({size} bytes) — deleted: {filename}")
            _register_file(dest, url, size, state, county, year, election_type, source_id,
                           "too_small", None, page_depth, candidate_score)
            return {
                "status": "too_small", "local_path": None,
                "file_size": size, "source_url": url,
                "source_domain": parsed.netloc,
                "download_timestamp": datetime.now().isoformat(),
                "error": f"File too small: {size} bytes (min {MIN_FILE_SIZE})",
                "file_hash": None, "page_depth": page_depth, "candidate_score": candidate_score,
            }

        # Compute hash and check for duplicates
        file_hash = _compute_hash(dest)
        reg = _load_registry()
        dup = next(
            (f for f in reg.get("files", [])
             if f.get("file_hash") == file_hash and f.get("source_url") != url),
            None,
        )
        if dup:
            dest.unlink(missing_ok=True)
            log.warning(f"[DOWNLOADER] DUPLICATE_HASH post-download: {filename} matches {dup.get('local_path')}")
            return {
                "status": "duplicate", "local_path": dup.get("local_path"),
                "file_size": size, "source_url": url,
                "source_domain": parsed.netloc,
                "download_timestamp": datetime.now().isoformat(),
                "error": f"DUPLICATE_HASH: matches {dup.get('local_path')}",
                "file_hash": file_hash, "page_depth": page_depth, "candidate_score": candidate_score,
            }

        log.info(f"[DOWNLOADER] Staged: {filename} ({size:,} bytes) hash={file_hash[:12]}")
        _register_file(dest, url, size, state, county, year, election_type, source_id,
                       "staged", file_hash, page_depth, candidate_score)
        return {
            "status": "staged", "local_path": str(dest),
            "file_size": size, "source_url": url,
            "source_domain": parsed.netloc,
            "download_timestamp": datetime.now().isoformat(),
            "error": None, "file_hash": file_hash,
            "page_depth": page_depth, "candidate_score": candidate_score,
        }

    except Exception as e:
        log.warning(f"[DOWNLOADER] Failed: {url}: {e}")
        _register_file(
            dest if dest.exists() else Path(str(dest) + ".fail"),
            url, 0, state, county, year, election_type, source_id, "failed",
            None, page_depth, candidate_score,
        )
        return {
            "status": "failed", "local_path": None,
            "file_size": 0, "source_url": url,
            "source_domain": parsed.netloc,
            "download_timestamp": datetime.now().isoformat(),
            "error": str(e), "file_hash": None,
            "page_depth": page_depth, "candidate_score": candidate_score,
        }


def download_batch(
    urls: list[str],
    state: str = "CA",
    county: str = "Sonoma",
    year: Optional[int] = None,
    election_type: Optional[str] = None,
    source_id: str = "unknown",
    force: bool = False,
    rate_limit: float = RATE_LIMIT_S,
) -> list[dict]:
    """
    Download a list of candidate file URLs with rate limiting.

    Returns list of result dicts (same structure as download_candidate_file).
    """
    results: list[dict] = []
    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(rate_limit)
        result = download_candidate_file(
            url, state, county, year, election_type, source_id, force=force
        )
        results.append({**result, "source_url": url})
        log.info(
            f"[DOWNLOADER] Batch [{i+1}/{len(urls)}] "
            f"{result['status']} — {Path(url).name}"
        )
    staged = sum(1 for r in results if r["status"] == "staged")
    log.info(
        f"[DOWNLOADER] Batch complete: {staged}/{len(urls)} staged "
        f"({len(urls)-staged} skipped/failed)"
    )
    return results
