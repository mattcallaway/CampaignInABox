"""
engine/archive_builder/archive_output_writer.py — Prompt 25

Archive output CSV writer.

Reads all ARCHIVE_READY ingested election datasets and writes 4 derived output files:

  data/election_archive/normalized/normalized_elections.csv
    One row per election, all metadata columns.

  derived/archive/precinct_profiles.csv
    One row per unique precinct (scoped_key), aggregated across all elections:
    - avg_turnout, elections_count, first_year, last_year, election_ids

  derived/archive/precinct_trends.csv
    One row per (precinct × election), capturing time-series turnout/vote share.

  derived/archive/similar_elections.csv
    Pairs of elections with similarity scores based on:
    - contest type match (ballot measure, partisan, etc.)
    - year proximity
    - county match
    - turnout proximity

All outputs use UTF-8 encoding.

Public API:
  write_archive_outputs(ingested_results, run_id) -> dict[str, Path]
    called by archive_builder after ingestion completes
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
NORM_DIR     = BASE_DIR / "data" / "election_archive" / "normalized"
ARCHIVE_DIR  = BASE_DIR / "derived" / "archive"
ARCHIVE_HIST = BASE_DIR / "data" / "historical_elections"

for _d in (NORM_DIR, ARCHIVE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ── Internal data structures ──────────────────────────────────────────────────

@dataclass
class ElectionMeta:
    election_id:    str
    state:          str
    county:         str
    year:           Optional[int]
    election_type:  Optional[str]
    source_url:     str
    fingerprint_type: str
    fingerprint_confidence: float
    precinct_schema: Optional[str]
    overall_confidence: float
    archive_status:  str
    join_fraction:   float
    row_count:       int
    archive_dir:     str
    run_id:          str
    ingested_at:     str


def _read_contest_metadata(archive_dir: str) -> Optional[dict]:
    """Read contest_metadata.json from an election's archive directory."""
    p = Path(archive_dir) / "contest_metadata.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_precinct_results(archive_dir: str):
    """Read precinct_results.csv from an election's archive directory. Returns df or None."""
    p = Path(archive_dir) / "precinct_results.csv"
    if not p.exists():
        return None
    try:
        import pandas as pd
        return pd.read_csv(p, low_memory=False)
    except Exception:
        return None


def _scan_archive_dirs() -> list[dict]:
    """
    Scan data/historical_elections/ for all directories containing contest_metadata.json.
    Returns list of contest_metadata dicts.
    """
    results: list[dict] = []
    for state_dir in ARCHIVE_HIST.iterdir():
        if not state_dir.is_dir():
            continue
        for county_dir in state_dir.iterdir():
            if not county_dir.is_dir():
                continue
            for elec_dir in county_dir.iterdir():
                if not elec_dir.is_dir():
                    continue
                md = _read_contest_metadata(str(elec_dir))
                if md:
                    md["_archive_dir"] = str(elec_dir)
                    results.append(md)
    return results


# ── normalized_elections.csv ──────────────────────────────────────────────────

_NORM_FIELDNAMES = [
    "election_id", "state", "county", "year", "election_type",
    "fingerprint_type", "fingerprint_display", "fingerprint_confidence",
    "precinct_schema", "overall_confidence", "archive_status",
    "archive_ready_fraction", "rows", "archive_dir", "run_id",
    "campaign_id", "contest_id", "ingested_at",
]


def _write_normalized_elections(all_meta: list[dict]) -> Path:
    out = NORM_DIR / "normalized_elections.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_NORM_FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        for md in all_meta:
            w.writerow({
                "election_id":              md.get("election_id", ""),
                "state":                    md.get("state", ""),
                "county":                   md.get("county", ""),
                "year":                     md.get("year", ""),
                "election_type":            md.get("election_type", ""),
                "fingerprint_type":         md.get("fingerprint_type", ""),
                "fingerprint_display":      md.get("fingerprint_display", ""),
                "fingerprint_confidence":   md.get("fingerprint_confidence", ""),
                "precinct_schema":          md.get("precinct_schema", ""),
                "overall_confidence":       md.get("overall_confidence", ""),
                "archive_status":           md.get("archive_status", ""),
                "archive_ready_fraction":   md.get("archive_ready_fraction", ""),
                "rows":                     md.get("rows", ""),
                "archive_dir":              md.get("_archive_dir", md.get("archive_dir", "")),
                "run_id":                   md.get("run_id", ""),
                "campaign_id":              md.get("campaign_id", ""),
                "contest_id":               md.get("contest_id", ""),
                "ingested_at":              md.get("ingested_at", ""),
            })
    log.info(f"[OUTPUT_WRITER] normalized_elections.csv: {len(all_meta)} rows → {out}")
    return out


# ── precinct_profiles.csv ─────────────────────────────────────────────────────

_PROFILE_FIELDNAMES = [
    "scoped_key", "state", "county", "elections_count",
    "first_year", "last_year", "avg_turnout", "election_ids",
]


