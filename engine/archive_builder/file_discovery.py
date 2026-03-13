"""
engine/archive_builder/file_discovery.py — Prompt 25

Candidate file discovery engine.

Given a list of election page URLs (from source_scanner), discovers candidate
election data files by:
  - Fetching HTML (online mode) or using configured file_patterns (offline)
  - Filtering by accepted extensions: xlsx, xls, csv, tsv, zip
  - Rejecting PDF, images, and non-tabular documents
  - Ranking candidates by filename signals (statement, vote, precinct, contest)
  - Downloading candidate files to a staging area for fingerprinting

Classification relies on fingerprinting, NOT filenames alone.
Filename signals only affect download priority/ranking.
"""
from __future__ import annotations

import fnmatch
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

log = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
STAGING_DIR = BASE_DIR / "derived" / "archive_staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)

# Accepted file extensions for election data
ACCEPTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv", ".zip"}

# Rejected types (non-tabular)
REJECTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".docx", ".doc", ".pptx"}

# Filename keywords that signal high-value election files
PRIORITY_KEYWORDS = [
    "statement", "vote", "precinct", "contest", "results",
    "election", "certified", "official", "turnout", "registration",
    "ballot", "measure", "canvass",
]

# HTTP timeout
HTTP_TIMEOUT = 15


@dataclass
class CandidateFile:
    """A discovered candidate election data file."""
    url: str                        # source URL where file was found / downloaded from
    filename: str                   # original filename
    local_path: Optional[str]       # path to staged local copy (None if not downloaded)
    extension: str
    source_id: str
    state: str
    county: str
    year: Optional[int]
    election_type: Optional[str]
    priority_score: int             # 0–10 based on filename signals
    download_status: str            # "staged" | "pending" | "failed" | "skipped"
    download_error: Optional[str]


def _priority_score(filename: str) -> int:
    """Rank a filename 0–10 by election-relevance keywords."""
    lower = filename.lower()
    score = 0
    for kw in PRIORITY_KEYWORDS:
        if kw in lower:
            score += 1
    return min(score, 10)


def _extract_file_links(html: str, base_url: str) -> list[str]:
    """Extract href links to accepted file types from HTML."""
    import re
    links: list[str] = []
    for match in re.finditer(r'href=["\']([^"\'#?]+)["\']', html, re.IGNORECASE):
        href = match.group(1).strip()
        if not href:
            continue
        # Resolve URL
        if href.startswith("http"):
            full_url = href
        elif href.startswith("/"):
            parsed = urlparse(base_url)
            full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
        else:
            full_url = urljoin(base_url, href)

        # Extension check
        ext = Path(urlparse(full_url).path).suffix.lower()
        if ext in ACCEPTED_EXTENSIONS and full_url not in links:
            links.append(full_url)

    return links


def _fetch_html(url: str) -> Optional[str]:
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "CampaignInABox-ArchiveBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log.warning(f"[DISCOVERY] HTML fetch failed {url}: {e}")
        return None


def _download_file(url: str, dest_dir: Path) -> tuple[Optional[Path], Optional[str]]:
    """Download a file to dest_dir. Returns (local_path, error)."""
    try:
        import urllib.request
        filename = Path(urlparse(url).path).name or "file"
        dest = dest_dir / filename
        # Avoid re-downloading
        if dest.exists():
            return dest, None
        req = urllib.request.Request(url, headers={"User-Agent": "CampaignInABox-ArchiveBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
        return dest, None
    except Exception as e:
        return None, str(e)


def discover_files_from_page(
    page_url: str,
    source: dict,
    download: bool = False,
    staging_subdir: Optional[str] = None,
) -> list[CandidateFile]:
    """
    Discover candidate election files from a single election page URL.

    Online mode: fetches HTML and finds file links. If download=True, stages them locally.
    Offline mode: returns empty list (no HTML fetch).

    Args:
        page_url:      URL of the election result page to scan
        source:        source registry dict (for metadata)
        download:      if True, download candidate files to staging area
        staging_subdir: subdirectory within STAGING_DIR (e.g. 'Sonoma/2024_general')

    Returns:
        list[CandidateFile]
    """
    source_id  = source.get("source_id", "unknown")
    state      = source.get("state", "")
    county     = source.get("county", "")
    year       = source.get("year")
    etype      = source.get("election_type")
    file_patterns = source.get("file_patterns", [])

    candidates: list[CandidateFile] = []

    log.info(f"[DISCOVERY] Scanning {page_url} for {source_id}")
    html = _fetch_html(page_url)
    if not html:
        log.warning(f"[DISCOVERY] Could not fetch {page_url}")
        return []

    links = _extract_file_links(html, page_url)

    # Filter by file_patterns from registry (if defined)
    if file_patterns:
        def _matches_any_pattern(url: str) -> bool:
            fname = Path(urlparse(url).path).name.lower()
            return any(fnmatch.fnmatch(fname, p.lower()) for p in file_patterns)
        links = [l for l in links if _matches_any_pattern(l)]

    # Set up staging directory
    stage_dir = STAGING_DIR
    if staging_subdir:
        stage_dir = STAGING_DIR / staging_subdir
    stage_dir.mkdir(parents=True, exist_ok=True)

    for url in links:
        filename = Path(urlparse(url).path).name
        ext = Path(filename).suffix.lower()

        # Skip rejected types even if they slipped through
        if ext in REJECTED_EXTENSIONS:
            continue

        score = _priority_score(filename)

        # Download if requested
        local_path: Optional[str] = None
        dl_status = "pending"
        dl_error: Optional[str] = None

        if download:
            lpath, err = _download_file(url, stage_dir)
            if lpath:
                local_path = str(lpath)
                dl_status = "staged"
                log.info(f"[DISCOVERY] Downloaded: {filename} → {lpath}")
            else:
                dl_status = "failed"
                dl_error = err
                log.warning(f"[DISCOVERY] Download failed {url}: {err}")

        candidates.append(CandidateFile(
            url=url, filename=filename, local_path=local_path,
            extension=ext, source_id=source_id,
            state=state, county=county, year=year, election_type=etype,
            priority_score=score, download_status=dl_status, download_error=dl_error,
        ))

    # Sort by priority score descending
    candidates.sort(key=lambda c: c.priority_score, reverse=True)
    log.info(f"[DISCOVERY] {source_id}: found {len(candidates)} candidate files from {page_url}")
    return candidates


def discover_from_local_staging(
    source: dict,
    staging_subdir: str,
) -> list[CandidateFile]:
    """
    Discover already-staged local files (for offline / re-run mode).

    Args:
        source:         source registry dict
        staging_subdir: path under STAGING_DIR

    Returns:
        list[CandidateFile] for all accepted-extension files in the directory
    """
    source_id = source.get("source_id", "unknown")
    state     = source.get("state", "")
    county    = source.get("county", "")
    year      = source.get("year")
    etype     = source.get("election_type")

    stage_dir = STAGING_DIR / staging_subdir
    if not stage_dir.exists():
        return []

    candidates: list[CandidateFile] = []
    for p in stage_dir.iterdir():
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in ACCEPTED_EXTENSIONS:
            continue
        if ext in REJECTED_EXTENSIONS:
            continue

        candidates.append(CandidateFile(
            url="file://" + str(p), filename=p.name, local_path=str(p),
            extension=ext, source_id=source_id, state=state, county=county,
            year=year, election_type=etype, priority_score=_priority_score(p.name),
            download_status="staged", download_error=None,
        ))

    candidates.sort(key=lambda c: c.priority_score, reverse=True)
    return candidates
