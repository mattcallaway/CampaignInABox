"""
engine/archive_builder/link_extractor.py — Prompt 25B

Comprehensive link extraction engine.

Extracts links from HTML using all possible sources:
  - <a href="..."> standard anchors
  - <button onclick="..."> onclick JS handlers
  - <iframe src="..."> embedded frames
  - window.open('...') JavaScript calls
  - data-document-url and data-url attributes (CivicPlus / custom viewers)
  - href="...xls..." / href="...csv..." direct file URL patterns
  - /DocumentCenter/View/<id> — Civica CivicEngage viewer links
  - /download.aspx?id=... — SharePoint-style downloads

All links are normalized to absolute URLs relative to the page's base_url.
Links are deduplicated before return.

Public API:
  extract_links(html, base_url) -> ExtractedLinks
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse, urlencode, parse_qs, unquote

# ── Accepted file extensions for candidate election files (Prompt 25B adds .pdf) ──
ACCEPTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv", ".zip", ".pdf"}

# ── Viewer URL patterns ────────────────────────────────────────────────────────
VIEWER_PATTERNS = [
    r"/DocumentCenter/View/",
    r"/DocumentCenter/Home/View/",
    r"/download\.aspx",
    r"/Download\.aspx",
    r"/sites/default/files/documents/",
    r"/fileadmin/",
    r"/ViewFile\.aspx",
    r"/GetDocument\.aspx",
    r"/File\.aspx",
]


@dataclass
class ExtractedLinks:
    """All links extracted from a single HTML page."""
    base_url:      str
    all_links:     list[str] = field(default_factory=list)   # every unique absolute URL found
    file_links:    list[str] = field(default_factory=list)   # links to accepted file types
    viewer_links:  list[str] = field(default_factory=list)   # document viewer URLs
    js_links:      list[str] = field(default_factory=list)   # links found in JS (window.open etc.)
    page_links:    list[str] = field(default_factory=list)   # links to HTML pages (for recursion)
    extraction_counts: dict[str, int] = field(default_factory=dict)


def _normalize_url(href: str, base_url: str) -> Optional[str]:
    """Normalize a raw href/src into an absolute URL. Returns None if unparseable."""
    if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    href = href.strip().split("#")[0]   # strip fragments
    if not href:
        return None
    try:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        elif href.startswith("//"):
            scheme = urlparse(base_url).scheme or "https"
            return f"{scheme}:{href}"
        elif href.startswith("/"):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{href}"
        else:
            return urljoin(base_url, href)
    except Exception:
        return None


def _is_file_url(url: str) -> bool:
    """Return True if url points to an accepted file extension."""
    path = urlparse(url).path.lower()
    return Path(path).suffix in ACCEPTED_EXTENSIONS


def _is_viewer_url(url: str) -> bool:
    """Return True if url matches a known document viewer pattern."""
    url_lower = url.lower()
    return any(re.search(pat, url, re.IGNORECASE) for pat in VIEWER_PATTERNS)


def _is_page_url(url: str) -> bool:
    """Return True if url looks like an HTML page (not a file, not a viewer)."""
    path = urlparse(url).path.lower()
    ext  = Path(path).suffix
    if not ext or ext in (".htm", ".html", ".asp", ".aspx", ".php", ".cfm", ""):
        return True
    return False


# ── Extraction functions ──────────────────────────────────────────────────────

def _extract_href_links(html: str, base_url: str) -> list[str]:
    """Extract all href="..." values from HTML anchor tags."""
    hrefs: list[str] = []
    for m in re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE):
        url = _normalize_url(m.group(1), base_url)
        if url:
            hrefs.append(url)
    # Also find unquoted hrefs
    for m in re.finditer(r'href\s*=\s*([^\s>"\']+)', html, re.IGNORECASE):
        url = _normalize_url(m.group(1), base_url)
        if url and url not in hrefs:
            hrefs.append(url)
    return hrefs


def _extract_onclick_links(html: str, base_url: str) -> list[str]:
    """Extract URLs from onclick and onclick-style JS attributes."""
    links: list[str] = []
    # onclick="location.href='...'" or onclick="window.location='...'"
    for pat in [
        r"onclick\s*=\s*[\"'][^\"']*(?:location\.href|window\.location)\s*=\s*['\"]([^'\"]+)['\"]",
        r"onclick\s*=\s*[\"'][^\"']*window\.open\s*\(\s*['\"]([^'\"]+)['\"]",
    ]:
        for m in re.finditer(pat, html, re.IGNORECASE):
            url = _normalize_url(m.group(1), base_url)
            if url:
                links.append(url)
    return links


def _extract_iframe_links(html: str, base_url: str) -> list[str]:
    """Extract src="..." from iframe tags."""
    links: list[str] = []
    for m in re.finditer(r'<iframe[^>]+src\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE):
        url = _normalize_url(m.group(1), base_url)
        if url:
            links.append(url)
    return links


def _extract_window_open_links(html: str, base_url: str) -> list[str]:
    """Extract URLs from window.open('...') JavaScript calls."""
    links: list[str] = []
    for m in re.finditer(r"window\.open\s*\(\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE):
        url = _normalize_url(m.group(1), base_url)
        if url:
            links.append(url)
    # Also location.assign and location.replace
    for pat in [r"location\.assign\s*\(\s*['\"]([^'\"]+)['\"]",
                r"location\.replace\s*\(\s*['\"]([^'\"]+)['\"]"]:
        for m in re.finditer(pat, html, re.IGNORECASE):
            url = _normalize_url(m.group(1), base_url)
            if url and url not in links:
                links.append(url)
    return links


def _extract_data_attribute_links(html: str, base_url: str) -> list[str]:
    """Extract URLs from data-* attributes commonly used by CivicPlus platforms."""
    links: list[str] = []
    for attr in ("data-document-url", "data-url", "data-href", "data-src", "data-download-url"):
        for m in re.finditer(
            rf'{attr}\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE
        ):
            url = _normalize_url(m.group(1), base_url)
            if url:
                links.append(url)
    return links


def _extract_document_center_links(html: str, base_url: str) -> list[str]:
    """Extract CivicEngage DocumentCenter/View/<id> patterns from raw HTML text."""
    links: list[str] = []
    parsed = urlparse(base_url)
    base   = f"{parsed.scheme}://{parsed.netloc}"

    # /DocumentCenter/View/1234 or /DocumentCenter/View/1234/filename
    for m in re.finditer(r'(/DocumentCenter/(?:View|Home/View)/\d+[^\s"\'<>]*)', html, re.IGNORECASE):
        path = m.group(1).split("?")[0]   # strip query string
        url  = base + path
        if url not in links:
            links.append(url)

    # /download.aspx?id=... patterns
    for m in re.finditer(r'(/[^"\'<>\s]*download\.aspx\?[^"\'<>\s]+)', html, re.IGNORECASE):
        url = _normalize_url(m.group(1), base_url)
        if url and url not in links:
            links.append(url)

    return links


def _extract_src_script_links(html: str, base_url: str) -> list[str]:
    """Extract file URLs embedded as string literals in <script> blocks."""
    links: list[str] = []
    # Find all JS string literals that look like file paths
    for m in re.finditer(r'["\']([^"\']*\.(?:xlsx?|csv|tsv|zip|pdf))["\']', html, re.IGNORECASE):
        raw = m.group(1)
        url = _normalize_url(raw, base_url)
        if url:
            links.append(url)
    return links


# ── Public API ────────────────────────────────────────────────────────────────

def extract_links(html: str, base_url: str) -> ExtractedLinks:
    """
    Extract all links from an HTML page using 7 extraction methods.

    Args:
        html:      raw HTML string
        base_url:  absolute URL of the page (for resolving relative links)

    Returns:
        ExtractedLinks with categorised, deduplicated absolute URLs
    """
    result = ExtractedLinks(base_url=base_url)
    seen:  set[str] = set()
    counts: dict[str, int] = {}

    def _add(urls: list[str], source: str, target_list: list[str]) -> None:
        n = 0
        for url in urls:
            if url and url not in seen:
                seen.add(url)
                result.all_links.append(url)
                target_list.append(url)
                n += 1
        counts[source] = n

    # Run all 7 extractors and categorize each link
    _href          = _extract_href_links(html, base_url)
    _onclick       = _extract_onclick_links(html, base_url)
    _iframe        = _extract_iframe_links(html, base_url)
    _window        = _extract_window_open_links(html, base_url)
    _data_attr     = _extract_data_attribute_links(html, base_url)
    _doc_center    = _extract_document_center_links(html, base_url)
    _script        = _extract_src_script_links(html, base_url)

    raw_js = _onclick + _window
    raw_viewer = _doc_center
    raw_all = _href + _onclick + _iframe + _window + _data_attr + _doc_center + _script

    counts["href"]          = len(_href)
    counts["onclick"]       = len(_onclick)
    counts["iframe"]        = len(_iframe)
    counts["window_open"]   = len(_window)
    counts["data_attr"]     = len(_data_attr)
    counts["doc_center"]    = len(_doc_center)
    counts["script"]        = len(_script)

    for url in raw_all:
        if url in seen:
            continue
        seen.add(url)
        result.all_links.append(url)

        if _is_file_url(url):
            result.file_links.append(url)
        elif _is_viewer_url(url):
            result.viewer_links.append(url)
        elif _is_page_url(url):
            result.page_links.append(url)

    # JS links are those from JS sources that aren't already files
    for url in raw_js:
        if url in (result.file_links + result.viewer_links):
            continue
        if url not in result.js_links:
            result.js_links.append(url)

    # Viewer links from doc_center patterns
    for url in raw_viewer:
        if url not in result.viewer_links:
            result.viewer_links.append(url)

    result.extraction_counts = counts
    return result


def filter_same_domain(links: list[str], base_url: str) -> list[str]:
    """Filter a list of links to only those within the same domain as base_url."""
    base_host = urlparse(base_url).netloc.lower().lstrip("www.")
    result: list[str] = []
    for lnk in links:
        host = urlparse(lnk).netloc.lower().lstrip("www.")
        if host == base_host or host.endswith("." + base_host):
            result.append(lnk)
    return result
