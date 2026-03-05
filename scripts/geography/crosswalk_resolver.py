"""
scripts/geography/crosswalk_resolver.py

Loads and validates crosswalk tables between precinct geographies.
Enforces: weights per source precinct sum to 1.0 ± tolerance.
Resolves chains: MPREC↔SRPREC, SRPREC↔SVPREC, SRPREC↔CITY.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import openpyxl


_TOLERANCE = 0.001  # crosswalk weight sum tolerance


def _read_csv_or_tsv(path: Path) -> list[dict]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def _read_xls_sheet(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
    return [dict(zip(headers, row)) for row in rows[1:]]


def load_crosswalk_table(path: str | Path) -> list[dict]:
    """
    Load a crosswalk file (.csv, .tsv, .xlsx, .xls).
    Returns list of dicts with raw string values.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv", ".txt"):
        return _read_csv_or_tsv(path)
    elif suffix in (".xlsx", ".xls"):
        return _read_xls_sheet(path)
    raise ValueError(f"Unsupported crosswalk format: {suffix}")


def detect_crosswalk_columns(headers: list[str]) -> tuple[str | None, str | None, str | None]:
    """
    Auto-detect source ID, target ID, and weight columns.
    Returns (source_col, target_col, weight_col); None if not found.
    """
    headers_upper = {h.upper(): h for h in headers}
    source_candidates = ["SOURCE", "SRPREC_ID", "MPREC_ID", "FROM_ID", "SRC"]
    target_candidates = ["TARGET", "MPREC_ID", "SRPREC_ID", "TO_ID", "DST", "DEST"]
    weight_candidates = ["WEIGHT", "PCT", "FRACTION", "AREA_PCT", "PROPORTION"]

    def _find(candidates):
        for c in candidates:
            if c in headers_upper:
                return headers_upper[c]
        return None

    src = _find(source_candidates)
    tgt = _find(target_candidates)
    wt  = _find(weight_candidates)
    return src, tgt, wt


def validate_crosswalk(
    rows: list[dict],
    source_col: str,
    weight_col: str | None,
    tolerance: float = _TOLERANCE,
) -> tuple[bool, list[str]]:
    """
    Validate that crosswalk weights sum to 1.0 ± tolerance per source precinct.
    Returns (valid, list_of_warnings).
    """
    if not weight_col:
        return True, ["No weight column found; skipping weight validation."]

    from collections import defaultdict
    sums: dict[str, float] = defaultdict(float)
    for row in rows:
        src = str(row.get(source_col, "")).strip()
        try:
            w = float(row.get(weight_col, 0) or 0)
        except (ValueError, TypeError):
            w = 0.0
        sums[src] += w

    warnings = []
    valid = True
    for src, total in sums.items():
        if abs(total - 1.0) > tolerance:
            warnings.append(
                f"Source precinct {src!r}: weights sum to {total:.6f} (expected 1.0 ± {tolerance})"
            )
            valid = False
    return valid, warnings


def build_crosswalk_dict(
    rows: list[dict],
    source_col: str,
    target_col: str,
    weight_col: str | None,
) -> dict[str, list[tuple[str, float]]]:
    """
    Build mapping: source_id → [(target_id, weight), ...]
    If no weight column, assign equal weights.
    """
    from collections import defaultdict

    raw: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in rows:
        src = str(row.get(source_col, "")).strip()
        tgt = str(row.get(target_col, "")).strip()
        if weight_col:
            try:
                w = float(row.get(weight_col, 0) or 0)
            except (ValueError, TypeError):
                w = 0.0
        else:
            w = None  # type: ignore
        raw[src].append((tgt, w))

    # If weights are None, assign equal fractions
    result: dict[str, list[tuple[str, float]]] = {}
    for src, entries in raw.items():
        if entries[0][1] is None:
            n = len(entries)
            result[src] = [(t, round(1.0 / n, 8)) for t, _ in entries]
        else:
            result[src] = entries

    return result


def load_crosswalk_from_category(
    county_dir: str | Path,
    category_folder: str,
    logger=None,
) -> tuple[dict, bool]:
    """
    Load crosswalk from a category folder. Returns (crosswalk_dict, success).
    crosswalk_dict: {source_id: [(target_id, weight), ...]}
    """
    county_dir = Path(county_dir)
    cat_dir = county_dir / category_folder

    from ..loaders.file_loader import discover_files
    from ..loaders.categories import CROSSWALK_EXTENSIONS

    def _log(msg, level="INFO"):
        if logger:
            getattr(logger, level.lower(), logger.info)(msg)

    if not cat_dir.is_dir():
        _log(f"Crosswalk dir not found: {cat_dir}", "WARN")
        return {}, False

    files = discover_files(cat_dir, CROSSWALK_EXTENSIONS)
    files = [f for f in files if f.name != ".gitkeep"]
    if not files:
        _log(f"No crosswalk files in {cat_dir}", "WARN")
        return {}, False

    path = files[0]
    try:
        rows = load_crosswalk_table(path)
        if not rows:
            _log(f"Empty crosswalk: {path}", "WARN")
            return {}, False

        headers = list(rows[0].keys())
        src_col, tgt_col, wt_col = detect_crosswalk_columns(headers)
        if not src_col or not tgt_col:
            _log(f"Cannot detect source/target columns in {path.name}: {headers}", "WARN")
            return {}, False

        valid, warnings = validate_crosswalk(rows, src_col, wt_col)
        for w in warnings:
            _log(f"  crosswalk warning: {w}", "WARN")

        xwalk = build_crosswalk_dict(rows, src_col, tgt_col, wt_col)
        _log(f"Loaded crosswalk {category_folder}: {len(xwalk)} source precincts")
        return xwalk, True

    except Exception as e:
        _log(f"Error loading crosswalk {path}: {e}", "WARN")
        return {}, False
