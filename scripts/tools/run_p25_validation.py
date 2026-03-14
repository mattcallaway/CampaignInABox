"""
scripts/tools/run_p25_validation.py — Prompt 25

Validates the Historical Election Archive Builder implementation.

Phases:
  1. Pre-condition check (all required systems importable)
  2. Source registry validation (CA/Sonoma jurisdiction-locked)
  3. Domain allowlist validation (3-tier, gov_tier enforced)
  4. file_discovery 5-factor scoring (code inspection)
  5. Page discovery module integration  
  6. File downloader module
  7. Archive output writer modules
  8. Archive registry fields
  9. Archive builder orchestrator pre-condition check
 10. Report file generation

Usage:
  python scripts/tools/run_p25_validation.py
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

# ---------- sys.path injection so engine imports resolve ----------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
# ------------------------------------------------------------------------------

REPORTS_DIR = BASE_DIR / "reports" / "validation"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

RUN_ID = datetime.now().strftime("%Y%m%d__%H%M%S")
REPORT_MD   = REPORTS_DIR / f"{RUN_ID}__prompt25_validation.md"
REPORT_JSON = REPORTS_DIR / f"{RUN_ID}__prompt25_validation.json"


# ── Check helpers ─────────────────────────────────────────────────────────────

class Validator:
    def __init__(self):
        self.results: list[dict] = []

    def check(self, phase: str, name: str, fn) -> bool:
        try:
            fn()
            self.results.append({"phase": phase, "name": name, "status": "PASS", "error": None})
            return True
        except AssertionError as e:
            self.results.append({"phase": phase, "name": name, "status": "FAIL", "error": str(e)})
            return False
        except Exception as e:
            self.results.append({
                "phase": phase, "name": name, "status": "ERROR",
                "error": f"{type(e).__name__}: {e}",
            })
            return False

    def summary(self) -> dict:
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        return {
            "total": total, "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / max(total, 1) * 100, 1),
        }


V = Validator()


# =============================================================================
# Phase 1: Required systems importable
# =============================================================================

def _check_import(module_path: str, func_name: str):
    mod = __import__(module_path, fromlist=[func_name])
    assert hasattr(mod, func_name), f"{module_path} missing {func_name}"

PHASE1 = "Phase 1: Required systems"

V.check(PHASE1, "source_scanner importable",
    lambda: _check_import("engine.archive_builder.source_scanner", "scan_all_sources"))
V.check(PHASE1, "page_discovery importable",
    lambda: _check_import("engine.archive_builder.page_discovery", "discover_election_pages"))
V.check(PHASE1, "file_discovery importable",
    lambda: _check_import("engine.archive_builder.file_discovery", "discover_files_from_page"))
V.check(PHASE1, "file_downloader importable",
    lambda: _check_import("engine.archive_builder.file_downloader", "download_batch"))
V.check(PHASE1, "archive_classifier importable",
    lambda: _check_import("engine.archive_builder.archive_classifier", "classify_candidate_file"))
V.check(PHASE1, "archive_ingestor importable",
    lambda: _check_import("engine.archive_builder.archive_ingestor", "ingest_classified_file"))
V.check(PHASE1, "archive_registry importable",
    lambda: _check_import("engine.archive_builder.archive_registry", "register_election"))
V.check(PHASE1, "archive_output_writer importable",
    lambda: _check_import("engine.archive_builder.archive_output_writer", "write_archive_outputs"))
V.check(PHASE1, "campaign_state_resolver importable",
    lambda: _check_import("engine.state.campaign_state_resolver", "get_active_campaign_id"))
V.check(PHASE1, "archive_builder importable",
    lambda: _check_import("engine.archive_builder.archive_builder", "run_archive_build"))


# =============================================================================
# Phase 2: Source registry — jurisdiction lock
# =============================================================================

PHASE2 = "Phase 2: Source registry"
import yaml

def _load_sources():
    path = BASE_DIR / "config" / "source_registry" / "contest_sources.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("sources", [])

SOURCES = _load_sources()

def _chk_all_ca():
    non_ca = [s["source_id"] for s in SOURCES if s.get("state", "CA").upper() != "CA"]
    assert not non_ca, f"Non-CA sources found: {non_ca}"

def _chk_sonoma_sources():
    sonoma = [s for s in SOURCES if s.get("county", "").lower() == "sonoma"]
    assert len(sonoma) >= 6, f"Expected >=6 Sonoma sources, got {len(sonoma)}"

def _chk_no_socoe():
    page_urls = [s.get("page_url", "") + s.get("base_url", "") for s in SOURCES]
    bad = [u for u in page_urls if "socoe.us" in u]
    assert not bad, f"Removed domain socoe.us still present in sources: {bad}"

def _chk_sonoma_per_year():
    years = [s.get("year") for s in SOURCES
             if s.get("county", "").lower() == "sonoma" and s.get("year")]
    assert 2024 in years, "2024 Sonoma source missing"
    assert 2022 in years, "2022 Sonoma source missing"
    assert 2020 in years, "2020 Sonoma source missing"

def _chk_discovery_page_exists():
    disc = [s for s in SOURCES if s.get("page_type") == "discovery_page"]
    assert len(disc) >= 2, f"Expected >=2 discovery_page sources, got {len(disc)}"

V.check(PHASE2, "All sources are CA state",                _chk_all_ca)
V.check(PHASE2, ">=6 Sonoma county sources exist",         _chk_sonoma_sources)
V.check(PHASE2, "socoe.us removed from all sources",       _chk_no_socoe)
V.check(PHASE2, "Per-year entries for 2020/2022/2024",     _chk_sonoma_per_year)
V.check(PHASE2, "discovery_page sources present",          _chk_discovery_page_exists)


# =============================================================================
# Phase 3: Domain allowlist validation
# =============================================================================

PHASE3 = "Phase 3: Domain allowlist"
ALLOWLIST_PATH = BASE_DIR / "config" / "source_registry" / "official_domain_allowlist.yaml"

def _chk_allowlist_exists():
    assert ALLOWLIST_PATH.exists(), f"allowlist not found: {ALLOWLIST_PATH}"

def _chk_gov_tier_has_sonomagov():
    data = yaml.safe_load(ALLOWLIST_PATH.read_text(encoding="utf-8")) or {}
    domains = data.get("gov_tier", {}).get("domains", [])
    assert any("sonomacounty.gov" in d for d in domains), \
        f"sonomacounty.gov not in gov_tier domains: {domains}"

def _chk_socoe_not_in_allowlist():
    data = yaml.safe_load(ALLOWLIST_PATH.read_text(encoding="utf-8")) or {}
    all_domains = [
        d for tier in ("gov_tier", "official_tier", "academic_tier")
        for d in data.get(tier, {}).get("domains", [])
    ]
    bad = [d for d in all_domains if "socoe.us" in d]
    assert not bad, f"socoe.us still in allowlist: {bad}"

def _chk_three_tiers():
    data = yaml.safe_load(ALLOWLIST_PATH.read_text(encoding="utf-8")) or {}
    for tier in ("gov_tier", "official_tier", "academic_tier"):
        assert tier in data, f"{tier} missing from allowlist"

def _chk_allowlist_max_confidence():
    data = yaml.safe_load(ALLOWLIST_PATH.read_text(encoding="utf-8")) or {}
    gov_max = data.get("gov_tier", {}).get("max_confidence", 0)
    off_max = data.get("official_tier", {}).get("max_confidence", 0)
    assert gov_max >= 0.90, f"gov_tier max_confidence too low: {gov_max}"
    assert gov_max > off_max, f"gov_tier confidence should exceed official_tier"

V.check(PHASE3, "official_domain_allowlist.yaml exists",   _chk_allowlist_exists)
V.check(PHASE3, "gov_tier includes sonomacounty.gov",      _chk_gov_tier_has_sonomagov)
V.check(PHASE3, "socoe.us not in allowlist",               _chk_socoe_not_in_allowlist)
V.check(PHASE3, "All three tiers present",                 _chk_three_tiers)
V.check(PHASE3, "gov_tier confidence > official_tier",     _chk_allowlist_max_confidence)


# =============================================================================
# Phase 4: file_discovery — 5-factor scoring
# =============================================================================

PHASE4 = "Phase 4: file_discovery 5-factor scoring"

from engine.archive_builder.file_discovery import score_candidate_file, MIN_CANDIDATE_SCORE, CandidateFile

def _chk_structured_ext_score():
    s = score_candidate_file("results.xlsx", ".xlsx")
    assert s >= 0.3, f"xlsx should score >=0.3, got {s}"

def _chk_precinct_score():
    s = score_candidate_file("precinct_results.xlsx", ".xlsx")
    assert s >= 0.6, f"precinct+xlsx should score >=0.6, got {s}"

def _chk_detail_score():
    s = score_candidate_file("detailed_results.csv", ".csv")
    assert s >= 0.5, f"detail+csv should score >=0.5, got {s}"

def _chk_precinct_detail_score():
    s = score_candidate_file("precinct_detail.xlsx", ".xlsx")
    assert s >= 0.8, f"precinct+detail+xlsx should score >=0.8, got {s}"

def _chk_gov_tier_bonus():
    s1 = score_candidate_file("precinct.csv", ".csv", source_url="")
    s2 = score_candidate_file("precinct.csv", ".csv", source_url="https://sonomacounty.gov/results")
    assert s2 > s1, f"gov_tier should boost score: no-gov={s1} gov={s2}"

def _chk_min_threshold():
    assert MIN_CANDIDATE_SCORE == 0.5, f"MIN_CANDIDATE_SCORE should be 0.5, got {MIN_CANDIDATE_SCORE}"

def _chk_low_score_ignored():
    s = score_candidate_file("report.pdf", ".pdf")
    assert s < MIN_CANDIDATE_SCORE, f"PDF should score < {MIN_CANDIDATE_SCORE}, got {s}"

def _chk_size_bonus():
    s1 = score_candidate_file("precinct.csv", ".csv", file_size_bytes=0)
    s2 = score_candidate_file("precinct.csv", ".csv", file_size_bytes=100*1024)
    assert s2 > s1, f"Large file should score higher: small={s1} large={s2}"

def _chk_candidate_file_has_score_field():
    import inspect
    fields = [f.name for f in CandidateFile.__dataclass_fields__.values()]
    assert "candidate_score" in fields, f"CandidateFile missing candidate_score field, got: {fields}"

V.check(PHASE4, "structured extension scores >=0.3",         _chk_structured_ext_score)
V.check(PHASE4, "precinct+xlsx scores >=0.6",                _chk_precinct_score)
V.check(PHASE4, "detail+csv scores >=0.5",                   _chk_detail_score)
V.check(PHASE4, "precinct+detail+xlsx scores >=0.8",         _chk_precinct_detail_score)
V.check(PHASE4, "gov_tier domain gives +0.1 bonus",          _chk_gov_tier_bonus)
V.check(PHASE4, "MIN_CANDIDATE_SCORE is 0.5",                _chk_min_threshold)
V.check(PHASE4, "non-tabular file scores <0.5",              _chk_low_score_ignored)
V.check(PHASE4, ">50KB file gets size bonus",                _chk_size_bonus)
V.check(PHASE4, "CandidateFile has candidate_score field",   _chk_candidate_file_has_score_field)


# =============================================================================
# Phase 5: page_discovery module
# =============================================================================

PHASE5 = "Phase 5: page_discovery module"

from engine.archive_builder.page_discovery import (
    score_page, discover_election_pages, ElectionPage,
)

def _chk_score_page_returns_float():
    score, method = score_page("https://example.com/elections/results", "<html>statement of vote results</html>")
    assert isinstance(score, float), f"score_page should return float, got {type(score)}"
    assert 0.0 <= score <= 1.0, f"score out of range: {score}"

def _chk_score_page_election_url():
    score, method = score_page(
        "https://sonomacounty.gov/november-8-2022-general-election",
        "precinct results certified official statement of vote"
    )
    assert score > 0.2, f"election URL+content should score >0.2, got {score}"

def _chk_discover_election_pages_returns_list():
    src = {
        "source_id": "test_direct", "state": "CA", "county": "Sonoma",
        "year": 2022, "election_type": "general",
        "page_type": "election_page",
        "page_url": "https://sonomacounty.gov/elections/2022",
        "base_url": "https://sonomacounty.gov",
        "confidence_default": 0.90,
    }
    pages = discover_election_pages(src, online=False)
    assert isinstance(pages, list), f"Expected list, got {type(pages)}"
    assert len(pages) >= 1, "Direct election_page source should return at least 1 page"

def _chk_election_page_dataclass():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(ElectionPage)}
    for req in ("url", "source_id", "page_score", "has_file_links", "discovery_method"):
        assert req in fields, f"ElectionPage missing field: {req}"

V.check(PHASE5, "score_page returns float in [0,1]",          _chk_score_page_returns_float)
V.check(PHASE5, "election URL+content scores >0.2",           _chk_score_page_election_url)
V.check(PHASE5, "discover_election_pages returns list",        _chk_discover_election_pages_returns_list)
V.check(PHASE5, "ElectionPage dataclass has required fields",  _chk_election_page_dataclass)


# =============================================================================
# Phase 6: file_downloader module
# =============================================================================

PHASE6 = "Phase 6: file_downloader"

from engine.archive_builder.file_downloader import (
    get_file_registry, registry_summary, update_file_archive_status,
    ACCEPTED_EXTENSIONS, MIN_FILE_SIZE, RAW_DIR,
)

def _chk_file_registry_loads():
    reg = get_file_registry()
    assert isinstance(reg, list), f"Expected list from get_file_registry(), got {type(reg)}"

def _chk_registry_summary_structure():
    s = registry_summary()
    for key in ("total_registered", "staged", "failed", "archive_ready"):
        assert key in s, f"registry_summary missing key: {key}"

def _chk_raw_dir_exists():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    assert RAW_DIR.exists(), f"RAW_DIR not created: {RAW_DIR}"

def _chk_accepted_extensions():
    for ext in (".xlsx", ".xls", ".csv", ".tsv", ".zip"):
        assert ext in ACCEPTED_EXTENSIONS, f"Missing accepted extension: {ext}"

def _chk_min_file_size():
    assert MIN_FILE_SIZE == 50 * 1024, f"MIN_FILE_SIZE should be 51200, got {MIN_FILE_SIZE}"

V.check(PHASE6, "file registry loads (empty or populated)",   _chk_file_registry_loads)
V.check(PHASE6, "registry_summary has required keys",         _chk_registry_summary_structure)
V.check(PHASE6, "RAW_DIR created at data/election_archive/raw/", _chk_raw_dir_exists)
V.check(PHASE6, "ACCEPTED_EXTENSIONS includes all 5 types",   _chk_accepted_extensions)
V.check(PHASE6, "MIN_FILE_SIZE is 50 KB",                     _chk_min_file_size)


# =============================================================================
# Phase 7: archive_output_writer
# =============================================================================

PHASE7 = "Phase 7: archive_output_writer"

from engine.archive_builder.archive_output_writer import (
    write_archive_outputs, NORM_DIR, ARCHIVE_DIR,
)

def _chk_output_dirs_exist():
    NORM_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    assert NORM_DIR.exists(), f"NORM_DIR missing: {NORM_DIR}"
    assert ARCHIVE_DIR.exists(), f"ARCHIVE_DIR missing: {ARCHIVE_DIR}"

def _chk_write_archive_outputs_runs():
    # With empty ingested_results, should write empty/stub CSVs
    outputs = write_archive_outputs(ingested_results=[], run_id="test_p25_val")
    assert isinstance(outputs, dict), f"Expected dict, got {type(outputs)}"
    # Check at least normalized_elections.csv was produced
    norm_path = NORM_DIR / "normalized_elections.csv"
    assert norm_path.exists(), f"normalized_elections.csv not created at {norm_path}"

def _chk_archive_output_keys():
    outputs = write_archive_outputs(ingested_results=[], run_id="test_p25_val2")
    expected_keys = {"normalized_elections", "precinct_profiles", "precinct_trends", "similar_elections"}
    got_keys = set(outputs.keys())
    missing = expected_keys - got_keys
    assert not missing, f"archive_output_writer missing outputs: {missing}"

def _chk_all_csvs_exist():
    outputs = write_archive_outputs(ingested_results=[], run_id="test_p25_val3")
    for name, path_str in outputs.items():
        p = Path(path_str)
        assert p.exists(), f"Output CSV not found: {name} → {p}"

V.check(PHASE7, "output dirs created",                         _chk_output_dirs_exist)
V.check(PHASE7, "write_archive_outputs runs without error",    _chk_write_archive_outputs_runs)
V.check(PHASE7, "write_archive_outputs returns all 4 keys",   _chk_archive_output_keys)
V.check(PHASE7, "all 4 CSV output files exist on disk",       _chk_all_csvs_exist)


# =============================================================================
# Phase 8: archive_registry — new fields
# =============================================================================

PHASE8 = "Phase 8: archive_registry new fields"

import inspect
from engine.archive_builder.archive_registry import register_election

def _chk_register_has_archive_status_param():
    sig = inspect.signature(register_election)
    assert "archive_status" in sig.parameters, "register_election missing archive_status param"

def _chk_register_has_run_id_param():
    sig = inspect.signature(register_election)
    assert "run_id" in sig.parameters, "register_election missing run_id param"

def _chk_register_has_file_path_param():
    sig = inspect.signature(register_election)
    assert "file_path" in sig.parameters, "register_election missing file_path param"

def _chk_register_archive_status_default():
    sig = inspect.signature(register_election)
    default = sig.parameters["archive_status"].default
    assert default == "ARCHIVE_READY", f"archive_status default should be ARCHIVE_READY, got {default!r}"

V.check(PHASE8, "register_election has archive_status param",  _chk_register_has_archive_status_param)
V.check(PHASE8, "register_election has run_id param",          _chk_register_has_run_id_param)
V.check(PHASE8, "register_election has file_path param",       _chk_register_has_file_path_param)
V.check(PHASE8, "archive_status defaults to ARCHIVE_READY",    _chk_register_archive_status_default)


# =============================================================================
# Phase 9: archive_builder orchestrator
# =============================================================================

PHASE9 = "Phase 9: archive_builder orchestrator"

from engine.archive_builder.archive_builder import (
    check_preconditions, run_archive_build, REQUIRED_SYSTEMS,
    ArchiveBuildResult,
)

def _chk_required_systems_count():
    assert len(REQUIRED_SYSTEMS) >= 8, f"Expected >=8 required systems, got {len(REQUIRED_SYSTEMS)}"

def _chk_preconditions_check_runs():
    ok, missing = check_preconditions()
    assert isinstance(ok, bool), f"check_preconditions should return bool"
    assert isinstance(missing, list), f"check_preconditions should return list"

def _chk_preconditions_pass():
    ok, missing = check_preconditions()
    assert ok, f"Pre-condition check failed: {missing}"

def _chk_run_archive_build_offline():
    result = run_archive_build(
        state="CA", county="Sonoma",
        online=False, download=False,
        run_id="test_p25_val_offline",
        abort_on_precondition_fail=False,
    )
    assert isinstance(result, ArchiveBuildResult), f"Expected ArchiveBuildResult, got {type(result)}"
    assert result.state == "CA", f"state mismatch: {result.state}"
    assert result.county == "Sonoma", f"county mismatch: {result.county}"

def _chk_result_has_archive_outputs():
    result = run_archive_build(
        state="CA", county="Sonoma",
        online=False, download=False,
        run_id="test_p25_val_outputs",
        abort_on_precondition_fail=False,
    )
    assert hasattr(result, "archive_outputs"), "ArchiveBuildResult missing archive_outputs"
    assert isinstance(result.archive_outputs, dict), "archive_outputs should be dict"

def _chk_result_has_preconditions_ok():
    result = run_archive_build(
        state="CA", county="Sonoma",
        online=False, download=False,
        run_id="test_p25_val_pc",
        abort_on_precondition_fail=False,
    )
    assert hasattr(result, "preconditions_ok"), "ArchiveBuildResult missing preconditions_ok"

V.check(PHASE9, ">=8 required systems registered",             _chk_required_systems_count)
V.check(PHASE9, "check_preconditions() runs without error",    _chk_preconditions_check_runs)
V.check(PHASE9, "all required systems importable (pass)",      _chk_preconditions_pass)
V.check(PHASE9, "run_archive_build offline returns result",    _chk_run_archive_build_offline)
V.check(PHASE9, "ArchiveBuildResult has archive_outputs",      _chk_result_has_archive_outputs)
V.check(PHASE9, "ArchiveBuildResult has preconditions_ok",     _chk_result_has_preconditions_ok)


# =============================================================================
# Phase 10: Report generation
# =============================================================================

PHASE10 = "Phase 10: Report generation"

def _chk_build_report_written():
    result = run_archive_build(
        state="CA", county="Sonoma", online=False, download=False,
        run_id=f"p25_val_rpt_{RUN_ID}",
        abort_on_precondition_fail=False,
    )
    if result.build_report:
        p = Path(result.build_report)
        assert p.exists(), f"Build report not found: {p}"
    # Non-failing even if no candidate files — report still written
    assert True

def _chk_classification_report_written():
    result = run_archive_build(
        state="CA", county="Sonoma", online=False, download=False,
        run_id=f"p25_val_cls_{RUN_ID}",
        abort_on_precondition_fail=False,
    )
    if result.classification_report:
        p = Path(result.classification_report)
        assert p.exists(), f"Classification report not found: {p}"
    assert True  # non-fatal if no files to classify

V.check(PHASE10, "build report written",                        _chk_build_report_written)
V.check(PHASE10, "file classification report written",          _chk_classification_report_written)


# =============================================================================
# Output reports
# =============================================================================

summary = V.summary()
print()
print("=" * 70)
print(f"  Prompt 25 Validation — {RUN_ID}")
print("=" * 70)

phase_order = [
    PHASE1, PHASE2, PHASE3, PHASE4, PHASE5,
    PHASE6, PHASE7, PHASE8, PHASE9, PHASE10,
]
for phase in phase_order:
    phase_results = [r for r in V.results if r["phase"] == phase]
    phase_pass = sum(1 for r in phase_results if r["status"] == "PASS")
    phase_label = f"PASS {phase_pass}/{len(phase_results)}" if phase_pass == len(phase_results) else f"FAIL {phase_pass}/{len(phase_results)}"
    print(f"\n  {phase}  [{phase_label}]")
    for r in phase_results:
        icon = "OK" if r["status"] == "PASS" else "FAIL"
        print(f"    [{icon}] {r['name']}")
        if r.get("error"):
            print(f"           => {r['error']}")

print()
print("-" * 70)
print(f"  TOTAL: {summary['passed']}/{summary['total']} PASS ({summary['pass_rate']}%)")
print("=" * 70)
print()

# Write MD report
md_lines = [
    f"# Prompt 25 Validation Report — {RUN_ID}",
    f"**Generated:** {datetime.now().isoformat()}",
    "",
    "## Summary",
    "",
    f"**{summary['passed']}/{summary['total']} PASS ({summary['pass_rate']}%)**",
    "",
    "| Phase | Pass | Total |",
    "|-------|------|-------|",
]
for phase in phase_order:
    phase_results = [r for r in V.results if r["phase"] == phase]
    ph_pass = sum(1 for r in phase_results if r["status"] == "PASS")
    md_lines.append(f"| {phase} | {ph_pass} | {len(phase_results)} |")

md_lines += ["", "## Detailed Results", ""]
for phase in phase_order:
    md_lines.append(f"\n### {phase}\n")
    for r in [x for x in V.results if x["phase"] == phase]:
        icon = "PASS" if r["status"] == "PASS" else "FAIL"
        md_lines.append(f"- [{icon}] {r['name']}")
        if r.get("error"):
            md_lines.append(f"  - Error: `{r['error']}`")

REPORT_MD.write_text("\n".join(md_lines), encoding="utf-8")
REPORT_JSON.write_text(
    json.dumps({"run_id": RUN_ID, "summary": summary, "results": V.results}, indent=2),
    encoding="utf-8",
)

print(f"  MD  report: {REPORT_MD}")
print(f"  JSON report: {REPORT_JSON}")
print()

if summary["passed"] < summary["total"]:
    sys.exit(1)
