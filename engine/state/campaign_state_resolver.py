"""
engine/state/campaign_state_resolver.py — Prompt 27

Central resolver for all campaign-scoped state paths.

All state reads and writes must go through this resolver.
No module may hardcode 'derived/state/latest/' as a primary write target.

Public API
----------
get_active_campaign_id()                  → str
get_campaign_state_dir(campaign_id)       → Path  (derived/state/campaigns/<cid>/)
get_latest_state_dir(campaign_id)         → Path  (derived/state/campaigns/<cid>/latest/)
get_history_dir(campaign_id)              → Path  (derived/state/campaigns/<cid>/history/)
get_latest_campaign_state(campaign_id)    → dict  (loaded JSON or {})
set_active_campaign(campaign_id)          → None  (writes pointer files)
validate_registry()                       → dict  (health check + auto-repair)
get_legacy_latest_dir()                   → Path  (for read-only backward compat only)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import yaml

log = logging.getLogger(__name__)

BASE_DIR          = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR        = BASE_DIR / "config"
DERIVED_STATE     = BASE_DIR / "derived" / "state"
CAMPAIGNS_STATE   = DERIVED_STATE / "campaigns"
LEGACY_LATEST     = DERIVED_STATE / "latest"          # READ-ONLY backward compat alias
POINTER_FILE      = DERIVED_STATE / "active_campaign_pointer.json"
ACTIVE_CAMPAIGN   = CONFIG_DIR / "active_campaign.yaml"
REGISTRY_PATH     = CONFIG_DIR / "campaign_registry.yaml"
REPORTS_STATE_DIR = BASE_DIR / "reports" / "state"

for _d in (CAMPAIGNS_STATE, LEGACY_LATEST, REPORTS_STATE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> Dict:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        log.warning(f"[Resolver] Cannot load {path}: {e}")
        return {}


def _load_json(path: Path) -> Dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_yaml(path: Path, data: Dict) -> None:
    path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True),
                    encoding="utf-8")


def _save_json(path: Path, data: Dict) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _now() -> str:
    return datetime.utcnow().isoformat()


# ── Public API ─────────────────────────────────────────────────────────────────

def get_active_campaign_id() -> str:
    """
    Return the active campaign_id from config/active_campaign.yaml.
    Raises RuntimeError if no active campaign is set or file is missing.
    """
    ac = _load_yaml(ACTIVE_CAMPAIGN)
    cid = ac.get("campaign_id", "").strip()
    if not cid:
        raise RuntimeError(
            "[CampaignStateResolver] No active campaign set. "
            "Go to Campaign Admin and set an active campaign before building state."
        )
    return cid


def get_campaign_state_dir(campaign_id: str) -> Path:
    """Return the campaign-scoped state root: derived/state/campaigns/<cid>/"""
    d = CAMPAIGNS_STATE / campaign_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_latest_state_dir(campaign_id: str) -> Path:
    """Return the latest/ dir for a campaign: derived/state/campaigns/<cid>/latest/"""
    d = get_campaign_state_dir(campaign_id) / "latest"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_history_dir(campaign_id: str) -> Path:
    """Return the history/ dir for a campaign: derived/state/campaigns/<cid>/history/"""
    d = get_campaign_state_dir(campaign_id) / "history"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_latest_campaign_state(campaign_id: Optional[str] = None) -> Dict:
    """
    Load and return the latest campaign_state.json for the given (or active) campaign.
    Returns {} if none exists yet.
    """
    if campaign_id is None:
        try:
            campaign_id = get_active_campaign_id()
        except RuntimeError:
            # Fall back to legacy path for backward compat (read-only)
            legacy = LEGACY_LATEST / "campaign_state.json"
            if legacy.exists():
                log.warning("[Resolver] No active campaign set; falling back to legacy latest/ path (read-only).")
                return _load_json(legacy)
            return {}

    latest_dir = get_latest_state_dir(campaign_id)
    state_file = latest_dir / "campaign_state.json"
    if state_file.exists():
        return _load_json(state_file)

    # Fallback to legacy for first-boot compatibility
    legacy = LEGACY_LATEST / "campaign_state.json"
    if legacy.exists():
        log.info(f"[Resolver] No scoped state for {campaign_id} yet; using legacy latest/ as seed (read-only).")
        data = _load_json(legacy)
        # Do NOT write back — legacy is read-only alias; state_builder will write properly
        return data
    return {}


def set_active_campaign(campaign_id: str) -> None:
    """
    Set the active campaign by:
      1. Updating config/active_campaign.yaml
      2. Updating derived/state/active_campaign_pointer.json
      3. Logging the switch
    Does NOT deactivate other campaigns in registry — that's campaign_manager's job.
    """
    ac = _load_yaml(ACTIVE_CAMPAIGN)
    old_id = ac.get("campaign_id", "")

    # Load campaign details from registry
    reg = _load_yaml(REGISTRY_PATH)
    campaigns = reg.get("campaigns", [])
    campaign = next((c for c in campaigns if c.get("campaign_id") == campaign_id), None)

    if campaign is None:
        raise ValueError(f"[Resolver] campaign_id '{campaign_id}' not found in campaign_registry.yaml")

    # Update active_campaign.yaml
    new_ac = {
        "campaign_id":   campaign_id,
        "campaign_name": campaign.get("campaign_name", ""),
        "stage":         campaign.get("stage", "setup"),
        "status":        campaign.get("status", "active"),
        "contest_name":  campaign.get("contest_name", ""),
        "state":         campaign.get("state", ""),
        "county":        campaign.get("county", ""),
        "switched_at":   _now(),
        "switched_from": old_id,
    }
    _save_yaml(ACTIVE_CAMPAIGN, new_ac)

    # Write pointer JSON for quick access
    _save_json(POINTER_FILE, {
        "campaign_id":   campaign_id,
        "campaign_name": campaign.get("campaign_name", ""),
        "switched_at":   _now(),
        "switched_from": old_id,
        "state_dir":     str(get_latest_state_dir(campaign_id)),
    })

    log.info(f"[Resolver] Active campaign switched: {old_id!r} → {campaign_id!r}")


def validate_registry() -> Dict:
    """
    Validate the campaign registry for single-active enforcement.

    Returns a dict with:
      - status: 'ok' | 'repaired' | 'warning' | 'error'
      - issues: list of issue strings
      - active_campaign_id: str | None
      - active_count: int
    """
    reg = _load_yaml(REGISTRY_PATH)
    campaigns = reg.get("campaigns", [])

    active = [c for c in campaigns if c.get("is_active", False)]
    active_count = len(active)
    issues = []
    status = "ok"

    if active_count == 0:
        issues.append("NO_ACTIVE_CAMPAIGN: zero campaigns are active — select an active campaign")
        status = "warning"
        active_id = None

    elif active_count > 1:
        # Auto-repair: keep first active, deactivate rest
        active_ids = [c.get("campaign_id") for c in active]
        issues.append(f"MULTIPLE_ACTIVE:{','.join(active_ids)} — auto-repairing to keep first")
        keep_id = active_ids[0]
        for c in campaigns:
            if c.get("campaign_id") != keep_id:
                c["is_active"] = False
        reg["campaigns"] = campaigns
        _save_yaml(REGISTRY_PATH, reg)
        status = "repaired"
        active_id = keep_id
        log.warning(f"[Resolver] Auto-repaired multiple active campaigns → kept {keep_id!r}")

    else:
        active_id = active[0].get("campaign_id")

    # Verify active_campaign.yaml is consistent
    ac = _load_yaml(ACTIVE_CAMPAIGN)
    if active_id and ac.get("campaign_id") != active_id:
        issues.append(
            f"POINTER_MISMATCH: active_campaign.yaml={ac.get('campaign_id')!r} "
            f"but registry active={active_id!r} — updating pointer"
        )
        set_active_campaign(active_id)
        status = "repaired" if status == "ok" else status

    result = {
        "timestamp":         _now(),
        "active_campaign_id": active_id,
        "active_count":      active_count,
        "total_campaigns":   len(campaigns),
        "issues":            issues,
        "status":            status,
    }
    return result


def get_legacy_latest_dir() -> Path:
    """
    Return the legacy derived/state/latest/ directory.
    This is READ-ONLY for backward compatibility.
    New state writes must NOT target this path directly.
    """
    return LEGACY_LATEST


def seed_legacy_alias(campaign_id: str, state_json: str) -> None:
    """
    Write a copy of state to the legacy latest/ path for backward compat.
    This is the ONLY permitted write to derived/state/latest/ — and only
    from state_builder via this function. All other code must use the
    campaign-scoped paths.
    """
    legacy_file = LEGACY_LATEST / "campaign_state.json"
    legacy_file.write_text(state_json, encoding="utf-8")
    log.info(f"[Resolver] Legacy alias updated: {legacy_file} (read-only compat for {campaign_id})")


def write_enforcement_report(run_id: str, validation_result: Dict) -> Path:
    """Write the single-active enforcement report to reports/state/."""
    REPORTS_STATE_DIR.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = BASE_DIR / "derived" / "state" / f"{run_id}__campaign_registry_validation.json"
    (BASE_DIR / "derived" / "state").mkdir(parents=True, exist_ok=True)
    _save_json(json_path, validation_result)

    # MD
    md_path = REPORTS_STATE_DIR / f"{run_id}__active_campaign_enforcement.md"
    issues_md = "\n".join(f"- {i}" for i in validation_result.get("issues", [])) or "- None"
    md = f"""# Active Campaign Enforcement Report
**Run ID:** {run_id}  **Timestamp:** {validation_result.get('timestamp', '')}

## Result
- Status: **{validation_result.get('status', 'unknown').upper()}**
- Active campaign: `{validation_result.get('active_campaign_id', 'NONE')}`
- Total campaigns: {validation_result.get('total_campaigns', 0)}
- Active count: {validation_result.get('active_count', 0)}

## Issues / Actions
{issues_md}
"""
    md_path.write_text(md, encoding="utf-8")
    log.info(f"[Resolver] Enforcement report written: {md_path.name}")
    return md_path
