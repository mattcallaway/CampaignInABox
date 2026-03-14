"""
engine/archive_builder/source_scanner.py — Prompt 25

Source Registry Scanner — discovers official election pages from registered sources.

Responsibilities:
  - Load contest_sources.yaml and geometry_sources.yaml
  - Filter sources by jurisdiction, page_type, discovery_mode
  - For each discovery_page source: fetch HTML and extract election sub-page links
  - For each election_page source: collect the direct page URL for file discovery
  - Return ScanResult per source with discovered page URLs

Safety rules:
  - Only crawl registered domains (base_url in registry)
  - Never follow links outside the registered base_url
  - Respect requires_confirmation flag — flag for user approval if set
  - Timeout all HTTP requests (10s default)
"""
from __future__ import annotations

import fnmatch
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import yaml

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REGISTRY_DIR = BASE_DIR / "config" / "source_registry"
CONTEST_REGISTRY = REGISTRY_DIR / "contest_sources.yaml"
GEOMETRY_REGISTRY = REGISTRY_DIR / "geometry_sources.yaml"

# HTTP timeout in seconds
HTTP_TIMEOUT = 10


@dataclass
class PageScanResult:
    """Result of scanning a single source registry entry."""
    source_id: str
    state: str
    county: str
    year: Optional[int]
    election_type: Optional[str]
    page_type: str                   # discovery_page | election_page
    source_url: str                  # the registry page_url
    discovered_urls: list[str]       # found election sub-page or direct URLs
    requires_confirmation: bool
    confidence: float
    error: Optional[str]
    scan_mode: str                   # "online" | "offline" | "registry_only"


def _load_registry(path: Path) -> list[dict]:
    """Load a source registry YAML file."""
    if not path.exists():
        log.warning(f"[SCANNER] Registry not found: {path}")
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data.get("sources", [])
    except Exception as e:
        log.error(f"[SCANNER] Failed to load registry {path}: {e}")
        return []


def _is_same_domain(url: str, base_url: str) -> bool:
    """Return True if url is within the registered base_url domain."""
    try:
        url_host  = urlparse(url).netloc.lower().lstrip("www.")
        base_host = urlparse(base_url).netloc.lower().lstrip("www.")
        return url_host == base_host or url_host.endswith("." + base_host)
    except Exception:
        return False


def _fetch_html(url: str, timeout: int = HTTP_TIMEOUT) -> Optional[str]:
    """Fetch HTML from a URL. Returns None on failure."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "CampaignInABox-ArchiveBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        log.warning(f"[SCANNER] HTTP fetch failed for {url}: {e}")
        return None


def _extract_links_matching_patterns(html: str, base_url: str, patterns: list[str]) -> list[str]:
    """
    Extract href links from HTML that match any of the glob patterns.
    Only returns links within the registered base_url domain.
    """
    import re
    links: list[str] = []
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE):
        href = match.group(1).strip()
        # Resolve relative URLs
        if href.startswith("http"):
            full_url = href
        elif href.startswith("/"):
            parsed = urlparse(base_url)
            full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
        else:
            full_url = urljoin(base_url, href)

        # Domain check
        if not _is_same_domain(full_url, base_url):
            continue

        # Pattern check against the URL path
        path_part = urlparse(full_url).path.lower()
        if any(fnmatch.fnmatch(path_part, p.lower()) for p in patterns):
            if full_url not in links:
                links.append(full_url)

    return links


def scan_source(
    source: dict,
    online: bool = False,
) -> PageScanResult:
    """
    Scan a single source registry entry.

    For discovery_page sources (online=True): fetches HTML and finds election sub-pages.
    For election_page sources: returns the page_url directly (no HTTP needed).
    For offline mode: returns registry page_url without HTTP.

    Args:
        source:  single source record dict from registry YAML
        online:  if True, attempt HTTP discovery for discovery_page sources

    Returns:
        PageScanResult
    """
    source_id   = source.get("source_id", "unknown")
    state       = source.get("state", "")
    county      = source.get("county", "")
    year        = source.get("year")
    election_type = source.get("election_type")
    page_type   = source.get("page_type", "election_page")
    page_url    = source.get("page_url", "")
    base_url    = source.get("base_url", page_url)
    confidence  = float(source.get("confidence_default", 0.80))
    requires_confirm = bool(source.get("requires_confirmation", True))
    discovery_patterns = source.get("discovery_patterns", [])

    discovered: list[str] = []
    error: Optional[str] = None
    mode = "registry_only"

    if page_type == "election_page" or not discovery_patterns:
        # Direct election page — use the URL as-is
        discovered = [page_url] if page_url else []
        mode = "registry_only"

    elif page_type == "discovery_page" and online:
        # Fetch HTML and extract matching links
        log.info(f"[SCANNER] Online scan: {source_id} → {page_url}")
        html = _fetch_html(page_url)
        if html:
            discovered = _extract_links_matching_patterns(html, base_url, discovery_patterns)
            mode = "online"
            if not discovered:
                log.info(f"[SCANNER] No links matched patterns for {source_id}")
        else:
            error = f"HTTP fetch failed for {page_url}"
            mode = "offline"

    elif page_type == "discovery_page" and not online:
        # Offline — return the discovery page URL itself
        discovered = [page_url] if page_url else []
        mode = "offline"

    return PageScanResult(
        source_id=source_id,
        state=state,
        county=county,
        year=year,
        election_type=election_type,
        page_type=page_type,
        source_url=page_url,
        discovered_urls=discovered,
        requires_confirmation=requires_confirm,
        confidence=confidence,
        error=error,
        scan_mode=mode,
    )


def scan_all_sources(
    state_filter: Optional[str] = None,
    county_filter: Optional[str] = None,
    online: bool = False,
    page_types: Optional[list[str]] = None,
) -> list[PageScanResult]:
    """
    Scan all sources from the contest registry.

    Args:
        state_filter:  limit to this state (e.g. 'CA')
        county_filter: limit to this county (e.g. 'Sonoma')
        online:        attempt HTTP discovery for discovery_page sources
        page_types:    filter to specific page_type values; None = all

    Returns:
        list[PageScanResult] — one per matching source entry
    """
    sources = _load_registry(CONTEST_REGISTRY)
    results: list[PageScanResult] = []

    for source in sources:
        # Filters
        if state_filter and source.get("state", "").upper() != state_filter.upper():
            continue
        if county_filter and source.get("county", "").lower() != county_filter.lower():
            continue
        if page_types and source.get("page_type") not in page_types:
            continue

        r = scan_source(source, online=online)
        results.append(r)
        log.info(
            f"[SCANNER] {r.source_id}: {len(r.discovered_urls)} URLs "
            f"({r.scan_mode}) error={r.error or 'none'}"
        )

    return results
