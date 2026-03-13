"""
engine/archive_builder/archive_ingestor.py — Prompt 25 / Prompt 27

Archive ingestor — writes validated election datasets to the canonical archive.

Prompt 27 additions:
  - Explicit precinct schema detection step (id_schema_detector)
  - Hard acceptance gates (ARCHIVE_READY / REVIEW_REQUIRED / REJECTED)
  - Join metadata written to derived/archive_review_queue/<RUN_ID>__join_summary.json
  - Ambiguous rows written to derived/archive_review_queue/<RUN_ID>__ambiguous_ids.csv
  - No-match rows written to derived/archive_review_queue/<RUN_ID>__no_match_ids.csv
  - normalization_report written to reports/archive_builder/<RUN_ID>__archive_normalization_report.md
  - campaign_id/contest_id embedded in file_manifest.json when active campaign is known

Normalizer pipeline:
  source discovery
  → fingerprint classification
  → precinct schema detection   ← NEW Prompt 27
  → id normalization            ← NEW Prompt 27
  → safe join validation        ← enhanced Prompt 27
  → acceptance gate decision    ← NEW Prompt 27
  → archive ingestion

Archive storage structure:
  data/historical_elections/
    <STATE>/
      <COUNTY>/
        <ELECTION_ID>/
          contest_metadata.json
          precinct_results.csv
          contest_results.csv
          file_manifest.json

After ingestion → writes modeling inputs to derived/model_inputs/
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

BASE_DIR          = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR       = BASE_DIR / "data" / "historical_elections"
MODEL_INPUTS_DIR  = BASE_DIR / "derived" / "model_inputs"
REVIEW_QUEUE_DIR  = BASE_DIR / "derived" / "archive_review_queue"
REPORTS_ARCHIVE   = BASE_DIR / "reports" / "archive_builder"

for _d in (ARCHIVE_DIR, MODEL_INPUTS_DIR, REVIEW_QUEUE_DIR, REPORTS_ARCHIVE):
    _d.mkdir(parents=True, exist_ok=True)

# ── Acceptance gate thresholds ─────────────────────────────────────────────────
FINGERPRINT_MIN_CONFIDENCE = 0.50   # below this → REJECTED
JOIN_ARCHIVE_READY_MIN     = 0.70   # below this → REVIEW_REQUIRED
AMBIGUOUS_BLOCK_THRESHOLD  = 0.10   # >10% ambiguous rows → REVIEW_REQUIRED


def _election_id(state: str, county: str, year: Optional[int], election_type: Optional[str]) -> str:
    parts = [str(year or "unknown"), str(election_type or "general")]
    return "_".join(parts)


def _archive_election_dir(state: str, county: str, election_id: str) -> Path:
    d = ARCHIVE_DIR / state / county.replace(" ", "_") / election_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_slug(text: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", str(text).strip().lower())


def _read_dataframe(path: Path):
    import pandas as pd
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    elif ext == ".tsv":
        return pd.read_csv(path, sep="\t", low_memory=False)
    else:
        return pd.read_csv(path, low_memory=False)


def _get_active_campaign_context() -> Dict:
    """Try to read active campaign context for provenance embedding. Never raises."""
    try:
        from engine.state.campaign_state_resolver import get_active_campaign_id, get_latest_campaign_state
        cid = get_active_campaign_id()
        state = get_latest_campaign_state(cid)
        return {
            "campaign_id":   cid,
            "campaign_name": state.get("campaign_name", ""),
            "contest_id":    state.get("contest_id", ""),
        }
    except Exception:
        return {}


# ── Prompt 27: Full normalizer pipeline ──────────────────────────────────────

def _run_normalizer_pipeline(
    df,
    state: str,
    county: str,
    schema_key: Optional[str],
    run_id: str,
) -> Tuple[object, float, str, Dict, List[Dict], List[Dict]]:
    """
    Run the full 4-step normalization pipeline:
      1. Schema detection (id_schema_detector)
      2. Id normalization (id_normalizer)
      3. Crosswalk resolution (id_crosswalk_resolver)
      4. Safe join (safe_join_engine)

    Returns:
        (df_with_scoped_key, join_fraction, normalization_method,
         join_summary_dict, ambiguous_rows, no_match_rows)
    """
    from engine.precinct_ids.id_schema_detector import detect_column_schema
    from engine.precinct_ids.id_normalizer import normalize_ids
    from engine.precinct_ids.safe_join_engine import join_batch

    prec_cols = [c for c in df.columns
                 if any(pk in str(c).lower() for pk in ["precinct", "prec", "srprec", "mprec"])]

    if not prec_cols:
        return df, 0.0, "no_precinct_column", {}, [], []

    prec_col = prec_cols[0]
    raw_ids  = df[prec_col].astype(str).tolist()

    # Step 1: Schema detection
    schema_result = detect_column_schema(raw_ids, prec_col)
    detected_schema = schema_result.dominant_schema
    schema_confidence = schema_result.schema_confidence

    # Step 2: Normalization (normalize_ids applies string cleaning/padding)
    try:
        normalized_ids = normalize_ids(raw_ids, detected_schema, state, county)
    except Exception as e:
        log.warning(f"[INGESTOR] id_normalizer failed: {e} — using raw ids")
        normalized_ids = raw_ids

    # Step 3+4: Crosswalk + safe join
    batch = join_batch(normalized_ids, state, county, "MPREC")
    join_results = batch.join_results

    scoped_keys = [
        r.resolved_scoped_key if r.resolved_scoped_key else f"UNRESOLVED|{r.raw_precinct}"
        for r in join_results
    ]
    df = df.copy()
    df["scoped_key"]   = scoped_keys
    df["join_status"]  = [r.status for r in join_results]
    df["raw_precinct"] = [r.raw_precinct for r in join_results]

    # Categorize rows
    ambiguous_rows: List[Dict] = []
    no_match_rows:  List[Dict] = []
    for r in join_results:
        if r.status == "AMBIGUOUS":
            ambiguous_rows.append({
                "raw_precinct": r.raw_precinct,
                "status": r.status,
                "candidates": getattr(r, "candidates", []),
            })
        elif r.status in ("NO_MATCH", "BLOCKED_CROSS_JURISDICTION"):
            no_match_rows.append({
                "raw_precinct": r.raw_precinct,
                "status": r.status,
            })

    join_summary = {
        "run_id":                    run_id,
        "state":                     state,
        "county":                    county,
        "total_rows":                len(join_results),
        "exact_matches":             batch.exact_matches,
        "crosswalk_matches":         batch.crosswalk_matches,
        "normalized_matches":        batch.normalized_matches,
        "ambiguous":                 batch.ambiguous,
        "no_matches":                batch.no_matches,
        "blocked_cross_jurisdiction": batch.blocked_cross_jurisdiction,
        "archive_ready_fraction":    round(batch.archive_ready_fraction, 4),
        "schema_detected":           detected_schema,
        "schema_confidence":         round(schema_confidence, 4),
        "precinct_column":           prec_col,
        "generated_at":              datetime.now().isoformat(),
    }

    return (df, batch.archive_ready_fraction,
            f"schema:{detected_schema}+safe_join",
            join_summary, ambiguous_rows, no_match_rows)


def _write_join_metadata(
    run_id: str,
    join_summary: Dict,
    ambiguous_rows: List[Dict],
    no_match_rows: List[Dict],
    election_id: str,
    classified,          # ClassifiedFile
    norm_method: str,
    archive_file_status: str,
) -> None:
    """Write all join metadata files for this ingest run."""

    # join_summary.json
    js_path = REVIEW_QUEUE_DIR / f"{run_id}__join_summary.json"
    existing_summaries = []
    if js_path.exists():
        try:
            existing_summaries = json.loads(js_path.read_text(encoding="utf-8"))
        except Exception:
            existing_summaries = []
    if not isinstance(existing_summaries, list):
        existing_summaries = [existing_summaries]
    join_summary["election_id"] = election_id
    join_summary["archive_file_status"] = archive_file_status
    existing_summaries.append(join_summary)
    js_path.write_text(json.dumps(existing_summaries, indent=2, default=str), encoding="utf-8")

    # ambiguous_ids.csv
    if ambiguous_rows:
        ambi_path = REVIEW_QUEUE_DIR / f"{run_id}__ambiguous_ids.csv"
        is_new = not ambi_path.exists()
        with open(ambi_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["election_id", "raw_precinct", "status", "candidates"])
            if is_new:
                w.writeheader()
            for row in ambiguous_rows:
                w.writerow({
                    "election_id": election_id,
                    "raw_precinct": row["raw_precinct"],
                    "status": row["status"],
                    "candidates": "|".join(str(c) for c in row.get("candidates", [])),
                })

    # no_match_ids.csv
    if no_match_rows:
        nm_path = REVIEW_QUEUE_DIR / f"{run_id}__no_match_ids.csv"
        is_new = not nm_path.exists()
        with open(nm_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["election_id", "raw_precinct", "status"])
            if is_new:
                w.writeheader()
            for row in no_match_rows:
                w.writerow({"election_id": election_id, **row})

    # normalization report MD
    js = join_summary
    accept_icon = {"ARCHIVE_READY": "✅", "REVIEW_REQUIRED": "⚠️", "REJECTED": "❌"}.get(
        archive_file_status, "?"
    )
    total = max(js.get("total_rows", 0), 1)
    report_path = REPORTS_ARCHIVE / f"{run_id}__archive_normalization_report.md"
    mode = "a" if report_path.exists() else "w"
    with open(report_path, mode, encoding="utf-8") as f:
        f.write(f"""
