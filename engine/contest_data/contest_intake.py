"""
engine/contest_data/contest_intake.py  — Prompt 28

Unified contest data intake workflow.

All election result files — whether uploaded through the Data Manager UI,
discovered by the archive builder, or supplied by any other means — must
enter the system through this module.

One upload → one canonical contest record. Duplicate uploads for the same
physical file are detected by SHA-256 and do NOT create new active entries.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from engine.contest_data.contest_resolver import ContestResolver

log = logging.getLogger(__name__)


class ContestIntake:
    """
    Canonical intake workflow for election result files.

    Steps:
        1. Hash file
        2. Detect duplicate (same SHA-256 already in contest)
        3. Fingerprint file type (delegates to fingerprint_engine if available)
        4. Copy to canonical raw/ directory
        5. Write manifests (ingest_manifest.json, contest_metadata.json)
        6. Register in canonical file registry
        7. Optionally mark as primary result file
    """

    def __init__(self, project_root: str | Path):
        self.root = Path(project_root)
        self.resolver = ContestResolver(self.root)
        self._registry_path = (
            self.root / "derived" / "file_registry" / "latest" / "file_registry.json"
        )
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def ingest(
        self,
        source_file: Path,
        state: str,
        county: str,
        year: int | str,
        contest_slug: str,
        provenance: str = "REAL",
        notes: str = "",
        set_as_primary: bool = True,
        raw_bytes: Optional[bytes] = None,
        uploaded_by: str = "manual",
        ingest_source: str = "data_manager_ui",
    ) -> dict:
        """
        Ingest one contest result file into the canonical contest structure.

        Returns the ingest record dict.
        Raises DuplicateFileError if the same SHA-256 already exists as primary.
        """
        year = str(year)
        src_bytes = raw_bytes if raw_bytes is not None else source_file.read_bytes()
        sha256 = hashlib.sha256(src_bytes).hexdigest()

        raw_dir = self.resolver.get_contest_raw_dir(state, county, year, contest_slug)

        # ── 1. Duplicate detection ────────────────────────────────────────────
        existing = self._find_duplicate(state, county, year, contest_slug, sha256)
        if existing:
            log.info(f"[INTAKE] Duplicate file detected (sha256={sha256[:12]}…), skipping copy.")
            return existing

        # ── 2. Determine destination filename ────────────────────────────────
        dest_name = source_file.name
        dest_path = raw_dir / dest_name
        # If a different file already exists with this name, version it
        if dest_path.exists():
            stem = dest_path.stem
            suffix = dest_path.suffix
            dest_name = f"{stem}_v{uuid.uuid4().hex[:4]}{suffix}"
            dest_path = raw_dir / dest_name

        # ── 3. Write to canonical location ───────────────────────────────────
        dest_path.write_bytes(src_bytes)
        log.info(f"[INTAKE] Written: {dest_path.relative_to(self.root)}")

        # ── 4. Fingerprint (optional, non-fatal) ─────────────────────────────
        fingerprint_type = "unknown"
        fingerprint_confidence = 0.0
        try:
            from engine.file_fingerprinting.fingerprint_engine import classify as fp_classify
            fp = fp_classify(dest_path, use_cache=False)
            fingerprint_type = fp.file_type
            fingerprint_confidence = fp.confidence
        except Exception:
            pass

        # ── 5. Build ingest record ────────────────────────────────────────────
        now = datetime.utcnow().isoformat()
        file_id = f"C_{uuid.uuid4().hex[:8].upper()}"
        contest_root_rel = str(
            self.resolver.get_contest_root(state, county, year, contest_slug).relative_to(self.root)
        )
        record = {
            "file_id": file_id,
            "original_filename": source_file.name,
            "canonical_filename": dest_name,
            "canonical_path": str(dest_path.relative_to(self.root)),
            "contest_root": contest_root_rel,
            "state": state,
            "county": county,
            "year": year,
            "contest_slug": contest_slug,
            "sha256": sha256,
            "size_bytes": len(src_bytes),
            "file_type": dest_path.suffix.lower().lstrip("."),
            "fingerprint_type": fingerprint_type,
            "fingerprint_confidence": fingerprint_confidence,
            "provenance": provenance,
            "is_primary": False,        # set below after registry write
            "normalization_status": "PENDING",
            "archive_status": "REGISTERED",
            "uploaded_by": uploaded_by,
            "ingest_source": ingest_source,
            "ingested_at": now,
            "last_modified": now,
            "notes": notes,
        }

        # ── 6. Write manifests ────────────────────────────────────────────────
        self._write_ingest_manifest(state, county, year, contest_slug, record)
        self._ensure_contest_metadata(state, county, year, contest_slug, state, contest_slug)

        # ── 7. Register in canonical registry ─────────────────────────────────
        self._append_to_registry(record)

        # ── 8. Mark primary ──────────────────────────────────────────────────
        if set_as_primary:
            self.resolver.set_primary_result_file(state, county, year, contest_slug, dest_name)
            record["is_primary"] = True
            self._update_registry_record(file_id, {"is_primary": True})

        log.info(f"[INTAKE] Ingested file_id={file_id}  primary={record['is_primary']}")
        return record

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_duplicate(
        self, state: str, county: str, year: str, contest_slug: str, sha256: str
    ) -> Optional[dict]:
        registry = self._load_registry()
        for r in registry:
            if (
                r.get("sha256") == sha256
                and r.get("state") == state
                and r.get("county") == county
                and r.get("year") == year
                and r.get("contest_slug") == contest_slug
            ):
                return r
        return None

    def _write_ingest_manifest(
        self, state: str, county: str, year: str, contest_slug: str, record: dict
    ) -> None:
        existing = self.resolver.resolve_contest_manifest(
            state, county, year, contest_slug, "ingest_manifest.json"
        ) or {"files": []}
        files = existing.get("files", [])
        files.append({
            "file_id": record["file_id"],
            "canonical_filename": record["canonical_filename"],
            "sha256": record["sha256"],
            "ingested_at": record["ingested_at"],
            "fingerprint_type": record["fingerprint_type"],
            "provenance": record["provenance"],
        })
        existing["files"] = files
        existing["last_updated"] = datetime.utcnow().isoformat()
        self.resolver.write_contest_manifest(
            state, county, year, contest_slug, "ingest_manifest.json", existing
        )

    def _ensure_contest_metadata(
        self,
        state: str, county: str, year: str, contest_slug: str,
        state_code: str, slug: str,
    ) -> None:
        existing = self.resolver.resolve_contest_manifest(
            state, county, year, contest_slug, "contest_metadata.json"
        )
        if existing:
            return
        meta = {
            "state": state_code,
            "county": county,
            "year": year,
            "contest_slug": slug,
            "election_type": "unknown",
            "created_at": datetime.utcnow().isoformat(),
        }
        self.resolver.write_contest_manifest(
            state, county, year, contest_slug, "contest_metadata.json", meta
        )

    def _load_registry(self) -> list[dict]:
        if self._registry_path.exists():
            try:
                data = json.loads(self._registry_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        return []

    def _save_registry(self, registry: list[dict]) -> None:
        self._registry_path.write_text(
            json.dumps(registry, indent=2, default=str), encoding="utf-8"
        )

    def _append_to_registry(self, record: dict) -> None:
        registry = self._load_registry()
        registry.append(record)
        self._save_registry(registry)

    def _update_registry_record(self, file_id: str, updates: dict) -> None:
        registry = self._load_registry()
        for r in registry:
            if r.get("file_id") == file_id:
                r.update(updates)
                break
        self._save_registry(registry)
