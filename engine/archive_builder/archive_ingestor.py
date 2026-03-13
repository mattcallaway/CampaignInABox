"""
engine/archive_builder/archive_ingestor.py — Prompt 25

Archive ingestor — writes validated election datasets to the canonical archive.

Archive storage structure:
  data/historical_elections/
    <STATE>/
      <COUNTY>/
        <ELECTION_ID>/
          contest_metadata.json
          precinct_results.csv
          contest_results.csv
          file_manifest.json

Provenance tracking per file:
  source_url, download_timestamp, fingerprint_type, fingerprint_confidence,
  precinct_schema, normalization_method, join_confidence

After ingestion → writes modeling inputs to derived/model_inputs/
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR          = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR       = BASE_DIR / "data" / "historical_elections"
MODEL_INPUTS_DIR  = BASE_DIR / "derived" / "model_inputs"
REVIEW_QUEUE_DIR  = BASE_DIR / "derived" / "archive_review_queue"

for _d in (ARCHIVE_DIR, MODEL_INPUTS_DIR, REVIEW_QUEUE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _election_id(state: str, county: str, year: Optional[int], election_type: Optional[str]) -> str:
    """Build a canonical election ID string."""
    parts = [str(year or "unknown"), str(election_type or "general")]
    return "_".join(parts)


def _archive_election_dir(state: str, county: str, election_id: str) -> Path:
    """Return the canonical archive directory for an election, creating it if needed."""
    d = ARCHIVE_DIR / state / county.replace(" ", "_") / election_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_slug(text: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", str(text).strip().lower())


def _read_dataframe(path: Path):
    """Read a spreadsheet into a pandas DataFrame."""
    import pandas as pd
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    elif ext == ".tsv":
        return pd.read_csv(path, sep="\t", low_memory=False)
    else:
        return pd.read_csv(path, low_memory=False)


def _normalize_precinct_ids(df, state: str, county: str, schema_key: str) -> tuple:
    """
    Apply precinct ID normalization to the precinct column in-place.
    Returns (df_with_scoped_keys, join_fraction, normalization_method).
    Adds 'scoped_key' column.
    """
    from engine.precinct_ids.safe_join_engine import join_batch

    prec_cols = [c for c in df.columns
                 if any(pk in str(c).lower() for pk in ["precinct", "prec", "srprec", "mprec"])]
    if not prec_cols:
        df["scoped_key"] = ""
        return df, 0.0, "no_precinct_column"

    prec_col = prec_cols[0]
    raw_ids = df[prec_col].astype(str).tolist()

    batch = join_batch(raw_ids, state, county, "MPREC")
    scoped_keys = [
        r.resolved_scoped_key if r.resolved_scoped_key else f"UNRESOLVED|{r.raw_precinct}"
        for r in batch.join_results
    ]
    df["scoped_key"] = scoped_keys
    return df, batch.archive_ready_fraction, "safe_join_engine"


def ingest_classified_file(
    classified,   # ClassifiedFile from archive_classifier
    run_id: Optional[str] = None,
    force: bool = False,
) -> dict:
    """
    Ingest a ClassifiedFile into the canonical archive.

    If classified.archive_ready is False and force is False → routes to review queue.

    Args:
        classified:  ClassifiedFile from archive_classifier.classify_candidate_file()
        run_id:      run identifier for provenance
        force:       if True, ingest even if not archive_ready (for manual approval)

    Returns:
        dict with ingestion result metadata
    """
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d__%H%M")

    state    = classified.state
    county   = classified.county
    year     = classified.year
    etype    = classified.election_type
    election_id = _election_id(state, county, year, etype)

    # ── Route non-ready files to review queue ─────────────────────────────────
    if not classified.archive_ready and not force:
        _write_to_review_queue(classified, run_id)
        return {
            "status": "REVIEW_QUEUE",
            "election_id": election_id,
            "local_path": classified.local_path,
            "reasons": classified.review_reasons,
        }

    # ── Load dataframe ────────────────────────────────────────────────────────
    path = Path(classified.local_path)
    try:
        df = _read_dataframe(path)
    except Exception as e:
        return {"status": "INGEST_ERROR", "error": str(e), "election_id": election_id}

    # ── Normalize precinct IDs ────────────────────────────────────────────────
    df, join_frac, norm_method = _normalize_precinct_ids(
        df, state, county, classified.precinct_schema or "mprec"
    )

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
        "rows":            len(df),
        "columns":         list(df.columns),
        "ingested_at":     datetime.now().isoformat(),
        "run_id":          run_id,
    }
    (elec_dir / "contest_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    # Write file manifest (provenance)
    manifest = {
        "source_url":             classified.source_url,
        "source_id":              classified.source_id,
        "local_path":             classified.local_path,
        "download_timestamp":     classified.classified_at,
        "fingerprint_type":       classified.fingerprint_type,
        "fingerprint_confidence": classified.fingerprint_confidence,
        "precinct_schema":        classified.precinct_schema,
        "normalization_method":   norm_method,
        "join_confidence":        join_frac,
        "join_statuses":          classified.join_statuses,
        "archive_ready":          classified.archive_ready,
        "ingested_at":            datetime.now().isoformat(),
        "run_id":                 run_id,
    }
    (elec_dir / "file_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # ── Write modeling inputs ─────────────────────────────────────────────────
    _write_modeling_inputs(df, state, county, election_id, classified.fingerprint_type)

    log.info(
        f"[INGESTOR] Ingested: {election_id} → {elec_dir} "
        f"(rows={len(df)} join={join_frac:.1%})"
    )
    return {
        "status":       "INGESTED",
        "election_id":  election_id,
        "archive_dir":  str(elec_dir),
        "rows":         len(df),
        "join_fraction": join_frac,
        "run_id":       run_id,
    }


def _write_to_review_queue(classified, run_id: str) -> None:
    """Write a non-archive-ready file to the ambiguity review queue CSV."""
    queue_dir = REVIEW_QUEUE_DIR
    queue_dir.mkdir(parents=True, exist_ok=True)

    csv_path = queue_dir / f"{run_id}__ambiguous_files.csv"
    is_new   = not csv_path.exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "local_path", "source_url", "source_id", "state", "county",
            "year", "election_type", "fingerprint_type",
            "fingerprint_confidence", "overall_confidence",
            "archive_ready", "review_reasons", "classified_at",
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
            "archive_ready":          classified.archive_ready,
            "review_reasons":         "; ".join(classified.review_reasons[:5]),
            "classified_at":          classified.classified_at,
        })
    log.info(f"[INGESTOR] Review queue: {csv_path}")


def _write_modeling_inputs(df, state: str, county: str, election_id: str, fp_type: str) -> None:
    """
    Write modeling input CSVs to derived/model_inputs/.

    Outputs:
      historical_turnout.csv     (if file has turnout data)
      historical_vote_share.csv  (if file has vote columns + precinct)
      precinct_vote_history.csv  (if precinct-level data)
    """
    import pandas as pd

    cols_lower = {str(c).lower(): c for c in df.columns}
    out_dir = MODEL_INPUTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Add jurisdiction metadata columns
    df = df.copy()
    df["_state"]       = state
    df["_county"]      = county
    df["_election_id"] = election_id
    df["_fp_type"]     = fp_type

    # Turnout data
    if "turnout" in cols_lower:
        out = out_dir / "historical_turnout.csv"
        mode = "a" if out.exists() else "w"
        df.to_csv(out, mode=mode, header=not out.exists(), index=False, encoding="utf-8")

    # Precinct vote history (any precinct-level file)
    if "scoped_key" in df.columns and (df["scoped_key"] != "").any():
        out = out_dir / "precinct_vote_history.csv"
        mode = "a" if out.exists() else "w"
        df.to_csv(out, mode=mode, header=not out.exists(), index=False, encoding="utf-8")

    # Vote share
    vote_cols = [c for c in df.columns if any(
        kw in str(c).lower() for kw in ["yes", "no", "candidate", "votes", "vote"]
    )][: 10]
    if vote_cols:
        out = out_dir / "historical_vote_share.csv"
        share_df = df[[c for c in df.columns if c.startswith("_")] + vote_cols].copy()
        mode = "a" if out.exists() else "w"
        share_df.to_csv(out, mode=mode, header=not out.exists(), index=False, encoding="utf-8")
