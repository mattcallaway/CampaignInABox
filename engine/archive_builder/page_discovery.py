"""
engine/archive_builder/page_discovery.py — Prompt 25 / Prompt 25B

Election page discovery engine.

Performs two-stage HTML traversal to identify election result pages within
registered official domains:

  Stage 1 — Identify candidate election index pages from a discovery_page source.
             Uses URL-path patterns AND keyword scoring on page content.
  Stage 2 — From each election index page, find result sub-pages containing
             downloadable election data files.

Respects:
  - official_domain_allowlist.yaml (never follows links outside)
  - Jurisdiction lock: CA / Sonoma County
  - Requires source from contest_sources.yaml with page_type=discovery_page

Public API:
  discover_election_pages(source, online, max_pages) -> list[ElectionPage]
  score_page(url, html) -> float
"""
from __future__ import annotations

import fnmatch
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import yaml

log = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parent.parent.parent
REGISTRY_DIR  = BASE_DIR / "config" / "source_registry"
ALLOWLIST_PATH = REGISTRY_DIR / "official_domain_allowlist.yaml"

HTTP_TIMEOUT = 12
RATE_LIMIT_S = 0.4   # seconds between HTTP requests

# ── Election page URL path signals ────────────────────────────────────────────
ELECTION_PATH_PATTERNS = [
    "*general-election*",
    "*primary-election*",
    "*special-election*",
    "*election-results*",
    "*election-returns*",
    "*november-election*",
    "*june-election*",
    "*march-election*",
    "*results*",
    "*statement-of-vote*",
    "*statement_of_vote*",
    "*certified*",
    "*canvass*",
]

# ── Prompt 25B: 4-factor page scoring ─────────────────────────────────────────
# Signal                           Weight   Condition
# URL contains election/results    +0.30    path match against ELECTION_PATH_PATTERNS
# "Statement of Vote" in content   +0.30    exact phrase in HTML text
# "Precinct Results" in content    +0.20    exact phrase in HTML text
# "Detailed Results" in content    +0.20    exact phrase in HTML text
# file-signal bonus (any ext link) +0.10    capped additive

MIN_PAGE_SCORE = 0.20   # pages below this score are discarded

# ── Keyword scoring (REPLACED by Prompt 25B 4-factor scoring below) ──────────
# Legacy list kept for page_links scoring heuristic only
ELECTION_CONTENT_KEYWORDS = [
    "statement of votes cast",
    "statement of vote",
    "precinct results",
    "detailed results",
    "official results",
    "election results",
    "certified results",
    "canvass results",
    "vote totals",
    "election returns",
    "final results",
    "contest totals",
    "precinct by precinct",
    "turnout by precinct",
]

# ── File-presence signals — a page with these links is a result page ──────────
RESULT_FILE_SIGNALS = [
    r"\.xlsx?\b",
    r"\.csv\b",
    r"statement_of_votes",
    r"precinct.*results",
    r"detailed.*results",
    r"sov",
]


@dataclass
class ElectionPage:
    """A discovered election result page."""
    url:               str
    source_id:         str
    state:             str
    county:            str
    year:              Optional[int]
    election_type:     Optional[str]
    page_score:        float          # 0.0–1.0 relevance score
    discovery_method:  str            # "url_pattern" | "content_keyword" | "file_signal" | "combined"
    parent_url:        str            # the discovery_page URL that led here
    has_file_links:    bool           # found download links on this page
    file_link_count:   int
    scan_error:        Optional[str]


# ── Allowlist loader (cached) ──────────────────────────────────────────────────
_ALLOWLIST_CACHE: Optional[dict] = None


