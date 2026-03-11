"""
engine/intelligence/polling_ingest.py — Prompt 17

Ingest polling data files into a normalized format.

Accepted formats: CSV, XLSX, JSON
Expected fields:
    pollster, field_date_start, field_date_end, sample_size,
    population, support_percent, oppose_percent, undecided_percent, geography

Output:
    derived/intelligence/polling_normalized.csv

Provenance tag: EXTERNAL (if real poll) or SIMULATED (if synthetic)

Security: No voter-level data. Aggregate poll data only.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

POLLING_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "intelligence" / "polling"
DERIVED_DIR = Path(__file__).resolve().parent.parent.parent / "derived" / "intelligence"

# Normalized output columns
NORM_COLS = [
    "pollster", "field_date_start", "field_date_end", "sample_size",
    "population", "support_percent", "oppose_percent", "undecided_percent",
    "geography", "source_type", "ingested_at",
]

# Column aliases to try for normalization
_ALIASES = {
    "pollster":         ["pollster", "firm", "organization", "org"],
    "field_date_start": ["field_date_start", "start_date", "date_start", "date"],
    "field_date_end":   ["field_date_end", "end_date", "date_end"],
    "sample_size":      ["sample_size", "n", "sample", "respondents"],
    "population":       ["population", "lv", "rv", "adults", "likely_voters", "registered_voters"],
    "support_percent":  ["support_percent", "yes_pct", "yes", "support", "favorable", "approve"],
    "oppose_percent":   ["oppose_percent", "no_pct", "no", "oppose", "unfavorable", "disapprove"],
    "undecided_percent":["undecided_percent", "undecided", "dontknow", "dk"],
    "geography":        ["geography", "region", "county", "district", "area"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map raw column names to normalized names via alias lookup."""
    col_map = {}
    df_lower_cols = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    for norm_col, aliases in _ALIASES.items():
        for alias in aliases:
            if alias in df_lower_cols:
                col_map[df_lower_cols[alias]] = norm_col
                break
    df = df.rename(columns=col_map)
    # Add missing columns as None
    for col in NORM_COLS:
        if col not in df.columns:
            df[col] = None
    return df[NORM_COLS]


def _parse_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _parse_xlsx(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, engine="openpyxl")


def _parse_json(path: Path) -> pd.DataFrame:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return pd.DataFrame(data)
    elif isinstance(data, dict) and "polls" in data:
        return pd.DataFrame(data["polls"])
    return pd.DataFrame([data])


def ingest_polling_file(path: Path, source_type: str = "EXTERNAL") -> Optional[pd.DataFrame]:
    """
    Ingest a single polling file. Returns normalized DataFrame or None.
    source_type: 'EXTERNAL' | 'SIMULATED'
    """
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            raw = _parse_csv(path)
        elif suffix in (".xlsx", ".xls"):
            raw = _parse_xlsx(path)
        elif suffix == ".json":
            raw = _parse_json(path)
        else:
            log.warning(f"[POLLING] Unsupported format: {path.suffix}")
            return None
    except Exception as e:
        log.warning(f"[POLLING] Could not parse {path.name}: {e}")
        return None

    df = _normalize_columns(raw)
    df["source_type"] = source_type
    df["ingested_at"] = datetime.utcnow().isoformat()

    # Numeric coercion
    for col in ["sample_size", "support_percent", "oppose_percent", "undecided_percent"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Convert percents if they look like 0–100 scale (not 0.0–1.0)
    for col in ["support_percent", "oppose_percent", "undecided_percent"]:
        if df[col].dropna().max() > 1.5:
            df[col] = df[col] / 100.0

    log.info(f"[POLLING] Ingested {len(df)} polls from {path.name}")
    return df


def ingest_all_polling(logger=None) -> pd.DataFrame:
    """
    Scan data/intelligence/polling/ and ingest all supported files.
    Returns combined normalized DataFrame.
    Writes derived/intelligence/polling_normalized.csv.
    """
    _log = logger or log
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DERIVED_DIR / "polling_normalized.csv"

    all_dfs = []
    for path in sorted(POLLING_DIR.glob("*")):
        if path.name.startswith(".") or path.name.endswith(".gitkeep"):
            continue
        if path.suffix.lower() in (".csv", ".xlsx", ".xls", ".json"):
            df = ingest_polling_file(path)
            if df is not None and not df.empty:
                df["source_file"] = path.name
                all_dfs.append(df)

    if not all_dfs:
        _log.info("[POLLING] No polling files found — returning empty DataFrame")
        empty = pd.DataFrame(columns=NORM_COLS + ["source_file"])
        empty.to_csv(out_path, index=False)
        return empty

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values("field_date_start", ascending=False, na_position="last")
    combined.to_csv(out_path, index=False)
    _log.info(f"[POLLING] Wrote {len(combined)} polls → {out_path.name}")
    return combined


def load_polling_normalized() -> pd.DataFrame:
    """Load the normalized polling CSV if it exists."""
    path = DERIVED_DIR / "polling_normalized.csv"
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            pass
    return pd.DataFrame()
