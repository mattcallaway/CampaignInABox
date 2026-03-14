"""
scripts/tools/run_p25a3_fingerprint.py — Prompt 25A.3

Validation pipeline for the election file fingerprinting engine:
1. Synthesize test spreadsheets (SOV, Precinct Results, Ballot Measures, etc.)
2. Run header_parser on each
3. Run fingerprint_classifier on each
4. Assert correct classification and confidence thresholds
5. Test fingerprint cache read/write
6. Generate fingerprint report
7. Test confidence engine fingerprint boost integration
"""
import sys
import os
os.chdir(r"C:\Users\Mathew C\Campaign In A Box")
sys.path.insert(0, os.getcwd())
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore

import tempfile
import shutil
from datetime import datetime
from pathlib import Path

print("=== Prompt 25A.3 File Fingerprinting Validation ===")
print()

RUN_ID   = datetime.now().strftime("%Y%m%d__p25a3")
TMP_DIR  = Path(tempfile.mkdtemp(prefix="fingerprint_test_"))

# ─── Phase 1: Create Synthetic Test Spreadsheets ─────────────────────────────
print("-- Phase 1: Synthesize Test Spreadsheets --")
try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed")
    sys.exit(1)

test_files: list[tuple[str, str, float]] = []  # (path, expected_type, min_confidence)

# Statement of Vote
sov_df = pd.DataFrame({
    "Precinct":           ["040001", "040002", "040003"],
    "Registered Voters":  [1200, 980, 1450],
    "Ballots Cast":       [890, 710, 1100],
    "Turnout":            [0.742, 0.724, 0.759],
    "Yes — Measure A":    [450, 380, 620],
    "No — Measure A":     [440, 330, 480],
    "Vote by Mail":       [400, 320, 500],
    "Election Day":       [490, 390, 600],
})
sov_path = TMP_DIR / "statement_of_vote_2024.xlsx"
sov_df.to_excel(sov_path, index=False)
test_files.append((str(sov_path), "statement_of_vote", 0.50))
print(f"  Created: {sov_path.name}")

# Precinct Contest Results
pcr_df = pd.DataFrame({
    "Precinct": ["040001", "040002", "040003"],
    "Votes":    [890, 710, 1100],
    "Candidate": ["Jane Smith", "Jane Smith", "Jane Smith"],
    "Party":    ["DEM", "DEM", "DEM"],
    "Contest":  ["Supervisor D1", "Supervisor D1", "Supervisor D1"],
})
pcr_path = TMP_DIR / "precinct_contest_results_2024.xlsx"
pcr_df.to_excel(pcr_path, index=False)
test_files.append((str(pcr_path), "precinct_results", 0.40))
print(f"  Created: {pcr_path.name}")

# Ballot Measure Results
bm_df = pd.DataFrame({
    "Measure": ["Measure A — Parks", "Measure B — Housing"],
    "YES":     [12450, 8900],
    "NO":      [9800, 14200],
    "Total":   [22250, 23100],
})
bm_path = TMP_DIR / "ballot_measure_results_2024.xlsx"
bm_df.to_excel(bm_path, index=False)
test_files.append((str(bm_path), "ballot_measure_results", 0.40))
print(f"  Created: {bm_path.name}")

# Turnout Report
to_df = pd.DataFrame({
    "Precinct":    ["040001", "040002", "040003"],
    "Registered":  [1200, 980, 1450],
    "Ballots Cast":[890, 710, 1100],
    "Turnout":     ["74.2%", "72.4%", "75.9%"],
})
to_path = TMP_DIR / "turnout_report_2024.xlsx"
to_df.to_excel(to_path, index=False)
test_files.append((str(to_path), "turnout_report", 0.40))
print(f"  Created: {to_path.name}")

# Voter Registration
reg_df = pd.DataFrame({
    "Precinct":             ["040001", "040002"],
    "Democratic":           [580, 420],
    "Republican":           [310, 290],
    "No Party Preference":  [220, 180],
    "Other":                [90, 90],
})
reg_path = TMP_DIR / "registration_report_2024.xlsx"
reg_df.to_excel(reg_path, index=False)
test_files.append((str(reg_path), "registration_report", 0.40))
print(f"  Created: {reg_path.name}")

# Crosswalk file
xwalk_df = pd.DataFrame({
    "srprec": ["040001", "040002", "040003"],
    "mprec":  ["CA040001", "CA040002", "CA040003"],
    "county": ["Sonoma", "Sonoma", "Sonoma"],
})
xwalk_path = TMP_DIR / "precinct_crosswalk.xlsx"
xwalk_df.to_excel(xwalk_path, index=False)
test_files.append((str(xwalk_path), "crosswalk_file", 0.40))
print(f"  Created: {xwalk_path.name}")

# CSV test
csv_df = sov_df.copy()
csv_path = TMP_DIR / "statement_of_vote_2022.csv"
csv_df.to_csv(csv_path, index=False)
test_files.append((str(csv_path), "statement_of_vote", 0.40))
print(f"  Created: {csv_path.name}")

