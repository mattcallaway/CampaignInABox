"""
engine/ingestion/contest_file_watcher.py — Prompt 31 Feature 1

Scans canonical contest directories for new/unregistered files and
classifies them so the pipeline can be triggered automatically.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Supported raw file extensions
SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv", ".json"}

# Known precinct column name candidates — ordered by likelihood
PRECINCT_COLUMN_CANDIDATES = [
    "SRPREC", "srprec", "MPREC", "mprec",
    "Precinct", "precinct", "PrecinctID", "precinct_id",
    "PrecinctCanvass",  # Sonoma canvass-style
    "PCT Number", "pct_num", "PCT", "pct",
    "Pct", "Pct.", "Precinct Number", "PrecinctName",
]

# When checking for precinct columns, also look for any column that starts
# with these prefixes (case-insensitive).
PRECINCT_PREFIX_CANDIDATES = ("prec", "srprec", "mprec", "pct")


@dataclass
class DetectedContestFile:
    state: str
    county: str
    year: str
    contest_slug: str
    filename: str
    filepath: str
    size_bytes: int
    detected_at: str
    status: str          # READY_FOR_PIPELINE | NEEDS_REVIEW | ALREADY_REGISTERED
    precinct_col: Optional[str] = None
    precinct_rows: Optional[int] = None
    file_type: Optional[str] = None      # statement_of_votes | canvass | detail | unknown
    notes: str = ""


def _classify_filename(filename: str) -> str:
    """Heuristic file type from filename."""
    fl = filename.lower()
    if "statement" in fl or "statementofvotes" in fl:
        return "statement_of_votes"
    if "canvass" in fl or "pctcanvass" in fl:
        return "canvass"
    if "detail" in fl:
        return "detail"
    if "results" in fl:
        return "results"
    return "unknown"


def _sniff_precinct_column(filepath: Path) -> tuple[Optional[str], Optional[int]]:
    """
    Try to detect precinct column and row count from file.

    Handles preamble rows (e.g. title rows before actual headers) by trying
    skiprows 0-5. Returns the first matching column name and total row count.
    """
    try:
        import pandas as pd
        is_excel = filepath.suffix.lower() in (".xlsx", ".xls")
        is_csv = filepath.suffix.lower() in (".csv", ".tsv")
        if not (is_excel or is_csv):
            return None, None

        # Try skiprows 0-5 to skip past preamble/title rows
        for skip in range(6):
            try:
                if is_excel:
                    df = pd.read_excel(filepath, nrows=5, skiprows=skip if skip > 0 else None)
                else:
                    sep = "\t" if filepath.suffix.lower() == ".tsv" else ","
                    df = pd.read_csv(filepath, nrows=5, sep=sep, skiprows=skip if skip > 0 else None)
            except Exception:
                continue

            # Skip if all columns are Unnamed (still in preamble)
            real_cols = [c for c in df.columns if not str(c).startswith("Unnamed")]
            if not real_cols:
                continue

            # Check explicit candidates
            for candidate in PRECINCT_COLUMN_CANDIDATES:
                if candidate in df.columns:
                    try:
                        if is_excel:
                            full_df = pd.read_excel(filepath, usecols=[candidate],
                                                    skiprows=skip if skip > 0 else None)
                        else:
                            full_df = pd.read_csv(filepath, usecols=[candidate],
                                                  skiprows=skip if skip > 0 else None)
                        return candidate, len(full_df)
                    except Exception:
                        return candidate, None

            # Prefix-match fallback: any column starting with prec/pct/srprec/mprec
            for col in real_cols:
                col_lower = str(col).lower().strip()
                if any(col_lower.startswith(pfx) for pfx in PRECINCT_PREFIX_CANDIDATES):
                    logger.debug(f"[WATCHER] Prefix match: '{col}' in {filepath.name}")
                    return col, None

            # Found real columns but no precinct col — stop preamble search
            break

        return None, None
    except Exception as exc:
        logger.debug(f"[WATCHER] Could not sniff {filepath.name}: {exc}")
        return None, None


def scan_for_new_contest_files(
    project_root: Path,
    state: str = "CA",
    county: str = "Sonoma",
    known_file_ids: Optional[set] = None,
) -> list[DetectedContestFile]:
    """
    Scan data/contests/<state>/<county>/<year>/<slug>/raw/ for files.

    Returns a list of DetectedContestFile records. Files that appear
    to be new (not in known_file_ids by path) are marked READY_FOR_PIPELINE.
    """
    contest_root = project_root / "data" / "contests" / state / county
    if not contest_root.exists():
        logger.warning(f"[WATCHER] Contest root not found: {contest_root}")
        return []

    results: list[DetectedContestFile] = []
    now = datetime.now(timezone.utc).isoformat()

    for year_dir in sorted(contest_root.iterdir()):
        if not year_dir.is_dir():
            continue
        year = year_dir.name

        for slug_dir in sorted(year_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            slug = slug_dir.name
            raw_dir = slug_dir / "raw"
            if not raw_dir.exists():
                continue

            for f in raw_dir.iterdir():
                if not f.is_file():
                    continue
                if f.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue

                rel_path = str(f.relative_to(project_root)).replace("\\", "/")
                is_known = (known_file_ids and rel_path in known_file_ids)

                precinct_col, precinct_rows = _sniff_precinct_column(f)
                file_type = _classify_filename(f.name)

                if precinct_col:
                    status = "READY_FOR_PIPELINE"
                    notes = f"Precinct column '{precinct_col}' detected — {precinct_rows} rows"
                elif is_known:
                    status = "ALREADY_REGISTERED"
                    notes = "File already registered in contest registry"
                else:
                    status = "NEEDS_REVIEW"
                    notes = "No precinct column detected — manual review required"

                rec = DetectedContestFile(
                    state=state, county=county, year=year,
                    contest_slug=slug, filename=f.name,
                    filepath=rel_path, size_bytes=f.stat().st_size,
                    detected_at=now, status=status,
                    precinct_col=precinct_col, precinct_rows=precinct_rows,
                    file_type=file_type, notes=notes,
                )
                results.append(rec)
                logger.info(
                    f"[WATCHER] Detected: {f.name} | contest={slug} | "
                    f"precinct_col={precinct_col} | rows={precinct_rows} | status={status}"
                )

    return results


def write_detection_report(
    results: list[DetectedContestFile],
    project_root: Path,
    run_id: Optional[str] = None,
) -> Path:
    """Write detection results as JSON report."""
    rid = run_id or datetime.now(timezone.utc).strftime("%Y%m%d__%H%M%S")
    out_dir = project_root / "reports" / "file_watcher"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{rid}__detection.json"
    out.write_text(
        json.dumps({"run_id": rid, "files": [asdict(r) for r in results]}, indent=2),
        encoding="utf-8",
    )
    logger.info(f"[WATCHER] Report written: {out}")
    return out
