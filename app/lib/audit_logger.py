"""
app/lib/audit_logger.py

Maintains the append-only data updates audit log and writes
machine-readable update pathway JSON files.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"
UPDATES_DIR = LOGS_DIR / "updates"
AUDIT_LOG_FILE = LOGS_DIR / "data_updates.log"


def _ensure_dirs():
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)


def log_update_event(
    action: str,
    category: str,
    county: str,
    contest: str | None,
    old_file_record: dict | None,
    new_file_record: dict | None,
    archive_dest: str | None,
    derived_stale: list[str],
) -> str:
    """
    Log a data update event.
    Returns the timestamp string used for the event.
    """
    _ensure_dirs()
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")

    # 1. Append to human-readable log
    log_line = (
        f"[{now_ts}] ACTION: {action} | CAT: {category} | "
        f"COUNTY: {county} | CONTEST: {contest or 'N/A'}\n"
    )
    if old_file_record:
        sz = old_file_record.get('size_bytes', 0)
        h = old_file_record.get('sha256', 'unknown')[:12]
        nm = old_file_record.get('filename', 'unknown')
        log_line += f"  - OLD: {nm} ({sz}b, sha:{h})\n"
    if new_file_record:
        sz = new_file_record.get('size_bytes', 0)
        h = new_file_record.get('sha256', 'unknown')[:12]
        nm = new_file_record.get('filename', 'unknown')
        log_line += f"  + NEW: {nm} ({sz}b, sha:{h})\n"
    if archive_dest:
        log_line += f"  > ARCHIVED TO: {archive_dest}\n"
    if derived_stale:
        log_line += f"  ! STALE: {', '.join(derived_stale)}\n"
    log_line += "-" * 60 + "\n"

    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line)

    # 2. Write machine-readable JSON
    payload = {
        "timestamp": now_ts,
        "action": action,
        "category": category,
        "county": county,
        "contest": contest,
        "old_file": old_file_record,
        "new_file": new_file_record,
        "archive_destination": archive_dest,
        "derived_outputs_marked_stale": derived_stale,
    }
    json_path = UPDATES_DIR / f"{now_ts}__update_{action}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return now_ts
