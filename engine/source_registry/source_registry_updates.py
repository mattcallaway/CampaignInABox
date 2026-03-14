"""
engine/source_registry/source_registry_updates.py — Prompt 25A

User Approval Writeback & Source Management.

Persists user-approved sources, manual additions, and overrides to
config/source_registry/local_overrides.yaml.

The seeded registry files (contest_sources.yaml, geometry_sources.yaml) are
kept stable. All user changes go into local_overrides.yaml.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_OVERRIDES_PATH = BASE_DIR / "config" / "source_registry" / "local_overrides.yaml"


def _load_overrides() -> dict:
    """Load current local_overrides.yaml. Returns empty structure if missing."""
    if LOCAL_OVERRIDES_PATH.exists():
        try:
            data = yaml.safe_load(LOCAL_OVERRIDES_PATH.read_text(encoding="utf-8")) or {}
            return data
        except Exception as e:
            log.warning(f"[REGISTRY_UPDATES] Could not load local_overrides.yaml: {e}")
    return {"schema_version": "1.0", "approved_updates": [], "manual_contest_sources": [], "manual_geometry_sources": []}


def _save_overrides(data: dict) -> None:
    """Write local_overrides.yaml with updated timestamp."""
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    LOCAL_OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_OVERRIDES_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    log.info(f"[REGISTRY_UPDATES] Saved local_overrides.yaml")


def approve_source(source_id: str, notes: Optional[str] = None) -> bool:
    """
    Mark a seeded source as user-approved.

    Args:
        source_id: The source_id of the registry entry to approve
        notes: Optional confirmation note (e.g. "Confirmed by data director on 2026-03-12")

    Returns:
        True on success
    """
    data = _load_overrides()
    # Safe pattern: ensure the key exists as a real list, then use data[key] directly.
    # NEVER do `data.setdefault(k, []) or []` — `or []` detaches when existing value is [].
    if not isinstance(data.get("approved_updates"), list):
        data["approved_updates"] = []
    updates = data["approved_updates"]

    # Check if already exists
    for entry in updates:
        if entry.get("source_id") == source_id:
            entry["user_approved"] = True
            entry["approved_at"] = datetime.now().isoformat()
            if notes:
                entry["notes"] = notes
            _save_overrides(data)
            log.info(f"[REGISTRY_UPDATES] Updated approval for {source_id}")
            return True

    # New approval
    new_entry = {
        "source_id":    source_id,
        "user_approved": True,
        "approved_at":  datetime.now().isoformat(),
    }
    if notes:
        new_entry["notes"] = notes
    updates.append(new_entry)
    _save_overrides(data)
    log.info(f"[REGISTRY_UPDATES] Approved source: {source_id}")
    return True


def reject_source(source_id: str, notes: Optional[str] = None) -> bool:
    """
    Mark a seeded source as user-rejected (will not be surfaced in recommendations).
    """
    data = _load_overrides()
    if not isinstance(data.get("approved_updates"), list):
        data["approved_updates"] = []
    updates = data["approved_updates"]

    for entry in updates:
        if entry.get("source_id") == source_id:
            entry["user_approved"] = False
            entry["rejected_at"] = datetime.now().isoformat()
            if notes:
                entry["notes"] = notes
            _save_overrides(data)
            return True

    updates.append({
        "source_id":    source_id,
        "user_approved": False,
        "rejected_at":  datetime.now().isoformat(),
        "notes":        notes or "",
    })
    _save_overrides(data)
    log.info(f"[REGISTRY_UPDATES] Rejected source: {source_id}")
    return True


def mark_preferred(source_id: str) -> bool:
    """Mark a geometry source as the preferred source for its boundary_type."""
    data = _load_overrides()
    if not isinstance(data.get("approved_updates"), list):
        data["approved_updates"] = []
    updates = data["approved_updates"]

    for entry in updates:
        if entry.get("source_id") == source_id:
            entry["preferred"] = True
            _save_overrides(data)
            return True

    updates.append({"source_id": source_id, "preferred": True})
    _save_overrides(data)
    log.info(f"[REGISTRY_UPDATES] Marked preferred: {source_id}")
    return True


def add_alias(source_id: str, alias: str) -> bool:
    """
    Add a contest alias to an existing registry entry.
    Aliases allow future contest_name searches to match this source.
    """
    data = _load_overrides()
    if not isinstance(data.get("approved_updates"), list):
        data["approved_updates"] = []
    updates = data["approved_updates"]

    for entry in updates:
        if entry.get("source_id") == source_id:
            existing = entry.setdefault("contest_aliases", [])
            if alias not in existing:
                existing.append(alias)
            _save_overrides(data)
            return True

    updates.append({"source_id": source_id, "contest_aliases": [alias]})
    _save_overrides(data)
    log.info(f"[REGISTRY_UPDATES] Added alias '{alias}' to {source_id}")
    return True


def add_manual_contest_source(entry: dict) -> bool:
    """
    Add a manually-specified contest source to local_overrides.yaml.

    Args:
        entry: Dict matching contest source schema. Must include source_id.
    """
    if "source_id" not in entry:
        log.warning("[REGISTRY_UPDATES] add_manual_contest_source: source_id required")
        return False

    data = _load_overrides()
    sources = data.setdefault("manual_contest_sources", []) or []

    # Update if already exists
    for i, s in enumerate(sources):
        if s.get("source_id") == entry["source_id"]:
            sources[i] = {**s, **entry}
            _save_overrides(data)
            log.info(f"[REGISTRY_UPDATES] Updated manual contest source: {entry['source_id']}")
            return True

    entry.setdefault("added_at", datetime.now().isoformat())
    sources.append(entry)
    _save_overrides(data)
    log.info(f"[REGISTRY_UPDATES] Added manual contest source: {entry['source_id']}")
    return True


def add_manual_geometry_source(entry: dict) -> bool:
    """
    Add a manually-specified geometry source to local_overrides.yaml.
    """
    if "source_id" not in entry:
        log.warning("[REGISTRY_UPDATES] add_manual_geometry_source: source_id required")
        return False

    data = _load_overrides()
    sources = data.setdefault("manual_geometry_sources", []) or []

    for i, s in enumerate(sources):
        if s.get("source_id") == entry["source_id"]:
            sources[i] = {**s, **entry}
            _save_overrides(data)
            return True

    entry.setdefault("added_at", datetime.now().isoformat())
    sources.append(entry)
    _save_overrides(data)
    log.info(f"[REGISTRY_UPDATES] Added manual geometry source: {entry['source_id']}")
    return True


def add_notes(source_id: str, notes: str, source_type: str = "contest") -> bool:
    """Append a note to an existing registry entry override."""
    data = _load_overrides()
    if not isinstance(data.get("approved_updates"), list):
        data["approved_updates"] = []
    updates = data["approved_updates"]

    for entry in updates:
        if entry.get("source_id") == source_id:
            existing = entry.get("notes", "")
            entry["notes"] = (existing + "\n" + notes).strip()
            _save_overrides(data)
            return True

    updates.append({
        "source_id": source_id,
        "notes":     notes,
        "noted_at":  datetime.now().isoformat(),
    })
    _save_overrides(data)
    return True