def _load_allowlist() -> dict:
    global _ALLOWLIST_CACHE
    if _ALLOWLIST_CACHE is not None:
        return _ALLOWLIST_CACHE
    if not ALLOWLIST_PATH.exists():
        _ALLOWLIST_CACHE = {}
        return _ALLOWLIST_CACHE
    try:
        _ALLOWLIST_CACHE = yaml.safe_load(ALLOWLIST_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:
        log.warning(f"[PAGE_DISCOVERY] Could not load allowlist: {e}")
        _ALLOWLIST_CACHE = {}
    return _ALLOWLIST_CACHE


def _all_allowed_domains() -> set[str]:
    """Return all domains present in the allowlist (any tier)."""
    al = _load_allowlist()
    domains: set[str] = set()
    for tier_key in ("gov_tier", "official_tier", "academic_tier"):
        tier = al.get(tier_key, {})
        for d in tier.get("domains", []):
            domains.add(d.lower().lstrip("www."))
    return domains


def _is_allowed_domain(url: str, base_url: str) -> bool:
    """Return True if url is within the registered source domain."""
    try:
        url_host  = urlparse(url).netloc.lower().lstrip("www.")
        base_host = urlparse(base_url).netloc.lower().lstrip("www.")
        if url_host == base_host or url_host.endswith("." + base_host):
            return True
        # Also accept any allowlisted domain
        for allowed in _all_allowed_domains():
            if url_host == allowed or url_host.endswith("." + allowed):
                return True
        return False
    except Exception:
        return False


def _fetch_html(url: str) -> Optional[str]:
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CampaignInABox-ArchiveBuilder/1.0 (election archive research)"},
        )
        import urllib.error
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            content = resp.read()
            charset = resp.headers.get_content_charset("utf-8") or "utf-8"
            return content.decode(charset, errors="replace")
    except Exception as e:
        log.debug(f"[PAGE_DISCOVERY] fetch failed {url}: {e}")
        return None


def _extract_all_links(html: str, base_url: str) -> list[str]:
    """Extract all href links from HTML, resolving relative URLs."""
    links: list[str] = []
    for match in re.finditer(r'href=["\']([^"\'#]+)["\']', html, re.IGNORECASE):
        href = match.group(1).strip()
        if not href:
            continue
        if href.startswith("http"):
            full_url = href
        elif href.startswith("/"):
            parsed = urlparse(base_url)
            full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
        else:
            full_url = urljoin(base_url, href)
        if full_url not in links:
            links.append(full_url)
    return links


def _url_path_score(url: str) -> float:
    """Prompt 25B: URL contains election/results — +0.30."""
    path = urlparse(url).path.lower()
    for pat in ELECTION_PATH_PATTERNS:
        if fnmatch.fnmatch(path, pat):
            return 0.30
    return 0.0


def _content_keyword_score(html: str) -> float:
    """
    Prompt 25B: 4-factor content scoring.
    - "Statement of Vote" in HTML  → +0.30
    - "Precinct Results" in HTML   → +0.20
    - "Detailed Results" in HTML   → +0.20
    Max from content alone: 0.70
    """
    if not html:
        return 0.0
    html_lower = html.lower()
    score = 0.0
    if "statement of vote" in html_lower:
        score += 0.30
    if "precinct results" in html_lower:
        score += 0.20
    if "detailed results" in html_lower:
        score += 0.20
    return min(score, 0.70)


def _file_signal_score(html: str) -> float:
    """Score a page for presence of result file download signals."""
    hits = sum(1 for sig in RESULT_FILE_SIGNALS
               if re.search(sig, html, re.IGNORECASE))
    return min(hits / 3.0, 1.0)


def score_page(url: str, html: str) -> tuple[float, str]:
    """
    Prompt 25B: compute overall election-result-page relevance score.

    Scoring:
      URL contains election/results   +0.30  (_url_path_score)
      "Statement of Vote" in content  +0.30  (content term)
      "Precinct Results" in content   +0.20  (content term)
      "Detailed Results" in content   +0.20  (content term)
      File-link signal bonus          +0.10  (capped additive)

    Returns (score: float, discovery_method: str).
    Min useful score: 0.20 (MIN_PAGE_SCORE).
    """
    url_score    = _url_path_score(url)
    kw_score     = _content_keyword_score(html)
    file_score   = min(_file_signal_score(html) * 0.10, 0.10)  # capped bonus

    combined = round(min(url_score + kw_score + file_score, 1.0), 4)

    if url_score > 0 and (kw_score > 0 or file_score > 0):
        method = "combined"
    elif url_score > 0:
        method = "url_pattern"
    elif file_score > 0.05:
        method = "file_signal"
    elif kw_score > 0:
        method = "content_keyword"
    else:
        method = "none"

    return combined, method


