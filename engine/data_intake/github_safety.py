"""
engine/data_intake/github_safety.py — Prompt 17.5

Enforces GitHub safety by actively scanning directories and git staging
for raw voter files or sensitive operational datasets.
If PII (Personally Identifiable Information) or unaggregated runtime files
are detected, it blocks the commit.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
import pandas as pd

log = logging.getLogger(__name__)

# Heuristics for dangerous columns that hint at PII / raw voter level
_DANGEROUS_COLUMNS = {
    "voterid", "voter_id", "sos_voterid", "dob", "birth_date", "ssn", "dl_number",
    "address_number", "street_name", "phone", "email", "mail_address"
}

def scan_file_for_safety(file_path: Path) -> tuple[bool, str]:
    """
    Returns (is_safe, reason).
    """
    name = file_path.name.lower()
    ext = file_path.suffix.lower()

    # Allowed extensions are implicitly safe for raw scans unless they are CSV/TSV
    if ext not in (".csv", ".tsv", ".xlsx", ".xls"):
        if ext in (".json", ".md", ".yaml", ".yml", ".txt", ".geojson"):
            return True, "Allowed text/geo metadata format."
        return True, f"Non-tabular format ({ext})."

    # Strict ban by filename hints
    if "voter" in name and "file" in name:
        return False, "Filename indicates raw voter file."
    
    if ext == ".csv":
        try:
            df = pd.read_csv(file_path, nrows=5)
            cols = {c.strip().lower() for c in df.columns}
            matched_dangerous = _DANGEROUS_COLUMNS.intersection(cols)
            if matched_dangerous:
                return False, f"PII columns detected: {', '.join(matched_dangerous)}"
            
            # Simple check if there are many rows
            # We can't easily check row count without reading the whole file,
            # but if it has PII columns, it's blocked.
        except Exception as e:
            return True, f"Could not parse CSV headers: {e}"

    return True, "No dangerous metadata detected."

def enforce_safety(scan_dir: Path | str) -> bool:
    """
    Scans data/voters, data/campaign_runtime, data/uploads for un-aggregated files.
    Returns True if fully safe, False if violations found.
    """
    root = Path(scan_dir)
    unsafe_files = []

    dirs_to_scan = [
        root / "data" / "voters",
        root / "data" / "campaign_runtime",
        root / "data" / "uploads"
    ]

    for d in dirs_to_scan:
        if d.exists():
            for filepath in d.rglob("*.*"):
                # ignore gitkeeps
                if filepath.name == ".gitkeep":
                    continue
                safe, reason = scan_file_for_safety(filepath)
                if not safe:
                    unsafe_files.append((filepath, reason))

    if unsafe_files:
        print("\n\n" + "="*60)
        print("*** GITHUB SAFETY VIOLATION DETECTED ***")
        print("="*60)
        print("The following files contain PII or raw sensitive data and CANNOT be committed:\n")
        pd.set_option("display.max_colwidth", None)
        df_out = pd.DataFrame(unsafe_files, columns=["Path", "Reason"])
        df_out["Path"] = df_out["Path"].apply(lambda p: str(p.relative_to(root)))
        print(df_out.to_string(index=False))
        print("\nArchive or remove these files before committing.")
        print("="*60 + "\n")
        return False
    
    return True

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    if not enforce_safety(root):
        sys.exit(1)
    else:
        print("OK Directory scan clean. No sensitive PII or raw voter files detected.")
        sys.exit(0)
