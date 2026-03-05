"""
scripts/lib/deps.py

Dependency gate for optional heavy packages (geopandas, pyarrow, etc.)
Does NOT hard-fail the pipeline — marks NEEDS and logs a warning.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Public API ────────────────────────────────────────────────────────────────
_cache: dict[str, bool] = {}


def check(package: str) -> bool:
    """Return True if `package` can be imported."""
    if package in _cache:
        return _cache[package]
    try:
        __import__(package)
        _cache[package] = True
    except ImportError:
        _cache[package] = False
    return _cache[package]


GEOPANDAS   = "geopandas"
PYARROW     = "pyarrow"
SKLEARN     = "sklearn"

# Packages that block specific outputs when missing
_BLOCKS: dict[str, list[str]] = {
    GEOPANDAS: ["kepler_export", "geometry_load", "geo_join"],
    SKLEARN:   ["region_clustering_kmeans"],
    PYARROW:   ["parquet_export"],
}

_INSTALL_HINT: dict[str, str] = {
    GEOPANDAS: "pip install geopandas  # or: uv add geopandas",
    SKLEARN:   "pip install scikit-learn",
    PYARROW:   "pip install pyarrow",
}


def gate(
    package: str,
    logger=None,
    *,
    feature: Optional[str] = None,
    hard_fail: bool = False,
) -> bool:
    """
    Check whether `package` is available.

    - If missing: logs a warning (or hard-fails if hard_fail=True),
      updates NEEDS, and returns False.
    - Returns True if available.
    """
    available = check(package)
    if available:
        return True

    blocks  = _BLOCKS.get(package, [])
    hint    = _INSTALL_HINT.get(package, f"pip install {package}")
    feature = feature or (blocks[0] if blocks else package)
    msg = (
        f"[DEPS] Optional package '{package}' is not installed. "
        f"Feature '{feature}' will be skipped. "
        f"To enable: `{hint}`"
    )

    if logger:
        try:
            logger.warn(msg)
        except Exception:
            print(f"WARN: {msg}")
    else:
        print(f"WARN: {msg}")

    _update_needs(package, blocks, hint)

    if hard_fail:
        raise ImportError(f"Required package missing: {package}. {hint}")

    return False


def _update_needs(package: str, blocks: list[str], hint: str) -> None:
    """Append geopandas_library / other dep entries to needs.yaml."""
    try:
        import yaml
        needs_path = BASE_DIR / "needs" / "needs.yaml"
        needs_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if needs_path.exists():
            try:
                existing = yaml.safe_load(needs_path.read_text()) or {}
            except Exception:
                existing = {}
        key = f"{package}_library"
        existing[key] = {
            "status": "missing",
            "blocks": blocks,
            "install_hint": hint,
        }
        needs_path.write_text(yaml.dump(existing, default_flow_style=False), encoding="utf-8")
    except Exception:
        pass  # Never crash the pipeline for a needs update


def update_needs_available(package: str) -> None:
    """Mark a dep as complete in needs.yaml (called after successful import)."""
    try:
        import yaml
        needs_path = BASE_DIR / "needs" / "needs.yaml"
        if not needs_path.exists():
            return
        existing = yaml.safe_load(needs_path.read_text()) or {}
        key = f"{package}_library"
        if key in existing:
            existing[key]["status"] = "complete"
            needs_path.write_text(yaml.dump(existing, default_flow_style=False), encoding="utf-8")
    except Exception:
        pass
