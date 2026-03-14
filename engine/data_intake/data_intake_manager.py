"""
engine/data_intake/data_intake_manager.py — Prompt 17.5

Canonical manager for all campaigned data files.
Responsibilities:
- classify newly uploaded files (polling, voter_file, election_results, etc.)
- determine destination paths
- manage the canonical file registry
- handle safe archiving, renaming, relocating, and relabeling
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

# Canonical paths map based on category
_DESTINATION_RULES = {
    "election_results":          "data/elections/{state}/{county}/{contest_id}/",
    "voter_file":                "data/voters/{state}/{county}/",
    "precinct_geometry":         "data/geography/{state}/{county}/",
    "crosswalk":                 "data/crosswalks/{state}/{county}/",
    "polling":                   "data/intelligence/polling/",
    "demographics":              "data/intelligence/demographics/",
    "registration_trends":       "data/intelligence/registration/",
    "ballot_returns":            "data/intelligence/ballot_returns/",
    "campaign_runtime_field":    "data/campaign_runtime/{state}/{county}/{contest_id}/field/",
    "campaign_runtime_budget":   "data/campaign_runtime/{state}/{county}/{contest_id}/finance/",
    "campaign_runtime_volunteers":"data/campaign_runtime/{state}/{county}/{contest_id}/volunteers/",
    "supporting_document":       "data/documents/{state}/{county}/{contest_id}/",
    "unknown":                   "data/uploads/unclassified/"
}


class FileRegistryManager:
    """Manages the lifecycle of Campaign In A Box data files."""

    # Expose the module-level rules as a class attribute so callers can access via manager._DESTINATION_RULES
    _DESTINATION_RULES = _DESTINATION_RULES

    def __init__(self, project_root: str | Path):
        self.root = Path(project_root)
        self.registry_dir_latest  = self.root / "derived" / "file_registry" / "latest"
        self.registry_dir_history = self.root / "derived" / "file_registry" / "history"
        self.archive_dir          = self.root / "archive" / "files"

        self.registry_dir_latest.mkdir(parents=True, exist_ok=True)
        self.registry_dir_history.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.registry_dir_latest / "file_registry.json"

    def load_registry(self) -> list[dict]:
        """Load the active file registry. Always returns a list."""
        if self.registry_path.exists():
            try:
                data = json.loads(self.registry_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
                # File was written as a dict (e.g. empty init) — reset gracefully
                log.warning(
                    f"file_registry.json contains a {type(data).__name__}, expected list. "
                    "Resetting to empty registry."
                )
                return []
            except Exception as e:
                log.error(f"Failed to read file registry: {e}")
        return []

    def _save_registry(self, registry: list[dict], run_id: Optional[str] = None):
        """Save to latest and history."""
        payload = json.dumps(registry, indent=2, default=str)
        self.registry_path.write_text(payload, encoding="utf-8")

        now = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
        hist_name = f"{run_id or now}__file_registry.json"
        (self.registry_dir_history / hist_name).write_text(payload, encoding="utf-8")

    def classify_file(self, file_path: Path) -> dict:
        """
        Scan a given file (filename, extension, headers) and guess its category.
        Returns dict with "campaign_data_type" and "provenance".
        """
        name = file_path.name.lower()
        ext  = file_path.suffix.lower()

        cat = "unknown"
        prov = "EXTERNAL"

        if ext == ".geojson" or ext == ".shp" or ext == ".zip":
            if "precinct" in name or "boundary" in name:
                cat = "precinct_geometry"

        elif ext in (".csv", ".tsv", ".xlsx", ".xls"):
            # Check filename clues
            if "voter" in name or "vf_" in name:
                cat = "voter_file"
                prov = "REAL"
            elif "election" in name or "result" in name or "sov" in name:
                cat = "election_results"
                prov = "REAL"
            elif "poll" in name or "survey" in name:
                cat = "polling"
            elif "demo" in name or "census" in name or "acs" in name:
                cat = "demographics"
            elif "reg" in name and "trend" in name:
                cat = "registration_trends"
            elif "return" in name or "ballot" in name:
                cat = "ballot_returns"
            elif "crosswalk" in name or "xwalk" in name:
                cat = "crosswalk"
            elif "field" in name or "door" in name or "canvass" in name:
                cat = "campaign_runtime_field"
                prov = "REAL"
            elif "budget" in name or "finance" in name:
                cat = "campaign_runtime_budget"
                prov = "REAL"
            elif "vol" in name or "schedule" in name:
                cat = "campaign_runtime_volunteers"
                prov = "REAL"
            else:
                # Try header scanning if CSV
                if ext == ".csv":
                    try:
                        df = pd.read_csv(file_path, nrows=5)
                        cols = [c.lower() for c in df.columns]
                        if any(c in cols for c in ["voterid", "voter_id", "dob", "address"]):
                            cat = "voter_file"
                            prov = "REAL"
                        elif any(c in cols for c in ["support_percent", "pollster"]):
                            cat = "polling"
                        elif any(c in cols for c in ["ballots_returned", "return_rate"]):
                            cat = "ballot_returns"
                    except Exception:
                        pass
        elif ext in (".pdf", ".docx", ".txt", ".md"):
            cat = "supporting_document"

        return {"campaign_data_type": cat, "provenance": prov}

    def propose_destination(self, filename: str, category: str, state: str="", county: str="", contest_id: str="") -> str:
        """Get the expected canonical path relative to project root."""
        rule = _DESTINATION_RULES.get(category, _DESTINATION_RULES["unknown"])
        s = state or "UNKNOWN_STATE"
        c = county or "UNKNOWN_COUNTY"
        cid = contest_id or "UNKNOWN_CONTEST"
        path_dir = rule.format(state=s, county=c, contest_id=cid)
        return str(Path(path_dir) / filename).replace("\\", "/")

    def register_new_file(
        self,
        source_file: Path,
        category: str,
        provenance: str,
        state: str = "",
        county: str = "",
        contest_id: str = "",
        notes: str = "",
        proposed_name: str = "",
    ) -> dict:
        """
        Move a source file to canonical location and add to registry.
        """
        orig_name = source_file.name
        new_name  = proposed_name if proposed_name else orig_name
        dest_rel  = self.propose_destination(new_name, category, state, county, contest_id)
        dest_abs  = self.root / dest_rel

        dest_abs.parent.mkdir(parents=True, exist_ok=True)

        # Use explicit binary read/write instead of shutil.copy2.
        # On Windows, pandas/openpyxl may hold the source file open during
        # preview/fingerprint analysis, causing WinError 32 with shutil.copy2.
        try:
            dest_abs.write_bytes(source_file.read_bytes())
        except PermissionError:
            # Last-resort fallback: read in chunks with shared-read mode
            import ctypes
            with open(source_file, "rb") as src_f:
                dest_abs.write_bytes(src_f.read())

        record = {
            "file_id": f"F_{uuid.uuid4().hex[:8].upper()}",
            "original_filename": orig_name,
            "current_filename": new_name,
            "current_path": dest_rel,
            "file_type": Path(new_name).suffix.lower().replace(".", ""),
            "campaign_data_type": category,
            "state": state,
            "county": county,
            "contest_id": contest_id,
            "uploaded_at": datetime.utcnow().isoformat(),
            "last_modified": datetime.utcnow().isoformat(),
            "source_type": "UPLOADED",
            "provenance": provenance,
            "status": "ACTIVE",
            "notes": notes
        }

        registry = self.load_registry()
        if not isinstance(registry, list):
            log.warning("register_new_file: registry was not a list, resetting.")
            registry = []
        registry.append(record)
        self._save_registry(registry)

        return record

    def update_file(
        self,
        file_id: str,
        new_name: Optional[str] = None,
        new_category: Optional[str] = None,
        state: Optional[str] = None,
        county: Optional[str] = None,
        contest_id: Optional[str] = None,
    ) -> dict | None:
        """
        Rename, relabel, or move an existing file.
        Updates the registry and physically moves the file.
        """
        registry = self.load_registry()
        record_idx = next((i for i, r in enumerate(registry) if r["file_id"] == file_id), None)
        if record_idx is None:
            return None

        record = registry[record_idx]
        old_path_rel = record["current_path"]
        old_path_abs = self.root / old_path_rel

        # Build updated properties
        cat  = new_category if new_category is not None else record["campaign_data_type"]
        name = new_name if new_name is not None else record["current_filename"]
        st   = state if state is not None else record["state"]
        co   = county if county is not None else record["county"]
        cid  = contest_id if contest_id is not None else record["contest_id"]

        new_path_rel = self.propose_destination(name, cat, st, co, cid)
        new_path_abs = self.root / new_path_rel

        # Physically move if changed
        if new_path_rel != old_path_rel:
            if old_path_abs.exists():
                new_path_abs.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(old_path_abs, new_path_abs)
            else:
                log.warning(f"Source file {old_path_abs} missing. Only updating registry.")

        record["current_filename"] = name
        record["campaign_data_type"] = cat
        record["state"] = st
        record["county"] = co
        record["contest_id"] = cid
        record["current_path"] = new_path_rel
        record["last_modified"] = datetime.utcnow().isoformat()

        self._save_registry(registry)
        return record

    def archive_file(self, file_id: str) -> bool:
        """
        Moves the file to the archive directory and marks registry as ARCHIVED.
        """
        registry = self.load_registry()
        record_idx = next((i for i, r in enumerate(registry) if r["file_id"] == file_id), None)
        if record_idx is None:
            return False

        record = registry[record_idx]
        if record["status"] == "ARCHIVED":
            return True

        old_path_abs = self.root / record["current_path"]
        today = datetime.utcnow().strftime("%Y-%m-%d")
        safe_name = f"{record['file_id']}__{record['current_filename']}"
        archive_dest = self.archive_dir / today / safe_name

        if old_path_abs.exists():
            archive_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(old_path_abs, archive_dest)

        record["status"] = "ARCHIVED"
        record["last_modified"] = datetime.utcnow().isoformat()
        
        self._save_registry(registry)
        return True

    def replace_file(self, file_id: str, new_source_file: Path) -> dict | None:
        """
        Archives the old file, saves new file in its place, updates record timestamp.
        """
        registry = self.load_registry()
        record = next((r for r in registry if r["file_id"] == file_id), None)
        if not record:
            return None

        # Archive old
        old_path_abs = self.root / record["current_path"]
        today = datetime.utcnow().strftime("%Y-%m-%d")
        safe_name_old = f"{record['file_id']}_OLD_{datetime.utcnow().strftime('%H%M%S')}__{record['current_filename']}"
        archive_dest = self.archive_dir / today / safe_name_old

        if old_path_abs.exists():
            archive_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(old_path_abs, archive_dest)

        # Place new
        new_path_abs = self.root / record["current_path"]
        new_path_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(new_source_file, new_path_abs)

        record["last_modified"] = datetime.utcnow().isoformat()
        
        self._save_registry(registry)
        return record
