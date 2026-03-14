"""
engine/precinct_ids/review_queue.py — Prompt 29

Writes human-reviewable CSV files for ambiguous crosswalk
and join decisions that could not be resolved deterministically.

Output files:
  derived/precinct_id_review/<RUN_ID>__crosswalk_review.csv
  derived/precinct_id_review/<RUN_ID>__join_review.csv

These are designed to be opened in Excel/Sheets and reviewed by a human
who can fill in the reviewer_decision and reviewer_notes columns.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class CrosswalkReviewRow:
    """One row in the crosswalk review CSV — one ambiguous crosswalk file."""
    file:                     str
    filepath:                 str
    detected_source_col:      str    # "" if not detected
    detected_target_col:      str    # "" if not detected
    candidate_source_columns: str    # comma-separated
    candidate_target_columns: str    # comma-separated
    ambiguity_reason:         str
    suggested_fix:            str    # e.g. "Add per_file_hints to crosswalk_column_hints.yaml"
    detection_status:         str    # "ok" | "failed" | "ambiguous"
    reviewer_decision:        str = ""
    reviewer_notes:           str = ""


@dataclass
class JoinReviewRow:
    """One row in the join review CSV — one unresolved precinct ID."""
    run_id:               str
    state:                str
    county:               str
    contest_slug:         str
    raw_precinct_value:   str
    detected_schema:      str
    join_outcome:         str
    candidate_mapped_ids: str   # comma-separated
    crosswalk_file_used:  str
    ambiguity_reason:     str
    suggested_fix:        str
    reviewer_decision:    str = ""
    reviewer_notes:       str = ""


class ReviewQueueWriter:
    """Collects review items and writes them as CSV files."""

    def __init__(self, run_id: str, state: str, county: str, contest_slug: str):
        self.run_id       = run_id
        self.state        = state
        self.county       = county
        self.contest_slug = contest_slug
        self._crosswalk_rows: list[CrosswalkReviewRow] = []
        self._join_rows:      list[JoinReviewRow] = []

    def add_crosswalk_issue(
        self,
        file: str,
        filepath: str,
        detected_source_col: str,
        detected_target_col: str,
        candidate_sources:   list[str],
        candidate_targets:   list[str],
        ambiguity_reason:    str,
        detection_status:    str = "failed",
    ) -> None:
        self._crosswalk_rows.append(CrosswalkReviewRow(
            file=file,
            filepath=filepath,
            detected_source_col=detected_source_col or "",
            detected_target_col=detected_target_col or "",
            candidate_source_columns=",".join(candidate_sources),
            candidate_target_columns=",".join(candidate_targets),
            ambiguity_reason=ambiguity_reason,
            suggested_fix=(
                f"Add entry to config/precinct_id/crosswalk_column_hints.yaml "
                f"under per_file_hints:{file}"
            ),
            detection_status=detection_status,
        ))

    def add_join_issue(
        self,
        raw_precinct_value:  str,
        detected_schema:     str,
        join_outcome:        str,
        candidate_mapped_ids: list[str],
        crosswalk_file_used: str,
        ambiguity_reason:    str,
    ) -> None:
        self._join_rows.append(JoinReviewRow(
            run_id=self.run_id,
            state=self.state,
            county=self.county,
            contest_slug=self.contest_slug,
            raw_precinct_value=raw_precinct_value,
            detected_schema=detected_schema,
            join_outcome=join_outcome,
            candidate_mapped_ids=",".join(candidate_mapped_ids),
            crosswalk_file_used=crosswalk_file_used or "none",
            ambiguity_reason=ambiguity_reason,
            suggested_fix=(
                "Confirm the correct target ID and add to "
                "config/precinct_id/manual_mapping_overrides.yaml"
            ),
        ))

    def write(self, output_dir: Optional[Path] = None) -> dict[str, Path]:
        """Write review CSVs. Returns {name: path}."""
        if output_dir is None:
            output_dir = BASE_DIR / "derived" / "precinct_id_review"
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}

        # Crosswalk review
        cw_path = output_dir / f"{self.run_id}__crosswalk_review.csv"
        if self._crosswalk_rows:
            with open(cw_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(asdict(self._crosswalk_rows[0]).keys()))
                writer.writeheader()
                writer.writerows([asdict(r) for r in self._crosswalk_rows])
            paths["crosswalk_review"] = cw_path
            log.info(f"[REVIEW] Wrote {len(self._crosswalk_rows)} crosswalk issues to {cw_path.name}")
        else:
            log.info("[REVIEW] No crosswalk issues — skipping crosswalk_review.csv")

        # Join review
        jn_path = output_dir / f"{self.run_id}__join_review.csv"
        if self._join_rows:
            with open(jn_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(asdict(self._join_rows[0]).keys()))
                writer.writeheader()
                writer.writerows([asdict(r) for r in self._join_rows])
            paths["join_review"] = jn_path
            log.info(f"[REVIEW] Wrote {len(self._join_rows)} join issues to {jn_path.name}")
        else:
            log.info("[REVIEW] No join issues — skipping join_review.csv")

        return paths
