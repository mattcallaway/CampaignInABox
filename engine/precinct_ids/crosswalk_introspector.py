"""
engine/precinct_ids/crosswalk_introspector.py — Prompt 29

Deep per-file crosswalk inspection. Records detection status, sample values,
null percentages, and failure reasons so humans can trace exactly why a crosswalk
join failed.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class CrosswalkFileReport:
    filename:          str
    filepath:          str
    filetype:          str
    row_count:         int
    col_names:         list[str]
    candidate_sources: list[str]       # columns that look like source IDs
    candidate_targets: list[str]       # columns that look like target IDs
    source_col:        Optional[str]   # resolved source column (or None)
    target_col:        Optional[str]   # resolved target column (or None)
    weight_col:        Optional[str]   # resolved weight column (or None)
    detection_ok:      bool
    detection_method:  str             # "config_override" | "alias_table" | "failed"
    detection_failure_reason: Optional[str]
    sample_values:     dict            # {col_name: [v1, v2, v3]}
    null_pcts:         dict            # {col_name: float}
    unique_counts:     dict            # {col_name: int}
    identity_fallback_risk: bool       # True if detection failed → fallback risk


def _col_looks_like_id(col: str) -> bool:
    """Heuristic: does this column name smell like a precinct/block ID?"""
    kw = ["prec", "block", "mprec", "srprec", "rgprec", "svprec", "rrprec",
          "id", "src", "tgt", "from", "to", "source", "target"]
    return any(k in col.lower() for k in kw)


def _col_looks_like_weight(col: str) -> bool:
    kw = ["pct", "weight", "frac", "proportion", "wt", "area"]
    return any(k in col.lower() for k in kw)


def introspect_file(path: Path) -> CrosswalkFileReport:
    """Inspect a single crosswalk file and return a detailed report."""
    fname = path.name
    ftype = path.suffix.lower().lstrip(".")

    try:
        import pandas as pd
        if ftype in ("csv", "txt"):
            df = pd.read_csv(path, nrows=50_000)
        elif ftype in ("xlsx", "xls"):
            df = pd.read_excel(path, nrows=50_000)
        elif ftype == "json":
            data = json.loads(path.read_text(encoding="utf-8"))
            df = pd.DataFrame(data if isinstance(data, list) else [data])
        else:
            return CrosswalkFileReport(
                filename=fname, filepath=str(path), filetype=ftype,
                row_count=0, col_names=[], candidate_sources=[], candidate_targets=[],
                source_col=None, target_col=None, weight_col=None,
                detection_ok=False, detection_method="failed",
                detection_failure_reason=f"Unsupported file type: {ftype}",
                sample_values={}, null_pcts={}, unique_counts={},
                identity_fallback_risk=True,
            )
    except Exception as e:
        return CrosswalkFileReport(
            filename=fname, filepath=str(path), filetype=ftype,
            row_count=0, col_names=[], candidate_sources=[], candidate_targets=[],
            source_col=None, target_col=None, weight_col=None,
            detection_ok=False, detection_method="failed",
            detection_failure_reason=f"Read error: {e}",
            sample_values={}, null_pcts={}, unique_counts={},
            identity_fallback_risk=True,
        )

    cols = list(df.columns)
    n    = len(df)

    # Candidate ID / weight columns
    cand_src = [c for c in cols if _col_looks_like_id(c) and not _col_looks_like_weight(c)]
    cand_wt  = [c for c in cols if _col_looks_like_weight(c)]
    cand_tgt = [c for c in cols if _col_looks_like_id(c) and c not in cand_src[:1]]

    # Sample values (first 5 non-null per column)
    samples: dict = {}
    null_pcts: dict = {}
    unique_counts: dict = {}
    for c in cols:
        nonnull = df[c].dropna()
        samples[c]      = [str(v) for v in nonnull.head(5).tolist()]
        null_pcts[c]    = round(df[c].isna().sum() / max(n, 1), 4)
        unique_counts[c] = int(df[c].nunique())

    # Try detection via the repaired detector
    try:
        from scripts.geography.crosswalk_resolver import detect_crosswalk_columns
        src, tgt, wt = detect_crosswalk_columns(cols, filename=str(path))
        ok = bool(src and tgt)
        method = "config_override" if ok else "alias_table"
        reason = None if ok else (
            f"Could not resolve source+target from headers {cols}. "
            f"Add per_file_hints to config/precinct_id/crosswalk_column_hints.yaml"
        )
    except Exception as e:
        src, tgt, wt, ok = None, None, None, False
        method = "failed"
        reason = str(e)

    return CrosswalkFileReport(
        filename=fname,
        filepath=str(path),
        filetype=ftype,
        row_count=n,
        col_names=cols,
        candidate_sources=cand_src,
        candidate_targets=cand_tgt,
        source_col=src,
        target_col=tgt,
        weight_col=wt,
        detection_ok=ok,
        detection_method=method,
        detection_failure_reason=reason,
        sample_values=samples,
        null_pcts=null_pcts,
        unique_counts=unique_counts,
        identity_fallback_risk=not ok,
    )


def introspect_crosswalk_directory(
    state: str,
    county: str,
    crosswalk_dir: Optional[Path] = None,
) -> list[CrosswalkFileReport]:
    """
    Inspect all crosswalk files for a given state/county.
    Returns list of CrosswalkFileReport, one per file.
    """
    if crosswalk_dir is None:
        crosswalk_dir = (
            BASE_DIR / "data" / state / "counties" / county / "geography" / "crosswalks"
        )

    if not crosswalk_dir.exists():
        log.warning(f"[INTROSPECT] Crosswalk directory not found: {crosswalk_dir}")
        return []

    reports = []
    for path in sorted(crosswalk_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in (".csv", ".xlsx", ".xls", ".json") \
                and ".gitkeep" not in path.name:
            log.info(f"[INTROSPECT] Inspecting {path.name}")
            reports.append(introspect_file(path))

    ok_count  = sum(1 for r in reports if r.detection_ok)
    fail_count = len(reports) - ok_count
    log.info(
        f"[INTROSPECT] {state}/{county}: {len(reports)} crosswalk files — "
        f"{ok_count} detection OK, {fail_count} failed"
    )
    return reports


def reports_to_trace_json(reports: list[CrosswalkFileReport]) -> dict:
    """Convert a list of CrosswalkFileReports to a JSON-serialisable dict."""
    return {
        "crosswalk_files_inspected": len(reports),
        "detection_ok_count":  sum(1 for r in reports if r.detection_ok),
        "identity_fallback_risk_count": sum(1 for r in reports if r.identity_fallback_risk),
        "files": [asdict(r) for r in reports],
    }
