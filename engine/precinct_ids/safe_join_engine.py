"""
engine/precinct_ids/safe_join_engine.py — Prompt 25A.4

Jurisdiction-scoped safe join engine for precinct IDs.

Orchestrates:
  1. Schema detection per column
  2. Jurisdiction validation (is this the right county/state?)
  3. Normalization attempt (mprec / mprec_unpadded only — deterministic schemas)
  4. Crosswalk resolution (for schemas requiring crosswalk)
  5. Result classification: EXACT_MATCH | CROSSWALK_MATCH | NORMALIZED_MATCH
                            | AMBIGUOUS | NO_MATCH | BLOCKED_CROSS_JURISDICTION

Hard safety rules:
  - Any cross-jurisdiction attempt is BLOCKED permanently (confidence=0.00)
  - Ambiguous IDs (multiple candidates, no crosswalk) → review queue, not joined
  - max ambiguous confidence: 0.50 (from id_rules.yaml policy)
  - SRPREC cannot become MPREC without crosswalk

Outputs:
  - JoinResult per row
  - Batch summary
  - CSV files for ambiguous / no-match rows → derived/precinct_id_review/
  - JSON summary → derived/precinct_id_review/<RUN_ID>__join_summary.json
  - Markdown audit → reports/precinct_ids/<RUN_ID>__precinct_id_audit.md
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

log = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
REVIEW_DIR  = BASE_DIR / "derived" / "precinct_id_review"
REPORTS_DIR = BASE_DIR / "reports" / "precinct_ids"

REVIEW_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Confidence policy from id_rules.yaml
CONFIDENCE = {
    "EXACT_MATCH":                0.99,
    "CROSSWALK_MATCH":            0.95,
    "NORMALIZED_MATCH":           0.90,
    "AMBIGUOUS":                  0.20,
    "NO_MATCH":                   0.00,
    "BLOCKED_CROSS_JURISDICTION": 0.00,
}
MAX_AMBIGUOUS_CONFIDENCE = 0.50


@dataclass
class JoinResult:
    """Result of safe join attempt for a single precinct ID."""
    raw_precinct:        str
    detected_schema:     str
    boundary_type:       str
    candidate_matches:   int
    join_status:         str      # see CONFIDENCE keys
    resolved_scoped_key: Optional[str]
    confidence:          float
    reason:              str
    state:               str
    county:              str
    normalization_method: Optional[str]


@dataclass
class JoinBatchResult:
    """Summary of safe join across a batch of precinct IDs."""
    total:                    int
    exact_matches:            int
    crosswalk_matches:        int
    normalized_matches:       int
    ambiguous:                int
    no_matches:               int
    blocked_cross_jurisdiction: int
    archive_ready_fraction:   float
    join_results:             list[JoinResult]
    run_id:                   str
    state:                    str
    county:                   str
    ambiguous_csv:            Optional[str]
    no_match_csv:             Optional[str]
    summary_json:             Optional[str]
    audit_report:             Optional[str]


def _check_jurisdiction_mismatch(
    raw_id: str,
    state: str,
    county: str,
    claimed_state: Optional[str],
    claimed_county: Optional[str],
) -> Optional[str]:
    """
    Return error message if claimed jurisdiction doesn't match the expected one.
    Returns None if no mismatch detected.
    """
    if claimed_state and claimed_state.upper().strip() != state.upper().strip():
        return (
            f"CROSS_JURISDICTION: ID '{raw_id}' claims state '{claimed_state}' "
            f"but expected '{state}'"
        )
    if claimed_county and claimed_county.strip().lower() != county.strip().lower():
        return (
            f"CROSS_JURISDICTION: ID '{raw_id}' claims county '{claimed_county}' "
            f"but expected '{county}'"
        )
    return None


def join_single(
    raw_id: str,
    state: str,
    county: str,
    boundary_type: str,
    canonical_index: Optional[set[str]] = None,
    claimed_state: Optional[str] = None,
    claimed_county: Optional[str] = None,
) -> JoinResult:
    """
    Attempt to safely join one raw precinct ID to a canonical scoped key.

    Steps:
      1. Jurisdiction mismatch check → BLOCKED_CROSS_JURISDICTION
      2. Schema detection
      3. If deterministic schema (mprec/mprec_unpadded) → normalize
      4. If ambiguous schema → crosswalk resolution attempt
      5. If no crosswalk or multiple candidates → AMBIGUOUS or NO_MATCH

    Args:
        raw_id:           raw precinct string
        state:            expected state code (CA)
        county:           expected county name (Sonoma)
        boundary_type:    expected boundary type (MPREC, SRPREC, etc.)
        canonical_index:  optional set of known valid canonical IDs
        claimed_state:    state code claimed by source file (if different)
        claimed_county:   county name claimed by source file (if different)

    Returns:
        JoinResult — never raises
    """
    from engine.precinct_ids.id_schema_detector import detect_schema_for_value
    from engine.precinct_ids.id_normalizer import normalize_id, build_scoped_key
    from engine.precinct_ids.id_crosswalk_resolver import resolve_via_crosswalk

    raw = str(raw_id).strip()

    # ── Step 1: Jurisdiction check ─────────────────────────────────────────────
    mismatch = _check_jurisdiction_mismatch(raw, state, county, claimed_state, claimed_county)
    if mismatch:
        return JoinResult(
            raw_precinct=raw, detected_schema="N/A", boundary_type=boundary_type,
            candidate_matches=0, join_status="BLOCKED_CROSS_JURISDICTION",
            resolved_scoped_key=None, confidence=0.00,
            reason=mismatch, state=state, county=county, normalization_method=None,
        )

    # ── Step 2: Schema detection ───────────────────────────────────────────────
    row_result = detect_schema_for_value(raw)
    schema_key = row_result.schema_key

    # ── Step 3: Exact canonical key match ─────────────────────────────────────
    # If canonical_index contains the raw ID directly (already normalized)
    if canonical_index and raw in canonical_index:
        key = build_scoped_key(state, county, boundary_type, raw)
        return JoinResult(
            raw_precinct=raw, detected_schema=schema_key, boundary_type=boundary_type,
            candidate_matches=1, join_status="EXACT_MATCH",
            resolved_scoped_key=key, confidence=CONFIDENCE["EXACT_MATCH"],
            reason="Exact match against canonical index", state=state, county=county,
            normalization_method="exact_match",
        )

    # ── Step 4: Deterministic normalization (mprec / mprec_unpadded) ──────────
    if schema_key in ("mprec", "mprec_unpadded"):
        norm = normalize_id(raw, schema_key, state, county, boundary_type, canonical_index)
        if norm.error is None and norm.scoped_key:
            status = "NORMALIZED_MATCH" if not norm.validated_against_index else "EXACT_MATCH"
            return JoinResult(
                raw_precinct=raw, detected_schema=schema_key,
                boundary_type=norm.boundary_type, candidate_matches=1,
                join_status=status, resolved_scoped_key=norm.scoped_key,
                confidence=norm.confidence,
                reason=f"Deterministic normalization: {norm.normalization_method}",
                state=state, county=county, normalization_method=norm.normalization_method,
            )
        else:
            # Normalization failed (not in canonical index)
            return JoinResult(
                raw_precinct=raw, detected_schema=schema_key, boundary_type=boundary_type,
                candidate_matches=0, join_status="NO_MATCH",
                resolved_scoped_key=None, confidence=CONFIDENCE["NO_MATCH"],
                reason=norm.error or "Normalization failed",
                state=state, county=county, normalization_method=None,
            )

    # ── Step 5: Crosswalk resolution for ambiguous schemas ────────────────────
    if schema_key in ("short_precinct", "prefixed_precinct", "srprec",
                       "city_precinct", "alphanumeric_precinct"):
        xwalk = resolve_via_crosswalk(
            raw, state, county,
            boundary_type_from=row_result.boundary_type,
            boundary_type_to=boundary_type,
            canonical_index=canonical_index,
        )
        if xwalk.status == "CROSSWALK_MATCH":
            return JoinResult(
                raw_precinct=raw, detected_schema=schema_key,
                boundary_type=boundary_type, candidate_matches=len(xwalk.candidates),
                join_status="CROSSWALK_MATCH", resolved_scoped_key=xwalk.resolved_key,
                confidence=CONFIDENCE["CROSSWALK_MATCH"],
                reason=xwalk.reason, state=state, county=county,
                normalization_method="crosswalk_file",
            )
        elif xwalk.status == "AMBIGUOUS":
            return JoinResult(
                raw_precinct=raw, detected_schema=schema_key, boundary_type=boundary_type,
                candidate_matches=len(xwalk.candidates), join_status="AMBIGUOUS",
                resolved_scoped_key=None,
                confidence=min(CONFIDENCE["AMBIGUOUS"], MAX_AMBIGUOUS_CONFIDENCE),
                reason=xwalk.reason, state=state, county=county, normalization_method=None,
            )
        else:
            # NO_MATCH from crosswalk
            return JoinResult(
                raw_precinct=raw, detected_schema=schema_key, boundary_type=boundary_type,
                candidate_matches=0, join_status="NO_MATCH",
                resolved_scoped_key=None, confidence=CONFIDENCE["NO_MATCH"],
                reason=f"No crosswalk found for schema '{schema_key}': {xwalk.reason}",
                state=state, county=county, normalization_method=None,
            )

    # ── Unknown schema — cannot join ──────────────────────────────────────────
    return JoinResult(
        raw_precinct=raw, detected_schema="unknown", boundary_type=boundary_type,
        candidate_matches=0, join_status="NO_MATCH",
        resolved_scoped_key=None, confidence=0.0,
        reason=f"Unknown precinct ID schema for '{raw}' — manual review required.",
        state=state, county=county, normalization_method=None,
    )


def join_batch(
    raw_ids: Sequence[str],
    state: str,
    county: str,
    boundary_type: str,
    canonical_index: Optional[set[str]] = None,
    run_id: Optional[str] = None,
) -> JoinBatchResult:
    """
    Run safe join for a batch of precinct IDs.

    Writes:
      derived/precinct_id_review/<run_id>__ambiguous_ids.csv
      derived/precinct_id_review/<run_id>__no_match_ids.csv
      derived/precinct_id_review/<run_id>__join_summary.json
      reports/precinct_ids/<run_id>__precinct_id_audit.md

    Returns:
        JoinBatchResult with per-row results and file paths.
    """
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d__%H%M")

    results: list[JoinResult] = []
    for raw in raw_ids:
        r = join_single(raw, state, county, boundary_type, canonical_index)
        results.append(r)

    # Tally
    total = len(results)
    exact       = sum(1 for r in results if r.join_status == "EXACT_MATCH")
    crosswalk   = sum(1 for r in results if r.join_status == "CROSSWALK_MATCH")
    normalized  = sum(1 for r in results if r.join_status == "NORMALIZED_MATCH")
    ambiguous   = sum(1 for r in results if r.join_status == "AMBIGUOUS")
    no_match    = sum(1 for r in results if r.join_status == "NO_MATCH")
    blocked     = sum(1 for r in results if r.join_status == "BLOCKED_CROSS_JURISDICTION")
    archive_ready = (exact + crosswalk + normalized) / max(total, 1)

    # ── Write ambiguous CSV ────────────────────────────────────────────────────
    ambig_path: Optional[str] = None
    ambig_rows = [r for r in results if r.join_status in ("AMBIGUOUS", "BLOCKED_CROSS_JURISDICTION")]
    if ambig_rows:
        ambig_csv = REVIEW_DIR / f"{run_id}__ambiguous_ids.csv"
        with open(ambig_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "raw_precinct", "detected_schema", "join_status",
                "candidate_matches", "confidence", "reason", "state", "county",
            ])
            w.writeheader()
            for r in ambig_rows:
                w.writerow({
                    "raw_precinct": r.raw_precinct, "detected_schema": r.detected_schema,
                    "join_status": r.join_status, "candidate_matches": r.candidate_matches,
                    "confidence": r.confidence, "reason": r.reason[:200],
                    "state": r.state, "county": r.county,
                })
        ambig_path = str(ambig_csv)

    # ── Write no-match CSV ─────────────────────────────────────────────────────
    nomatch_path: Optional[str] = None
    nomatch_rows = [r for r in results if r.join_status == "NO_MATCH"]
    if nomatch_rows:
        nomatch_csv = REVIEW_DIR / f"{run_id}__no_match_ids.csv"
        with open(nomatch_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "raw_precinct", "detected_schema", "reason", "state", "county",
            ])
            w.writeheader()
            for r in nomatch_rows:
                w.writerow({
                    "raw_precinct": r.raw_precinct, "detected_schema": r.detected_schema,
                    "reason": r.reason[:200], "state": r.state, "county": r.county,
                })
        nomatch_path = str(nomatch_csv)

    # ── Write JSON summary ─────────────────────────────────────────────────────
    summary_data = {
        "run_id": run_id, "state": state, "county": county,
        "boundary_type": boundary_type, "generated_at": datetime.now().isoformat(),
        "total": total, "exact_matches": exact, "crosswalk_matches": crosswalk,
        "normalized_matches": normalized, "ambiguous": ambiguous,
        "no_matches": no_match, "blocked_cross_jurisdiction": blocked,
        "archive_ready_fraction": round(archive_ready, 4),
    }
    summary_json_path = REVIEW_DIR / f"{run_id}__join_summary.json"
    summary_json_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")

    # ── Write audit report ─────────────────────────────────────────────────────
    audit_path = _write_audit_report(
        run_id, state, county, boundary_type, results,
        exact, crosswalk, normalized, ambiguous, no_match, blocked, total,
    )

    log.info(
        f"[SAFE_JOIN] {state}|{county} batch: total={total} exact={exact} "
        f"crosswalk={crosswalk} normalized={normalized} ambiguous={ambiguous} "
        f"no_match={no_match} blocked={blocked} "
        f"archive_ready={archive_ready:.1%}"
    )

    return JoinBatchResult(
        total=total, exact_matches=exact, crosswalk_matches=crosswalk,
        normalized_matches=normalized, ambiguous=ambiguous,
        no_matches=no_match, blocked_cross_jurisdiction=blocked,
        archive_ready_fraction=round(archive_ready, 4),
        join_results=results, run_id=run_id, state=state, county=county,
        ambiguous_csv=ambig_path, no_match_csv=nomatch_path,
        summary_json=str(summary_json_path), audit_report=str(audit_path),
    )


def _write_audit_report(run_id, state, county, boundary_type, results,
                         exact, crosswalk, normalized, ambiguous, no_match, blocked, total) -> Path:
    """Generate Markdown audit report."""
    report_path = REPORTS_DIR / f"{run_id}__precinct_id_audit.md"
    archive_ready = (exact + crosswalk + normalized) / max(total, 1)

    lines = [
        f"# Precinct ID Audit Report — {run_id}",
        "",
        f"**Jurisdiction:** {state} / {county} / {boundary_type}",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**Total IDs inspected:** {total}",
        "",
        "## Summary",
        "",
        "| Status | Count | % |",
        "|--------|-------|---|",
        f"| EXACT_MATCH | {exact} | {exact/max(total,1):.1%} |",
        f"| CROSSWALK_MATCH | {crosswalk} | {crosswalk/max(total,1):.1%} |",
        f"| NORMALIZED_MATCH | {normalized} | {normalized/max(total,1):.1%} |",
        f"| AMBIGUOUS | {ambiguous} | {ambiguous/max(total,1):.1%} |",
        f"| NO_MATCH | {no_match} | {no_match/max(total,1):.1%} |",
        f"| BLOCKED_CROSS_JURISDICTION | {blocked} | {blocked/max(total,1):.1%} |",
        f"| **Archive-Ready** | **{exact+crosswalk+normalized}** | **{archive_ready:.1%}** |",
        "",
        "## Schema Distribution",
        "",
        "| Schema | Count |",
        "|--------|-------|",
    ]
    schema_counts: dict[str, int] = {}
    for r in results:
        schema_counts[r.detected_schema] = schema_counts.get(r.detected_schema, 0) + 1
    for s, c in sorted(schema_counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| {s} | {c} |")

    # Sample ambiguous
    ambig_rows = [r for r in results if r.join_status == "AMBIGUOUS"]
    if ambig_rows:
        lines += ["", "## Ambiguous IDs (sample — first 10)", ""]
        for r in ambig_rows[:10]:
            lines.append(f"- `{r.raw_precinct}` — schema=`{r.detected_schema}` — {r.reason[:120]}")

    # Blocked cross-jurisdiction
    blocked_rows = [r for r in results if r.join_status == "BLOCKED_CROSS_JURISDICTION"]
    if blocked_rows:
        lines += ["", "## BLOCKED Cross-Jurisdiction Attempts", ""]
        for r in blocked_rows[:10]:
            lines.append(f"- `{r.raw_precinct}` — {r.reason[:120]}")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
