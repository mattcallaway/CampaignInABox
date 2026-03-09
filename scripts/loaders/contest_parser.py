"""
scripts/loaders/contest_parser.py

Agnostic Excel workbook parser for election results.
Supports: 
  - Mandatory contestant/sheet discovery rules.
  - Automatic contest type detection (ballot_measure vs candidate_race).
  - Standardized long-format output.
  - Optional registration sheet extraction.
"""

import re
import json
import pandas as pd
from pathlib import Path
from typing import Any, Iterator
import openpyxl

from .file_loader import load_excel_workbook, iter_excel_sheets
from .contest_registry import detect_contest_type
from ..lib.naming import normalize_precinct_id

# Column Alias Sets
PRECINCT_COL_ALIASES = {
    "precinct", "precinct_id", "mprec_id", "srprec_id", "prec_id",
    "precinct id", "masterprecinctid", "precinct name", "voter precinct", "precinct_name"
}

REGISTRATION_COL_ALIASES = {
    "registered", "registration", "reg", "registered voters", "total registered", "voters"
}

BALLOTS_COL_ALIASES = {
    "ballots cast", "total ballots", "ballots", "votes cast", "total votes", "ballots_cast"
}

VOTE_METHOD_COLS = {
    "mail", "mail ballot", "vote by mail", "vbm", "absentee",
    "in person", "election day", "early voting", "early",
    "provisional", "precinct", "poll"
}

TOTAL_COL_ALIASES = {"total", "totals", "grand total", "total votes"}

NOISE_SHEETS = {
    "table of contents", "toc", "index", "summary", "registered voters", 
    "voter turnout", "turnout", "precincts", "crosswalk"
}

def is_contest_sheet(sheet_name: str, rows: list[list]) -> bool:
    """
    Discovery rules: Numeric sheets or match contest patterns.
    Exclude known noise sheets.
    """
    name_clean = sheet_name.strip().lower()
    if name_clean in NOISE_SHEETS:
        return False
    
    # Sheet name is numeric
    if re.match(r'^\d+$', name_clean):
        return True
    
    # Heuristic: Check if sheet has data rows that look like a contest
    if len(rows) < 3:
        return False
        
    return True

def discover_contests(workbook_path: Path) -> list[str]:
    """Return names of sheets identified as contests."""
    wb = load_excel_workbook(workbook_path)
    contests = []
    for name, rows in iter_excel_sheets(wb):
        if is_contest_sheet(name, rows):
            contests.append(name)
    return contests

def extract_registered_voters(workbook_path: Path) -> dict[str, int]:
    """
    Look for a 'Registered Voters' sheet and extract per-precinct counts.
    Returns {precinct_id: registered_count}.
    """
    wb = load_excel_workbook(workbook_path)
    reg_data = {}
    
    target_names = ["registered voters", "turnout", "registered", "voters"]
    target_sheet = None
    for name in wb.sheetnames:
        if name.strip().lower() in target_names:
            target_sheet = name
            break
            
    if not target_sheet:
        return {}
        
    ws = wb[target_sheet]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    
    # Find header row
    header_idx = 0
    for i, row in enumerate(rows):
        if any(str(c).lower() in PRECINCT_COL_ALIASES for c in row if c):
            header_idx = i
            break
            
    headers = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    df = pd.DataFrame(rows[header_idx+1:], columns=headers)
    
    prec_col = None
    for h in headers:
        if h.lower() in PRECINCT_COL_ALIASES:
            prec_col = h
            break
            
    reg_col = None
    for h in headers:
        if h.lower() in REGISTRATION_COL_ALIASES:
            reg_col = h
            break
            
    if not prec_col or not reg_col:
        return {}
        
    for _, row in df.iterrows():
        p_raw = str(row[prec_col]).strip()
        if not p_raw or p_raw.lower().startswith("total"):
            continue
        try:
            p_id = normalize_precinct_id(p_raw, pad_to=0)
            val = int(row[reg_col])
            reg_data[p_id] = val
        except (ValueError, TypeError):
            continue
            
    return reg_data