def _count_file_links(html: str) -> int:
    """Count downloadable file links (.xlsx, .xls, .csv, .tsv, .zip) in HTML."""
    return len(re.findall(r'href=["\'][^"\']*\.(xlsx?|csv|tsv|zip)["\']', html, re.IGNORECASE))


# ── Stage 1: discovery_page → election sub-pages ──────────────────────────────

def _discover_sub_pages(
    source: dict,
    discovery_html: str,
    base_url: str,
    discovery_patterns: list[str],
) -> list[str]:
    """
    From a discovery_page HTML, extract links to election-specific sub-pages.
    Combines registry discovery_patterns with ELECTION_PATH_PATTERNS.
    """
    links = _extract_all_links(discovery_html, base_url)
    result: list[str] = []

    all_patterns = list(discovery_patterns) + ELECTION_PATH_PATTERNS

    for link in links:
        # Jurisdiction: only follow links within allowed domain
        if not _is_allowed_domain(link, base_url):
            continue
        path = urlparse(link).path.lower()
        if any(fnmatch.fnmatch(path, p.lower()) for p in all_patterns):
            if link not in result:
                result.append(link)

    return result


# ── Stage 2: election page → score + file detection ───────────────────────────

def _score_election_page(
    url: str,
    source: dict,
    parent_url: str,
    online: bool,
) -> ElectionPage:
    """Fetch and score a single candidate election result page."""
    source_id    = source.get("source_id", "unknown")
    state        = source.get("state", "CA")
    county       = source.get("county", "Sonoma")
    year         = source.get("year")
    election_type = source.get("election_type")

    # Try to extract year from URL if not in source
    if not year:
        m = re.search(r"(20\d\d)", url)
        if m:
            year = int(m.group(1))

    # Try to detect election type from URL
    if not election_type:
        url_lower = url.lower()
        if "general" in url_lower:
            election_type = "general"
        elif "primary" in url_lower:
            election_type = "primary"
        elif "special" in url_lower:
            election_type = "special"

    html: Optional[str] = None
    scan_error: Optional[str] = None
    file_link_count = 0
    has_file_links  = False

    # URL-path score (no HTTP needed)
    url_score, _ = score_page(url, html or "")

    if online:
        time.sleep(RATE_LIMIT_S)
        html = _fetch_html(url)
        if html is None:
            scan_error = f"HTTP fetch failed for {url}"

    if html:
        page_score, method = score_page(url, html)
        file_link_count = _count_file_links(html)
        has_file_links  = file_link_count > 0
    else:
        # Score on URL path alone (offline mode or fetch failure)
        page_score = url_score
        method = "url_pattern"

    return ElectionPage(
        url=url,
        source_id=source_id,
        state=state,
        county=county,
        year=year,
        election_type=election_type,
        page_score=page_score,
        discovery_method=method,
        parent_url=parent_url,
        has_file_links=has_file_links,
        file_link_count=file_link_count,
        scan_error=scan_error,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def discover_election_pages(
    source: dict,
    online: bool = False,
    max_pages: int = 30,
    min_score: float = 0.15,
) -> list[ElectionPage]:
    """
    Discover election result pages from a registered source.

    Two-stage process:
      Stage 1 — If source is discovery_page: fetch the index page and extract
                 election-specific sub-page links using discovery_patterns + path scoring.
      Stage 2 — Fetch each sub-page (online mode) or score its URL (offline mode)
                 to compute final relevance score. Return scored ElectionPage objects.

    For election_page sources: returns the source page_url directly as a single
    high-confidence ElectionPage (no traversal needed).

    Args:
        source:    source registry dict from contest_sources.yaml
        online:    if True, fetch HTML for scoring; otherwise use URL patterns only
        max_pages: maximum number of sub-pages to evaluate
        min_score: minimum page_score to include in results

    Returns:
        list[ElectionPage] sorted by page_score descending
    """
    page_type          = source.get("page_type", "election_page")
    page_url           = source.get("page_url", "")
    base_url           = source.get("base_url", page_url)
    discovery_patterns = source.get("discovery_patterns", [])
    source_id          = source.get("source_id", "unknown")

    if not page_url:
        log.warning(f"[PAGE_DISCOVERY] {source_id}: no page_url in source")
        return []

    # ── election_page: direct URL, no traversal ───────────────────────────────
    if page_type == "election_page":
        ep = _score_election_page(page_url, source, parent_url=page_url, online=online)
        # Direct source pages always qualify regardless of score
        ep.page_score = max(ep.page_score, source.get("confidence_default", 0.80))
        ep.discovery_method = "registry_direct"
        log.info(
            f"[PAGE_DISCOVERY] {source_id}: direct election_page "
            f"score={ep.page_score:.2f} files={ep.file_link_count}"
        )
        return [ep]

    # ── discovery_page: two-stage traversal ──────────────────────────────────
    log.info(f"[PAGE_DISCOVERY] {source_id}: two-stage discovery from {page_url} online={online}")

    # Stage 1: get the discovery index page
    discovery_html: Optional[str] = None
    if online:
        time.sleep(RATE_LIMIT_S)
        discovery_html = _fetch_html(page_url)
        if not discovery_html:
            log.warning(f"[PAGE_DISCOVERY] {source_id}: could not fetch discovery page {page_url}")

    if discovery_html:
        sub_page_urls = _discover_sub_pages(source, discovery_html, base_url, discovery_patterns)
    else:
        # Offline: generate candidate URLs from known path patterns + registry patterns
        sub_page_urls = [page_url]  # at minimum, score the discovery page itself

    # Deduplicate + limit
    seen: set[str] = set()
    unique_urls: list[str] = []
    for u in sub_page_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
        if len(unique_urls) >= max_pages:
            break

    log.info(f"[PAGE_DISCOVERY] {source_id}: {len(unique_urls)} sub-pages to score")

    # Stage 2: score each sub-page
    election_pages: list[ElectionPage] = []
    for url in unique_urls:
        ep = _score_election_page(url, source, parent_url=page_url, online=online)
        if ep.page_score >= min_score:
            election_pages.append(ep)
        else:
            log.debug(f"[PAGE_DISCOVERY] Dropped low-score page: {url} score={ep.page_score:.2f}")

    # Sort by score descending
    election_pages.sort(key=lambda e: e.page_score, reverse=True)

    log.info(
        f"[PAGE_DISCOVERY] {source_id}: {len(election_pages)} election pages "
        f"(min_score={min_score}) from {len(unique_urls)} candidates"
    )
    return election_pages


def discover_all_sources(
    sources: list[dict],
    online: bool = False,
    state_filter: str = "CA",
    county_filter: str = "Sonoma",
    max_pages_per_source: int = 20,
    min_score: float = 0.15,
) -> list[ElectionPage]:
    """
    Discover election pages from all matching source registry entries.

    Jurisdiction lock: only sources matching state_filter + county_filter
    (or state-level sources for state_filter) are processed.

    Returns:
        list[ElectionPage] sorted by page_score descending, deduplicated by URL
    """
    all_pages: list[ElectionPage] = []
    seen_urls: set[str] = set()

    for source in sources:
        src_state  = source.get("state", "").upper()
        src_county = source.get("county", "").lower()

        # Jurisdiction lock
        if src_state != state_filter.upper():
            continue
        if src_county and src_county != county_filter.lower():
            continue  # county-level source for wrong county

        pages = discover_election_pages(
            source, online=online,
            max_pages=max_pages_per_source,
            min_score=min_score,
        )
        for ep in pages:
            if ep.url not in seen_urls:
                seen_urls.add(ep.url)
                all_pages.append(ep)

    all_pages.sort(key=lambda e: e.page_score, reverse=True)
    log.info(
        f"[PAGE_DISCOVERY] Total: {len(all_pages)} unique election pages "
        f"from {len(sources)} sources"
    )
    return all_pages
