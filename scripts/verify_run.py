"""scripts/verify_run.py — Verify all log artifacts for the latest run."""
import sys
from pathlib import Path

base = Path(__file__).resolve().parent.parent
run_id_file = base / "logs" / "latest" / "RUN_ID.txt"
if not run_id_file.exists():
    print("No RUN_ID.txt found — no run has been executed yet.")
    sys.exit(1)

run_id = run_id_file.read_text().strip()
print(f"Verifying RUN_ID: {run_id}\n")

required = {
    f"logs/runs/{run_id}__run.log":                    "Run log",
    f"logs/runs/{run_id}__pathway.json":               "Pathway JSON (DAG)",
    f"reports/validation/{run_id}__validation_report.md": "Validation report",
    f"reports/qa/{run_id}__qa_sanity_checks.md":       "QA sanity checks",
    "needs/needs.yaml":                                 "NEEDS registry",
    f"needs/history/{run_id}__needs_snapshot.yaml":    "NEEDS snapshot",
    "logs/latest/run.log":                             "logs/latest/run.log",
    "logs/latest/pathway.json":                        "logs/latest/pathway.json",
    "logs/latest/validation.md":                       "logs/latest/validation.md",
    "logs/latest/qa.md":                               "logs/latest/qa.md",
    "logs/latest/needs.yaml":                          "logs/latest/needs.yaml",
    "logs/latest/RUN_ID.txt":                          "logs/latest/RUN_ID.txt",
}

all_ok = True
for rel, label in required.items():
    p = base / rel
    ok = p.exists() and p.stat().st_size > 0
    size = p.stat().st_size if p.exists() else 0
    tag = "PASS" if ok else "FAIL"
    if not ok:
        all_ok = False
    print(f"  [{tag}] {label:45s} ({size:,} bytes)")

print()

# Derived outputs
csv_found = list((base / "derived").rglob("*.csv"))
print(f"Derived CSVs produced: {len(csv_found)}")
for f in sorted(csv_found):
    print(f"  {f.relative_to(base)}  ({f.stat().st_size:,} bytes)")

print()
if all_ok:
    print("All required log artifact checks PASSED.")
else:
    print("FAILURES detected — see above.")
    sys.exit(1)
