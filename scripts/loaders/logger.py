"""
scripts/loaders/logger.py

NOTE: All log strings use ASCII-only symbols for Windows CP1252 compatibility.
  - Arrows: -> (not →)
  - Check:  [OK] / [FAIL] (not ✓/✗)
  - Skip:   [SKIP] (not ⊘)

Implements the full Campaign In A Box logging contract.

Every pipeline run produces:
  logs/runs/<RUN_ID>__run.log
  logs/runs/<RUN_ID>__pathway.json
  reports/validation/<RUN_ID>__validation_report.md
  reports/qa/<RUN_ID>__qa_sanity_checks.md
  needs/needs.yaml  (updated)
  needs/history/<RUN_ID>__needs_snapshot.yaml
  logs/latest/  (copies of above + RUN_ID.txt)
"""

import json
import os
import shutil
import time
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from scripts.lib.naming import normalize_county, generate_contest_id


def generate_run_id() -> str:
    """Generate deterministic RUN_ID: YYYYMMDD_HHMMSS_<8hex>."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"{ts}_{short}"


def sha256_file(path: str | Path) -> str:
    """Return hex SHA-256 of a file, or 'N/A' if not readable."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "N/A"


class RunLogger:
    """
    Central logger for a single pipeline run.

    Usage:
        logger = RunLogger(run_id, base_dir)
        logger.step_start("LOAD_GEOMETRY")
        logger.step_skip("LOAD_GEOMETRY", reason="File not found")
        logger.step_done("LOAD_GEOMETRY", outputs=[...])
        logger.hard_fail("LOAD_GEOMETRY", "No geometry could be loaded")
        logger.finalize(needs_registry, sanity_results)
    """

    def __init__(self, run_id: str, base_dir: str | Path):
        self.run_id = run_id
        self.base_dir = Path(base_dir)
        self.start_time = datetime.now(timezone.utc)
        self._start_ts = time.monotonic()

        # Paths
        self.log_path = self.base_dir / "logs" / "runs" / f"{run_id}__run.log"
        self.pathway_path = self.base_dir / "logs" / "runs" / f"{run_id}__pathway.json"
        self.validation_path = (
            self.base_dir / "reports" / "validation" / f"{run_id}__validation_report.md"
        )
        self.qa_path = (
            self.base_dir / "reports" / "qa" / f"{run_id}__qa_sanity_checks.md"
        )
        self.needs_path = self.base_dir / "needs" / "needs.yaml"
        self.needs_snapshot_path = (
            self.base_dir / "needs" / "history" / f"{run_id}__needs_snapshot.yaml"
        )
        self.latest_dir = self.base_dir / "logs" / "latest"

        # Internal state
        self._pathway: list[dict] = []
        self._log_lines: list[str] = []
        self._needs_entries: list[dict] = []
        self._sanity_results: list[dict] = []
        self._input_hashes: dict[str, str] = {}
        self._output_hashes: dict[str, str] = {}
        self._coverage: dict[str, Any] = {}
        self._current_step: dict | None = None

        # Open log file
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_fh = open(self.log_path, "w", encoding="utf-8")
        self._write_header()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _elapsed(self) -> float:
        return round(time.monotonic() - self._start_ts, 3)

    def _emit(self, level: str, msg: str):
        line = f"[{self._ts()}] [{level}] {msg}"
        self._log_fh.write(line + "\n")
        self._log_fh.flush()
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))
        self._log_lines.append(line)

    def _write_header(self):
        self._emit(
            "INFO",
            f"{'='*72}\n"
            f"  Campaign In A Box — Pipeline Run\n"
            f"  RUN_ID  : {self.run_id}\n"
            f"  Started : {self.start_time.isoformat()}\n"
            f"{'='*72}",
        )

    # ------------------------------------------------------------------
    # Public logging API
    # ------------------------------------------------------------------

    def info(self, msg: str):
        self._emit("INFO ", msg)

    def warn(self, msg: str):
        self._emit("WARN ", msg)

    def error(self, msg: str):
        self._emit("ERROR", msg)

    def step_start(self, step_name: str, expected: list[str] | None = None):
        """Mark the start of a pipeline DAG step."""
        self._emit("STEP ", f"START  -> {step_name}")
        if expected:
            for e in expected:
                self._emit("INFO ", f"  expected: {e}")
        self._current_step = {
            "step": step_name,
            "status": "running",
            "started_at": self._ts(),
            "elapsed_s": None,
            "inputs": [],
            "outputs": [],
            "hashes_in": {},
            "hashes_out": {},
            "notes": [],
        }

    def step_done(
        self,
        step_name: str,
        outputs: list[str | Path] | None = None,
        notes: list[str] | None = None,
    ):
        """Mark a step as completed successfully."""
        hashes_out = {}
        if outputs:
            for o in outputs:
                h = sha256_file(o)
                hashes_out[str(o)] = h
                self._output_hashes[str(o)] = h
                self._emit("INFO ", f"  output: {o}  [sha256:{h[:12]}...]")
        elapsed = self._elapsed()
        self._emit("STEP ", f"DONE   [OK] {step_name} ({elapsed}s)")
        entry = {
            "step": step_name,
            "status": "done",
            "elapsed_s": elapsed,
            "outputs": [str(o) for o in (outputs or [])],
            "hashes_out": hashes_out,
            "notes": notes or [],
        }
        self._pathway.append(entry)

    def step_skip(self, step_name: str, reason: str):
        """Mark a step as skipped with a reason."""
        elapsed = self._elapsed()
        self._emit("STEP ", f"SKIP   [SKIP] {step_name} -- {reason}")
        self._pathway.append(
            {
                "step": step_name,
                "status": "skipped",
                "elapsed_s": elapsed,
                "reason": reason,
            }
        )

    def hard_fail(self, step_name: str, reason: str):
        """Log a hard-fail condition and raise RuntimeError."""
        elapsed = self._elapsed()
        self._emit("ERROR", f"FAIL   [FAIL] {step_name} -- {reason}")
        self._pathway.append(
            {
                "step": step_name,
                "status": "failed",
                "elapsed_s": elapsed,
                "reason": reason,
            }
        )
        self._finalize_logs_on_fail(reason)
        raise RuntimeError(f"[HARD FAIL] {step_name}: {reason}")

    def register_input(self, label: str, path: str | Path):
        """Record an input file with its hash."""
        h = sha256_file(path)
        self._input_hashes[label] = h
        self._emit("INFO ", f"  input: {label} -> {path}  [sha256:{h[:12]}...]")

    def register_need(
        self,
        category: str,
        status: str,
        blocks: list[str],
        path: str | None = None,
    ):
        """Register a missing/partial data need."""
        entry = {"category": category, "status": status, "blocks": blocks}
        if path:
            entry["expected_path"] = str(path)
        self._needs_entries.append(entry)
        self._emit(
            "WARN ",
            f"  NEED: {category} [{status}] -- blocks: {', '.join(blocks)}",
        )

    def register_sanity(self, check: str, passed: bool, detail: str = ""):
        """Register a sanity check result."""
        icon = "[OK]" if passed else "[FAIL]"
        level = "INFO " if passed else "WARN "
        self._emit(level, f"  SANITY {icon} {check}{': ' + detail if detail else ''}")
        self._sanity_results.append({"check": check, "passed": passed, "detail": detail})

    def set_coverage(self, key: str, value: Any):
        self._coverage[key] = value

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def finalize(
        self,
        state: str,
        county: str,
        contest_slug: str,
        run_status: str = "success",
    ):
        """Write all log artifacts and refresh logs/latest/."""
        # Derive canonical naming for serialization
        county_name, self._county_slug, self._county_fips = normalize_county(county)
        self._contest_id = generate_contest_id(str(datetime.now().year), state, self._county_slug, contest_slug) if contest_slug else None
        elapsed = self._elapsed()
        self._emit(
            "INFO ",
            f"{'='*72}\n"
            f"  Run complete — {run_status.upper()}  elapsed: {elapsed}s\n"
            f"{'='*72}",
        )
        self._log_fh.close()

        self._write_pathway_json(run_status, elapsed)
        self._write_validation_report(state, county, contest_slug, run_status)
        self._write_qa_report(state, county, contest_slug)
        self._update_needs_yaml(state, county, run_status)
        self._write_needs_snapshot(state, county)
        self._refresh_latest()
        print(f"\n[RunLogger] All log artifacts written for RUN_ID={self.run_id}")

    def _finalize_logs_on_fail(self, fail_reason: str):
        """Partial finalization on hard-fail before raising."""
        try:
            self._log_fh.flush()
        except Exception:
            pass

    def _write_pathway_json(self, run_status: str, elapsed_s: float):
        data = {
            "run_id": self.run_id,
            "run_status": run_status,
            "total_elapsed_s": elapsed_s,
            "started_at": self.start_time.isoformat(),
            "county_fips": getattr(self, "_county_fips", "N/A"),
            "county_slug": getattr(self, "_county_slug", "N/A"),
            "contest_id": getattr(self, "_contest_id", "N/A"),
            "input_hashes": self._input_hashes,
            "output_hashes": self._output_hashes,
            "coverage": self._coverage,
            "steps": self._pathway,
            "needs": self._needs_entries,
        }
        self.pathway_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pathway_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _write_validation_report(
        self, state: str, county: str, contest_slug: str, run_status: str
    ):
        lines = [
            f"# Validation Report",
            f"",
            f"| Field | Value |",
            f"|---|---|",
            f"| **RUN_ID** | `{self.run_id}` |",
            f"| **Status** | {run_status.upper()} |",
            f"| **State** | {state} |",
            f"| **County** | {county} |",
            f"| **Contest** | {contest_slug} |",
            f"| **Started** | {self.start_time.isoformat()} |",
            f"",
            f"## Input Files",
            f"",
            f"| Label | SHA-256 (first 16) |",
            f"|---|---|",
        ]
        for label, h in self._input_hashes.items():
            lines.append(f"| {label} | `{h[:16]}...` |")

        lines += [
            f"",
            f"## Output Files",
            f"",
            f"| Path | SHA-256 (first 16) |",
            f"|---|---|",
        ]
        for path, h in self._output_hashes.items():
            lines.append(f"| `{Path(path).name}` | `{h[:16]}...` |")

        lines += [
            f"",
            f"## Coverage Metrics",
            f"",
        ]
        for k, v in self._coverage.items():
            lines.append(f"- **{k}**: {v}")

        lines += [
            f"",
            f"## NEEDS / Missing Data",
            f"",
        ]
        if self._needs_entries:
            for n in self._needs_entries:
                blocks_str = ", ".join(n.get("blocks", []))
                lines.append(
                    f"- **{n['category']}** [{n['status']}] — blocks: {blocks_str}"
                )
                if "expected_path" in n:
                    lines.append(f"  - Expected at: `{n['expected_path']}`")
        else:
            lines.append("_No missing data._")

        lines += [
            f"",
            f"## Pipeline Steps",
            f"",
            f"| Step | Status | Elapsed (s) |",
            f"|---|---|---|",
        ]
        for s in self._pathway:
            lines.append(
                f"| {s['step']} | {s['status']} | {s.get('elapsed_s', 'N/A')} |"
            )

        self.validation_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.validation_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _write_qa_report(self, state: str, county: str, contest_slug: str):
        passed = [s for s in self._sanity_results if s["passed"]]
        failed = [s for s in self._sanity_results if not s["passed"]]
        lines = [
            f"# QA Sanity Checks",
            f"",
            f"**RUN_ID**: `{self.run_id}`  |  **{state}/{county}/{contest_slug}**",
            f"",
            f"**Result**: {len(passed)}/{len(self._sanity_results)} checks passed",
            f"",
            f"## ✓ Passed",
            f"",
        ]
        if passed:
            for s in passed:
                lines.append(f"- ✓ **{s['check']}**{': ' + s['detail'] if s['detail'] else ''}")
        else:
            lines.append("_None_")

        lines += [f"", f"## ✗ Failed", f""]
        if failed:
            for s in failed:
                lines.append(f"- ✗ **{s['check']}**{': ' + s['detail'] if s['detail'] else ''}")
        else:
            lines.append("_None — all checks passed._")

        self.qa_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.qa_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _update_needs_yaml(self, state: str, county: str, run_status: str):
        """Load existing needs.yaml, update, and save."""
        self.needs_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        if self.needs_path.exists():
            with open(self.needs_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        data.setdefault("meta", {})
        data["meta"]["last_updated"] = self._ts()
        data["meta"]["last_run_id"] = self.run_id

        jur_key = f"{state}/{county}"
        data.setdefault("jurisdictions", {})
        data["jurisdictions"][jur_key] = {
            "last_run_id": self.run_id,
            "needs": self._needs_entries,
        }

        data.setdefault("runs", [])
        data["runs"].append(
            {
                "run_id": self.run_id,
                "timestamp": self._ts(),
                "state": state,
                "county": county,
                "status": run_status,
                "artifacts": {
                    "run_log": str(self.log_path),
                    "pathway_json": str(self.pathway_path),
                    "validation_report": str(self.validation_path),
                    "qa_report": str(self.qa_path),
                    "needs_snapshot": str(self.needs_snapshot_path),
                },
            }
        )
        with open(self.needs_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    def _write_needs_snapshot(self, state: str, county: str):
        snapshot = {
            "run_id": self.run_id,
            "timestamp": self._ts(),
            "state": state,
            "county": county,
            "needs": self._needs_entries,
            "coverage": self._coverage,
        }
        self.needs_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.needs_snapshot_path, "w", encoding="utf-8") as f:
            yaml.dump(snapshot, f, allow_unicode=True, sort_keys=False)

    def _refresh_latest(self):
        """Copy all run artifacts to logs/latest/ for quick access."""
        self.latest_dir.mkdir(parents=True, exist_ok=True)

        copies = [
            (self.log_path,          self.latest_dir / "run.log"),
            (self.pathway_path,      self.latest_dir / "pathway.json"),
            (self.validation_path,   self.latest_dir / "validation.md"),
            (self.qa_path,           self.latest_dir / "qa.md"),
            (self.needs_path,        self.latest_dir / "needs.yaml"),
        ]
        for src, dst in copies:
            if src.exists():
                shutil.copy2(src, dst)

        # Write RUN_ID.txt
        (self.latest_dir / "RUN_ID.txt").write_text(self.run_id + "\n", encoding="utf-8")
