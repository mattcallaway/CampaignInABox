"""
engine/precinct_ids/id_trace.py — Prompt 29

Per-row precinct ID resolution trace logger.

For each contest row entering normalization, records:
  - raw precinct value
  - detected schema
  - normalization method applied
  - crosswalk used
  - join outcome (from join_outcomes taxonomy)
  - failure reason

Results are aggregated and sampled — not every row is written,
but the distribution of outcomes is captured.
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from engine.precinct_ids.join_outcomes import (
    ALL_OUTCOMES, SUCCESS_OUTCOMES, FAILURE_OUTCOMES, REVIEW_REQUIRED_OUTCOMES
)

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class PrecincIDTraceRow:
    run_id:              str
    state:               str
    county:              str
    contest_slug:        str
    row_index:           int
    raw_precinct_value:  str
    detected_schema:     str
    normalization_method: str
    candidate_normalized_ids: str   # comma-separated
    crosswalk_file_used: str        # filename or "none"
    final_scoped_key:    str        # canonical key or ""
    join_outcome:        str        # from join_outcomes constants
    failure_reason:      str        # "" if success


class PrecincIDTracer:
    """
    Collects per-row precinct ID trace records for a single pipeline run.

    Usage:
        tracer = PrecincIDTracer(run_id, state, county, contest_slug)
        tracer.record(row_index, raw_id, schema, ...)
        tracer.write(output_dir)
    """

    def __init__(self, run_id: str, state: str, county: str, contest_slug: str):
        self.run_id       = run_id
        self.state        = state
        self.county       = county
        self.contest_slug = contest_slug
        self._rows: list[PrecincIDTraceRow] = []

    def record(
        self,
        row_index:            int,
        raw_precinct_value:   str,
        detected_schema:      str,
        normalization_method: str,
        candidate_ids:        list[str],
        crosswalk_file:       str,
        scoped_key:           str,
        join_outcome:         str,
        failure_reason:       str = "",
    ) -> None:
        """Record a single row's join outcome."""
        if join_outcome not in ALL_OUTCOMES:
            log.warning(f"[TRACE] Unknown join_outcome: {join_outcome!r}")

        self._rows.append(PrecincIDTraceRow(
            run_id=self.run_id,
            state=self.state,
            county=self.county,
            contest_slug=self.contest_slug,
            row_index=row_index,
            raw_precinct_value=str(raw_precinct_value),
            detected_schema=detected_schema,
            normalization_method=normalization_method,
            candidate_normalized_ids=",".join(candidate_ids),
            crosswalk_file_used=crosswalk_file or "none",
            final_scoped_key=scoped_key or "",
            join_outcome=join_outcome,
            failure_reason=failure_reason or "",
        ))

    def summary(self) -> dict:
        """Return aggregate outcome counts."""
        counts: dict[str, int] = {}
        for r in self._rows:
            counts[r.join_outcome] = counts.get(r.join_outcome, 0) + 1
        total = len(self._rows)
        joined = sum(counts.get(o, 0) for o in SUCCESS_OUTCOMES)
        return {
            "total_rows":       total,
            "joined":           joined,
            "unjoined":         total - joined,
            "pct_joined":       round(joined / max(total, 1) * 100, 2),
            "outcome_counts":   counts,
        }

    def write(self, output_dir: Path, sample_size: int = 2000) -> dict[str, Path]:
        """
        Write trace CSV (sampled) and summary JSON to output_dir.
        Returns dict of {name: path}.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}

        # Write sampled CSV — include all failures + random sample of successes
        failures   = [r for r in self._rows if r.join_outcome in FAILURE_OUTCOMES | REVIEW_REQUIRED_OUTCOMES]
        successes  = [r for r in self._rows if r.join_outcome in SUCCESS_OUTCOMES]
        import random
        sample     = failures + random.sample(successes, min(sample_size, len(successes)))

        csv_path   = output_dir / f"{self.run_id}__id_trace.csv"
        if sample:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(asdict(sample[0]).keys()))
                writer.writeheader()
                writer.writerows([asdict(r) for r in sample])
            paths["id_trace_csv"] = csv_path

        # Write summary JSON
        summary_path = output_dir / f"{self.run_id}__id_trace_summary.json"
        summary_path.write_text(json.dumps(self.summary(), indent=2), encoding="utf-8")
        paths["id_trace_summary_json"] = summary_path

        log.info(
            f"[TRACE] Wrote {len(sample)} sampled rows to {csv_path.name}. "
            f"Summary: {self.summary()}"
        )
        return paths
