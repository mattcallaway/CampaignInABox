"""
engine/admin/campaign_manager.py — Prompt 20.8

Campaign registry management engine.

Reads and writes:
  config/campaign_registry.yaml  — all campaigns
  config/active_campaign.yaml    — single active campaign pointer
  config/campaigns/<id>.yaml     — per-campaign config files

Operations:
  list_campaigns()               — all campaigns
  get_campaign(campaign_id)      — one campaign dict
  create_campaign(actor, ...)    — create new campaign
  update_campaign(actor, ...)    — update campaign fields
  set_active(actor, campaign_id) — switch active campaign
  deactivate(actor, campaign_id) — mark inactive (doesn't archive)
  archive_campaign(actor, id)    — archive (sets status=archived, is_active=False)

Audit trail written to: logs/admin/campaign_admin_log.csv

Stage lifecycle:
  setup → data_ingest → modeling → field → gotv → post_election → archived
"""
from __future__ import annotations

import csv
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

log = logging.getLogger(__name__)

BASE_DIR         = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH    = BASE_DIR / "config" / "campaign_registry.yaml"
ACTIVE_PATH      = BASE_DIR / "config" / "active_campaign.yaml"
CAMPAIGNS_DIR    = BASE_DIR / "config" / "campaigns"
ADMIN_LOG_PATH   = BASE_DIR / "logs" / "admin" / "campaign_admin_log.csv"

VALID_STAGES  = ["setup", "data_ingest", "modeling", "field", "gotv", "post_election", "archived"]
VALID_STATUSES = ["active", "inactive", "archived"]

_LOG_HEADER = [
    "timestamp", "actor_user_id", "action", "campaign_id",
    "old_status", "new_status", "old_stage", "new_stage", "notes",
]


def _ensure_log():
    ADMIN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ADMIN_LOG_PATH.exists() or ADMIN_LOG_PATH.stat().st_size == 0:
        with open(ADMIN_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(_LOG_HEADER)


def _write_audit(actor: str, action: str, campaign_id: str,
                 old_status: str = "", new_status: str = "",
                 old_stage: str = "", new_stage: str = "",
                 notes: str = ""):
    _ensure_log()
    with open(ADMIN_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.utcnow().isoformat(), actor, action, campaign_id,
            old_status, new_status, old_stage, new_stage, notes,
        ])