def _write_precinct_profiles(all_meta: list[dict]) -> Path:
    """Aggregate all precinct_results.csv files into per-precinct profile rows."""
    out = ARCHIVE_DIR / "precinct_profiles.csv"

    # Aggregate by scoped_key
    profiles: dict[str, dict] = {}

    for md in all_meta:
        if md.get("archive_status") != "ARCHIVE_READY":
            continue
        archive_dir = md.get("_archive_dir", md.get("archive_dir", ""))
        df = _read_precinct_results(archive_dir)
        if df is None or df.empty:
            continue

        year         = md.get("year")
        election_id  = md.get("election_id", "")
        state        = md.get("state", "CA")
        county       = md.get("county", "")

        if "scoped_key" not in df.columns:
            continue

        # Detect turnout column
        turnout_col = None
        for col in df.columns:
            if "turnout" in str(col).lower() or "votes_cast" in str(col).lower():
                turnout_col = col
                break

        for _, row in df.iterrows():
            sk = str(row.get("scoped_key", "")).strip()
            if not sk or sk.startswith("UNRESOLVED"):
                continue

            if sk not in profiles:
                profiles[sk] = {
                    "scoped_key":       sk,
                    "state":            state,
                    "county":           county,
                    "elections_count":  0,
                    "first_year":       year,
                    "last_year":        year,
                    "turnout_sum":      0.0,
                    "turnout_count":    0,
                    "election_ids":     [],
                }

            p = profiles[sk]
            p["elections_count"] += 1
            if election_id not in p["election_ids"]:
                p["election_ids"].append(election_id)
            if year:
                if not p["first_year"] or year < p["first_year"]:
                    p["first_year"] = year
                if not p["last_year"] or year > p["last_year"]:
                    p["last_year"] = year
            if turnout_col and row.get(turnout_col) is not None:
                try:
                    p["turnout_sum"]   += float(row[turnout_col])
                    p["turnout_count"] += 1
                except (ValueError, TypeError):
                    pass

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_PROFILE_FIELDNAMES)
        w.writeheader()
        for p in profiles.values():
            avg_turnout = (
                round(p["turnout_sum"] / p["turnout_count"], 1)
                if p["turnout_count"] > 0 else ""
            )
            w.writerow({
                "scoped_key":       p["scoped_key"],
                "state":            p["state"],
                "county":           p["county"],
                "elections_count":  p["elections_count"],
                "first_year":       p["first_year"] or "",
                "last_year":        p["last_year"] or "",
                "avg_turnout":      avg_turnout,
                "election_ids":     "|".join(p["election_ids"]),
            })

    log.info(f"[OUTPUT_WRITER] precinct_profiles.csv: {len(profiles)} precincts → {out}")
    return out


# ── precinct_trends.csv ───────────────────────────────────────────────────────

_TRENDS_FIELDNAMES = [
    "scoped_key", "state", "county", "election_id", "year",
    "election_type", "turnout", "yes_votes", "no_votes",
    "top_candidate_votes", "join_status",
]


def _write_precinct_trends(all_meta: list[dict]) -> Path:
    """Write one row per (precinct × election) time-series slice."""
    out = ARCHIVE_DIR / "precinct_trends.csv"

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_TRENDS_FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        row_count = 0

        for md in all_meta:
            if md.get("archive_status") != "ARCHIVE_READY":
                continue
            archive_dir  = md.get("_archive_dir", md.get("archive_dir", ""))
            election_id  = md.get("election_id", "")
            year         = md.get("year", "")
            election_type = md.get("election_type", "")
            state         = md.get("state", "CA")
            county        = md.get("county", "")

            df = _read_precinct_results(archive_dir)
            if df is None or df.empty:
                continue
            if "scoped_key" not in df.columns:
                continue

            # Detect vote columns
            yes_col = next((c for c in df.columns if "yes" in str(c).lower()), None)
            no_col  = next((c for c in df.columns if "no" in str(c).lower() and "none" not in str(c).lower()), None)
            turnout_col = next((c for c in df.columns if "turnout" in str(c).lower() or "votes_cast" in str(c).lower()), None)

            # Try to find the column with highest totals (top candidate)
            numeric_cols = df.select_dtypes(include="number").columns.tolist()
            top_cand_col = None
            if numeric_cols:
                totals = {c: df[c].sum() for c in numeric_cols if c not in ("scoped_key",)}
                if totals:
                    top_cand_col = max(totals, key=totals.get)

            for _, row in df.iterrows():
                sk = str(row.get("scoped_key", "")).strip()
                if not sk:
                    continue

                def _val(col):
                    if col is None:
                        return ""
                    v = row.get(col, "")
                    try:
                        return float(v) if v not in ("", None) else ""
                    except (ValueError, TypeError):
                        return ""

                w.writerow({
                    "scoped_key":          sk,
                    "state":               state,
                    "county":              county,
                    "election_id":         election_id,
                    "year":                year,
                    "election_type":       election_type,
                    "turnout":             _val(turnout_col),
                    "yes_votes":           _val(yes_col),
                    "no_votes":            _val(no_col),
                    "top_candidate_votes": _val(top_cand_col),
                    "join_status":         row.get("join_status", ""),
                })
                row_count += 1

    log.info(f"[OUTPUT_WRITER] precinct_trends.csv: {row_count} rows → {out}")
    return out


