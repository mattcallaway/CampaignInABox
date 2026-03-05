"""
scripts/lib/schema_normalize.py  — Prompt 8.6

Single canonical column normalization for all precinct DataFrames.
Maps workbook/parser-produced variant names → canonical names used everywhere
downstream in the pipeline.

Usage:
    from scripts.lib.schema_normalize import normalize_precinct_columns
    df_norm, report = normalize_precinct_columns(df, context="Sheet1")
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Canonical target → accepted source variants (ordered by preference) ───────
CANONICAL_MAP: dict[str, list[str]] = {
    "canonical_precinct_id": [
        "canonical_precinct_id", "MPREC_ID", "PrecinctID", "precinct_id",
        "Precinct", "precinct", "PRECINCT_ID",
    ],
    "registered": [
        "registered", "Registered", "REG", "registration",
        "total_registered", "reg", "Reg",
    ],
    "ballots_cast": [
        "ballots_cast", "BallotsCast", "ballots", "total_votes",
        "TotalVotes", "Ballots", "total_ballots",
    ],
    "yes_votes": [
        "yes_votes", "YES", "Yes", "votes_yes", "for", "FOR",
        "votes_for", "VotesFor", "yes", "SupportVotes",
    ],
    "no_votes": [
        "no_votes", "NO", "No", "votes_no", "against", "AGAINST",
        "votes_against", "VotesAgainst", "no", "OpposeVotes",
    ],
    "support_pct": [
        "support_pct", "SupportPct", "yes_pct", "YesPct", "pct_yes",
        "support_rate",
    ],
    "turnout_pct": [
        "turnout_pct", "TurnoutPct", "pct_turnout", "turnout_rate",
        "Turnout",
    ],
}

# Required for the pipeline to continue
REQUIRED_CANONICAL = {"canonical_precinct_id", "registered", "ballots_cast"}

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class SchemaError(ValueError):
    """Raised when required fields are completely absent from DataFrame."""


def normalize_precinct_columns(
    df: pd.DataFrame,
    context: str = "unknown",
    contest_id: str = "unknown",
    run_id: str = "unknown",
    logger=None,
) -> tuple[pd.DataFrame, dict]:
    """
    Detect and rename variant column names to canonical names.

    Returns:
        (df_normalized, mapping_report)

    Raises:
        SchemaError if any REQUIRED_CANONICAL field cannot be mapped.
    """
    df = df.copy()
    original_cols = list(df.columns)
    mapping: dict[str, str] = {}          # original → canonical
    missing_canonical: list[str] = []
    inferred_cols: list[str] = []

    for canonical, variants in CANONICAL_MAP.items():
        found = None
        for v in variants:
            if v in df.columns:
                found = v
                break
        if found is None:
            missing_canonical.append(canonical)
        elif found != canonical:
            df = df.rename(columns={found: canonical})
            mapping[found] = canonical
            if logger:
                logger.info(f"  [SCHEMA] {found!r} → {canonical!r}")
        # else already canonical — no rename needed

    # Infer missing derived cols if possible
    if "turnout_pct" not in df.columns and "registered" in df.columns and "ballots_cast" in df.columns:
        safe_reg = pd.to_numeric(df["registered"], errors="coerce").replace(0, float("nan"))
        safe_balls = pd.to_numeric(df["ballots_cast"], errors="coerce")
        df["turnout_pct"] = (safe_balls / safe_reg).fillna(0.0).clip(0, 1)
        inferred_cols.append("turnout_pct")

    if "support_pct" not in df.columns and "yes_votes" in df.columns and "ballots_cast" in df.columns:
        safe_balls = pd.to_numeric(df["ballots_cast"], errors="coerce").replace(0, float("nan"))
        safe_yes = pd.to_numeric(df["yes_votes"], errors="coerce")
        df["support_pct"] = (safe_yes / safe_balls).fillna(0.5).clip(0, 1)
        inferred_cols.append("support_pct")

    # Infer contest type
    if "yes_votes" in df.columns or "no_votes" in df.columns:
        inferred_type = "ballot_measure"
    elif any("choice" in c.lower() for c in df.columns):
        inferred_type = "candidate_race"
    else:
        inferred_type = "unknown"

    # Hard stop for required fields
    hard_missing = [c for c in REQUIRED_CANONICAL if c not in df.columns]
    if hard_missing:
        msg = (
            f"[SCHEMA] REQUIRED fields could not be mapped in context={context!r}: "
            f"{hard_missing}. Original columns: {original_cols}"
        )
        if logger:
            logger.warn(msg)
        raise SchemaError(msg)

    report = {
        "context":          context,
        "contest_id":       contest_id,
        "run_id":           run_id,
        "original_columns": original_cols,
        "mapping":          mapping,
        "missing_optional": [c for c in missing_canonical if c not in REQUIRED_CANONICAL],
        "inferred_columns": inferred_cols,
        "inferred_contest_type": inferred_type,
        "final_columns":    list(df.columns),
        "status":           "ok",
    }

    # Write diagnostics
    _write_mapping_report(report, contest_id, run_id)

    return df, report


def _write_mapping_report(report: dict, contest_id: str, run_id: str) -> None:
    """Write JSON + Markdown mapping report."""
    import datetime
    report["timestamp"] = datetime.datetime.now().isoformat()

    diag_dir = BASE_DIR / "derived" / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    qa_dir = BASE_DIR / "reports" / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    json_path = diag_dir / f"{contest_id}__schema_mapping.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md_lines = [
        f"# Schema Mapping Report\n",
        f"**Context:** {report['context']}  **Contest:** `{contest_id}`  **Run:** `{run_id}`\n",
        f"**Inferred Contest Type:** `{report['inferred_contest_type']}`\n",
        "\n## Column Mappings\n",
        "| Original | Canonical |",
        "|---|---|",
    ]
    for orig, canon in report["mapping"].items():
        md_lines.append(f"| `{orig}` | `{canon}` |")
    if not report["mapping"]:
        md_lines.append("| _(all columns already canonical)_ | — |")
    if report["inferred_columns"]:
        md_lines.append(f"\n**Inferred (computed):** {', '.join(f'`{c}`' for c in report['inferred_columns'])}")
    if report["missing_optional"]:
        md_lines.append(f"\n**Missing optional:** {', '.join(f'`{c}`' for c in report['missing_optional'])}")

    md_path = qa_dir / f"{run_id}__schema_mapping.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