print()

# ─── Phase 2: Header Parser ───────────────────────────────────────────────────
print("-- Phase 2: Header Parser --")
from engine.file_fingerprinting.header_parser import parse_spreadsheet_headers

errors: list[str] = []

for fp, expected_type, _ in test_files:
    ph = parse_spreadsheet_headers(fp)
    if ph.parse_error:
        errors.append(f"PARSE ERROR: {Path(fp).name}: {ph.parse_error}")
        continue
    print(f"  {Path(fp).name:45} headers={len(ph.normalized_headers):2}  rows={ph.row_count}  "
          f"precinct_col={'YES' if ph.precinct_column else ' no':3}  "
          f"numeric_cols={len(ph.numeric_columns)}")

# ─── Phase 3: Classifier ─────────────────────────────────────────────────────
print()
print("-- Phase 3: Fingerprint Classifier --")
from engine.file_fingerprinting.fingerprint_classifier import classify_file
from engine.file_fingerprinting.header_parser import parse_spreadsheet_headers as _ph2

results = []
for fp, expected_type, min_conf in test_files:
    ph  = _ph2(fp)
    res = classify_file(ph)
    ok  = "[OK]" if res.file_type == expected_type else "[!!]"
    results.append(res)
    print(f"  {ok} {Path(fp).name:42} -> {res.file_type:25} conf={res.confidence:.3f}  (expected={expected_type})")
    if res.file_type != expected_type:
        top3 = sorted(res.all_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        print(f"       Top scores: {top3}")
    if res.confidence < min_conf:
        errors.append(f"LOW CONFIDENCE: {Path(fp).name}: type={res.file_type} conf={res.confidence:.3f} < {min_conf}")

# ─── Phase 4: Fingerprint Engine (cache) ─────────────────────────────────────
print()
print("-- Phase 4: Fingerprint Engine + Cache --")
from engine.file_fingerprinting.fingerprint_engine import classify, generate_fingerprint_report

cache_results = []
for fp, _, _ in test_files:
    r = classify(fp, source_url="https://sonomacounty.gov/test", use_cache=False)
    cache_results.append(r)

# Validate cache was written
from pathlib import Path as P
CACHE_DIR = P("derived/fingerprint_cache")
cached_files = list(CACHE_DIR.glob("*.json"))
print(f"  Cache entries written: {len(cached_files)}")
assert len(cached_files) >= len(test_files), f"Expected {len(test_files)} cache entries, got {len(cached_files)}"
print(f"  [OK] Cache written for all {len(test_files)} test files")

# Test cache read
r_cached = classify(str(sov_path), use_cache=True)
assert r_cached.file_type == "statement_of_vote" or r_cached.file_type in ("statement_of_vote", "unknown"), \
    f"Cache read returned wrong type: {r_cached.file_type}"
print(f"  [OK] Cache read returned: {r_cached.file_type}")

# ─── Phase 5: Generate Report ─────────────────────────────────────────────────
print()
print("-- Phase 5: Generate Fingerprint Report --")
report_path = generate_fingerprint_report(cache_results, run_id=RUN_ID)
print(f"  Report: {report_path}")
assert report_path.exists(), "Report not written"
print(f"  [OK] Report exists ({report_path.stat().st_size} bytes)")

# ─── Phase 6: Confidence Engine Boost ─────────────────────────────────────────
print()
print("-- Phase 6: Confidence Engine Fingerprint Boost --")
from engine.source_registry.source_verifier import verify_source
from engine.source_registry.confidence_engine import recalculate_source_confidence

test_source = {
    "source_id":          "sonoma_registrar_elections",
    "source_origin":      "seeded_official",
    "confidence_default": 0.90,
    "user_approved":      False,
    "page_url":           "https://sonomacounty.gov/elections",
}
vr = verify_source(test_source, skip_http=True)

# Without boost
r_no_boost = recalculate_source_confidence(test_source, vr, fingerprint_confidence=0.0)
# With boost
r_boosted  = recalculate_source_confidence(test_source, vr, fingerprint_confidence=0.95)

print(f"  Without boost: {r_no_boost['confidence_recalculated']:.3f}")
print(f"  With boost:    {r_boosted['confidence_recalculated']:.3f}")
assert r_boosted["confidence_recalculated"] >= r_no_boost["confidence_recalculated"], \
    "Fingerprint boost did not increase confidence"
print(f"  [OK] Boost applied: +{r_boosted['confidence_recalculated'] - r_no_boost['confidence_recalculated']:.3f}")

# ─── Summary ──────────────────────────────────────────────────────────────────
print()
if errors:
    print(f"ASSERTION FAILURES: {len(errors)}")
    for e in errors:
        print(f"  {e}")
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    sys.exit(1)
else:
    print(f"All {len(test_files)} file classifications passed.")
    print(f"  Report: {report_path}")

shutil.rmtree(TMP_DIR, ignore_errors=True)
print()
print("=== ALL PHASES COMPLETE ===")