# ── similar_elections.csv ─────────────────────────────────────────────────────

_SIMILAR_FIELDNAMES = [
    "election_id_a", "election_id_b", "similarity_score",
    "same_county", "same_election_type", "year_delta",
    "state_a", "county_a", "year_a", "type_a",
    "state_b", "county_b", "year_b", "type_b",
]


def _compute_similarity(a: dict, b: dict) -> float:
    """
    Compute a similarity score (0.0–1.0) between two election metadata dicts.

    Factors:
      - contest type match: 0.40 points
      - county match:       0.30 points
      - year proximity:     0.30 points (linear decay over 8 years)
    """
    score = 0.0

    # Election type match
    if a.get("election_type") and a.get("election_type") == b.get("election_type"):
        score += 0.40

    # County match
    if (a.get("county", "").lower() or "X") == (b.get("county", "").lower() or "Y"):
        score += 0.30

    # Year proximity (capped at 8 years)
    try:
        year_a = int(a.get("year") or 0)
        year_b = int(b.get("year") or 0)
        if year_a and year_b:
            delta = abs(year_a - year_b)
            year_score = max(0.0, 1.0 - delta / 8.0) * 0.30
            score += year_score
    except (ValueError, TypeError):
        pass

    return round(score, 4)


def _write_similar_elections(all_meta: list[dict], min_similarity: float = 0.40) -> Path:
    out = ARCHIVE_DIR / "similar_elections.csv"
    pairs: list[dict] = []

    ready = [m for m in all_meta if m.get("election_id")]
    for a, b in combinations(ready, 2):
        sim = _compute_similarity(a, b)
        if sim >= min_similarity:
            try:
                year_delta = abs(int(a.get("year") or 0) - int(b.get("year") or 0))
            except (ValueError, TypeError):
                year_delta = ""
            pairs.append({
                "election_id_a":    a.get("election_id", ""),
                "election_id_b":    b.get("election_id", ""),
                "similarity_score": sim,
                "same_county":      a.get("county", "").lower() == b.get("county", "").lower(),
                "same_election_type": a.get("election_type") == b.get("election_type"),
                "year_delta":       year_delta,
                "state_a":          a.get("state", ""),
                "county_a":         a.get("county", ""),
                "year_a":           a.get("year", ""),
                "type_a":           a.get("election_type", ""),
                "state_b":          b.get("state", ""),
                "county_b":         b.get("county", ""),
                "year_b":           b.get("year", ""),
                "type_b":           b.get("election_type", ""),
            })

    pairs.sort(key=lambda p: p["similarity_score"], reverse=True)

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_SIMILAR_FIELDNAMES)
        w.writeheader()
        w.writerows(pairs)

    log.info(f"[OUTPUT_WRITER] similar_elections.csv: {len(pairs)} pairs → {out}")
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def write_archive_outputs(
    ingested_results: Optional[list[dict]] = None,
    run_id: Optional[str] = None,
) -> dict[str, str]:
    """
    Write all 4 archive output files.

    If ingested_results is provided, it supplements the on-disk archive scan.
    Always rescans data/historical_elections/ for the full picture.

    Args:
        ingested_results: list of result dicts from archive_ingestor (may be empty)
        run_id:           run identifier for logging

    Returns:
        dict mapping output_name -> str(path)
    """
    run_id = run_id or datetime.now().strftime("%Y%m%d__%H%M")
    log.info(f"[OUTPUT_WRITER] [{run_id}] Scanning archive dirs...")

    all_meta = _scan_archive_dirs()
    log.info(f"[OUTPUT_WRITER] Found {len(all_meta)} archived elections on disk")

    outputs: dict[str, str] = {}

    try:
        p = _write_normalized_elections(all_meta)
        outputs["normalized_elections"] = str(p)
    except Exception as e:
        log.error(f"[OUTPUT_WRITER] normalized_elections failed: {e}")

    try:
        p = _write_precinct_profiles(all_meta)
        outputs["precinct_profiles"] = str(p)
    except Exception as e:
        log.error(f"[OUTPUT_WRITER] precinct_profiles failed: {e}")

    try:
        p = _write_precinct_trends(all_meta)
        outputs["precinct_trends"] = str(p)
    except Exception as e:
        log.error(f"[OUTPUT_WRITER] precinct_trends failed: {e}")

    try:
        p = _write_similar_elections(all_meta)
        outputs["similar_elections"] = str(p)
    except Exception as e:
        log.error(f"[OUTPUT_WRITER] similar_elections failed: {e}")

    log.info(f"[OUTPUT_WRITER] [{run_id}] Done: {len(outputs)}/4 outputs written")
    return outputs
