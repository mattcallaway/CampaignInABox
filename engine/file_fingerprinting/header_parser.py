"""
engine/file_fingerprinting/header_parser.py — Prompt 25A.3

Spreadsheet header extraction and normalization.

Responsibilities:
- Open spreadsheet safely (xlsx, xls, csv, tsv)
- Scan first 15 rows to find the header row
- Extract and normalize column headers
- Detect numeric column patterns
- Detect precinct ID patterns in first column
- Return ParsedHeader dataclass
"""
from __future__ import annotations

import hashlib
import logging
import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Regex patterns for precinct ID detection
PRECINCT_PATTERNS = [
    re.compile(r"^\d{4,7}$"),           # 4-7 digit numeric  (e.g. 040001)
    re.compile(r"^\d{4}[A-Z]\d*$"),     # alphanumeric SRPREC (e.g. 0400A1)
    re.compile(r"^[A-Z]{2}\d{3,}$"),    # state-prefix (e.g. CA00401)
    re.compile(r"^\d{2,3}-\d{2,4}$"),   # dash-separated (e.g. 04-0001)
]

SCAN_ROWS = 15    # number of rows to scan for header detection
SAMPLE_ROWS = 50  # rows to sample for numeric/precinct pattern detection


@dataclass
class ParsedHeader:
    """Result of parsing a spreadsheet file's headers and structure."""
    file_path: str
    file_hash: str
    raw_headers: list[str]
    normalized_headers: list[str]
    header_row_index: int
    numeric_columns: list[str]       # column names that are predominantly numeric
    precinct_column: Optional[str]   # name of likely precinct ID column
    precinct_format: Optional[str]   # detected format pattern  e.g. "0400***"
    precinct_sample: list[str]       # sample precinct IDs found
    row_count: int
    col_count: int
    parse_error: Optional[str] = None
    sheet_name: Optional[str] = None


def _normalize_header(h: str) -> str:
    """Normalize a header string: lowercase, strip punctuation, collapse whitespace."""
    if not isinstance(h, str):
        h = str(h) if h is not None else ""
    # Remove punctuation except spaces and alphanumeric
    h = re.sub(r"[^\w\s]", " ", h.lower())
    h = re.sub(r"\s+", " ", h).strip()
    return h


def _file_hash(path: Path, chunk_size: int = 65536) -> str:
    """MD5 hash of the first 64KB of a file (fast, for caching)."""
    md5 = hashlib.md5()
    try:
        with open(path, "rb") as f:
            md5.update(f.read(chunk_size))
    except Exception:
        return "unknown"
    return md5.hexdigest()


def _detect_precinct_format(samples: list[str]) -> Optional[str]:
    """Infer a format pattern string from sample precinct IDs."""
    if not samples:
        return None
    # Use first valid sample as template, replace digits with *
    s = samples[0]
    pattern = re.sub(r"\d", "*", s)
    return pattern


