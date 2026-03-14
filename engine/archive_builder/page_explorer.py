"""
engine/archive_builder/page_explorer.py — Prompt 25B

Recursive election page exploration engine (depth-limited).

Replaces the flat two-stage page traversal with a proper depth-limited
recursive crawler that uses link_extractor + viewer_resolver to find all
election result files on county election websites.

Depth semantics:
  Depth 0 → registry index / discovery pages (start_urls)
  Depth 1 → election result pages
  Depth 2 → intermediate document pages
  Depth 3 → final file link pages / directory listings

Rules:
  - Visited URL set prevents loops
  - Only follows links within jurisdiction-allowed domains (allowlist + source domain)
  - Pages scoring < MIN_PAGE_SCORE at depth > 0 are pruned (no recursion)
  - viewer_resolver is applied to all viewer-pattern URLs at any depth
  - file_links collected at all depths are returned as candidate downloads
  - Rate-limited HTTP (RATE_LIMIT_S between requests)
  - HTTP timeout enforced per request

Public API:
  explore_election_pages(
      start_urls, source, depth_limit=3, online=False, state="CA", county="Sonoma"
  ) -> ExplorationResult
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

log = logging.getLogger(__name__)

HTTP_TIMEOUT  = 12
RATE_LIMIT_S  = 0.5
MIN_PAGE_SCORE = 0.10          # pages below this at depth > 0 are pruned
MAX_PAGES_PER_DEPTH = 25       # safety cap per depth level


@dataclass
class ExploredPage:
    """A single page visited during recursive exploration."""
    url:            str
    depth:          int
    score:          float
    file_links:     list[str] = field(default_factory=list)
    viewer_links:   list[str] = field(default_factory=list)
    page_links:     list[str] = field(default_factory=list)
    js_links:       list[str] = field(default_factory=list)
    resolved_files: list[str] = field(default_factory=list)   # after viewer resolution
    fetch_error:    Optional[str] = None
    fetched:        bool = False


@dataclass
class ExplorationResult:
    """Summary result from a full recursive exploration run."""
    source_id:        str
    state:            str
    county:           str
    start_urls:       list[str]
    depth_limit:      int
    pages_visited:    int
    pages_fetched:    int
    pages_pruned:     int
    links_extracted:  int
    viewer_links_found: int
    viewer_links_resolved: int
    candidate_file_urls: list[str]   # all discovered file URLs (before download)
    explored_pages:   list[ExploredPage]
    errors:           list[str]


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _fetch_html(url: str, timeout: int = HTTP_TIMEOUT) -> Optional[str]:
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CampaignInABox-ArchiveBuilder/1.0 (election archive research)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset("utf-8") or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception as e:
        log.debug(f"[EXPLORER] fetch failed {url}: {e}")
        return None


# ── Domain jurisdiction check ─────────────────────────────────────────────────

def _load_allowed_domains() -> set[str]:
    """Load all allowed domains from the official_domain_allowlist.yaml."""
    allowed: set[str] = set()
    try:
        allowlist_path = (
            Path(__file__).resolve().parent.parent.parent
            / "config" / "source_registry" / "official_domain_allowlist.yaml"
        )
        import yaml
        data = yaml.safe_load(allowlist_path.read_text(encoding="utf-8")) or {}
        for tier in ("gov_tier", "official_tier", "academic_tier"):
            for d in data.get(tier, {}).get("domains", []):
                allowed.add(d.lower().lstrip("www."))
    except Exception as e:
        log.warning(f"[EXPLORER] Could not load allowlist: {e}")
    return allowed


_ALLOWED_DOMAINS_CACHE: Optional[set[str]] = None


def _is_allowed(url: str, source_base_url: str) -> bool:
    """Return True if url is within the source domain or any allowlisted domain."""
    global _ALLOWED_DOMAINS_CACHE
    if _ALLOWED_DOMAINS_CACHE is None:
        _ALLOWED_DOMAINS_CACHE = _load_allowed_domains()
    try:
        host      = urlparse(url).netloc.lower().lstrip("www.")
        base_host = urlparse(source_base_url).netloc.lower().lstrip("www.")
        # Same domain as source
        if host == base_host or host.endswith("." + base_host):
            return True
        # In allowlist
        for allowed in _ALLOWED_DOMAINS_CACHE:
            if host == allowed or host.endswith("." + allowed):
                return True
    except Exception:
        pass
    return False


# ── Recursive explorer ────────────────────────────────────────────────────────

def _explore_url(
    url: str,
    depth: int,
    depth_limit: int,
    visited: set[str],
    source_base_url: str,
    online: bool,
    all_candidate_files: list[str],
    explored_pages: list[ExploredPage],
    errors: list[str],
    counters: dict,
) -> None:
    """
    Recursively explore a single URL up to depth_limit.
    Mutates visited, all_candidate_files, explored_pages, counters in place.
    """
    from engine.archive_builder.link_extractor import extract_links, filter_same_domain
    from engine.archive_builder.viewer_resolver import is_viewer_url, resolve_viewer_url
    from engine.archive_builder.page_discovery import score_page

    if url in visited:
        return
    visited.add(url)
    counters["pages_visited"] += 1

    ep = ExploredPage(url=url, depth=depth, score=0.0)
    explored_pages.append(ep)

    # Score on URL alone first (no HTTP needed)
    url_score, _ = score_page(url, "")

    # Prune low-score pages at depth > 0 to avoid wasting HTTP requests
    if depth > 0 and url_score < MIN_PAGE_SCORE and not online:
        counters["pages_pruned"] += 1
        return

    # Fetch HTML if online
    html: Optional[str] = None
    if online:
        time.sleep(RATE_LIMIT_S)
        html = _fetch_html(url)
        ep.fetched = html is not None
        if html is not None:
            counters["pages_fetched"] += 1
        else:
            ep.fetch_error = f"HTTP fetch failed for {url}"
            errors.append(ep.fetch_error)

    # Compute final score
    final_score, method = score_page(url, html or "")
    ep.score = final_score

    # Prune if score too low (post-fetch)
    if depth > 0 and final_score < MIN_PAGE_SCORE:
        counters["pages_pruned"] += 1
        return

    # Extract links from this page
    if html:
        extracted = extract_links(html, url)
        ep.file_links   = extracted.file_links
        ep.viewer_links = extracted.viewer_links
        ep.page_links   = extracted.page_links
        ep.js_links     = extracted.js_links
        counters["links_extracted"] += len(extracted.all_links)
        counters["viewer_links_found"] += len(extracted.viewer_links)
    else:
        extracted = None

    # Collect direct file links at any depth
    for file_url in ep.file_links:
        if file_url not in all_candidate_files:
            all_candidate_files.append(file_url)

    # Resolve viewer links
    for viewer_url in ep.viewer_links:
        counters["viewer_links_found"] += 1
        vr = resolve_viewer_url(viewer_url, _fetch_html)
        if vr.resolved and vr.resolved_url and vr.resolved_url not in all_candidate_files:
            all_candidate_files.append(vr.resolved_url)
            ep.resolved_files.append(vr.resolved_url)
            counters["viewer_links_resolved"] += 1
            log.info(
                f"[EXPLORER] Viewer resolved: {viewer_url} → {vr.resolved_url} "
                f"(method={vr.method})"
            )

    # Check JS links for file patterns too
    for js_url in ep.js_links:
        from engine.archive_builder.link_extractor import ACCEPTED_EXTENSIONS
        from pathlib import Path as _P
        if _P(urlparse(js_url).path).suffix.lower() in ACCEPTED_EXTENSIONS:
            if js_url not in all_candidate_files:
                all_candidate_files.append(js_url)

    # ── Recurse into page links (if not at depth limit) ──────────────────────
    if depth < depth_limit and html:
        # Gather all page links and filter by domain
        next_pages = filter_same_domain(ep.page_links + ep.js_links, source_base_url)

        # De-duplicate and cap per depth
        new_pages = [p for p in next_pages
                     if p not in visited
                     and _is_allowed(p, source_base_url)][:MAX_PAGES_PER_DEPTH]

        for next_url in new_pages:
            _explore_url(
                url=next_url,
                depth=depth + 1,
                depth_limit=depth_limit,
                visited=visited,
                source_base_url=source_base_url,
                online=online,
                all_candidate_files=all_candidate_files,
                explored_pages=explored_pages,
                errors=errors,
                counters=counters,
            )


# ── Public API ────────────────────────────────────────────────────────────────

def explore_election_pages(
    start_urls: list[str],
    source: dict,
    depth_limit: int = 3,
    online: bool = False,
    state: str = "CA",
    county: str = "Sonoma",
) -> ExplorationResult:
    """
    Recursively explore election result pages starting from start_urls.

    Depth 0: start_urls (registry pages or election index pages)
    Depth 1: election result pages linked from index
    Depth 2: intermediate document pages
    Depth 3: final file link pages (directory listings, viewer pages)

    Args:
        start_urls:  list of root URLs to begin exploration
        source:      source registry dict (for source_id, base_url, etc.)
        depth_limit: maximum recursion depth (0–3, default 3)
        online:      if True, fetch HTML at each depth
        state:       jurisdiction state (CA)
        county:      jurisdiction county (Sonoma)

    Returns:
        ExplorationResult with all candidate file URLs and metrics
    """
    source_id       = source.get("source_id", "unknown")
    source_base_url = source.get("base_url", start_urls[0] if start_urls else "")

    visited:             set[str] = set()
    all_candidate_files: list[str] = []
    explored_pages:      list[ExploredPage] = []
    errors:              list[str] = []
    counters: dict = {
        "pages_visited":         0,
        "pages_fetched":         0,
        "pages_pruned":          0,
        "links_extracted":       0,
        "viewer_links_found":    0,
        "viewer_links_resolved": 0,
    }

    log.info(
        f"[EXPLORER] {source_id}: exploring {len(start_urls)} start URLs "
        f"depth_limit={depth_limit} online={online}"
    )

    for url in start_urls:
        _explore_url(
            url=url,
            depth=0,
            depth_limit=depth_limit,
            visited=visited,
            source_base_url=source_base_url,
            online=online,
            all_candidate_files=all_candidate_files,
            explored_pages=explored_pages,
            errors=errors,
            counters=counters,
        )

    # Jurisdiction filter: remove cross-jurisdiction candidates
    from urllib.parse import urlparse as _up
    safe_files = [
        f for f in all_candidate_files
        if _is_allowed(f, source_base_url)
    ]
    cross_jurisdiction = [f for f in all_candidate_files if f not in safe_files]
    if cross_jurisdiction:
        log.warning(
            f"[EXPLORER] {source_id}: blocked {len(cross_jurisdiction)} cross-jurisdiction "
            f"candidate URLs"
        )
        errors.extend(
            f"BLOCKED_CROSS_JURISDICTION: {u}" for u in cross_jurisdiction
        )

    log.info(
        f"[EXPLORER] {source_id}: done. "
        f"pages={counters['pages_visited']} "
        f"files={len(safe_files)} "
        f"viewers_resolved={counters['viewer_links_resolved']} "
        f"errors={len(errors)}"
    )

    return ExplorationResult(
        source_id=source_id,
        state=state,
        county=county,
        start_urls=start_urls,
        depth_limit=depth_limit,
        pages_visited=counters["pages_visited"],
        pages_fetched=counters["pages_fetched"],
        pages_pruned=counters["pages_pruned"],
        links_extracted=counters["links_extracted"],
        viewer_links_found=counters["viewer_links_found"],
        viewer_links_resolved=counters["viewer_links_resolved"],
        candidate_file_urls=safe_files,
        explored_pages=explored_pages,
        errors=errors,
    )
