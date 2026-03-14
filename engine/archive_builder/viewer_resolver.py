"""
engine/archive_builder/viewer_resolver.py — Prompt 25B

Document viewer URL resolver.

Many county election websites serve files through document viewer wrappers
rather than direct download links. This module detects those patterns and
resolves them to actual file download URLs.

Supported patterns:
  - /DocumentCenter/View/<id>              CivicEngage (CivicPlus)
  - /DocumentCenter/View/<id>/filename     CivicEngage with filename hint
  - /DocumentCenter/Home/View/<id>         CivicEngage alternate path
  - /download.aspx?id=<id>                 SharePoint-style
  - /sites/default/files/documents/<file>  Drupal (direct, no resolution needed)
  - /fileadmin/<path>/<file>               TYPO3 (direct, no resolution needed)
  - /ViewFile.aspx / /GetDocument.aspx     Generic ASP.NET viewers
  - /File.aspx?id=<id>                     Generic ASP.NET viewers

Resolution methods (in order):
  1. Extract direct file link from page HTML
  2. Try appending /Download or /View suffix (CivicEngage convention)
  3. Try common extension suffixes (.xlsx, .xls, .csv)
  4. Return original URL if resolution fails (so pipeline can still try)

Public API:
  is_viewer_url(url) -> bool
  resolve_viewer_url(url, fetch_html_fn) -> ViewerResult
  resolve_batch(urls, fetch_html_fn) -> list[ViewerResult]
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse, urljoin

# Accepted extensions for election result files (Prompt 25B)
ACCEPTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv", ".zip", ".pdf"}

# ── Viewer URL detection patterns ─────────────────────────────────────────────
_VIEWER_REGEX_PATTERNS = [
    re.compile(r"/DocumentCenter/(?:View|Home/View)/(\d+)", re.IGNORECASE),
    re.compile(r"/download\.aspx", re.IGNORECASE),
    re.compile(r"/ViewFile\.aspx", re.IGNORECASE),
    re.compile(r"/GetDocument\.aspx", re.IGNORECASE),
    re.compile(r"/File\.aspx", re.IGNORECASE),
    re.compile(r"/View(?:er)?\.aspx", re.IGNORECASE),
]

# ── CivicEngage DocumentCenter specifics ─────────────────────────────────────
_CIVICENGAGE_VIEW_RE = re.compile(
    r"/DocumentCenter/(?:View|Home/View)/(\d+)(?:/([^/?#]+))?",
    re.IGNORECASE,
)

# ── Links that look like actual downloaded files ──────────────────────────────
_FILE_HREF_RE = re.compile(
    r'href\s*=\s*["\']([^"\']*\.(?:xlsx?|csv|tsv|zip|pdf)(?:\?[^"\']*)?)["\']',
    re.IGNORECASE,
)


@dataclass
class ViewerResult:
    """Result of attempting to resolve a viewer URL."""
    original_url:  str
    resolved_url:  Optional[str]   # None if resolution failed
    resolved:      bool            # True if we found a direct file URL
    method:        str             # how resolution was achieved
    error:         Optional[str]   # error message if resolution failed


# ── Pattern detection ─────────────────────────────────────────────────────────

def is_viewer_url(url: str) -> bool:
    """Return True if url matches any known document viewer pattern."""
    return any(pat.search(url) for pat in _VIEWER_REGEX_PATTERNS)


def _is_direct_file_url(url: str) -> bool:
    """Return True if url points directly to an accepted file type."""
    path = urlparse(url).path.lower()
    return Path(path).suffix in ACCEPTED_EXTENSIONS


def _extract_file_link_from_html(html: str, base_url: str) -> Optional[str]:
    """
    Scan page HTML for the first direct file download link.
    Returns absolute URL or None.
    """
    for m in _FILE_HREF_RE.finditer(html):
        raw = m.group(1).strip()
        if raw.startswith("http"):
            return raw
        elif raw.startswith("/"):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{raw}"
        else:
            return urljoin(base_url, raw)
    return None


def _civicengage_download_urls(url: str) -> list[str]:
    """
    Generate candidate download URLs for a CivicEngage /DocumentCenter/View/<id> URL.

    CivicEngage convention: appending /Download to the view URL often returns the file.
    Example:
      /DocumentCenter/View/1234        → view page
      /DocumentCenter/View/1234/Download → force-download
    """
    m = _CIVICENGAGE_VIEW_RE.search(url)
    if not m:
        return []
    doc_id   = m.group(1)
    filename = m.group(2) or ""
    parsed   = urlparse(url)
    base     = f"{parsed.scheme}://{parsed.netloc}"

    candidates: list[str] = []

    # Try /Download suffix
    candidates.append(f"{base}/DocumentCenter/View/{doc_id}/Download")

    # If we have a filename hint, derive extension candidates
    if filename:
        stem = Path(filename).stem
        for ext in (".xlsx", ".xls", ".csv"):
            candidates.append(f"{base}/DocumentCenter/View/{doc_id}/{stem}{ext}")

    # Try common election result filenames with the ID
    for name in ("statement_of_votes_cast", "precinct_results", "detailed_results", "sov"):
        for ext in (".xlsx", ".xls", ".csv"):
            candidates.append(f"{base}/DocumentCenter/View/{doc_id}/{name}{ext}")

    return candidates


# ── Resolution logic ──────────────────────────────────────────────────────────

def resolve_viewer_url(
    url: str,
    fetch_html_fn: Callable[[str], Optional[str]],
) -> ViewerResult:
    """
    Resolve a viewer URL to an actual file download URL.

    Args:
        url:           the viewer/wrapper URL to resolve
        fetch_html_fn: callable(url) -> Optional[str] that returns page HTML

    Returns:
        ViewerResult with resolved_url and method
    """
    # Direct file URL — no resolution needed
    if _is_direct_file_url(url):
        return ViewerResult(
            original_url=url,
            resolved_url=url,
            resolved=True,
            method="direct_file",
            error=None,
        )

    parsed = urlparse(url)
    base   = f"{parsed.scheme}://{parsed.netloc}"

    # ── Method 1: CivicEngage DocumentCenter ─────────────────────────────────
    if re.search(r"/DocumentCenter/", url, re.IGNORECASE):
        download_candidates = _civicengage_download_urls(url)
        for candidate in download_candidates:
            if _is_direct_file_url(candidate):
                # Extension-derived candidate — assume resolvable; try fetching
                try:
                    html = fetch_html_fn(candidate)
                    if html is not None:
                        return ViewerResult(
                            original_url=url,
                            resolved_url=candidate,
                            resolved=True,
                            method="civicengage_download_suffix",
                            error=None,
                        )
                except Exception:
                    pass

        # Fallback: fetch the view page and extract file link from HTML
        try:
            html = fetch_html_fn(url)
            if html:
                file_url = _extract_file_link_from_html(html, url)
                if file_url:
                    return ViewerResult(
                        original_url=url,
                        resolved_url=file_url,
                        resolved=True,
                        method="civicengage_html_extract",
                        error=None,
                    )
        except Exception as e:
            return ViewerResult(
                original_url=url, resolved_url=None,
                resolved=False, method="civicengage_html_extract",
                error=str(e),
            )

    # ── Method 2: Generic ASP.NET viewers (ViewFile.aspx, download.aspx) ─────
    if re.search(r"\.(aspx|asp)\b", url, re.IGNORECASE) or "download" in url.lower():
        try:
            html = fetch_html_fn(url)
            if html:
                file_url = _extract_file_link_from_html(html, url)
                if file_url:
                    return ViewerResult(
                        original_url=url,
                        resolved_url=file_url,
                        resolved=True,
                        method="aspx_html_extract",
                        error=None,
                    )
        except Exception as e:
            return ViewerResult(
                original_url=url, resolved_url=None,
                resolved=False, method="aspx_html_extract",
                error=str(e),
            )

    # ── Method 3: Try appending common extensions to URL ─────────────────────
    for ext in (".xlsx", ".xls", ".csv"):
        candidate = url.rstrip("/") + ext
        # We can't verify without fetching; just note as a candidate
        if _is_direct_file_url(candidate):
            return ViewerResult(
                original_url=url,
                resolved_url=candidate,
                resolved=True,
                method="extension_suffix",
                error=None,
            )

    # ── Fallback: return original URL, let downloader try ────────────────────
    return ViewerResult(
        original_url=url,
        resolved_url=url,
        resolved=False,
        method="passthrough",
        error="Could not resolve viewer URL to a direct file link",
    )


def resolve_batch(
    urls: list[str],
    fetch_html_fn: Callable[[str], Optional[str]],
    only_viewers: bool = True,
) -> list[ViewerResult]:
    """
    Resolve a batch of URLs. If only_viewers=True, skip non-viewer URLs.

    Returns list of ViewerResult in same order as input.
    """
    results: list[ViewerResult] = []
    for url in urls:
        if only_viewers and not is_viewer_url(url):
            results.append(ViewerResult(
                original_url=url, resolved_url=url,
                resolved=True, method="not_viewer", error=None,
            ))
        else:
            results.append(resolve_viewer_url(url, fetch_html_fn))
    return results
