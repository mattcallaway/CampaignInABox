"""
engine/voters/voter_parser.py — Prompt 11

Voter file ingestion and normalization.

Responsibilities:
  - Auto-detect column schema from voter_schema.yaml aliases
  - Normalize precinct IDs → canonical_precinct_id via crosswalk
  - Parse vote history columns → participation count
  - Strip PII columns from any committed output
  - Compress to Parquet for fast downstream joins

Security: output Parquet is in derived/voter_models/ which is .gitignored.
Never includes voter_id, name, address, or any individual PII.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCHEMA_CONFIG = BASE_DIR / "config" / "voter_schema.yaml"
CROSSWALK_DIR = BASE_DIR / "data" / "CA" / "counties" / "Sonoma" / "geography" / "crosswalks"

log = logging.getLogger(__name__)


# ── Schema Loading ─────────────────────────────────────────────────────────────

def _load_schema() -> dict:
    if SCHEMA_CONFIG.exists():
        with open(SCHEMA_CONFIG, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def _match_alias(columns: list[str], aliases: list[str]) -> Optional[str]:
    """Return the first column that matches any alias (case-insensitive)."""
    col_lower = {c.lower(): c for c in columns}
    for alias in aliases:
        if alias.lower() in col_lower:
            return col_lower[alias.lower()]
    return None


# ── Column Detection ──────────────────────────────────────────────────────────

def detect_schema(df: pd.DataFrame, schema: dict) -> dict:
    """
    Auto-detect canonical column mappings from raw voter file columns.

    Returns a mapping dict: canonical_name -> raw_column_name
    """
    cols = list(df.columns)
    mapping = {}

    for field, key in [
        ("voter_id", "voter_id_aliases"),
        ("precinct", "precinct_aliases"),
        ("party", "party_aliases"),
        ("age", "age_aliases"),
        ("gender", "gender_aliases"),
        ("ethnicity", "ethnicity_aliases"),
        ("language", "language_aliases"),
        ("mail_ballot_status", "mail_ballot_aliases"),
    ]:
        aliases = schema.get(key, [])
        found = _match_alias(cols, aliases)
        if found:
            mapping[field] = found
        else:
            log.debug(f"[VOTER_PARSER] No column found for '{field}' — skipped")

    # Detect vote history columns (prefix-based)
    vh_prefixes = schema.get("vote_history_prefixes", ["vote_history_", "VH_", "vh_"])
    history_cols = [c for c in cols if any(c.startswith(p) or c.lower().startswith(p.lower())
                                           for p in vh_prefixes)]
    mapping["vote_history_cols"] = history_cols

    log.info(f"[VOTER_PARSER] Detected {len(mapping)-1} standard fields, "
             f"{len(history_cols)} vote history columns")
    return mapping


# ── Precinct Normalization ────────────────────────────────────────────────────

def _load_precinct_crosswalk() -> dict:
    """
    Build srprec → canonical_precinct_id (mprec) lookup.
    Falls back to identity mapping if crosswalk not found.
    """
    cw_path = CROSSWALK_DIR / "mprec_srprec_097_g24.csv"
    if not cw_path.exists():
        log.warning("[VOTER_PARSER] mprec_srprec crosswalk not found — using identity mapping")
        return {}

    cw = pd.read_csv(cw_path, dtype=str)
    # mprec_srprec has mprec -> srprec; invert to srprec -> mprec
    # Take first mprec for each srprec
    cw = cw.drop_duplicates("srprec")
    lookup = dict(zip(
        cw["srprec"].str.strip().str.lstrip("0"),
        cw["mprec"].str.strip().str.lstrip("0"),
    ))
    log.info(f"[VOTER_PARSER] Loaded precinct crosswalk: {len(lookup)} SRPREC → MPREC entries")
    return lookup


def normalize_precinct_ids(df: pd.DataFrame, precinct_col: str) -> pd.DataFrame:
    """
    Map voter precinct IDs → canonical_precinct_id (MPREC, lstripped of leading zeros).
    """
    lookup = _load_precinct_crosswalk()
    raw = df[precinct_col].astype(str).str.strip().str.lstrip("0")

    if lookup:
        mapped = raw.map(lookup)
        match_rate = mapped.notna().mean()
        log.info(f"[VOTER_PARSER] Precinct match rate: {match_rate:.1%} "
                 f"({mapped.notna().sum():,}/{len(mapped):,} voters)")
        # Fill unmatched with the raw value (identity fallback for direct MPREC IDs)
        df = df.copy()
        df["canonical_precinct_id"] = mapped.fillna(raw)
    else:
        df = df.copy()
        df["canonical_precinct_id"] = raw
        log.info("[VOTER_PARSER] Using identity precinct mapping (no crosswalk)")

    return df


# ── Vote History Parsing ──────────────────────────────────────────────────────

def parse_vote_history(df: pd.DataFrame, history_cols: list[str]) -> pd.DataFrame:
    """
    Parse vote history participation columns into:
      - elections_participated: count of elections voter participated in
      - most_recent_election: latest election year they voted in
      - propensity_score: 0-1 fraction of available elections where they voted
    """
    df = df.copy()

    if not history_cols:
        log.info("[VOTER_PARSER] No vote history columns found — propensity will be null")
        df["elections_participated"] = None
        df["propensity_score"] = None
        return df

    # History columns are typically binary (1=voted, 0/NaN=did not)
    hist = df[history_cols].copy()

    # Coerce to numeric: 'Y', 'YES', '1' → 1; everything else → 0
    def _to_flag(series: pd.Series) -> pd.Series:
        s = series.astype(str).str.upper().str.strip()
        return s.isin(["1", "Y", "YES", "X", "V", "TRUE"]).astype(int)

    hist_numeric = hist.apply(_to_flag)

    df["elections_participated"] = hist_numeric.sum(axis=1)
    df["propensity_score"] = df["elections_participated"] / len(history_cols)

    # Try to extract year from column names for most_recent_election
    years = []
    for c in history_cols:
        for token in c.replace("_", " ").split():
            if token.isdigit() and 2000 <= int(token) <= 2030:
                years.append((int(token), c))
    if years:
        most_recent_col = max(years, key=lambda x: x[0])[1]
        df["most_recent_election"] = hist_numeric[most_recent_col].apply(
            lambda v: max(years, key=lambda x: x[0])[0] if v == 1 else None
        )
    else:
        df["most_recent_election"] = None

    log.info(f"[VOTER_PARSER] Vote history parsed: "
             f"avg {df['elections_participated'].mean():.1f} of {len(history_cols)} elections")
    return df


# ── Party Normalization ────────────────────────────────────────────────────────

def normalize_party(df: pd.DataFrame, party_col: str, schema: dict) -> pd.DataFrame:
    """Normalize party labels to single-letter codes (D, R, N, L, G, A, O)."""
    party_map = schema.get("party_map", {})
    df = df.copy()
    df["party_normalized"] = (
        df[party_col].astype(str).str.strip()
        .map(lambda v: party_map.get(v, v[0].upper() if v else "O"))
    )
    return df


# ── PII Stripping ─────────────────────────────────────────────────────────────

def strip_pii(df: pd.DataFrame, schema: dict, keep_voter_id: bool = False) -> pd.DataFrame:
    """Remove PII columns from DataFrame before any aggregation output."""
    exclude = set(schema.get("address_columns_exclude", []))
    if not keep_voter_id:
        exclude.update(schema.get("voter_id_aliases", []))

    to_drop = [c for c in df.columns if c in exclude or c.lower() in {e.lower() for e in exclude}]
    if to_drop:
        log.debug(f"[VOTER_PARSER] Stripping PII columns: {to_drop}")
    return df.drop(columns=to_drop, errors="ignore")


# ── Main Ingestion Function ───────────────────────────────────────────────────

def ingest_voter_file(
    filepath: Path,
    run_id: str,
    county: str = "Sonoma",
    state: str = "CA",
    logger=None,
) -> Optional[pd.DataFrame]:
    """
    Full voter file ingestion pipeline.

    Returns a normalized DataFrame (voter-level, PII stripped except voter_id for join key)
    or None if the file cannot be loaded.

    Writes:
      derived/voter_models/<run_id>__voter_base.parquet   (local only, .gitignored)
    """
    _log = logger or log

    if not filepath.exists():
        _log.info(f"[VOTER_PARSER] No voter file at {filepath} — skipping")
        return None

    _log.info(f"[VOTER_PARSER] Loading voter file: {filepath} ({filepath.stat().st_size:,} bytes)")

    # ── Load ──────────────────────────────────────────────────────────────────
    ext = filepath.suffix.lower()
    try:
        if ext == ".parquet":
            df = pd.read_parquet(filepath)
        elif ext in (".tsv", ".txt"):
            df = pd.read_csv(filepath, sep="\t", dtype=str, low_memory=False)
        else:  # .csv default
            df = pd.read_csv(filepath, dtype=str, low_memory=False)
    except Exception as e:
        _log.warning(f"[VOTER_PARSER] Failed to load voter file: {e}")
        return None

    _log.info(f"[VOTER_PARSER] Loaded {len(df):,} voters, {len(df.columns)} columns")

    # ── Schema detection ──────────────────────────────────────────────────────
    schema = _load_schema()
    col_map = detect_schema(df, schema)

    # ── Precinct normalization ────────────────────────────────────────────────
    precinct_col = col_map.get("precinct")
    if precinct_col:
        df = normalize_precinct_ids(df, precinct_col)
    else:
        _log.warning("[VOTER_PARSER] No precinct column detected — cannot join to precinct model")
        df["canonical_precinct_id"] = None

    # ── Party normalization ───────────────────────────────────────────────────
    party_col = col_map.get("party")
    if party_col:
        df = normalize_party(df, party_col, schema)

    # ── Vote history ──────────────────────────────────────────────────────────
    history_cols = col_map.get("vote_history_cols", [])
    df = parse_vote_history(df, history_cols)

    # ── Coerce age to int ─────────────────────────────────────────────────────
    age_col = col_map.get("age")
    if age_col:
        df["age"] = pd.to_numeric(df[age_col], errors="coerce").astype("Int64")

    # ── Write Parquet (local only) ────────────────────────────────────────────
    out_dir = BASE_DIR / "derived" / "voter_models"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}__voter_base.parquet"

    try:
        df_to_save = strip_pii(df, schema, keep_voter_id=True)
        df_to_save.to_parquet(out_path, index=False)
        _log.info(f"[VOTER_PARSER] Wrote voter base: {out_path} ({out_path.stat().st_size:,} bytes)")
    except Exception as e:
        _log.warning(f"[VOTER_PARSER] Could not write Parquet: {e}")

    return df


# ── Discovery Helper ──────────────────────────────────────────────────────────

def find_voter_file(county: str = "Sonoma", state: str = "CA") -> Optional[Path]:
    """
    Search for a voter file in the standard local directory.
    Returns the first found file, or None.
    """
    voter_dir = BASE_DIR / "data" / "voters" / state / county
    if not voter_dir.exists():
        return None
    for pattern in ("*.parquet", "*.csv", "*.tsv", "voter_file*.csv"):
        matches = sorted(voter_dir.glob(pattern))
        if matches:
            # Prefer most recently modified
            return max(matches, key=lambda p: p.stat().st_mtime)
    return None


if __name__ == "__main__":
    # Quick smoke test
    import sys
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        df = ingest_voter_file(path, run_id="test_run")
        if df is not None:
            print(f"Loaded {len(df):,} voters")
            print(df[["canonical_precinct_id", "party_normalized",
                        "elections_participated", "propensity_score"]].head(10))
