"""
app/lib/archiver.py

Handles moving active files into the archive/ directory structure
during an update, preserving original filenames.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = BASE_DIR / "archive"


def get_archive_dest(
    timestamp: str,
    domain: str,       # 'votes', 'voters', or 'geography'
    county: str,
    year: str | None = None,
    contest: str | None = None,
    state: str = "CA"
) -> Path:
    """Determine the archive folder for a given domain/context."""
    if domain == "votes" and year and contest:
        return ARCHIVE_DIR / "votes" / year / state / county / contest / timestamp
    elif domain == "voters":
        return ARCHIVE_DIR / "voters" / state / county / timestamp
    elif domain == "geography":
        return ARCHIVE_DIR / "data" / state / "counties" / county / "geography" / timestamp
    else:
        # Fallback generic
        return ARCHIVE_DIR / "misc" / timestamp


def archive_file(
    active_path: str | Path,
    timestamp: str,
    domain: str,
    county: str,
    year: str | None = None,
    contest: str | None = None,
    state: str = "CA"
) -> Path | None:
    """
    Move a file from active_path to the appropriate archive folder.
    Also moves standard shapefile sidecars if active_path is a .shp.
    Returns the path to the main archived file, or None if active_path didn't exist.
    """
    src = Path(active_path)
    if not src.exists():
        return None

    dest_dir = get_archive_dest(timestamp, domain, county, year, contest, state)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / src.name
    shutil.move(str(src), str(dest))

    # Handle shapefile sidecars
    if src.suffix.lower() == ".shp":
        stem = src.stem
        parent = src.parent
        sidecars = [".shx", ".dbf", ".prj", ".cpg", ".qix"]
        for ext in sidecars:
            for c in (stem + ext, stem + ext.upper()):
                sidecar_src = parent / c
                if sidecar_src.exists():
                    shutil.move(str(sidecar_src), str(dest_dir / c))

    return dest


def list_archives(
    domain: str,
    county: str,
    year: str | None = None,
    contest: str | None = None,
    state: str = "CA"
) -> list[Path]:
    """List all timestamp archive folders for a specific context."""
    # Build base path without timestamp
    if domain == "votes" and year and contest:
        base = ARCHIVE_DIR / "votes" / year / state / county / contest
    elif domain == "voters":
        base = ARCHIVE_DIR / "voters" / state / county
    elif domain == "geography":
        base = ARCHIVE_DIR / "data" / state / "counties" / county / "geography"
    else:
        return []

    if not base.is_dir():
        return []

    return sorted([d for d in base.iterdir() if d.is_dir()], reverse=True)
