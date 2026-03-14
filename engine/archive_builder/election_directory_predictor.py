"""
engine/archive_builder/election_directory_predictor.py — Prompt 25C

Election Directory Predictor: deterministic result folder discovery.

Instead of relying solely on recursive crawling, this module generates
likely directory paths where Sonoma County election result files are stored,
tests those paths via HTTP, classifies confirmed pages, and extracts
candidate file URLs.

Strategy:
  1. Generate predicted URLs: 10 path templates × 5 years = 50 candidates
  2. HTTP-test each (200=valid, 301/302=follow, 404/403=discard)
  3. Score and classify confirmed pages (ELECTION_RESULTS_PAGE vs OTHER)
  4. Extract file links from confirmed pages using link_extractor
  5. Resolve viewer links via viewer_resolver
  6. Return PredictionResult with confirmed_dirs and file_candidates

All candidate URLs must pass jurisdiction check (CA/Sonoma domain allowlist).
Files from confirmed directories receive directory_priority = "HIGH",
which adds +0.10 to candidate_score downstream in file_discovery.

Public API:
  predict_election_result_paths(domain, years, online=False, state, county)
      -> PredictionResult
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

HTTP_TIMEOUT   = 8       # seconds per probe
RATE_LIMIT_S   = 0.4    # seconds between HTTP requests
MAX_REDIRECTS  = 3

# ── Default target years ───────────────────────────────────────────────────────
DEFAULT_YEARS = [2024, 2023, 2022, 2021, 2020]

# ── Election result page classification keywords ───────────────────────────────
ELECTION_PAGE_KEYWORDS = [
    "statement of vote",
    "detailed results",
    "precinct results",
    "election summary",
    "official results",
]

# ── 10 path template patterns ──────────────────────────────────────────────────
# {year} is replaced with each target year.
# Templates without {year} are tested once (base directory paths).
PATH_TEMPLATES = [
    "/elections/election-results",
    "/elections/results",
    "/elections/election-results/{year}",
    "/elections/results/{year}",
    "/registrar-of-voters/election-results",
    "/registrar-of-voters/elections/{year}",
    "/government/registrar-of-voters/election-results",
    "/elections/election-results/{year}-general-election",
    "/elections/election-results/{year}-primary-election",
    "/elections/election-results/{year}-special-election",
]


@dataclass
class ConfirmedDirectory:
    """A confirmed election result directory page."""
    url:              str
    http_status:      int
    final_url:        str                    # after any redirects
    page_score:       float
    classified_as:    str                    # ELECTION_RESULTS_PAGE | OTHER
    file_candidates:  list[str]             # file URLs found on this page
    viewer_links:     list[str]             # viewer URLs found (pre-resolution)
    resolved_files:   list[str]             # file URLs after viewer resolution
    year:             Optional[int]          # year extracted from URL template
    template:         str                    # which PATH_TEMPLATE matched
    directory_priority: str = "HIGH"        # always HIGH for predictor results


@dataclass
class PredictionResult:
    """Result from a full directory prediction run."""
    domain:            str
    state:             str
    county:            str
    years:             list[int]
    predicted_urls:    list[str]            # all 50 candidate URLs
    confirmed_dirs:    list[ConfirmedDirectory]
    file_candidates:   list[str]            # all file URLs, deduplicated
    metrics: dict = field(default_factory=dict)
    errors:  list[str] = field(default_factory=list)


# ── Domain jurisdiction check ─────────────────────────────────────────────────

def _load_allowed_domains() -> set[str]:
    try:
        import yaml
        p = BASE_DIR / "config" / "source_registry" / "official_domain_allowlist.yaml"
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        result: set[str] = set()
        for tier in ("gov_tier", "official_tier", "academic_tier"):
            for d in data.get(tier, {}).get("domains", []):
                result.add(d.lower().lstrip("www."))
        return result
    except Exception as e:
        log.warning(f"[PREDICTOR] Could not load allowlist: {e}")
        return set()


_ALLOWED_CACHE: Optional[set[str]] = None


def _is_allowed_domain(url: str) -> bool:
    global _ALLOWED_CACHE
    if _ALLOWED_CACHE is None:
        _ALLOWED_CACHE = _load_allowed_domains()
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        for allowed in _ALLOWED_CACHE:
            if host == allowed or host.endswith("." + allowed):
                return True
    except Exception:
        pass
    return False


# ── URL generation ────────────────────────────────────────────────────────────

def _generate_predicted_urls(domain: str, years: list[int]) -> list[tuple[str, str, Optional[int]]]:
    """
    Generate (url, template, year) tuples for all path templates × years.

    Templates without {year} are emitted once (year=None).
    Templates with {year} are emitted once per year.
    Domain is stripped of trailing slash.
    """
    domain = domain.rstrip("/")
    seen: set[str] = set()
    results: list[tuple[str, str, Optional[int]]] = []

    for template in PATH_TEMPLATES:
        if "{year}" in template:
            for year in years:
                path = template.format(year=year)
                url  = domain + path
                if url not in seen:
                    seen.add(url)
                    results.append((url, template, year))
        else:
            url = domain + template
            if url not in seen:
                seen.add(url)
                results.append((url, template, None))

    return results


# ── HTTP probe ────────────────────────────────────────────────────────────────

def _probe_url(url: str) -> tuple[int, str, Optional[str]]:
    """
    Probe a URL.

    Returns (http_status, final_url, html_or_None).
    Follows up to MAX_REDIRECTS manually so we capture the final URL.
    """
    import urllib.request
    import urllib.error

    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        try:
            req = urllib.request.Request(
                current_url,
                headers={"User-Agent": "CampaignInABox-ArchiveBuilder/1.0"},
            )
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                status   = resp.status
                final    = resp.url
                charset  = resp.headers.get_content_charset("utf-8") or "utf-8"
                html     = resp.read().decode(charset, errors="replace")
                return status, final, html
        except urllib.error.HTTPError as e:
            return e.code, current_url, None
        except urllib.error.URLError as e:
            reason = str(e.reason)
            if "Errno 11001" in reason or "getaddrinfo failed" in reason:
                log.debug(f"[PREDICTOR] DNS fail (offline?): {current_url}")
            else:
                log.debug(f"[PREDICTOR] URLError {current_url}: {e.reason}")
            return 0, current_url, None
        except Exception as e:
            log.debug(f"[PREDICTOR] Probe failed {current_url}: {e}")
            return 0, current_url, None

    return 0, current_url, None


# ── Page classification ───────────────────────────────────────────────────────

def _score_election_page(html: str) -> tuple[float, str]:
    """
    Score an HTML page for election result content.

    Returns (score, classification).
    classification = ELECTION_RESULTS_PAGE | OTHER
    """
    if not html:
        return 0.0, "OTHER"
    lower = html.lower()
    hits  = sum(1 for kw in ELECTION_PAGE_KEYWORDS if kw in lower)
    score = round(min(hits / len(ELECTION_PAGE_KEYWORDS), 1.0), 3)
    classification = "ELECTION_RESULTS_PAGE" if hits >= 1 else "OTHER"
    return score, classification


# ── File extraction from a confirmed page ────────────────────────────────────

def _extract_files_from_page(
    html: str,
    base_url: str,
) -> tuple[list[str], list[str], list[str]]:
    """
    Extract file links and viewer links from a confirmed directory page.

    Returns (file_links, viewer_links, resolved_files).
    """
    try:
        from engine.archive_builder.link_extractor import extract_links
        from engine.archive_builder.viewer_resolver import resolve_batch

        extracted     = extract_links(html, base_url)
        file_links    = extracted.file_links
        viewer_links  = extracted.viewer_links

        # Resolve viewer links (no HTTP fetch in offline mode — passthrough)
        def _noop_fetch(url: str) -> Optional[str]:
            return None

        viewer_results = resolve_batch(viewer_links, _noop_fetch, only_viewers=True)
        resolved_files = [
            vr.resolved_url for vr in viewer_results
            if vr.resolved and vr.resolved_url
        ]

        return file_links, viewer_links, resolved_files
    except Exception as e:
        log.warning(f"[PREDICTOR] Link extraction failed for {base_url}: {e}")
        return [], [], []


# ── Main public function ──────────────────────────────────────────────────────

def predict_election_result_paths(
    domain: str,
    years: Optional[list[int]] = None,
    online: bool = False,
    state: str = "CA",
    county: str = "Sonoma",
) -> PredictionResult:
    """
    Predict and test election result directory paths on a county elections website.

    Generates 10 path templates × len(years) candidate URLs, probes each via HTTP
    (if online=True), classifies confirmed pages, and extracts candidate file URLs.

    Args:
        domain:  base URL of the county elections website (e.g. "https://sonomacounty.ca.gov")
        years:   list of election years to predict (default: [2024, 2023, 2022, 2021, 2020])
        online:  if True, perform HTTP probes; if False, return predicted paths only
        state:   jurisdiction state (CA)
        county:  jurisdiction county (Sonoma)

    Returns:
        PredictionResult with confirmed_dirs, file_candidates, and metrics
    """
    if years is None:
        years = DEFAULT_YEARS

    # Jurisdiction guard
    if not _is_allowed_domain(domain):
        log.warning(f"[PREDICTOR] Domain {domain} is NOT in allowlist — aborting")
        return PredictionResult(
            domain=domain, state=state, county=county, years=years,
            predicted_urls=[], confirmed_dirs=[], file_candidates=[],
            metrics={}, errors=[f"BLOCKED_CROSS_JURISDICTION: domain {domain} not in allowlist"],
        )

    candidates    = _generate_predicted_urls(domain, years)
    predicted_urls = [c[0] for c in candidates]
    log.info(f"[PREDICTOR] Generated {len(predicted_urls)} predicted URLs for {domain}")

    confirmed_dirs:  list[ConfirmedDirectory] = []
    all_file_candidates: list[str] = []
    errors: list[str] = []

    metrics = {
        "predicted":          len(predicted_urls),
        "tested":             0,
        "http_200":           0,
        "http_redirect":      0,
        "http_404_403":       0,
        "http_error":         0,
        "classified_results": 0,
        "classified_other":   0,
        "files_found":        0,
        "viewers_resolved":   0,
    }

    if not online:
        log.info(f"[PREDICTOR] offline=True — returning predicted URLs without HTTP probing")
        return PredictionResult(
            domain=domain, state=state, county=county, years=years,
            predicted_urls=predicted_urls,
            confirmed_dirs=[],
            file_candidates=[],
            metrics=metrics,
            errors=[],
        )

    # ── Online: probe each candidate URL ─────────────────────────────────────
    for idx, (url, template, year) in enumerate(candidates):
        if idx > 0:
            time.sleep(RATE_LIMIT_S)

        log.info(f"[PREDICTOR] Probing [{idx+1}/{len(candidates)}]: {url}")
        status, final_url, html = _probe_url(url)
        metrics["tested"] += 1

        if status == 200:
            metrics["http_200"] += 1
        elif status in (301, 302, 303, 307, 308):
            metrics["http_redirect"] += 1
            log.debug(f"[PREDICTOR] Redirect {status}: {url} → {final_url}")
        elif status in (404, 403, 0):
            if status in (404, 403):
                metrics["http_404_403"] += 1
            else:
                metrics["http_error"] += 1
            continue
        else:
            metrics["http_error"] += 1
            log.debug(f"[PREDICTOR] Unexpected status {status}: {url}")
            continue

        # Score the page
        page_score, classification = _score_election_page(html or "")

        if classification == "ELECTION_RESULTS_PAGE":
            metrics["classified_results"] += 1
        else:
            metrics["classified_other"] += 1
            # Still register the directory, but note it's general content
            log.debug(f"[PREDICTOR] Page at {final_url} classified as OTHER (score={page_score})")

        # Extract file links from the page
        file_links, viewer_links, resolved_files = _extract_files_from_page(
            html or "", final_url
        )
        metrics["files_found"]       += len(file_links) + len(resolved_files)
        metrics["viewers_resolved"]  += len(resolved_files)

        # Collect unique candidates
        for fu in file_links + resolved_files:
            if fu not in all_file_candidates:
                all_file_candidates.append(fu)

        confirmed_dirs.append(ConfirmedDirectory(
            url=url,
            http_status=status,
            final_url=final_url,
            page_score=page_score,
            classified_as=classification,
            file_candidates=file_links,
            viewer_links=viewer_links,
            resolved_files=resolved_files,
            year=year,
            template=template,
            directory_priority="HIGH",
        ))

        log.info(
            f"[PREDICTOR]   → {classification} score={page_score} "
            f"files={len(file_links)} viewers_resolved={len(resolved_files)}"
        )

    log.info(
        f"[PREDICTOR] Done. confirmed={len(confirmed_dirs)} "
        f"files_found={metrics['files_found']} results_pages={metrics['classified_results']}"
    )

    return PredictionResult(
        domain=domain,
        state=state,
        county=county,
        years=years,
        predicted_urls=predicted_urls,
        confirmed_dirs=confirmed_dirs,
        file_candidates=all_file_candidates,
        metrics=metrics,
        errors=errors,
    )
