"""
app/lib/state_manager.py

Tracks "staleness" of derived outputs based on raw input changes.
Reads/writes derived/STATE.json.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DERIVED_DIR = BASE_DIR / "derived"
STATE_FILE = DERIVED_DIR / "STATE.json"

# Standard artifact domains that can become stale
STALE_DOMAINS = ["memberships", "precinct_models", "district_aggregates", "campaign_targets", "maps"]


def _read_state() -> dict:
    if not STATE_FILE.exists():
        return {"stale": {}, "last_run": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"stale": {}, "last_run": {}}


def _write_state(state: dict):
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def mark_stale(
    context_key: str,  # e.g. "CA/Sonoma" or "CA/Sonoma/2024/nov2024_general"
    reason: str,       # Human-readable reason, e.g. "votes_updated"
    domains: list[str] = STALE_DOMAINS
):
    """
    Mark specific derived domains as stale for a given context.
    """
    state = _read_state()
    stale_map = state.setdefault("stale", {})
    ctx_stale = stale_map.setdefault(context_key, {})

    for d in domains:
        ctx_stale[d] = {
            "is_stale": True,
            "reason": reason
        }

    _write_state(state)


def clear_stale(context_key: str, domains_cleared: list[str]):
    """
    Remove staleness flags for the specified domains after a successful rebuild.
    """
    state = _read_state()
    stale_map = state.get("stale", {})
    if context_key in stale_map:
        for d in domains_cleared:
            stale_map[context_key].pop(d, None)
        # Cleanup empty context
        if not stale_map[context_key]:
            del stale_map[context_key]
        _write_state(state)


def get_stale_status(context_key: str) -> dict:
    """Return dictionary of domain -> staleness info for a context."""
    state = _read_state()
    # Return specific contest staleness PLUS any parent county staleness
    # e.g., if county geography is stale, ALL contests in that county are stale.
    parts = context_key.split("/")
    result = {}

    # Accumulate from broadest (state/county) to narrowest (contest)
    for i in range(2, len(parts) + 1):
        sub_key = "/".join(parts[:i])
        sub_stale = state.get("stale", {}).get(sub_key, {})
        for domain, info in sub_stale.items():
            # Narrower context overrides broader
            result[domain] = info

    return result


def determine_stale_domains_for_update(category: str) -> list[str]:
    """
    Business rules: map an updated input category to downstream domains that become stale.
    """
    cat = category.lower()
    if "detail" in cat or "votes" in cat:
        return ["precinct_models", "district_aggregates", "campaign_targets", "maps"]
    elif "mprec" in cat or "srprec" in cat or "geojson" in cat or "shapefile" in cat:
        return ["maps", "memberships", "precinct_models", "district_aggregates", "campaign_targets"]
    elif "crosswalk" in cat or "blk to mprec" in cat or "to 2020 blk" in cat:
        return ["memberships", "precinct_models", "district_aggregates", "campaign_targets", "maps"]
    elif "boundary" in cat or "supervisorial" in cat or "school" in cat or "city" in cat:
        return ["memberships", "district_aggregates"]
    return STALE_DOMAINS