def parse_contest_sheet(sheet_name: str, rows: list[list], logger=None) -> dict[str, Any]:
    """
    Standardized parsing for a contest sheet.
    Handles both simple (1-row) and compound (2-row) headers.

    Compound header example (CA election format):
      Row N  :   [Precinct] [Registered Voters] [YES         ...] [NO          ...]  [Total]
      Row N+1:   [Precinct] [Registered Voters] [Elec Day] [VBM] [Total Votes] [Elec Day] [VBM] [Total Votes] [Total]
    In this case YES/NO labels sit one row above the column-name row.
    """
    def _log(msg):
        if logger:
            logger.info(msg)

    # 1. Title Extraction (top rows)
    title = sheet_name
    for row in rows[:5]:
        non_null = [str(c).strip() for c in row if c is not None and str(c).strip()]
        if len(non_null) == 1:
            title = non_null[0]
            break

    # 2. Find the column-header row — first row with >= 3 non-null values
    header_idx = 0
    for i, row in enumerate(rows):
        non_null = [c for c in row if c is not None and str(c).strip()]
        if len(non_null) >= 3:
            header_idx = i
            break

    # 3. Check for compound header: row directly above the header row may carry YES/NO labels
    label_row = rows[header_idx - 1] if header_idx > 0 else []
    candidate_labels = {}   # col_index -> label string (e.g. "YES", "NO", "JOHN SMITH")
    for idx, cell in enumerate(label_row):
        if cell is not None and str(cell).strip():
            candidate_labels[idx] = str(cell).strip()

    has_compound_header = bool(candidate_labels)

    # 4. Build column names from the header row
    header_cells = rows[header_idx]
    raw_headers = [str(c).strip() if c is not None else "" for c in header_cells]

    # 5. In compound-header mode, build disambiguated column names
    #    by prepending the candidate label to duplicate column names
    if has_compound_header:
        # Forward-fill labels across columns: label spans until the next label
        active_label = ""
        col_labels = []
        for idx in range(len(raw_headers)):
            if idx in candidate_labels:
                active_label = candidate_labels[idx]
            col_labels.append(active_label)

        # Build disambiguated headers
        seen: dict[str, int] = {}
        headers = []
        for idx, h in enumerate(raw_headers):
            label = col_labels[idx]
            if h.lower() in {"election day", "vote by mail", "total votes"} and label:
                col_name = f"{label}__{h}"
            else:
                col_name = h if h else f"unnamed_{idx}"
            # De-duplicate
            if col_name in seen:
                seen[col_name] += 1
                col_name = f"{col_name}_{seen[col_name]}"
            else:
                seen[col_name] = 0
            headers.append(col_name)
    else:
        seen: dict[str, int] = {}
        headers = []
        for idx, h in enumerate(raw_headers):
            col_name = h if h else f"unnamed_{idx}"
            if col_name in seen:
                seen[col_name] += 1
                col_name = f"{col_name}_{seen[col_name]}"
            else:
                seen[col_name] = 0
            headers.append(col_name)

    # 6. Build DataFrame from data rows
    df = pd.DataFrame(rows[header_idx + 1:], columns=headers)
    df = df.dropna(how="all").reset_index(drop=True)

    # 7. Identify key columns
    prec_col = next((h for h in headers if h.lower() in PRECINCT_COL_ALIASES), None)
    if not prec_col:
        # Fallback: first column whose values look like precinct IDs
        prec_col = headers[0] if headers else None

    # For compound-header ballot measures extract YES_Total Votes / NO_Total Votes
    yes_col = no_col = None
    if has_compound_header:
        # Look for YES__Total Votes and NO__Total Votes (case-insensitive)
        for h in headers:
            hl = h.lower()
            if "yes" in hl and "total votes" in hl:
                yes_col = h
            elif "no" in hl and "total votes" in hl:
                no_col = h

        if yes_col and yes_col in df.columns:
            df["yes_votes"] = pd.to_numeric(df[yes_col], errors="coerce").fillna(0).astype(int)
        if no_col and no_col in df.columns:
            df["no_votes"] = pd.to_numeric(df[no_col], errors="coerce").fillna(0).astype(int)

        # Registered Voters
        reg_col = next((h for h in headers if "registered" in h.lower() and "__" not in h), None)
        if reg_col and reg_col in df.columns:
            df["Registered"] = pd.to_numeric(df[reg_col], errors="coerce").fillna(0).astype(int)

        # Total ballots cast — "Total" column
        total_col = next((h for h in headers if h.lower() == "total"), None)
        if total_col and total_col in df.columns:
            df["BallotsCast"] = pd.to_numeric(df[total_col], errors="coerce").fillna(0).astype(int)

    # 8. Determine contest type
    type_guess = detect_contest_type(headers)
    if yes_col or no_col:
        type_guess = "ballot_measure"

    # 9. Choice columns
    if yes_col or no_col:
        # Compound ballot-measure: use synthesized columns
        choice_cols = [c for c in ["yes_votes", "no_votes"] if c in df.columns]
    else:
        meta = (PRECINCT_COL_ALIASES | REGISTRATION_COL_ALIASES | BALLOTS_COL_ALIASES
                | VOTE_METHOD_COLS | TOTAL_COL_ALIASES | {"District", "Precinct Name", ""})
        choice_cols = [h for h in headers if h.lower() not in meta and h and not h.startswith("unnamed_")]
        if type_guess == "ballot_measure":
            choice_cols = [h for h in choice_cols if h.upper() in ("YES", "NO", "YES VOTES", "NO VOTES")]

    _log(f"  parse_contest_sheet: title={title!r} type={type_guess} "
         f"prec_col={prec_col!r} choice_cols={choice_cols} rows={len(df)}")

    # Determine actual total_col name (non-disambiguated)
    total_col_name = next((h for h in headers if h.lower() == "total"), None)

    return {
        "contest_title": title,
        "sheet_name": sheet_name,
        "contest_type": type_guess,
        "df": df,
        "prec_col": prec_col,
        "total_col": total_col_name,
        "choice_cols": choice_cols,
        "headers": headers,
        "has_compound_header": has_compound_header,
    }