## {accept_icon} {election_id} — {archive_file_status}

| Field | Value |
|-------|-------|
| Precinct column detected | `{js.get('precinct_column', 'N/A')}` |
| Schema detected | `{js.get('schema_detected', 'unknown')}` |
| Schema confidence | {js.get('schema_confidence', 0):.0%} |
| Normalization method | `{norm_method}` |
| Total rows | {js.get('total_rows', 0)} |
| Exact matches | {js.get('exact_matches', 0)} ({js.get('exact_matches', 0)/total:.0%}) |
| Crosswalk matches | {js.get('crosswalk_matches', 0)} ({js.get('crosswalk_matches', 0)/total:.0%}) |
| Normalized matches | {js.get('normalized_matches', 0)} ({js.get('normalized_matches', 0)/total:.0%}) |
| Ambiguous | {js.get('ambiguous', 0)} ({js.get('ambiguous', 0)/total:.0%}) |
| Blocked (cross-jurisdiction) | {js.get('blocked_cross_jurisdiction', 0)} |
| No match | {js.get('no_matches', 0)} ({js.get('no_matches', 0)/total:.0%}) |
| **Join rate (archive-ready)** | **{js.get('archive_ready_fraction', 0):.0%}** |
| **Archive file status** | **{archive_file_status}** |

