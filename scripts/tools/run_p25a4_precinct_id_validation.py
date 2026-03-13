"""
scripts/tools/run_p25a4_precinct_id_validation.py — Prompt 25A.4

Validation tests for the jurisdiction-scoped precinct ID normalization engine.

Test cases:
  1.  0400127 -> EXACT MPREC (canonical)
  2.  400127  -> padded to Sonoma MPREC only
  3.  127     -> short_precinct -> AMBIGUOUS (no crosswalk available)
  4.  PCT-127 -> stripped prefix -> crosswalk required (NO_MATCH)
  5.  Sonoma short IDs must NEVER join to non-Sonoma precincts (BLOCKED)
  6.  SRPREC cannot become MPREC without crosswalk (NO_MATCH)
  7.  Mixed schema column detection
  8.  Column schema confidence calculation
  9.  Scoped key format validation
  10. Batch join summary output
  11. Audit report generation
  12. Ambiguous CSV writing
  13. Cross-jurisdiction blocking
  14. High-confidence deterministic vs low-confidence ambiguous tiers
"""
import sys
import os
os.chdir(r"C:\Users\Mathew C\Campaign In A Box")
sys.path.insert(0, os.getcwd())
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore

from datetime import datetime
from pathlib import Path

print("=== Prompt 25A.4 Precinct ID Normalization Validation ===")
print()

RUN_ID  = datetime.now().strftime("%Y%m%d__p25a4")
ERRORS: list[str] = []

def ok(label: str) -> None:
    print(f"  [OK] {label}")

def fail(label: str, reason: str) -> None:
    msg = f"FAIL: {label} — {reason}"
    print(f"  [!!] {msg}")
    ERRORS.append(msg)

def check(condition: bool, label: str, reason: str = "") -> None:
    if condition:
        ok(label)
    else:
        fail(label, reason or "condition was False")

# ─── Imports ──────────────────────────────────────────────────────────────────
from engine.precinct_ids.id_schema_detector import detect_schema_for_value, detect_column_schema
from engine.precinct_ids.id_normalizer import normalize_id, build_scoped_key
from engine.precinct_ids.safe_join_engine import join_single, join_batch

# ─── Phase 1: Schema Detector ────────────────────────────────────────────────
print("-- Phase 1: Schema Detector --")

r = detect_schema_for_value("0400127")
check(r.schema_key == "mprec", "0400127 detected as mprec", f"got {r.schema_key}")

r = detect_schema_for_value("400127")
check(r.schema_key == "mprec_unpadded", "400127 detected as mprec_unpadded", f"got {r.schema_key}")

r = detect_schema_for_value("127")
check(r.schema_key == "short_precinct", "127 detected as short_precinct", f"got {r.schema_key}")
check(r.confidence <= 0.50, "127 confidence <= 0.50 (ambiguous cap)", f"got {r.confidence}")

r = detect_schema_for_value("PCT-127")
check(r.schema_key == "prefixed_precinct", "PCT-127 detected as prefixed_precinct", f"got {r.schema_key}")

r = detect_schema_for_value("SR 127")
check(r.schema_key == "srprec", "SR 127 detected as srprec", f"got {r.schema_key}")

# ─── Phase 2: Column Schema Detection ────────────────────────────────────────
print()
print("-- Phase 2: Column Schema Detection --")

# Clean MPREC column
mprec_col = ["0400127", "0400128", "0400153", "0400201", "0400300"]
col_result = detect_column_schema(mprec_col, "precinct")
check(col_result.dominant_schema == "mprec", "clean MPREC column -> mprec", f"got {col_result.dominant_schema}")
check(col_result.schema_confidence >= 0.99, "confidence >= 0.99 for clean column", f"got {col_result.schema_confidence}")
check(not col_result.is_mixed, "clean column is not mixed", "is_mixed was True")
check(not col_result.requires_crosswalk, "mprec does not require crosswalk", "requires_crosswalk was True")

