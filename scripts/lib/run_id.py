"""
scripts/lib/run_id.py

Deterministic RUN_ID generation.
Format: YYYY-MM-DD__HHMMSS__<git_short_sha_or_nogit>__<host_tag>

Examples:
  2026-03-04__224433__a1b2c3d4__mathew-c-pc
  2026-03-04__224433__nogit__mathew-c-pc
"""

import re
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _git_short_sha(repo_dir: str | Path) -> str:
    """Return 8-char git short SHA, or 'nogit' if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=3,
        )
        sha = result.stdout.strip()
        if sha and re.match(r"^[0-9a-f]{4,}", sha):
            return sha
    except Exception:
        pass
    return "nogit"


def _host_tag() -> str:
    """Return a filesystem-safe hostname tag (max 20 chars, lower-case)."""
    try:
        host = socket.gethostname().lower()
        # Replace non-alphanumeric with hyphens, strip leading/trailing
        host = re.sub(r"[^a-z0-9]+", "-", host).strip("-")
        return host[:20] or "local"
    except Exception:
        return "local"


def generate_run_id(repo_dir: str | Path | None = None) -> str:
    """
    Generate a deterministic RUN_ID.
    Format: YYYY-MM-DD__HHMMSS__<git_short_sha_or_nogit>__<host_tag>
    """
    now = datetime.now()  # local time for readability
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S")
    sha = _git_short_sha(repo_dir) if repo_dir else "nogit"
    host = _host_tag()
    return f"{date_str}__{time_str}__{sha}__{host}"
