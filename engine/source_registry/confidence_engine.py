"""
engine/source_registry/confidence_engine.py — Prompt 25A.1

Confidence recalculation engine for the source registry.

Applies policy-based rules to compute a corrected confidence score for each
registry entry, taking into account:
  - Domain allowlist tier (gov / official / academic / not_allowlisted)
  - source_origin classification
  - URL verification result
  - User approval status

All changes are non-destructive — original confidence_default is preserved;
recalculated value is written to confidence_recalculated.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.source_registry.source_verifier import VerificationResult

log = logging.getLogger(__name__)

# Maximum confidence per source_origin type
ORIGIN_MAX_CONFIDENCE = {
    "seeded_official":     0.99,
    "discovered_official": 0.95,
    "user_approved":       0.95,
    "manual_upload":       0.90,
    "heuristic_candidate": 0.59,
}

# Confidence when URL verification fails (and source is not user-approved)
VERIFICATION_FAILURE_CONFIDENCE = 0.30

# Confidence cap for non-allowlisted domains (unless user_approved)
NON_ALLOWLISTED_CAP = 0.59


def recalculate_source_confidence(
    source_record: dict,
    verification_result: "VerificationResult",
) -> dict:
    """
    Apply confidence policy rules to a source record and return an annotated copy.

    Rules (applied in order, most restrictive wins):

    1. heuristic_candidate  → cap at 0.59
    2. Not in allowlist (and not user_approved) → cap at 0.59
    3. URL verification failed (and not user_approved) → reduce to 0.30
    4. Apply domain tier ceiling (gov=0.99, official=0.90, academic=0.85)
    5. Apply source_origin ceiling
    6. Use min(confidence_default, all applicable ceilings) as final score

    Args:
        source_record: raw dict from registry YAML
        verification_result: VerificationResult from source_verifier.verify_source()

    Returns:
        Annotated copy of source_record with added fields:
          confidence_recalculated, confidence_reason, verified,
          domain, domain_tier, source_origin (if missing)
    """
    result = dict(source_record)

    source_origin = source_record.get("source_origin", "heuristic_candidate")
    user_approved = bool(source_record.get("user_approved", False))
    confidence_default = float(source_record.get("confidence_default", 0.50))

    vr = verification_result
    in_allowlist = vr.in_allowlist
    tier_max = vr.max_confidence   # from allowlist tier
    url_resolves = vr.url_resolves

    reasons: list[str] = []
    caps: list[float] = [confidence_default]  # start from stated default

    # ── Rule 1: heuristic_candidate always capped ─────────────────────────────
    if source_origin == "heuristic_candidate":
        caps.append(ORIGIN_MAX_CONFIDENCE["heuristic_candidate"])
        reasons.append("Heuristic candidate: capped at 0.59")

    # ── Rule 2: Non-allowlisted domain (unless user approved) ─────────────────
    if not in_allowlist and not user_approved:
        caps.append(NON_ALLOWLISTED_CAP)
        reasons.append(f"Domain '{vr.domain}' not in official allowlist: capped at 0.59")

    # ── Rule 3: URL verification failure penalty ───────────────────────────────
    # Only apply the 0.30 penalty when ALL of these are true:
    #   - Source has a URL (local-file sources have no URL -> no penalty)
    #   - AND not user_approved
    #   - AND domain is NOT in the allowlist
    # Rationale: if we're offline or firewalled, allowlisted gov/official/academic
    # domains should NOT be downgraded — the domain being in the allowlist is the
    # primary trust signal. HTTP failure for a known-good domain = network issue.
    # The 0.30 penalty is reserved for non-allowlisted sources with failing URLs.
    if not url_resolves and not user_approved and vr.url and not in_allowlist:
        caps.append(VERIFICATION_FAILURE_CONFIDENCE)
        reasons.append(f"URL verification failed (status={vr.status_code}): reduced to 0.30")

    # ── Rule 4: Domain tier ceiling ────────────────────────────────────────────
    if in_allowlist:
        caps.append(tier_max)
        if not reasons:
            reasons.append(f"Official domain ({vr.tier.replace('_', ' ')} tier), ceiling={tier_max}")
    elif user_approved:
        caps.append(ORIGIN_MAX_CONFIDENCE["user_approved"])
        reasons.append("User approved source, ceiling=0.95")

    # ── Rule 5: Source origin ceiling ─────────────────────────────────────────
    origin_max = ORIGIN_MAX_CONFIDENCE.get(source_origin, NON_ALLOWLISTED_CAP)
    caps.append(origin_max)
    if source_origin == "seeded_official" and vr.verified and not reasons:
        reasons.append(f"Official seeded source, verified, ceiling={origin_max}")
    elif source_origin == "discovered_official" and not reasons:
        reasons.append(f"Discovered official source, ceiling={origin_max}")

    # ── Final score: minimum of all caps ──────────────────────────────────────
    final_confidence = round(min(caps), 4)
    changed = abs(final_confidence - confidence_default) > 0.001

    if not reasons:
        reasons.append(vr.reason)

    confidence_reason = "; ".join(reasons) if reasons else "Standard confidence"

    # ── Write back to result dict ──────────────────────────────────────────────
    result["confidence_recalculated"] = final_confidence
    result["confidence_default_original"] = confidence_default
    result["confidence_changed"] = changed
    result["confidence_reason"] = confidence_reason
    result["verified"] = vr.verified
    result["domain"] = vr.domain
    result["domain_tier"] = vr.tier
    result["source_origin"] = source_origin   # ensure field present

    if changed:
        log.info(
            f"[CONFIDENCE] {source_record.get('source_id')} "
            f"{confidence_default:.3f} -> {final_confidence:.3f} ({confidence_reason[:60]})"
        )

    return result


def build_confidence_summary(processed_records: list[dict]) -> dict:
    """
    Build a summary dict of confidence recalculation results across all records.
    """
    total = len(processed_records)
    verified = sum(1 for r in processed_records if r.get("verified"))
    changed = sum(1 for r in processed_records if r.get("confidence_changed"))
    downgraded = sum(1 for r in processed_records if r.get("confidence_changed") and
                     r.get("confidence_recalculated", 1) < r.get("confidence_default_original", 1))
    heuristic_capped = sum(1 for r in processed_records
                           if r.get("source_origin") == "heuristic_candidate")
    invalid_domain = sum(1 for r in processed_records
                         if not r.get("verified") and r.get("domain") and
                         r.get("domain_tier") == "not_allowlisted")
    user_approved = sum(1 for r in processed_records if r.get("user_approved"))

    return {
        "total_sources":        total,
        "verified_sources":     verified,
        "heuristic_sources":    heuristic_capped,
        "invalid_domain":       invalid_domain,
        "user_approved_sources": user_approved,
        "confidence_changed":   changed,
        "downgraded":           downgraded,
    }
