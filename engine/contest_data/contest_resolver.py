"""
engine/contest_data/contest_resolver.py  — Prompt 28

Single authoritative resolver for all contest/election-result data.

Canonical contest root:
  data/contests/{state}/{county}/{year}/{contest_slug}/
    raw/          — original uploaded files
    normalized/   — cleaned result tables
    manifests/    — contest_metadata.json, ingest_manifest.json, primary_result_file.json

NO OTHER MODULE should hardcode paths like:
  data/elections/...           (old Data Manager upload path)
  data/CA/counties/.../votes/  (old pipeline native path)

All contest-data reads/writes must go through this resolver.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_DEFAULT_ROOT = "data/contests"


class ContestResolver:
    """
    Resolves canonical paths and manifest data for contest/election-result files.

    Usage:
        resolver = ContestResolver(project_root)
        raw_dir  = resolver.get_contest_raw_dir("CA", "Sonoma", 2020, "nov2020_general")
        xlsx     = resolver.resolve_primary_result_file("CA", "Sonoma", 2020, "nov2020_general")
    """

    def __init__(self, project_root: str | Path, contests_root: str = _DEFAULT_ROOT):
        self.root = Path(project_root)
        self.contests_root = self.root / contests_root

    # ── Path resolvers ────────────────────────────────────────────────────────

    def get_contest_root(
        self,
        state: str,
        county: str,
        year: int | str,
        contest_slug: str,
    ) -> Path:
        """Return the canonical contest directory (creates it if needed)."""
        p = self.contests_root / state / county / str(year) / contest_slug
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_contest_raw_dir(self, state: str, county: str, year: int | str, contest_slug: str) -> Path:
        d = self.get_contest_root(state, county, year, contest_slug) / "raw"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_contest_normalized_dir(self, state: str, county: str, year: int | str, contest_slug: str) -> Path:
        d = self.get_contest_root(state, county, year, contest_slug) / "normalized"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_contest_manifests_dir(self, state: str, county: str, year: int | str, contest_slug: str) -> Path:
        d = self.get_contest_root(state, county, year, contest_slug) / "manifests"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── Manifest helpers ──────────────────────────────────────────────────────

    def resolve_contest_manifest(
        self,
        state: str,
        county: str,
        year: int | str,
        contest_slug: str,
        manifest_name: str = "contest_metadata.json",
    ) -> Optional[dict]:
        """Load a manifest dict or None if not yet written."""
        mdir = self.get_contest_manifests_dir(state, county, year, contest_slug)
        p = mdir / manifest_name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning(f"Could not parse manifest {p}: {e}")
        return None

    def write_contest_manifest(
        self,
        state: str,
        county: str,
        year: int | str,
        contest_slug: str,
        manifest_name: str,
        data: dict,
    ) -> Path:
        """Write a manifest and return the path."""
        mdir = self.get_contest_manifests_dir(state, county, year, contest_slug)
        p = mdir / manifest_name
        p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return p

    # ── Primary result file ───────────────────────────────────────────────────

    def resolve_primary_result_file(
        self,
        state: str,
        county: str,
        year: int | str,
        contest_slug: str,
    ) -> Optional[Path]:
        """
        Return the chosen primary result file for this contest, or None.
        Preference order:
          1. Explicit selection in manifests/primary_result_file.json
          2. Largest .xlsx / .xls / .csv in raw/

        NOTE: This method does NOT create directories.
        """
        # Build paths without triggering mkdir
        contest_dir = self.contests_root / state / county / str(year) / contest_slug
        if not contest_dir.exists():
            return None

        raw_dir      = contest_dir / "raw"
        manifests_dir = contest_dir / "manifests"

        # Check explicit manifest first
        manifest_path = manifests_dir / "primary_result_file.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("primary_file"):
                    p = raw_dir / manifest["primary_file"]
                    if p.exists():
                        return p
                    log.warning(f"primary_result_file.json points to missing file: {p}")
            except Exception as e:
                log.warning(f"Could not parse manifest {manifest_path}: {e}")

        # Fallback: largest result file in raw/
        if raw_dir.exists():
            candidates = sorted(
                [f for f in raw_dir.iterdir() if f.is_file() and f.suffix.lower() in (".xlsx", ".xls", ".csv")],
                key=lambda f: f.stat().st_size,
                reverse=True,
            )
            if candidates:
                log.info(f"Auto-selected primary result file: {candidates[0].name}")
                return candidates[0]
        return None


    def set_primary_result_file(
        self,
        state: str,
        county: str,
        year: int | str,
        contest_slug: str,
        filename: str,
    ) -> Path:
        """Mark a file as the primary result file for the contest."""
        return self.write_contest_manifest(
            state, county, year, contest_slug,
            "primary_result_file.json",
            {"primary_file": filename, "set_at": __import__("datetime").datetime.utcnow().isoformat()},
        )

    # ── Discovery helpers ─────────────────────────────────────────────────────

    def list_all_contests(self) -> list[dict]:
        """Return list of all contest dicts discoverable under data/contests/."""
        results = []
        if not self.contests_root.exists():
            return results
        for state_dir in self.contests_root.iterdir():
            if not state_dir.is_dir(): continue
            state = state_dir.name
            for county_dir in state_dir.iterdir():
                if not county_dir.is_dir(): continue
                county = county_dir.name
                for year_dir in county_dir.iterdir():
                    if not year_dir.is_dir(): continue
                    year = year_dir.name
                    for slug_dir in year_dir.iterdir():
                        if not slug_dir.is_dir(): continue
                        slug = slug_dir.name
                        raw_files = list((slug_dir / "raw").glob("*")) if (slug_dir / "raw").exists() else []
                        primary = self.resolve_primary_result_file(state, county, year, slug)
                        meta = self.resolve_contest_manifest(state, county, year, slug)
                        results.append({
                            "state": state,
                            "county": county,
                            "year": year,
                            "contest_slug": slug,
                            "raw_file_count": len(raw_files),
                            "has_primary": primary is not None,
                            "primary_file": primary.name if primary else None,
                            "label": f"{county} / {year} / {slug}",
                            "contest_root": str(slug_dir),
                            "election_type": (meta or {}).get("election_type", "unknown"),
                        })
        return sorted(results, key=lambda c: (c["county"], c["year"], c["contest_slug"]))

    # ── Legacy path detection ─────────────────────────────────────────────────

    def detect_legacy_contest_files(self) -> list[dict]:
        """
        Scan known legacy paths and report any contest/result files still present.
        Used by contest_health.py.
        """
        legacy = []
        legacy_roots = [
            self.root / "data" / "elections",
            self.root / "votes",
        ]
        # Also scan data/{state}/counties/{county}/votes/
        data_root = self.root / "data"
        if data_root.exists():
            for state_dir in data_root.iterdir():
                if not state_dir.is_dir() or state_dir.name in ("contests", "elections", "uploads"): continue
                counties_d = state_dir / "counties"
                if counties_d.exists():
                    for county_dir in counties_d.iterdir():
                        votes_d = county_dir / "votes"
                        if votes_d.exists():
                            legacy_roots.append(votes_d)

        for lr in legacy_roots:
            if not lr.exists(): continue
            for f in lr.rglob("*"):
                if f.is_file() and f.suffix.lower() in (".xlsx", ".xls", ".csv"):
                    legacy.append({
                        "path": str(f.relative_to(self.root)),
                        "legacy_root": str(lr.relative_to(self.root)),
                        "size_bytes": f.stat().st_size,
                    })
        return legacy
