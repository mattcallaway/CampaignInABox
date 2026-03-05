"""
scripts/lib/hashing.py

Shared hashing and file-info utilities used across the pipeline.
"""

import hashlib
import os
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    """Return hex SHA-256 of a file, or 'ERROR:<msg>' if unreadable."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        return f"ERROR:{e}"


def file_size(path: str | Path) -> int:
    """Return file size in bytes, or -1 if unavailable."""
    try:
        return os.path.getsize(path)
    except Exception:
        return -1


def file_info(path: str | Path) -> dict:
    """Return dict with path, filename, size_bytes, sha256."""
    p = Path(path)
    return {
        "path":       str(p),
        "filename":   p.name,
        "size_bytes": file_size(p),
        "sha256":     sha256_file(p),
    }