""")


def _determine_archive_status(
    classified,          # ClassifiedFile
    join_fraction: float,
    norm_method: str,
    join_summary: Dict,
) -> str:
    """
    Apply hard acceptance gates to determine ARCHIVE_READY / REVIEW_REQUIRED / REJECTED.

    REJECTED (hard block):
      - fingerprint confidence < 0.50
      - blocked cross-jurisdiction rows > 0
      - normalization not completed (no precinct column)
      - file type unknown/error

    REVIEW_REQUIRED:
      - join_fraction < 0.70
      - ambiguous rows > 10%
      - schema confidence < 0.60

    ARCHIVE_READY:
      - all gates pass
    """
    # Hard REJECTED gates
    if classified.fingerprint_confidence < FINGERPRINT_MIN_CONFIDENCE:
        return "REJECTED"
    if join_summary.get("blocked_cross_jurisdiction", 0) > 0:
        return "REJECTED"
    if norm_method == "no_precinct_column" and not classified.archive_ready:
        return "REJECTED"
    if classified.fingerprint_type in ("unknown", "parse_error", "file_not_found"):
        return "REJECTED"

    # Soft gates → REVIEW_REQUIRED
    total = max(join_summary.get("total_rows", 0), 1)
    ambiguous_frac = join_summary.get("ambiguous", 0) / total
    if join_fraction < JOIN_ARCHIVE_READY_MIN:
        return "REVIEW_REQUIRED"
    if ambiguous_frac > AMBIGUOUS_BLOCK_THRESHOLD:
        return "REVIEW_REQUIRED"
    if join_summary.get("schema_confidence", 1.0) < 0.60:
        return "REVIEW_REQUIRED"

    return "ARCHIVE_READY"


# ── Main ingestion function ───────────────────────────────────────────────────

def ingest_classified_file(
    classified,        # ClassifiedFile from archive_classifier
    run_id: Optional[str] = None,
    force: bool = False,
) -> dict:
    """
    Ingest a ClassifiedFile into the canonical archive.

    Prompt 27 changes:
      - Runs full normalizer pipeline (schema detect → normalize → safe join)
      - Applies hard acceptance gates (ARCHIVE_READY / REVIEW_REQUIRED / REJECTED)
      - Writes join metadata files regardless of acceptance status
      - Embeds campaign context in file_manifest.json
      - Only ARCHIVE_READY files flow to modeling inputs
    """
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d__%H%M")

    state    = classified.state
    county   = classified.county
    year     = classified.year
    etype    = classified.election_type
    election_id = _election_id(state, county, year, etype)

    # Get active campaign context for provenance
    campaign_ctx = _get_active_campaign_context()

    # ── Load dataframe ────────────────────────────────────────────────────────
    path = Path(classified.local_path) if classified.local_path else None
    if not path or not path.exists():
        _write_to_review_queue(classified, run_id)
        return {
            "status": "REVIEW_QUEUE",
            "archive_file_status": "REJECTED",
            "election_id": election_id,
            "reasons": ["File not available locally"],
        }

    try:
        df = _read_dataframe(path)
    except Exception as e:
        return {"status": "INGEST_ERROR", "error": str(e), "election_id": election_id}

    # ── Prompt 27: Full normalizer pipeline ───────────────────────────────────
    df, join_frac, norm_method, join_summary, ambiguous_rows, no_match_rows = \
        _run_normalizer_pipeline(df, state, county, classified.precinct_schema, run_id)

    # ── Prompt 27: Hard acceptance gate ──────────────────────────────────────
    archive_file_status = _determine_archive_status(
        classified, join_frac, norm_method, join_summary
    )

    # ── Write join metadata (always, regardless of acceptance) ────────────────
    _write_join_metadata(
        run_id, join_summary, ambiguous_rows, no_match_rows,
        election_id, classified, norm_method, archive_file_status,
    )

    # ── Route non-ARCHIVE_READY files unless forced ───────────────────────────
    if archive_file_status != "ARCHIVE_READY" and not force:
        _write_to_review_queue(classified, run_id)
        return {
            "status": "REVIEW_QUEUE",
            "archive_file_status": archive_file_status,
            "election_id": election_id,
            "local_path": classified.local_path,
            "reasons": classified.review_reasons,
            "join_fraction": join_frac,
        }

    # ── Write to archive ──────────────────────────────────────────────────────
    elec_dir = _archive_election_dir(state, county, election_id)

    # Write precinct results CSV
    precinct_csv = elec_dir / "precinct_results.csv"
    df.to_csv(precinct_csv, index=False, encoding="utf-8")

    # Write contest metadata JSON
    metadata = {
        "election_id":     election_id,
        "state":           state,
        "county":          county,
        "year":            year,
        "election_type":   etype,
        "fingerprint_type": classified.fingerprint_type,
        "fingerprint_display": classified.fingerprint_display,
        "fingerprint_confidence": classified.fingerprint_confidence,
        "precinct_schema": classified.precinct_schema,
        "overall_confidence": classified.overall_confidence,
        "archive_file_status": archive_file_status,   # Prompt 27
        "rows":            len(df),
        "columns":         list(df.columns),
        "ingested_at":     datetime.now().isoformat(),
        "run_id":          run_id,
        # Prompt 27: campaign context
        "campaign_id":     campaign_ctx.get("campaign_id", ""),
        "campaign_name":   campaign_ctx.get("campaign_name", ""),
        "contest_id":      campaign_ctx.get("contest_id", ""),
        "archive_scope":   f"{state}/{county}",
    }
    (elec_dir / "contest_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    # Write file manifest (provenance) — Prompt 27 additions
    manifest = {
        "source_url":               classified.source_url,
        "source_id":                classified.source_id,
        "local_path":               classified.local_path,
        "download_timestamp":       classified.classified_at,
        "fingerprint_type":         classified.fingerprint_type,
        "fingerprint_confidence":   classified.fingerprint_confidence,
        "precinct_schema_detected": join_summary.get("schema_detected", ""),
        "normalization_method":     norm_method,
        "join_confidence_summary": {
            "archive_ready_fraction":    join_frac,
            "exact_matches":             join_summary.get("exact_matches", 0),
            "crosswalk_matches":         join_summary.get("crosswalk_matches", 0),
            "normalized_matches":        join_summary.get("normalized_matches", 0),
            "ambiguous":                 join_summary.get("ambiguous", 0),
            "blocked_cross_jurisdiction": join_summary.get("blocked_cross_jurisdiction", 0),
            "no_matches":                join_summary.get("no_matches", 0),
        },
        "ambiguous_row_count":      len(ambiguous_rows),
        "join_statuses":            classified.join_statuses,
        "archive_file_status":      archive_file_status,    # Prompt 27
        "archive_ready":            classified.archive_ready,
        # Campaign context (Prompt 27)
        "campaign_id":              campaign_ctx.get("campaign_id", ""),
        "campaign_name":            campaign_ctx.get("campaign_name", ""),
        "contest_id":               campaign_ctx.get("contest_id", ""),
        "jurisdiction_context":     f"{state}/{county}",
        "ingested_at":              datetime.now().isoformat(),
        "run_id":                   run_id,
    }
    (elec_dir / "file_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # ── Only ARCHIVE_READY files flow to modeling inputs ──────────────────────
    if archive_file_status == "ARCHIVE_READY":
        _write_modeling_inputs(df, state, county, election_id, classified.fingerprint_type)
    else:
        log.info(f"[INGESTOR] Skipping modeling inputs for {election_id} — status={archive_file_status}")

    log.info(
        f"[INGESTOR] Ingested: {election_id} → {elec_dir} "
        f"(rows={len(df)} join={join_frac:.1%} status={archive_file_status})"
    )
    return {
        "status":               "INGESTED",
        "archive_file_status":  archive_file_status,
        "election_id":          election_id,
        "archive_dir":          str(elec_dir),
        "rows":                 len(df),
        "join_fraction":        join_frac,
        "ambiguous_count":      len(ambiguous_rows),
        "no_match_count":       len(no_match_rows),
        "campaign_id":          campaign_ctx.get("campaign_id", ""),
        "run_id":               run_id,
    }


def _write_to_review_queue(classified, run_id: str) -> None:
    """Write a file to the ambiguity review queue CSV."""
    csv_path = REVIEW_QUEUE_DIR / f"{run_id}__ambiguous_files.csv"
    is_new   = not csv_path.exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "local_path", "source_url", "source_id", "state", "county",
            "year", "election_type", "fingerprint_type",
            "fingerprint_confidence", "overall_confidence",
            "archive_status", "archive_ready", "review_reasons", "classified_at",
        ])
        if is_new:
            w.writeheader()
        w.writerow({
            "local_path":             classified.local_path or "",
            "source_url":             classified.source_url or "",
            "source_id":              classified.source_id or "",
            "state":                  classified.state,
            "county":                 classified.county,
            "year":                   classified.year or "",
            "election_type":          classified.election_type or "",
            "fingerprint_type":       classified.fingerprint_type,
            "fingerprint_confidence": classified.fingerprint_confidence,
            "overall_confidence":     classified.overall_confidence,
            "archive_status":         getattr(classified, "archive_status", "UNKNOWN"),
            "archive_ready":          classified.archive_ready,
            "review_reasons":         "; ".join(classified.review_reasons[:5]),
            "classified_at":          classified.classified_at,
        })
    log.info(f"[INGESTOR] Review queue: {csv_path}")


def _write_modeling_inputs(df, state: str, county: str, election_id: str, fp_type: str) -> None:
    """
    Write modeling input CSVs to derived/model_inputs/.
    Only called for ARCHIVE_READY files.
    """
    import pandas as pd

    cols_lower = {str(c).lower(): c for c in df.columns}
    out_dir = MODEL_INPUTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    df = df.copy()
    df["_state"]       = state
    df["_county"]      = county
    df["_election_id"] = election_id
    df["_fp_type"]     = fp_type

    if "turnout" in cols_lower:
        out = out_dir / "historical_turnout.csv"
        mode = "a" if out.exists() else "w"
        df.to_csv(out, mode=mode, header=not out.exists(), index=False, encoding="utf-8")

    if "scoped_key" in df.columns and (df["scoped_key"] != "").any():
        out = out_dir / "precinct_vote_history.csv"
        mode = "a" if out.exists() else "w"
        df.to_csv(out, mode=mode, header=not out.exists(), index=False, encoding="utf-8")

    vote_cols = [c for c in df.columns if any(
        kw in str(c).lower() for kw in ["yes", "no", "candidate", "votes", "vote"]
    )][:10]
    if vote_cols:
        out = out_dir / "historical_vote_share.csv"
        share_df = df[[c for c in df.columns if c.startswith("_")] + vote_cols].copy()
        mode = "a" if out.exists() else "w"
        share_df.to_csv(out, mode=mode, header=not out.exists(), index=False, encoding="utf-8")
