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
    Determines contest_title, precinct_id col, and choice cols.
    """
    # 1. Title Extraction (top rows)
    title = sheet_name
    for row in rows[:5]:
        non_null = [str(c).strip() for c in row if c is not None and str(c).strip()]
        if len(non_null) == 1:
            title = non_null[0]
            break
            
    # 2. Header Row Discovery
    header_idx = 0
    for i, row in enumerate(rows):
        non_null = [c for c in row if c is not None and str(c).strip()]
        if len(non_null) >= 3:
            header_idx = i
            break
            
    headers = [str(c).strip() if c is not None else f"unnamed_{i}" for i, c in enumerate(rows[header_idx])]
    df = pd.DataFrame(rows[header_idx+1:], columns=headers)
    df = df.dropna(how="all").reset_index(drop=True)
    
    # 3. Column Identification
    prec_col = next((h for h in headers if h.lower() in PRECINCT_COL_ALIASES), None)
    total_col = next((h for h in headers if h.lower() in TOTAL_COL_ALIASES), None)
    
    # Detect contest type
    type_guess = detect_contest_type(headers)
    
    # Identify choice columns (those that aren't meta data or vote methods)
    meta = PRECINCT_COL_ALIASES | REGISTRATION_COL_ALIASES | BALLOTS_COL_ALIASES | VOTE_METHOD_COLS | TOTAL_COL_ALIASES | {"District", "Precinct Name", ""}
    choice_cols = [h for h in headers if h.lower() not in meta and h and not h.startswith("unnamed_")]
    
    # Special case: Ballot Measures (YES/NO)
    if type_guess == "ballot_measure":
        choice_cols = [h for h in choice_cols if h.upper() in ("YES", "NO", "YES VOTES", "NO VOTES")]

    return {
        "contest_title": title,
        "sheet_name": sheet_name,
        "contest_type": type_guess,
        "df": df,
        "prec_col": prec_col,
        "total_col": total_col,
        "choice_cols": choice_cols,
        "headers": headers
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