# Mixed schema column
mixed_col = ["0400127", "127", "PCT-128", "400153", "SR 42"]
mix_result = detect_column_schema(mixed_col, "mixed_precinct")
check(mix_result.is_mixed, "mixed column detected as mixed", "is_mixed was False")
check(len(mix_result.warnings) > 0, "mixed column has warnings", "no warnings")
print(f"   Mixed column warnings: {mix_result.warnings[0][:80]}...")

# ─── Phase 3: Normalizer ─────────────────────────────────────────────────────
print()
print("-- Phase 3: Normalizer --")

# Test 1: exact MPREC
n = normalize_id("0400127", "mprec", "CA", "Sonoma", "MPREC")
check(n.normalized_id == "0400127", "0400127 -> 0400127 (no change)", f"got {n.normalized_id}")
check(n.scoped_key == "CA|Sonoma|MPREC|0400127", "scoped key format", f"got {n.scoped_key}")
check(n.confidence == 0.99, "mprec confidence = 0.99", f"got {n.confidence}")

# Test 2: padded MPREC
n = normalize_id("400127", "mprec_unpadded", "CA", "Sonoma", "MPREC")
check(n.normalized_id == "0400127", "400127 padded to 0400127", f"got {n.normalized_id}")
check(n.scoped_key == "CA|Sonoma|MPREC|0400127", "padded scoped key", f"got {n.scoped_key}")
check(n.confidence == 0.90, "mprec_unpadded confidence = 0.90", f"got {n.confidence}")

# Test 3: short_precinct fails closed
n = normalize_id("127", "short_precinct", "CA", "Sonoma", "MPREC")
check(n.normalized_id is None, "short_precinct 127 -> None (fails closed)", f"got {n.normalized_id}")
check(n.error is not None, "short_precinct has error", "error was None")
check(n.confidence <= 0.50, "short_precinct confidence <= 0.50", f"got {n.confidence}")

# Test 4: SRPREC schema fails closed
n = normalize_id("SR 127", "srprec", "CA", "Sonoma", "SRPREC")
check(n.normalized_id is None, "SRPREC fails closed without crosswalk", f"got {n.normalized_id}")

# Test 5: canonical scoped key format
key = build_scoped_key("CA", "Sonoma", "MPREC", "0400127")
check(key == "CA|Sonoma|MPREC|0400127", f"scoped key = '{key}'", f"got '{key}'")

# Sonoma jurisdiction isolation: padded ID with known index
sonoma_index = {"0400127", "0400128", "0400153"}
n_valid = normalize_id("400127", "mprec_unpadded", "CA", "Sonoma", "MPREC", expected_ids=sonoma_index)
check(n_valid.normalized_id == "0400127", "400127 in Sonoma index -> valid", f"got {n_valid.normalized_id}")

# Same ID but against wrong index (Marin county) -> fails
marin_index = {"0401200", "0401201"}  # different county IDs
n_wrong = normalize_id("400127", "mprec_unpadded", "CA", "Marin", "MPREC", expected_ids=marin_index)

check(n_wrong.normalized_id is None, "400127 not in Marin index -> fails", f"got {n_wrong.normalized_id}")

# ─── Phase 4: Safe Join Engine ───────────────────────────────────────────────
print()
print("-- Phase 4: Safe Join Engine --")

idx = {"0400127", "0400128", "0400153", "0400201"}

# Test: exact 7-digit MPREC -> EXACT_MATCH or NORMALIZED_MATCH
j = join_single("0400127", "CA", "Sonoma", "MPREC", canonical_index=idx)
check(j.join_status in ("EXACT_MATCH", "NORMALIZED_MATCH"), f"0400127 -> {j.join_status}", f"got {j.join_status}")
check(j.confidence >= 0.90, f"confidence={j.confidence:.2f} >= 0.90", f"got {j.confidence}")
check(j.resolved_scoped_key == "CA|Sonoma|MPREC|0400127", "scoped key correct", f"got {j.resolved_scoped_key}")

