"""
scripts/loaders/contest_registry.py

Scaffolds or updates contest.json for a contest folder.
Detects contest type from workbook contents when possible.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


UNKNOWN = "unknown"

CONTEST_TYPES = ["ballot_measure", "candidate_race", "unknown"]
SCOPE_TYPES = ["countywide", "district", "city", "unknown"]


def scaffold_contest_json(
    votes_root: str | Path,
    year: str | int,
    state: str,
    county: str,
    contest_slug: str,
    contest_name: str = UNKNOWN,
    contest_type: str = UNKNOWN,
    jurisdiction_scope: str = UNKNOWN,
    source_notes: str = "",
) -> Path:
    """
    Create or update contest.json in the contest folder.
    Returns path written.
    """
    votes_root = Path(votes_root)
    contest_dir = votes_root / str(year) / state / county / contest_slug
    contest_dir.mkdir(parents=True, exist_ok=True)
    out_path = contest_dir / "contest.json"

    # If file exists, load and merge
    existing: dict = {}
    if out_path.exists():
        try:
            with open(out_path, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    data = {
        "contest_slug":       contest_slug,
        "contest_name":       contest_name if contest_name != UNKNOWN else existing.get("contest_name", UNKNOWN),
        "contest_type":       contest_type if contest_type != UNKNOWN else existing.get("contest_type", UNKNOWN),
        "jurisdiction_scope": jurisdiction_scope if jurisdiction_scope != UNKNOWN else existing.get("jurisdiction_scope", UNKNOWN),
        "year":               str(year),
        "state":              state,
        "county":             county,
        "source_notes":       source_notes or existing.get("source_notes", ""),
        "last_updated":       datetime.now(timezone.utc).isoformat(),
        "sheets_detected":    existing.get("sheets_detected", []),
        "candidates":         existing.get("candidates", []),
        "measures":           existing.get("measures", []),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return out_path


def detect_contest_type(sheet_headers: list[str]) -> str:
    """
    Heuristically detect contest type from column headers.
    Returns 'ballot_measure' or 'candidate_race' or 'unknown'.
    """
    headers_upper = [str(h).upper().strip() for h in sheet_headers if h]
    # Ballot measure signals
    if any(h in ("YES", "NO", "YES VOTES", "NO VOTES") for h in headers_upper):
        return "ballot_measure"
    # Candidate race: multiple non-standard columns that aren't vote-method aggregators
    standard_cols = {
        "PRECINCT", "PRECINCT_ID", "MPREC_ID", "SRPREC_ID", "TOTAL", "BALLOTS",
        "REGISTERED", "MAIL", "IN PERSON", "EARLY", "PROVISIONAL", "ELECTION DAY",
        "PRECINCT NAME", "DISTRICT",
    }
    candidate_cols = [h for h in headers_upper if h and h not in standard_cols]
    if len(candidate_cols) >= 2:
        return "candidate_race"
    return UNKNOWN


def update_contest_from_parse(
    out_path: str | Path,
    sheets: list[str],
    contest_type: str,
    candidates: list[str] | None = None,
    measures: list[str] | None = None,
):
    """Update contest.json after parsing the workbook."""
    out_path = Path(out_path)
    data: dict = {}
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
    data["sheets_detected"] = sheets
    data["contest_type"] = contest_type
    if candidates:
        data["candidates"] = candidates
    if measures:
        data["measures"] = measures
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
