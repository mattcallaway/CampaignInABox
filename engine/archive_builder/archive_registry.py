"""
engine/archive_builder/archive_registry.py — Prompt 25 / Prompt 27

Archive registry manager.

Maintains data/historical_elections/archive_registry.yaml with one entry
per ingested election dataset.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = BASE_DIR / "data" / "historical_elections" / "archive_registry.yaml"
REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"schema_version": "1.0", "elections": []}
    try:
        data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
        if "elections" not in data:
            data["elections"] = []
        return data
    except Exception as e:
        log.error(f"[REGISTRY] Failed to load: {e}")
        return {"schema_version": "1.0", "elections": []}


def _save_registry(data: dict) -> None:
    REGISTRY_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def register_election(
    election_id: str, state: str, county: str,
    year: Optional[int], election_type: Optional[str],
    source_url: str, files_ingested: int, confidence_score: float,
    fingerprint_type: str, precinct_schema: Optional[str],
    normalization_method: str, join_confidence: float, archive_dir: str,
    # Prompt 27 / Prompt 25 additions
    archive_status: str = "ARCHIVE_READY",
    run_id: Optional[str] = None,
    file_path: Optional[str] = None,
) -> dict:
    """Register or update an ingested election in the archive registry."""
    registry = _load_registry()
    elections: list[dict] = registry.get("elections", [])

    entry = {
        "election_id": election_id, "state": state, "county": county,
        "year": year, "election_type": election_type,
        "source_url": source_url, "files_ingested": files_ingested,
        "confidence_score": round(confidence_score, 4),
        "fingerprint_type": fingerprint_type, "precinct_schema": precinct_schema,
        "normalization_method": normalization_method,
        "join_confidence": round(join_confidence, 4),
        "archive_dir": archive_dir,
        # Prompt 27 / Prompt 25 additions
        "archive_status":   archive_status,
        "run_id":           run_id or "",
        "file_path":        file_path or "",
        "ingestion_date": datetime.now().strftime("%Y-%m-%d"),
        "last_updated": datetime.now().isoformat(),
    }

    updated = False
    for i, existing in enumerate(elections):
        if existing.get("election_id") == election_id:
            elections[i] = entry
            updated = True
            break
    if not updated:
        elections.append(entry)

    registry["elections"] = elections
    registry["last_updated"] = datetime.now().isoformat()
    _save_registry(registry)
    log.info(f"[REGISTRY] {'Updated' if updated else 'Registered'}: {election_id}")
    return entry


def get_election(election_id: str) -> Optional[dict]:
    data = _load_registry()
    for e in data.get("elections", []):
        if e.get("election_id") == election_id:
            return e
    return None


def list_elections(state: Optional[str] = None, county: Optional[str] = None) -> list[dict]:
    data = _load_registry()
    entries = data.get("elections", [])
    if state:
        entries = [e for e in entries if e.get("state", "").upper() == state.upper()]
    if county:
        entries = [e for e in entries if e.get("county", "").lower() == county.lower()]
    return entries


def registry_summary() -> dict:
    data = _load_registry()
    elections = data.get("elections", [])
    total = len(elections)
    avg_conf = sum(e.get("confidence_score", 0) for e in elections) / max(total, 1)
    return {
        "total": total,
        "states": sorted({e.get("state", "") for e in elections}),
        "counties": sorted({e.get("county", "") for e in elections}),
        "years": sorted({e.get("year") for e in elections if e.get("year")}),
        "avg_confidence": round(avg_conf, 3),
        "election_types": sorted({e.get("election_type", "") for e in elections}),
    }