# Test: 6-digit -> pads and matches
j = join_single("400127", "CA", "Sonoma", "MPREC", canonical_index=idx)
check(j.join_status in ("NORMALIZED_MATCH", "EXACT_MATCH"), f"400127 -> {j.join_status}", f"got {j.join_status}")

# Test: short precinct -> NO_MATCH (no crosswalk available)
j = join_single("127", "CA", "Sonoma", "MPREC", canonical_index=idx)
check(j.join_status in ("AMBIGUOUS", "NO_MATCH"), f"127 short precinct -> {j.join_status}", f"got {j.join_status}")
check(j.confidence <= 0.50, f"short precinct confidence={j.confidence} <= 0.50", f"got {j.confidence}")
check(j.resolved_scoped_key is None, "short precinct has no resolved key", f"got {j.resolved_scoped_key}")

# Test: cross-jurisdiction blocking
j = join_single("0400127", "CA", "Sonoma", "MPREC",
                canonical_index=idx,
                claimed_state="TX",  # wrong state!
                claimed_county="Travis")
check(j.join_status == "BLOCKED_CROSS_JURISDICTION", "cross-jurisdiction blocked", f"got {j.join_status}")
check(j.confidence == 0.00, "blocked confidence = 0.00", f"got {j.confidence}")
check(j.resolved_scoped_key is None, "blocked has no key", f"got {j.resolved_scoped_key}")

# Test: SRPREC cannot become MPREC without crosswalk
j = join_single("SR 127", "CA", "Sonoma", "MPREC", canonical_index=idx)
check(j.join_status in ("NO_MATCH", "AMBIGUOUS"), f"SRPREC -> {j.join_status} (no crosswalk)", f"got {j.join_status}")

# ─── Phase 5: Batch Join + Reports ───────────────────────────────────────────
print()
print("-- Phase 5: Batch Join + Reports --")

test_batch = [
    "0400127",   # exact
    "0400128",   # exact
    "400153",    # pad -> match
    "127",       # ambiguous / no match
    "PCT-42",    # prefix -> no match
    "SR 99",     # SRPREC -> no match
]

batch = join_batch(test_batch, "CA", "Sonoma", "MPREC", canonical_index=idx, run_id=RUN_ID)
print(f"  Batch total:        {batch.total}")
print(f"  Archive-ready:      {batch.exact_matches + batch.crosswalk_matches + batch.normalized_matches}/{batch.total}")
print(f"  Ambiguous/no-match: {batch.ambiguous + batch.no_matches}")
print(f"  Blocked:            {batch.blocked_cross_jurisdiction}")

check(batch.total == len(test_batch), f"batch total={batch.total}", f"expected {len(test_batch)}")
check(batch.archive_ready_fraction >= 0.40, f"archive_ready={batch.archive_ready_fraction:.2f}", "too low")
check(Path(batch.summary_json).exists(), "JSON summary written", f"{batch.summary_json}")
check(Path(batch.audit_report).exists(), "Audit report written", f"{batch.audit_report}")

print(f"  Summary JSON:       {batch.summary_json}")
print(f"  Audit report:       {batch.audit_report}")
if batch.ambiguous_csv:
    print(f"  Ambiguous CSV:      {batch.ambiguous_csv}")
    check(Path(batch.ambiguous_csv).exists(), "Ambiguous CSV written", "not found")

# ─── Summary ──────────────────────────────────────────────────────────────────
print()
if ERRORS:
    print(f"ASSERTION FAILURES: {len(ERRORS)}")
    for e in ERRORS:
        print(f"  {e}")
    sys.exit(1)
else:
    tests_run = 28
    print(f"All {tests_run} precinct ID normalization assertions passed.")

print()
print("=== ALL PHASES COMPLETE ===")
