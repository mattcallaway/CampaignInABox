"""
engine/utils/helpers.py — Prompt 23 Stabilization

Shared utility functions for all engine modules.
Eliminates duplicated _g(), _find_latest(), BASE_DIR patterns.

Usage:
    from engine.utils.helpers import g, find_latest_csv, BASE_DIR, load_yaml
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd

log = logging.getLogger(__name__)

# Canonical root: go up from engine/utils/ → engine/ → project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def g(d: Any, *keys, default=None) -> Any:
    """
    Safe nested dict accessor.
    Returns default if any key is missing or d is not a dict.

    Example:
        g(cfg, "field_program", "contact_rate", default=0.22)
    """
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def find_latest_csv(
    directory: Path,
    pattern: str,
    contest_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Find the most recently written CSV matching pattern in directory.

    Args:
        directory:  Base directory to search (may be non-existent).
        pattern:    Glob pattern (e.g. "**/*__vote_path.csv").
        contest_id: If given, only matches files whose name contains contest_id.
        run_id:     If given, prefers the exact run_id match before falling back to latest.

    Returns:
        DataFrame or None if no match found.
    """
    if not directory.exists():
        log.debug(f"[HELPERS] find_latest_csv: directory missing — {directory}")
        return None
    try:
        matches = sorted(
            directory.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not matches:
            return None

        # Filter by contest_id if provided
        if contest_id:
            matches = [m for m in matches if contest_id in m.name or contest_id in str(m)]
            if not matches:
                log.debug(f"[HELPERS] find_latest_csv: no match for contest_id={contest_id}")
                return None

        # Prefer exact run_id match
        if run_id:
            exact = [m for m in matches if m.name.startswith(run_id)]
            if exact:
                return pd.read_csv(exact[0], index_col=False)

        # Fall back to most recently modified
        f = matches[0]
        log.debug(f"[HELPERS] find_latest_csv: using {f.relative_to(BASE_DIR)}")
        return pd.read_csv(f, index_col=False)

    except Exception as e:
        log.warning(f"[HELPERS] find_latest_csv({directory}, {pattern}) failed: {e}")
        return None


def load_yaml(path: Path) -> dict:
    """
    Safely load a YAML file.
    Returns empty dict on error or if file missing.
    """
    if not path.exists():
        log.debug(f"[HELPERS] load_yaml: file missing — {path}")
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        log.warning(f"[HELPERS] load_yaml({path}) failed: {e}")
        return {}


def load_json(path: Path) -> dict:
    """
    Safely load a JSON file.
    Returns empty dict on error or if file missing.
    """
    import json
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"[HELPERS] load_json({path}) failed: {e}")
        return {}