def parse_spreadsheet_headers(file_path: str | Path, sheet_index: int = 0) -> ParsedHeader:
    """
    Parse a spreadsheet file and extract normalized headers and structural metadata.

    Handles:
    - .xlsx / .xls via openpyxl/xlrd through pandas
    - .csv / .tsv via pandas
    - Multi-row preambles (scans first SCAN_ROWS rows to find the header row)

    Returns ParsedHeader. Never raises.
    """
    path = Path(file_path)
    fhash = _file_hash(path)
    ext = path.suffix.lower()

    try:
        import pandas as pd

        # ── Load raw rows ──────────────────────────────────────────────────
        if ext in (".xlsx", ".xls"):
            try:
                # Read without header to inspect all rows
                raw = pd.read_excel(
                    path,
                    sheet_name=sheet_index,
                    header=None,
                    nrows=SCAN_ROWS + SAMPLE_ROWS,
                    dtype=str,
                )
                sheet_name = str(sheet_index)
                try:
                    xl = pd.ExcelFile(path)
                    sheets = xl.sheet_names
                    sheet_name = sheets[sheet_index] if sheet_index < len(sheets) else str(sheet_index)
                except Exception:
                    pass
            except Exception as e:
                # Try sheet 0 by name
                raw = pd.read_excel(path, header=None, nrows=SCAN_ROWS + SAMPLE_ROWS, dtype=str)
                sheet_name = None
        elif ext == ".csv":
            raw = pd.read_csv(path, header=None, nrows=SCAN_ROWS + SAMPLE_ROWS, dtype=str)
            sheet_name = None
        elif ext == ".tsv":
            raw = pd.read_csv(path, sep="\t", header=None, nrows=SCAN_ROWS + SAMPLE_ROWS, dtype=str)
            sheet_name = None
        else:
            return ParsedHeader(
                file_path=str(path), file_hash=fhash,
                raw_headers=[], normalized_headers=[], header_row_index=-1,
                numeric_columns=[], precinct_column=None, precinct_format=None,
                precinct_sample=[], row_count=0, col_count=0,
                parse_error=f"Unsupported file type: {ext}", sheet_name=None,
            )

        # ── Find header row ────────────────────────────────────────────────
        scan = raw.iloc[:min(SCAN_ROWS, len(raw))]
        header_row_idx = 0
        best_score = 0

        for i, row in scan.iterrows():
            vals = [v for v in row.values if isinstance(v, str) and v.strip()]
            # Score: how many cells look like column headers (non-numeric strings)
            score = sum(1 for v in vals if not re.match(r"^\d+\.?\d*$", v.strip()))
            if score > best_score:
                best_score = score
                header_row_idx = int(i)  # type: ignore[arg-type]

        # Re-read with detected header row
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(path, sheet_name=sheet_index, header=header_row_idx,
                               nrows=SAMPLE_ROWS, dtype=str)
        elif ext == ".csv":
            df = pd.read_csv(path, header=header_row_idx, nrows=SAMPLE_ROWS, dtype=str)
        else:
            df = pd.read_csv(path, sep="\t", header=header_row_idx, nrows=SAMPLE_ROWS, dtype=str)

        raw_headers = [str(c) for c in df.columns]
        normalized_headers = [_normalize_header(h) for h in raw_headers]

        # ── Numeric column detection ───────────────────────────────────────
        numeric_cols: list[str] = []
        for col in df.columns:
            col_data = df[col].dropna()
            if len(col_data) == 0:
                continue
            numeric_count = sum(1 for v in col_data if re.match(r"^\d+\.?\d*$", str(v).strip()))
            if numeric_count / len(col_data) >= 0.7:
                numeric_cols.append(str(col))

        # ── Precinct ID detection ──────────────────────────────────────────
        precinct_col: Optional[str] = None
        precinct_samples: list[str] = []
        precinct_format: Optional[str] = None

        # Check first few columns for precinct IDs
        for col in df.columns[:4]:
            samples = df[col].dropna().astype(str).head(20).tolist()
            matched = [v.strip() for v in samples
                       if any(p.match(v.strip()) for p in PRECINCT_PATTERNS)]
            if len(matched) >= 3:
                precinct_col = str(col)
                precinct_samples = matched[:5]
                precinct_format = _detect_precinct_format(matched)
                break

        return ParsedHeader(
            file_path=str(path),
            file_hash=fhash,
            raw_headers=raw_headers,
            normalized_headers=normalized_headers,
            header_row_index=header_row_idx,
            numeric_columns=numeric_cols,
            precinct_column=precinct_col,
            precinct_format=precinct_format,
            precinct_sample=precinct_samples,
            row_count=len(df),
            col_count=len(df.columns),
            parse_error=None,
            sheet_name=sheet_name,
        )

    except Exception as e:
        log.error(f"[HEADER_PARSER] Failed to parse {path}: {e}")
        return ParsedHeader(
            file_path=str(path), file_hash=fhash,
            raw_headers=[], normalized_headers=[], header_row_index=-1,
            numeric_columns=[], precinct_column=None, precinct_format=None,
            precinct_sample=[], row_count=0, col_count=0,
            parse_error=str(e), sheet_name=None,
        )
