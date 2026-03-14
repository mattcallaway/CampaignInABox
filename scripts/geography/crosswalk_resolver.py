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



_HINTS_CACHE: dict | None = None


def _load_column_hints() -> dict:
    """Load crosswalk column hints from config (cached)."""
    global _HINTS_CACHE
    if _HINTS_CACHE is not None:
        return _HINTS_CACHE
    hints_path = Path(__file__).resolve().parent.parent.parent / "config" / "precinct_id" / "crosswalk_column_hints.yaml"
    try:
        import yaml
        with open(hints_path, encoding="utf-8") as f:
            _HINTS_CACHE = yaml.safe_load(f) or {}
    except Exception:
        _HINTS_CACHE = {}
    return _HINTS_CACHE


def detect_crosswalk_columns(
    headers: list[str],
    filename: str = "",
) -> tuple[str | None, str | None, str | None]:
    """
    Auto-detect source ID, target ID, and weight columns from crosswalk headers.

    Resolution order (P29 repair):
      1. Per-file explicit override from config/precinct_id/crosswalk_column_hints.yaml
      2. Expanded lowercase + uppercase alias table (covers actual Sonoma column names)
      3. Filename-based heuristic tiebreaker

    Returns (source_col, target_col, weight_col); None if column not found.
    Never silently falls back when a config override is available — logs clearly.
    """
    import logging
    log = logging.getLogger(__name__)

    hints    = _load_column_hints()
    headers_lower = {h.lower(): h for h in headers}  # lowercase → original name

    # ── Tier 1: Per-file config override ──────────────────────────────────────
    per_file = hints.get("per_file_hints", {})
    fname    = Path(filename).name if filename else ""
    if fname and fname in per_file:
        override = per_file[fname]
        src_hint = override.get("source_col", "")
        tgt_hint = override.get("target_col", "")
        wt_hint  = override.get("weight_col") or ""
        # Resolve against actual header names (case-insensitive)
        src = headers_lower.get(src_hint.lower()) if src_hint else None
        tgt = headers_lower.get(tgt_hint.lower()) if tgt_hint else None
        wt  = headers_lower.get(wt_hint.lower())  if wt_hint  else None
        if src and tgt:
            log.debug(f"[CROSSWALK] Config override for {fname}: src={src}, tgt={tgt}, wt={wt}")
            return src, tgt, wt
        log.warning(
            f"[CROSSWALK] Config override for {fname} specified src='{src_hint}', tgt='{tgt_hint}' "
            f"but those columns weren't found in file. Actual headers: {headers}"
        )

    # ── Tier 2: Filename heuristics (narrow candidate list) ───────────────────
    fn_hints_cfg = hints.get("filename_heuristics", {})
    prefer_src: list[str] = []
    prefer_tgt: list[str] = []
    fname_lower = fname.lower()
    for key, fh in fn_hints_cfg.items():
        if key in fname_lower:
            prefer_src = [c.lower() for c in fh.get("prefer_source", [])]
            prefer_tgt = [c.lower() for c in fh.get("prefer_target", [])]
            break

    # ── Tier 3: Alias table (expanded, lowercase + uppercase) ─────────────────
    alias_cfg       = hints.get("column_aliases", {})
    src_candidates  = [c.lower() for c in alias_cfg.get("source_candidates", [])]
    tgt_candidates  = [c.lower() for c in alias_cfg.get("target_candidates", [])]
    wt_candidates   = [c.lower() for c in alias_cfg.get("weight_candidates", [])]

    # If no config loaded at all, use hard-coded defaults (covers both old and new column styles)
    if not src_candidates:
        src_candidates = [
            "block", "mprec", "srprec", "rgprec", "svprec", "rrprec",
            "block20", "mprec_id", "srprec_id", "rgprec_id", "svprec_id",
            "source", "from_id", "src", "source_id",
        ]
    if not tgt_candidates:
        tgt_candidates = [
            "mprec", "srprec", "svprec", "city", "block",
            "mprec_id", "srprec_id", "svprec_id", "block20",
            "target", "to_id", "dst", "dest", "target_id",
        ]
    if not wt_candidates:
        wt_candidates = [
            "pct_block", "pctsrprec", "pctrgprec", "pct_blk", "weight",
            "pct", "fraction", "area_pct", "proportion",
        ]

    def _pick(candidates: list[str], prefer: list[str], exclude: str | None = None) -> str | None:
        """Return first candidate found in headers, trying preferred ones first."""
        prioritised = prefer + [c for c in candidates if c not in prefer]
        for c in prioritised:
            actual = headers_lower.get(c)
            if actual and actual != exclude:
                return actual
        return None

    src = _pick(src_candidates, prefer_src)
    tgt = _pick(tgt_candidates, prefer_tgt, exclude=src)
    wt  = _pick(wt_candidates, [])

    if not src or not tgt:
        log.warning(
            f"[CROSSWALK] Could not detect source/target columns in {fname or '?'}: "
            f"{headers}  (src={src}, tgt={tgt}). "
            f"Add a per_file_hints entry to config/precinct_id/crosswalk_column_hints.yaml to fix this."
        )

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
        src_col, tgt_col, wt_col = detect_crosswalk_columns(headers, filename=str(path))
        if not src_col or not tgt_col:
            _log(
                f"[CROSSWALK] ⚠️  IDENTITY_FALLBACK_USED: Cannot detect source/target columns "
                f"in {path.name}: {headers}\n"
                f"  src_col={src_col!r}, tgt_col={tgt_col!r}\n"
                f"  This means contest precincts will NOT be correctly joined to geometry.\n"
                f"  Fix: add entry under per_file_hints in "
                f"config/precinct_id/crosswalk_column_hints.yaml",
                "WARN",
            )
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
