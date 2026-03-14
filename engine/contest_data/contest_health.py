"""
engine/contest_data/contest_health.py  — Prompt 28

Contest data health checker.

Answers:
  - Are there any legacy contest files left outside canonical structure?
  - Is there exactly one primary result file per contest?
  - Are there duplicate contest-result registry entries?
  - Are any manifests broken?
  - Is any pipeline module still pointing at legacy contest paths?

Usage:
    checker = ContestHealthChecker(project_root)
    report  = checker.run()
    checker.write_report(output_path, report)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from engine.contest_data.contest_resolver import ContestResolver

log = logging.getLogger(__name__)


class ContestHealthChecker:

    LEGACY_ROOTS = [
        "data/elections",
        "votes",
        "data/election_archive/raw",
        "data/election_archive/normalized",
    ]

    LEGACY_CODE_PATTERNS = [
        "data/elections",
        "data/CA/counties",
        "votes/{year}",
        "/votes/",
    ]

    SCAN_CODE_DIRS = [
        "scripts",
        "engine",
        "ui",
    ]

    def __init__(self, project_root: str | Path):
        self.root = Path(project_root)
        self.resolver = ContestResolver(self.root)
        self._registry_path = (
            self.root / "derived" / "file_registry" / "latest" / "file_registry.json"
        )

    def run(self) -> dict:
        contests = self.resolver.list_all_contests()
        legacy   = self.resolver.detect_legacy_contest_files()
        dupes    = self._detect_registry_duplicates()
        manifest_issues = self._check_manifests(contests)
        legacy_code     = self._scan_code_for_legacy_paths()
        multi_primary   = self._check_multiple_primaries(contests)

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "canonical_contests": len(contests),
            "contests": contests,
            "legacy_files_remaining": legacy,
            "legacy_file_count": len(legacy),
            "registry_duplicates": dupes,
            "duplicate_count": len(dupes),
            "manifest_issues": manifest_issues,
            "legacy_code_references": legacy_code,
            "contests_with_multiple_primaries": multi_primary,
            "health_score": self._compute_health(legacy, dupes, manifest_issues, multi_primary),
        }

    def write_report(self, output_path: Path, report: Optional[dict] = None) -> Path:
        if report is None:
            report = self.run()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )
        return output_path

    def write_markdown_report(self, output_path: Path, report: Optional[dict] = None) -> Path:
        if report is None:
            report = self.run()
        lines = [
            "# Contest Data Health Report",
            f"**Generated:** {report['generated_at']}",
            f"**Health Score:** {report['health_score']}/10",
            "",
            "## Summary",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Canonical contests | {report['canonical_contests']} |",
            f"| Legacy files remaining | {report['legacy_file_count']} |",
            f"| Registry duplicates | {report['duplicate_count']} |",
            f"| Manifest issues | {len(report['manifest_issues'])} |",
            f"| Legacy code references | {len(report['legacy_code_references'])} |",
            f"| Multi-primary contests | {len(report['contests_with_multiple_primaries'])} |",
            "",
        ]

        lines.append("## Canonical Contests")
        if report["contests"]:
            lines.append("| State | County | Year | Slug | Has Primary | Raw Files |")
            lines.append("|---|---|---|---|---|---|")
            for c in report["contests"]:
                lines.append(
                    f"| {c['state']} | {c['county']} | {c['year']} | {c['contest_slug']} "
                    f"| {'✅' if c['has_primary'] else '❌'} | {c['raw_file_count']} |"
                )
        else:
            lines.append("_No canonical contests found._")
        lines.append("")

        lines.append("## Legacy Files Remaining")
        if report["legacy_files_remaining"]:
            lines.append("> [!CAUTION]")
            lines.append("> These files are outside the canonical contest structure and may cause path confusion.")
            lines.append("")
            lines.append("| Path | Legacy Root | Size |")
            lines.append("|---|---|---|")
            for f in report["legacy_files_remaining"]:
                lines.append(f"| `{f['path']}` | `{f['legacy_root']}` | {f['size_bytes']:,} bytes |")
        else:
            lines.append("✅ No legacy contest files found outside canonical structure.")
        lines.append("")

        lines.append("## Registry Duplicates")
        if report["registry_duplicates"]:
            for d in report["registry_duplicates"]:
                lines.append(f"- File IDs: {d['file_ids']} — SHA256: `{d['sha256'][:12]}…`")
        else:
            lines.append("✅ No duplicate registry entries found.")
        lines.append("")

        lines.append("## Legacy Code References")
        if report["legacy_code_references"]:
            lines.append("> [!WARNING]")
            lines.append("> These source files still reference legacy contest data paths.")
            lines.append("")
            for ref in report["legacy_code_references"][:20]:
                lines.append(f"- `{ref['file']}:{ref['line']}` — `{ref['text'].strip()}`")
        else:
            lines.append("✅ No legacy contest path references found in source.")
        lines.append("")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    # ── Internal checks ───────────────────────────────────────────────────────

    def _detect_registry_duplicates(self) -> list[dict]:
        if not self._registry_path.exists():
            return []
        try:
            data = json.loads(self._registry_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
        except Exception:
            return []

        seen: dict[str, list[str]] = {}
        for r in data:
            sha = r.get("sha256") or r.get("original_filename", "")
            key = f"{r.get('state','')}:{r.get('county','')}:{r.get('year','')}:{sha}"
            seen.setdefault(key, []).append(r.get("file_id", "?"))

        return [
            {"sha256": k.split(":")[-1], "file_ids": v}
            for k, v in seen.items()
            if len(v) > 1
        ]

    def _check_manifests(self, contests: list[dict]) -> list[dict]:
        issues = []
        for c in contests:
            mdir = self.resolver.get_contest_manifests_dir(
                c["state"], c["county"], c["year"], c["contest_slug"]
            )
            meta = mdir / "contest_metadata.json"
            if not meta.exists():
                issues.append({"contest": c["label"], "issue": "contest_metadata.json missing"})
        return issues

    def _scan_code_for_legacy_paths(self) -> list[dict]:
        refs = []
        for code_dir in self.SCAN_CODE_DIRS:
            d = self.root / code_dir
            if not d.exists():
                continue
            for py_file in d.rglob("*.py"):
                try:
                    lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
                except Exception:
                    continue
                for i, line in enumerate(lines, 1):
                    for pat in self.LEGACY_CODE_PATTERNS:
                        if pat in line and "contest_resolver" not in line and "#" not in line[:line.find(pat)]:
                            refs.append({
                                "file": str(py_file.relative_to(self.root)),
                                "line": i,
                                "pattern": pat,
                                "text": line,
                            })
        return refs

    def _check_multiple_primaries(self, contests: list[dict]) -> list[str]:
        multi = []
        for c in contests:
            raw_dir = self.resolver.get_contest_raw_dir(
                c["state"], c["county"], c["year"], c["contest_slug"]
            )
            files = [f for f in raw_dir.glob("*") if f.suffix.lower() in (".xlsx", ".xls", ".csv")]
            if len(files) > 1:
                manifest = self.resolver.resolve_contest_manifest(
                    c["state"], c["county"], c["year"], c["contest_slug"], "primary_result_file.json"
                )
                if not manifest:
                    multi.append(c["label"])
        return multi

    def _compute_health(self, legacy, dupes, manifest_issues, multi_primary) -> float:
        score = 10.0
        score -= min(len(legacy) * 0.5, 3.0)
        score -= min(len(dupes) * 0.5, 2.0)
        score -= min(len(manifest_issues) * 0.3, 1.5)
        score -= min(len(multi_primary) * 0.5, 1.5)
        return round(max(0.0, score), 1)
