"""
app/lib/pipeline_runner.py

Runs run_pipeline.py as a subprocess, streams log output line by line.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from typing import Generator

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PYTHON = sys.executable
PIPELINE_SCRIPT = BASE_DIR / "scripts" / "run_pipeline.py"


def build_args(
    county: str,
    year: str,
    contest_slug: str,
    state: str = "CA",
    detail_path: str | None = None,
    staging_dir: str | None = None,
    membership_method: str = "auto",
    no_commit: bool = True,
    target_candidate: str | None = None,
    rebuild_targets_only: bool = False,
    rebuild_maps_only: bool = False,
    contest_mode: str = "auto",
) -> list[str]:
    args = [
        PYTHON, str(PIPELINE_SCRIPT),
        "--state", state,
        "--county", county,
        "--year", year,
        "--contest-slug", contest_slug,
        "--membership-method", membership_method,
        "--log-level", "verbose",
    ]
    if detail_path:
        args += ["--detail-path", detail_path]
    if staging_dir:
        args += ["--staging-dir", staging_dir]
    if no_commit:
        args.append("--no-commit")
    if target_candidate:
        args += ["--target-candidate", target_candidate]
    if rebuild_targets_only:
        args.append("--rebuild-targets-only")
    if rebuild_maps_only:
        args.append("--rebuild-maps-only")
    if contest_mode and contest_mode != "auto":
        args += ["--contest-mode", contest_mode]
    return args


def run_pipeline_streaming(
    county: str,
    year: str,
    contest_slug: str,
    state: str = "CA",
    detail_path: str | None = None,
    staging_dir: str | None = None,
    membership_method: str = "auto",
    no_commit: bool = False,
    target_candidate: str | None = None,
    rebuild_targets_only: bool = False,
    rebuild_maps_only: bool = False,
    contest_mode: str = "auto",
) -> Generator[str, None, None]:
    """
    Stream pipeline output line by line.
    Yields each line as a string.
    Last yielded line is either '__SUCCESS__' or '__FAIL__:<code>'.
    """
    args = build_args(county, year, contest_slug, state, detail_path,
                      staging_dir, membership_method, no_commit,
                      target_candidate, rebuild_targets_only, rebuild_maps_only,
                      contest_mode)

    proc = subprocess.Popen(
        args,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    assert proc.stdout is not None
    for line in proc.stdout:
        yield line.rstrip("\n")

    proc.wait()
    if proc.returncode == 0:
        yield "__SUCCESS__"
    else:
        yield f"__FAIL__:{proc.returncode}"


def get_latest_run_id() -> str | None:
    p = BASE_DIR / "logs" / "latest" / "RUN_ID.txt"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return None


def read_latest_artifact(name: str) -> str | None:
    """Read a file from logs/latest/ by filename."""
    p = BASE_DIR / "logs" / "latest" / name
    if p.exists():
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            return None
    return None