def extract_long_results(parsed: dict, meta: dict, logger=None) -> pd.DataFrame:
    """
    Standardizes parsed contest into 'results_long.csv' format.
    Schema: contest_id, contest_title, contest_type, state, county_name, county_fips, 
            precinct_raw, precinct_norm, choice, votes_total, votes_by_method_json
    """
    df = parsed["df"]
    prec_col = parsed["prec_col"]
    choice_cols = parsed["choice_cols"]
    
    if not prec_col:
        # Fallback to first column
        prec_col = df.columns[0]
        
    rows = []
    for _, row in df.iterrows():
        p_raw = str(row[prec_col]).strip()
        if not p_raw or p_raw.lower().startswith("total"):
            continue
            
        p_norm = normalize_precinct_id(p_raw, pad_to=0)
        
        for choice in choice_cols:
            val_raw = row[choice]
            try:
                votes = int(pd.to_numeric(val_raw, errors="coerce") or 0)
            except:
                votes = 0
                
            entry = {
                "contest_id": meta.get("contest_id", "FIXME"),
                "contest_title": parsed["contest_title"],
                "contest_type": parsed["contest_type"],
                "state": meta.get("state", "CA"),
                "county_name": meta.get("county_name", "Unknown"),
                "county_fips": meta.get("county_fips", "000"),
                "precinct_raw": p_raw,
                "precinct_norm": p_norm,
                "choice": choice,
                "votes_total": votes,
                "votes_by_method_json": None, # Future: implement if needed
                "parse_notes": ""
            }
            rows.append(entry)
            
    return pd.DataFrame(rows)