def _load_registry() -> List[Dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return []
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    return data.get("campaigns", [])


def _save_registry(campaigns: List[Dict[str, Any]]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        yaml.dump({"campaigns": campaigns}, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def _load_active() -> Dict[str, Any]:
    if not ACTIVE_PATH.exists():
        return {}
    return yaml.safe_load(ACTIVE_PATH.read_text(encoding="utf-8")) or {}


def _save_active(data: Dict[str, Any]) -> None:
    ACTIVE_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


class CampaignManager:
    """Read/write campaign registry. All mutating methods require actor_user_id."""

    def __init__(self, auth_manager=None):
        """
        Args:
            auth_manager: AuthManager instance for permission checks.
                         If None, permission checks are skipped (testing mode).
        """
        self._auth = auth_manager

    def _check_permission(self, actor_user_id: str) -> None:
        if self._auth is not None:
            self._auth.require_permission(actor_user_id, "manage_campaigns")

    # ── Read ──────────────────────────────────────────────────────────────────

    def list_campaigns(self) -> List[Dict[str, Any]]:
        return _load_registry()

    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        for c in _load_registry():
            if c.get("campaign_id") == campaign_id:
                return c
        return None

    def get_active_campaign(self) -> Optional[Dict[str, Any]]:
        """Return the active campaign dict from the registry."""
        campaigns = _load_registry()
        active = [c for c in campaigns if c.get("is_active")]
        return active[0] if active else None

    def get_active_campaign_pointer(self) -> Dict[str, Any]:
        """Return the fast-access active_campaign.yaml pointer."""
        return _load_active()

    # ── Create ────────────────────────────────────────────────────────────────

    def create_campaign(
        self,
        actor_user_id: str,
        campaign_name: str,
        contest_name: str,
        contest_type: str,
        state: str,
        county: str,
        jurisdiction: str,
        election_date: str,
        stage: str = "setup",
        notes: str = "",
        set_active: bool = False,
        campaign_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new campaign and add it to the registry.

        Args:
            actor_user_id:  Admin performing the action
            campaign_name:  Human-readable name
            contest_name:   Contest label
            contest_type:   ballot_measure | general | primary | special | runoff
            state, county, jurisdiction: Geographic scope
            election_date:  ISO date string (YYYY-MM-DD)
            stage:          Starting stage (default: setup)
            notes:          Optional notes
            set_active:     If True, immediately set this campaign as active
            campaign_id:    Optional explicit ID (auto-generated if None)

        Returns:
            The new campaign dict

        Raises:
            PermissionError if actor lacks manage_campaigns
            ValueError if stage invalid or campaign_id already exists
        """
        self._check_permission(actor_user_id)

        if stage not in VALID_STAGES:
            raise ValueError(f"Invalid stage '{stage}'. Valid: {VALID_STAGES}")

        # Generate deterministic ID from name if not provided
        if not campaign_id:
            slug = campaign_name.lower().replace(" ", "_").replace("-", "_")
            slug = "".join(c for c in slug if c.isalnum() or c == "_")[:40]
            year = election_date[:4] if election_date else "0000"
            campaign_id = f"{year}_{state.lower()}_{county.lower()}_{slug}"

        campaigns = _load_registry()
        if any(c.get("campaign_id") == campaign_id for c in campaigns):
            raise ValueError(f"campaign_id '{campaign_id}' already exists")

        now = datetime.utcnow().isoformat()
        new_campaign = {
            "campaign_id":   campaign_id,
            "campaign_name": campaign_name,
            "state":         state,
            "county":        county,
            "jurisdiction":  jurisdiction,
            "contest_name":  contest_name,
            "contest_type":  contest_type,
            "election_date": election_date,
            "stage":         stage,
            "status":        "active" if set_active else "inactive",
            "is_active":     False,
            "created_at":    now,
            "archived_at":   None,
            "notes":         notes,
        }

        if set_active:
            # Deactivate all others
            for c in campaigns:
                c["is_active"] = False
                c["status"] = "inactive" if c.get("status") == "active" else c.get("status", "inactive")
            new_campaign["is_active"] = True
            _save_active({
                "campaign_id":   campaign_id,
                "campaign_name": campaign_name,
                "stage":         stage,
                "status":        "active",
                "switched_at":   now,
                "switched_by":   actor_user_id,
            })

        campaigns.append(new_campaign)
        _save_registry(campaigns)

        # Create per-campaign config stub
        self._create_campaign_config(new_campaign)

        _write_audit(actor_user_id, "create_campaign", campaign_id,
                     new_status="active" if set_active else "inactive",
                     new_stage=stage, notes=campaign_name)
        log.info(f"[CAMPAIGN] Created campaign: {campaign_id} by {actor_user_id}")
        return new_campaign

    def _create_campaign_config(self, campaign: Dict[str, Any]) -> None:
        """Create a per-campaign config stub in config/campaigns/<id>.yaml."""
        CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)
        path = CAMPAIGNS_DIR / f"{campaign['campaign_id']}.yaml"
        if not path.exists():
            cfg = {
                "campaign": {
                    "campaign_id":   campaign["campaign_id"],
                    "campaign_name": campaign["campaign_name"],
                    "election_date": campaign.get("election_date", ""),
                    "state":         campaign.get("state", ""),
                    "county":        campaign.get("county", ""),
                    "contest_name":  campaign.get("contest_name", ""),
                    "contest_type":  campaign.get("contest_type", ""),
                },
                "targets": {
                    "target_vote_share": 0.52,
                    "win_margin": 0.04,
                },
                "budget": {
                    "total_budget": 0,
                },
                "strategy": {
                    "persuasion_gotv_split": 0.65,
                },
            }
            path.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True),
                            encoding="utf-8")
            log.info(f"[CAMPAIGN] Created config stub: {path}")

    # ── Update ────────────────────────────────────────────────────────────────

    def update_campaign(
        self,
        actor_user_id: str,
        campaign_id: str,
        **updates,
    ) -> Dict[str, Any]:
        """
        Update non-lifecycle fields of a campaign.

        Updatable: campaign_name, contest_name, contest_type, election_date,
                   jurisdiction, state, county, notes.

        Use set_active(), deactivate(), archive_campaign(), set_stage()
        for lifecycle changes.
        """
        self._check_permission(actor_user_id)
        campaigns = _load_registry()
        campaign = next((c for c in campaigns if c.get("campaign_id") == campaign_id), None)
        if not campaign:
            raise ValueError(f"Campaign '{campaign_id}' not found")

        SAFE_FIELDS = {"campaign_name", "contest_name", "contest_type",
                       "election_date", "jurisdiction", "state", "county", "notes"}
        changed = {}
        for field, value in updates.items():
            if field in SAFE_FIELDS:
                old = campaign.get(field)
                if old != value:
                    campaign[field] = value
                    changed[field] = (old, value)

        if changed:
            # If renamed, keep campaign config in sync
            if "campaign_name" in changed:
                self._update_campaign_config_name(campaign_id, campaign["campaign_name"])
            _save_registry(campaigns)
            _write_audit(actor_user_id, "update_campaign", campaign_id, notes=str(changed))

        return campaign

    def set_stage(
        self,
        actor_user_id: str,
        campaign_id: str,
        new_stage: str,
        notes: str = "",
    ) -> None:
        """Change a campaign's lifecycle stage."""
        self._check_permission(actor_user_id)
        if new_stage not in VALID_STAGES:
            raise ValueError(f"Invalid stage '{new_stage}'. Valid: {VALID_STAGES}")

        campaigns = _load_registry()
        campaign = next((c for c in campaigns if c.get("campaign_id") == campaign_id), None)
        if not campaign:
            raise ValueError(f"Campaign '{campaign_id}' not found")

        old_stage = campaign.get("stage", "")
        campaign["stage"] = new_stage
        _save_registry(campaigns)

        # Update active pointer if this is the active campaign
        active = _load_active()
        if active.get("campaign_id") == campaign_id:
            active["stage"] = new_stage
            _save_active(active)

        _write_audit(actor_user_id, "set_stage", campaign_id,
                     old_stage=old_stage, new_stage=new_stage, notes=notes)
        log.info(f"[CAMPAIGN] Stage changed: {campaign_id} {old_stage} → {new_stage}")

    # ── Activation ────────────────────────────────────────────────────────────

    def set_active(
        self,
        actor_user_id: str,
        campaign_id: str,
        notes: str = "",
    ) -> None:
        """
        Set a campaign as the globally active campaign.

        Only one campaign can be active at a time.
        All other campaigns are set to is_active=False.
        """
        self._check_permission(actor_user_id)
        campaigns = _load_registry()
        target = None
        for c in campaigns:
            if c.get("campaign_id") == campaign_id:
                target = c
            else:
                c["is_active"] = False

        if target is None:
            raise ValueError(f"Campaign '{campaign_id}' not found")

        old_status = target.get("status", "")
        target["is_active"] = True
        target["status"] = "active"
        _save_registry(campaigns)

        now = datetime.utcnow().isoformat()
        _save_active({
            "campaign_id":   campaign_id,
            "campaign_name": target.get("campaign_name", ""),
            "stage":         target.get("stage", ""),
            "status":        "active",
            "switched_at":   now,
            "switched_by":   actor_user_id,
        })

        _write_audit(actor_user_id, "set_active", campaign_id,
                     old_status=old_status, new_status="active", notes=notes)
        log.info(f"[CAMPAIGN] Set active: {campaign_id} by {actor_user_id}")

    def deactivate(
        self,
        actor_user_id: str,
        campaign_id: str,
        notes: str = "",
    ) -> None:
        """Mark a campaign inactive (does not delete or archive)."""
        self._check_permission(actor_user_id)
        campaigns = _load_registry()
        campaign = next((c for c in campaigns if c.get("campaign_id") == campaign_id), None)
        if not campaign:
            raise ValueError(f"Campaign '{campaign_id}' not found")

        old_status = campaign.get("status", "")
        campaign["is_active"] = False
        campaign["status"] = "inactive"
        _save_registry(campaigns)

        # If this was active, clear the pointer
        active = _load_active()
        if active.get("campaign_id") == campaign_id:
            active["status"] = "inactive"
            _save_active(active)

        _write_audit(actor_user_id, "deactivate", campaign_id,
                     old_status=old_status, new_status="inactive", notes=notes)

    def archive_campaign(
        self,
        actor_user_id: str,
        campaign_id: str,
        notes: str = "",
    ) -> None:
        """Archive a campaign — sets status=archived, is_active=False."""
        self._check_permission(actor_user_id)
        campaigns = _load_registry()
        campaign = next((c for c in campaigns if c.get("campaign_id") == campaign_id), None)
        if not campaign:
            raise ValueError(f"Campaign '{campaign_id}' not found")

        old_status = campaign.get("status", "")
        old_stage  = campaign.get("stage", "")
        campaign["is_active"] = False
        campaign["status"] = "archived"
        campaign["stage"]  = "archived"
        campaign["archived_at"] = datetime.utcnow().isoformat()
        _save_registry(campaigns)

        _write_audit(actor_user_id, "archive_campaign", campaign_id,
                     old_status=old_status, new_status="archived",
                     old_stage=old_stage, new_stage="archived", notes=notes)
        log.info(f"[CAMPAIGN] Archived: {campaign_id} by {actor_user_id}")

    def _update_campaign_config_name(self, campaign_id: str, new_name: str) -> None:
        path = CAMPAIGNS_DIR / f"{campaign_id}.yaml"
        if path.exists():
            try:
                cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                cfg.setdefault("campaign", {})["campaign_name"] = new_name
                path.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True),
                                encoding="utf-8")
            except Exception as e:
                log.debug(f"[CAMPAIGN] Could not update campaign config name: {e}")

    # ── Stage Warning Helper ───────────────────────────────────────────────────

    @staticmethod
    def stage_warnings(campaign: Dict[str, Any]) -> List[str]:
        """
        Return any warnings appropriate for the campaign's current stage.
        Used by UI to show stage-contextual alerts.
        """
        warnings = []
        stage = campaign.get("stage", "")
        base = Path(__file__).resolve().parent.parent.parent

        if stage == "modeling":
            archive = base / "derived" / "archive" / "normalized_elections.csv"
            if not archive.exists():
                warnings.append("Stage is 'modeling' but no historical election archive found. "
                                "Run the Archive Builder to load historical data.")
        if stage in ("field", "gotv"):
            war_room = base / "derived" / "war_room"
            if not any(war_room.glob("*.json")):
                warnings.append(f"Stage is '{stage}' but no War Room runtime data found. "
                                "Log field results in the War Room.")
        return warnings
