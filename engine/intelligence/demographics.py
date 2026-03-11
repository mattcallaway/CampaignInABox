"""
engine/intelligence/demographics.py — Prompt 17

Integrate precinct-level demographic data into the intelligence layer.

Accepted inputs (place in data/intelligence/demographics/):
    - Census ACS data CSV
    - Precinct demographic CSV

Expected fields:
    precinct_id (or canonical_precinct_id), median_income, median_age,
    education_level (pct_college_or_higher), homeownership_rate

Output:
    derived/intelligence/precinct_demographics.csv

Provenance: EXTERNAL (census) | ESTIMATED (modeled)
Security: No voter-level data. Precinct aggregates only.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

DEMO_DIR  = Path(__file__).resolve().parent.parent.parent / "data" / "intelligence" / "demographics"
DERIVED   = Path(__file__).resolve().parent.parent.parent / "derived" / "intelligence"

# Normalized output columns
DEMO_COLS = [
    "canonical_precinct_id", "median_income", "median_age",
    "pct_college_or_higher", "homeownership_rate",
    "pct_nonwhite", "pct_under_35", "pct_over_65",
    "source_type", "source_file",
]

_ALIASES = {
    "canonical_precinct_id": ["canonical_precinct_id", "precinct_id", "precinct", "geoid", "fips"],
    "median_income":         ["median_income", "med_income", "income", "median_hh_income"],
    "median_age":            ["median_age", "med_age", "age_median"],
    "pct_college_or_higher": ["pct_college_or_higher", "education_level", "pct_college",
                              "college_pct", "pct_bachelors"],
    "homeownership_rate":    ["homeownership_rate", "owner_occupied", "pct_homeowner"],
    "pct_nonwhite":          ["pct_nonwhite", "pct_minority", "pct_non_white"],
    "pct_under_35":          ["pct_under_35", "pct_young", "pct_youth"],
    "pct_over_65":           ["pct_over_65", "pct_senior", "pct_elderly"],
}


def _normalize(df: pd.DataFrame, source_file: str, source_type: str = "EXTERNAL") -> pd.DataFrame:
    col_lower = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    col_map = {}
    for norm_col, aliases in _ALIASES.items():
        for a in aliases:
            if a in col_lower:
                col_map[col_lower[a]] = norm_col
                break
    df = df.rename(columns=col_map)
    for col in DEMO_COLS:
        if col not in df.columns:
            df[col] = None
    df["source_type"] = source_type
    df["source_file"] = source_file
    # Coerce numerics
    for col in ["median_income", "median_age", "pct_college_or_higher",
                "homeownership_rate", "pct_nonwhite", "pct_under_35", "pct_over_65"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Convert 0–100 percents to 0.0–1.0
    for col in ["pct_college_or_higher", "homeownership_rate",
                "pct_nonwhite", "pct_under_35", "pct_over_65"]:
        if df[col].dropna().max() > 1.5:
            df[col] = df[col] / 100.0
    return df[DEMO_COLS].dropna(subset=["canonical_precinct_id"])


def load_demographics(logger=None) -> pd.DataFrame:
    """
    Scan data/intelligence/demographics/, ingest all CSV/XLSX files.
    Writes derived/intelligence/precinct_demographics.csv.
    Returns combined DataFrame.
    """
    _log = logger or log
    DERIVED.mkdir(parents=True, exist_ok=True)
    out_path = DERIVED / "precinct_demographics.csv"

    dfs = []
    for path in sorted(DEMO_DIR.glob("*")):
        if path.name.startswith(".") or ".gitkeep" in path.name:
            continue
        try:
            raw = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
            df = _normalize(raw, path.name)
            if not df.empty:
                dfs.append(df)
                _log.info(f"[DEMO] Loaded {len(df)} precincts from {path.name}")
        except Exception as e:
            _log.warning(f"[DEMO] Could not parse {path.name}: {e}")

    if not dfs:
        _log.info("[DEMO] No demographic files found — returning empty")
        empty = pd.DataFrame(columns=DEMO_COLS)
        empty.to_csv(out_path, index=False)
        return empty

    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["canonical_precinct_id"], keep="first")
    combined.to_csv(out_path, index=False)
    _log.info(f"[DEMO] Wrote {len(combined)} precinct demographics → {out_path.name}")
    return combined


def compute_demographic_signal(demo_df: pd.DataFrame, precinct_model: pd.DataFrame) -> dict:
    """
    Compute aggregate demographic signal for intelligence fusion.

    Returns dict with:
        has_demographics: bool
        avg_education:    float (pct college+)
        avg_income:       float (median $)
        pct_high_income:  float (>= $75k precincts)
        education_adjustment: float (-0.05 to +0.05 relative support adjustment)
    """
    if demo_df.empty:
        return {
            "has_demographics": False,
            "avg_education": None,
            "avg_income": None,
            "pct_high_income": None,
            "education_adjustment": 0.0,
            "source_type": "MISSING",
        }

    # Merge with precinct model to weight by voter pool size
    if not precinct_model.empty and "canonical_precinct_id" in precinct_model.columns:
        merged = demo_df.merge(
            precinct_model[["canonical_precinct_id", "registered"]],
            on="canonical_precinct_id", how="left",
        )
        merged["registered"] = merged["registered"].fillna(1)
    else:
        merged = demo_df.copy()
        merged["registered"] = 1

    weights = merged["registered"].values

    avg_edu    = float(np.average(merged["pct_college_or_higher"].fillna(0), weights=weights))
    avg_income = float(np.average(merged["median_income"].fillna(50000), weights=weights))
    pct_high   = float((merged["median_income"] >= 75000).mean())

    # Simple heuristic: more educated precincts tend slightly more favorable
    # to ballot measures and reform candidates (campaign-context-dependent)
    # This is a signal contribution, not a causal claim
    edu_adj = round((avg_edu - 0.30) * 0.05, 5)  # centered around 30% college rate

    return {
        "has_demographics": True,
        "avg_education": round(avg_edu, 4),
        "avg_income": round(avg_income, 0),
        "pct_high_income": round(pct_high, 4),
        "education_adjustment": edu_adj,
        "source_type": "EXTERNAL",
    }


def load_demographics_derived() -> pd.DataFrame:
    path = DERIVED / "precinct_demographics.csv"
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            pass
    return pd.DataFrame()
