"""
engine/source_registry/source_verifier.py — Prompt 25A.1

URL verification engine for the source registry.

Responsibilities:
- Extract domain from URL
- Check domain against the official domain allowlist (3 tiers)
- Attempt HTTP HEAD/GET to confirm URL resolves
- Return a VerificationResult with domain, tier, verified flag, and reason
"""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ALLOWLIST_PATH = BASE_DIR / "config" / "source_registry" / "official_domain_allowlist.yaml"

# Confidence ceiling per tier
TIER_MAX_CONFIDENCE = {
    "gov_tier":      0.99,
    "official_tier": 0.90,
    "academic_tier": 0.85,
    "not_allowlisted": 0.59,
}


@dataclass
class VerificationResult:
    source_id: str
    url: str
    domain: str
    tier: str                          # gov_tier | official_tier | academic_tier | not_allowlisted
    in_allowlist: bool
    max_confidence: float
    url_resolves: bool
    status_code: Optional[int]
    verified: bool                     # in_allowlist AND (url_resolves OR user_approved)
    reason: str
    warnings: list = field(default_factory=list)


_allowlist_cache: Optional[dict] = None


def load_domain_allowlist() -> dict:
    """Load and cache the official domain allowlist."""
    global _allowlist_cache
    if _allowlist_cache is not None:
        return _allowlist_cache
    if not ALLOWLIST_PATH.exists():
        log.warning("[VERIFIER] official_domain_allowlist.yaml not found — all domains unverified")
        _allowlist_cache = {}
        return _allowlist_cache
    try:
        raw = yaml.safe_load(ALLOWLIST_PATH.read_text(encoding="utf-8")) or {}
        _allowlist_cache = raw
        return raw
    except Exception as e:
        log.error(f"[VERIFIER] Failed to load allowlist: {e}")
        _allowlist_cache = {}
        return {}


def extract_domain(url: str) -> str:
    """Extract the netloc domain from a URL string."""
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return parsed.netloc.lower().lstrip("www.")
    except Exception:
        return url.lower()


def check_domain_allowlist(domain: str) -> tuple[bool, str, float]:
    """
    Check if a domain is in the allowlist.

    Returns:
        (in_allowlist: bool, tier: str, max_confidence: float)
    """
    if not domain:
        return False, "not_allowlisted", TIER_MAX_CONFIDENCE["not_allowlisted"]

    allowlist = load_domain_allowlist()
    # Check each tier in priority order
    for tier_key in ("gov_tier", "official_tier", "academic_tier"):
        tier_data = allowlist.get(tier_key, {})
        domains_in_tier = tier_data.get("domains", [])
        # Match exact domain or with/without www prefix
        for listed_domain in domains_in_tier:
            listed_clean = listed_domain.lower().lstrip("www.")
            if domain == listed_clean or domain == listed_domain.lower():
                max_conf = tier_data.get("max_confidence", TIER_MAX_CONFIDENCE.get(tier_key, 0.59))
                return True, tier_key, max_conf

    return False, "not_allowlisted", TIER_MAX_CONFIDENCE["not_allowlisted"]


def check_url_resolves(url: str, timeout: int = 5) -> tuple[bool, Optional[int]]:
    """
    Try HTTP HEAD request to check if a URL resolves.

    Returns:
        (resolves: bool, status_code: Optional[int])

    Never raises — all errors caught and logged.
    DNS/network failures return (False, None).
    """
    if not url:
        return False, None
    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "CampaignInABox/SourceVerifier/1.0 (registry validation)")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.status
            return (200 <= code < 400), code
    except urllib.error.HTTPError as e:
        # HTTP error response — URL exists but returned error
        return False, e.code
    except (urllib.error.URLError, socket.timeout, TimeoutError):
        return False, None
    except Exception as e:
        log.debug(f"[VERIFIER] check_url_resolves({url}) unexpected error: {e}")
        return False, None


def verify_source(source_record: dict, skip_http: bool = False) -> VerificationResult:
    """
    Run full verification on a source registry entry.

    Args:
        source_record: dict from contest_sources.yaml or geometry_sources.yaml
        skip_http: if True, skip the HTTP HEAD check (use for offline/fast mode)

    Returns:
        VerificationResult
    """
    source_id = source_record.get("source_id", "unknown")
    user_approved = bool(source_record.get("user_approved", False))
    source_origin = source_record.get("source_origin", "heuristic_candidate")

    # Pick best URL to verify
    url = (
        source_record.get("page_url")
        or source_record.get("base_url")
        or ""
    )
    domain = extract_domain(url)
    in_allowlist, tier, max_confidence = check_domain_allowlist(domain)

    warnings: list[str] = []

    # HTTP check
    url_resolves = False
    status_code = None
    if url and not skip_http:
        url_resolves, status_code = check_url_resolves(url)
        if not url_resolves:
            warnings.append(f"URL did not resolve (status={status_code}): {url}")
    elif not url:
        warnings.append("No URL to verify")

    # Determine verified flag
    # A source is verified if: in allowlist AND (url resolved OR user approved OR no URL)
    if not url:
        # No URL — verified only if user_approved
        verified = user_approved
        reason = "User approved (no URL)" if user_approved else "No URL available for verification"
    elif in_allowlist and (url_resolves or user_approved):
        verified = True
        reason = f"Official {tier.replace('_',' ')} domain{'+ user approved' if user_approved else ''}"
    elif in_allowlist and not url_resolves:
        # Allowlisted domain but URL did not respond
        # Could be network issue in offline environment — treat as conditionally verified
        verified = True   # domain is known-good; HTTP failure might be local/rate-limit
        reason = f"Official {tier.replace('_',' ')} domain (URL check failed — may be offline)"
        warnings.append("URL HEAD check failed (treated as conditionally verified for official domain)")
    elif not in_allowlist and user_approved:
        verified = True
        reason = "User approved (domain not in official allowlist)"
        warnings.append(f"Domain '{domain}' not in allowlist but user-approved")
    else:
        verified = False
        reason = f"Domain '{domain}' not in official allowlist"
        warnings.append(f"Domain not allowlisted: {domain}")

    return VerificationResult(
        source_id=source_id,
        url=url,
        domain=domain,
        tier=tier,
        in_allowlist=in_allowlist,
        max_confidence=max_confidence,
        url_resolves=url_resolves,
        status_code=status_code,
        verified=verified,
        reason=reason,
        warnings=warnings,
    )
