"""
scripts/tools/run_p25c_validation.py -- Prompt 25C

Validates the Election Directory Predictor engine.

Phases:
  1. Required systems importable (including election_directory_predictor)
  2. Predictor: URL generation (10 templates x 5 years)
  3. Predictor: offline mode, dataclass structure, jurisdiction guard
  4. file_discovery: Prompt 25C scoring weights and MIN_CANDIDATE_SCORE
  5. archive_builder: predictor in REQUIRED_SYSTEMS, report writers exist
  6. Report outputs: offline run generates 4 report files

Usage:
  python scripts/tools/run_p25c_validation.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

REPORTS_DIR = BASE_DIR / "reports" / "archive_builder"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

RUN_ID      = datetime.now().strftime("%Y%m%d__%H%M%S")
REPORT_MD   = REPORTS_DIR / f"{RUN_ID}__prompt25C_validation.md"
REPORT_JSON = REPORTS_DIR / f"{RUN_ID}__prompt25C_validation.json"


# ── Validator ─────────────────────────────────────────────────────────────────

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
        return {"total": total, "passed": passed,
                "failed": total - passed,
                "pass_rate": round(passed / max(total, 1) * 100, 1)}


V = Validator()

# =============================================================================
# Phase 1: Required systems
# =============================================================================
PHASE1 = "Phase 1: Required systems"

def _chk_import(mod, fn):
    m = __import__(mod, fromlist=[fn])
    assert hasattr(m, fn), f"{mod} missing {fn}"

V.check(PHASE1, "election_directory_predictor importable",
    lambda: _chk_import("engine.archive_builder.election_directory_predictor",
                         "predict_election_result_paths"))
V.check(PHASE1, "link_extractor importable",
    lambda: _chk_import("engine.archive_builder.link_extractor", "extract_links"))
V.check(PHASE1, "viewer_resolver importable",
    lambda: _chk_import("engine.archive_builder.viewer_resolver", "is_viewer_url"))
V.check(PHASE1, "page_explorer importable",
    lambda: _chk_import("engine.archive_builder.page_explorer", "explore_election_pages"))
V.check(PHASE1, "file_discovery importable",
    lambda: _chk_import("engine.archive_builder.file_discovery", "score_candidate_file"))
V.check(PHASE1, "file_downloader importable",
    lambda: _chk_import("engine.archive_builder.file_downloader", "download_candidate_file"))
V.check(PHASE1, "archive_builder importable",
    lambda: _chk_import("engine.archive_builder.archive_builder", "run_archive_build"))
V.check(PHASE1, "campaign_state_resolver importable",
    lambda: _chk_import("engine.state.campaign_state_resolver", "get_active_campaign_id"))


# =============================================================================
# Phase 2: Predictor URL generation
# =============================================================================
PHASE2 = "Phase 2: Predictor URL generation"

from engine.archive_builder.election_directory_predictor import (
    predict_election_result_paths,
    _generate_predicted_urls,
    _score_election_page,
    PredictionResult,
    ConfirmedDirectory,
    PATH_TEMPLATES,
    DEFAULT_YEARS,
    ELECTION_PAGE_KEYWORDS,
)

DOMAIN = "https://sonomacounty.ca.gov"

def _chk_path_template_count():
    assert len(PATH_TEMPLATES) == 10, f"Expected 10 PATH_TEMPLATES, got {len(PATH_TEMPLATES)}"

def _chk_default_years():
    assert set(DEFAULT_YEARS) == {2024, 2023, 2022, 2021, 2020}, \
        f"DEFAULT_YEARS mismatch: {DEFAULT_YEARS}"

def _chk_generated_url_count():
    """10 templates x 5 years, some templates have no {year} so emitted once."""
    urls = _generate_predicted_urls(DOMAIN, DEFAULT_YEARS)
    # Templates with {year}: 7 * 5 = 35. Templates without {year}: 3 * 1 = 3. Total = 38.
    assert len(urls) >= 30, f"Expected >=30 generated URLs, got {len(urls)}"

def _chk_generated_urls_are_absolute():
    urls = _generate_predicted_urls(DOMAIN, [2024])
    for url, template, year in urls:
        assert url.startswith("https://"), f"URL not absolute: {url}"

def _chk_generated_urls_include_year():
    urls = _generate_predicted_urls(DOMAIN, [2024])
    year_urls = [u for u, t, y in urls if y == 2024]
    assert len(year_urls) >= 5, f"Expected >=5 URLs with year=2024, got {year_urls}"

def _chk_no_duplicate_urls():
    urls = _generate_predicted_urls(DOMAIN, DEFAULT_YEARS)
    url_strs = [u for u, t, y in urls]
    assert len(url_strs) == len(set(url_strs)), "Duplicate URLs found in generated set"

def _chk_general_election_template():
    urls = _generate_predicted_urls(DOMAIN, [2024])
    url_strs = [u for u, t, y in urls]
    assert any("2024-general-election" in u for u in url_strs), \
        f"No 2024-general-election URL found: {url_strs[:5]}"

def _chk_registrar_template():
    urls = _generate_predicted_urls(DOMAIN, [2022])
    url_strs = [u for u, t, y in urls]
    assert any("registrar-of-voters" in u for u in url_strs), \
        f"No registrar-of-voters URL found"

V.check(PHASE2, "10 PATH_TEMPLATES defined",                    _chk_path_template_count)
V.check(PHASE2, "DEFAULT_YEARS = [2024..2020]",                 _chk_default_years)
V.check(PHASE2, "URL generation produces >=30 candidates",       _chk_generated_url_count)
V.check(PHASE2, "all generated URLs are absolute https://",     _chk_generated_urls_are_absolute)
V.check(PHASE2, "year-parameterized templates include year",    _chk_generated_urls_include_year)
V.check(PHASE2, "no duplicate URLs in generated set",           _chk_no_duplicate_urls)
V.check(PHASE2, "{year}-general-election template present",     _chk_general_election_template)
V.check(PHASE2, "registrar-of-voters template present",         _chk_registrar_template)


# =============================================================================
# Phase 3: Offline mode, dataclasses, jurisdiction guard
# =============================================================================
PHASE3 = "Phase 3: Offline mode / dataclasses / jurisdiction guard"

def _chk_offline_returns_prediction_result():
    r = predict_election_result_paths(DOMAIN, [2024], online=False)
    assert isinstance(r, PredictionResult), f"Expected PredictionResult, got {type(r)}"

def _chk_offline_no_confirmed_dirs():
    r = predict_election_result_paths(DOMAIN, [2024], online=False)
    assert r.confirmed_dirs == [], \
        f"Offline mode should have no confirmed dirs, got {r.confirmed_dirs}"

def _chk_offline_has_predicted_urls():
    r = predict_election_result_paths(DOMAIN, [2024], online=False)
    assert len(r.predicted_urls) > 0, "Offline mode should still return predicted_urls"

def _chk_prediction_result_fields():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PredictionResult)}
    for req in ("domain", "years", "predicted_urls", "confirmed_dirs",
                "file_candidates", "metrics", "errors"):
        assert req in fields, f"PredictionResult missing field: {req}"

def _chk_confirmed_directory_fields():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(ConfirmedDirectory)}
    for req in ("url", "http_status", "final_url", "page_score", "classified_as",
                "file_candidates", "viewer_links", "resolved_files", "year",
                "template", "directory_priority"):
        assert req in fields, f"ConfirmedDirectory missing field: {req}"

def _chk_confirmed_directory_priority_is_high():
    import dataclasses
    fld = next(f for f in dataclasses.fields(ConfirmedDirectory) if f.name == "directory_priority")
    assert fld.default == "HIGH", f"directory_priority default should be HIGH, got {fld.default!r}"

def _chk_cross_jurisdiction_blocked():
    """A non-allowlisted domain should be rejected immediately."""
    r = predict_election_result_paths("https://example.com", [2024], online=False)
    has_error = any("BLOCKED_CROSS_JURISDICTION" in e for e in r.errors)
    assert has_error, f"Cross-jurisdiction domain should be blocked. Errors: {r.errors}"
    assert r.predicted_urls == [], "Cross-jurisdiction domain should have no predicted URLs"

def _chk_keyword_count():
    assert len(ELECTION_PAGE_KEYWORDS) >= 5, \
        f"Expected >=5 ELECTION_PAGE_KEYWORDS, got {len(ELECTION_PAGE_KEYWORDS)}"

def _chk_page_scoring_sov():
    score, classification = _score_election_page(
        "<html>Sonoma County Statement of Vote 2024 General Election</html>"
    )
    assert classification == "ELECTION_RESULTS_PAGE", \
        f"Page with 'Statement of Vote' should be ELECTION_RESULTS_PAGE, got {classification}"
    assert score > 0, f"Score should be > 0, got {score}"

def _chk_page_scoring_unrelated():
    score, classification = _score_election_page(
        "<html>Parks &amp; Recreation Department</html>"
    )
    assert classification == "OTHER", f"Unrelated page should be OTHER, got {classification}"

V.check(PHASE3, "offline returns PredictionResult",              _chk_offline_returns_prediction_result)
V.check(PHASE3, "offline has no confirmed_dirs",                 _chk_offline_no_confirmed_dirs)
V.check(PHASE3, "offline has predicted_urls",                    _chk_offline_has_predicted_urls)
V.check(PHASE3, "PredictionResult has all required fields",      _chk_prediction_result_fields)
V.check(PHASE3, "ConfirmedDirectory has all required fields",    _chk_confirmed_directory_fields)
V.check(PHASE3, "directory_priority default = HIGH",             _chk_confirmed_directory_priority_is_high)
V.check(PHASE3, "cross-jurisdiction domain blocked",             _chk_cross_jurisdiction_blocked)
V.check(PHASE3, ">=5 ELECTION_PAGE_KEYWORDS defined",            _chk_keyword_count)
V.check(PHASE3, "SoV keyword -> ELECTION_RESULTS_PAGE",          _chk_page_scoring_sov)
V.check(PHASE3, "unrelated page -> OTHER",                        _chk_page_scoring_unrelated)


# =============================================================================
# Phase 4: file_discovery Prompt 25C scoring
# =============================================================================
PHASE4 = "Phase 4: file_discovery Prompt 25C scoring"

from engine.archive_builder.file_discovery import (
    score_candidate_file,
    MIN_CANDIDATE_SCORE,
    HIGH_PRIORITY_BONUS,
    ACCEPTED_EXTENSIONS,
)

def _chk_min_score_is_060():
    assert MIN_CANDIDATE_SCORE == 0.60, \
        f"MIN_CANDIDATE_SCORE should be 0.60, got {MIN_CANDIDATE_SCORE}"

def _chk_high_priority_bonus_is_010():
    assert HIGH_PRIORITY_BONUS == 0.10, \
        f"HIGH_PRIORITY_BONUS should be 0.10, got {HIGH_PRIORITY_BONUS}"

def _chk_structured_ext_weight_035():
    """xlsx only -> should score 0.35 (not more, not less)."""
    score = score_candidate_file("results.xlsx", ".xlsx")
    assert score == 0.35, f"xlsx-only should score 0.35, got {score}"

def _chk_precinct_weight_025():
    """precinct only (no extension bonus) -> would be 0.25."""
    score = score_candidate_file("precinct.pdf", ".pdf")
    assert score == 0.25, f"precinct-only (pdf) should score 0.25, got {score}"

def _chk_statement_of_vote_keyword():
    """statement_of_vote in filename -> +0.25."""
    score = score_candidate_file("statement_of_vote_2024.xlsx", ".xlsx")
    assert score >= 0.60, \
        f"statement_of_vote + xlsx should score >=0.60, got {score}"

def _chk_high_priority_bonus_applied():
    """xlsx + precinct at normal priority vs HIGH priority."""
    normal = score_candidate_file("precinct_results.xlsx", ".xlsx", directory_priority="normal")
    high   = score_candidate_file("precinct_results.xlsx", ".xlsx", directory_priority="HIGH")
    assert high == round(min(normal + 0.10, 1.0), 3), \
        f"HIGH bonus should add 0.10: normal={normal} high={high}"

def _chk_full_high_score_xlsx_precinct_sov():
    """xlsx + precinct + statement_of_vote + HIGH = 0.35+0.25+0.25+0.10 = 0.95."""
    score = score_candidate_file(
        "statement_of_vote_precinct_results_2024.xlsx", ".xlsx",
        directory_priority="HIGH",
    )
    assert score >= 0.90, f"Full match should score >=0.90, got {score}"

def _chk_pdf_below_threshold_no_keywords():
    """Plain .pdf with no keywords at normal priority -> 0.0 < 0.60 threshold."""
    score = score_candidate_file("document.pdf", ".pdf")
    assert score < MIN_CANDIDATE_SCORE, \
        f"Plain pdf with no keywords should be below threshold, got {score}"

def _chk_directory_priority_param_exists():
    import inspect
    sig = inspect.signature(score_candidate_file)
    assert "directory_priority" in sig.parameters, \
        "score_candidate_file missing directory_priority param"

V.check(PHASE4, "MIN_CANDIDATE_SCORE = 0.60",                   _chk_min_score_is_060)
V.check(PHASE4, "HIGH_PRIORITY_BONUS = 0.10",                   _chk_high_priority_bonus_is_010)
V.check(PHASE4, "structured ext .xlsx scores exactly +0.35",    _chk_structured_ext_weight_035)
V.check(PHASE4, "'precinct' in pdf scores +0.25",               _chk_precinct_weight_025)
V.check(PHASE4, "'statement_of_vote' + xlsx >= 0.60",           _chk_statement_of_vote_keyword)
V.check(PHASE4, "HIGH priority adds +0.10 bonus",               _chk_high_priority_bonus_applied)
V.check(PHASE4, "full match xlsx+precinct+sov+HIGH >= 0.90",    _chk_full_high_score_xlsx_precinct_sov)
V.check(PHASE4, "plain pdf scores below threshold (no keywords)", _chk_pdf_below_threshold_no_keywords)
V.check(PHASE4, "directory_priority param in score_candidate_file", _chk_directory_priority_param_exists)


# =============================================================================
# Phase 5: archive_builder REQUIRED_SYSTEMS + report writers
# =============================================================================
PHASE5 = "Phase 5: archive_builder integration"

from engine.archive_builder.archive_builder import (
    REQUIRED_SYSTEMS,
    check_preconditions,
    _write_predictor_reports,
    _write_discovery_report,
    _write_archive_summary_json,
    ArchiveBuildResult,
)

def _chk_predictor_in_required():
    modules = [m for m, _ in REQUIRED_SYSTEMS]
    assert "engine.archive_builder.election_directory_predictor" in modules, \
        f"election_directory_predictor not in REQUIRED_SYSTEMS: {modules}"

def _chk_required_systems_count():
    assert len(REQUIRED_SYSTEMS) >= 10, \
        f"Expected >=10 REQUIRED_SYSTEMS, got {len(REQUIRED_SYSTEMS)}"

def _chk_write_predictor_reports_callable():
    assert callable(_write_predictor_reports), "_write_predictor_reports not callable"

def _chk_write_discovery_report_callable():
    assert callable(_write_discovery_report), "_write_discovery_report not callable"

def _chk_write_summary_json_callable():
    assert callable(_write_archive_summary_json), "_write_archive_summary_json not callable"

def _chk_archive_build_result_has_predictor_fields():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(ArchiveBuildResult)}
    for req in ("predicted_directories", "directories_confirmed",
                "directory_files_found", "directory_predictions_report",
                "archive_discovery_report"):
        assert req in fields, f"ArchiveBuildResult missing field: {req}"

def _chk_preconditions_run():
    """check_preconditions should return (bool, list) without crashing."""
    ok, missing = check_preconditions()
    assert isinstance(ok, bool)
    assert isinstance(missing, list)

V.check(PHASE5, "election_directory_predictor in REQUIRED_SYSTEMS", _chk_predictor_in_required)
V.check(PHASE5, "REQUIRED_SYSTEMS has >=10 entries",               _chk_required_systems_count)
V.check(PHASE5, "_write_predictor_reports is callable",            _chk_write_predictor_reports_callable)
V.check(PHASE5, "_write_discovery_report is callable",             _chk_write_discovery_report_callable)
V.check(PHASE5, "_write_archive_summary_json is callable",         _chk_write_summary_json_callable)
V.check(PHASE5, "ArchiveBuildResult has predictor fields",         _chk_archive_build_result_has_predictor_fields)
V.check(PHASE5, "check_preconditions() runs without error",        _chk_preconditions_run)


# =============================================================================
# Phase 6: Report file generation (offline build)
# =============================================================================
PHASE6 = "Phase 6: Report generation (offline build)"

from engine.archive_builder.archive_builder import run_archive_build

def _run_offline_build():
    return run_archive_build(
        state="CA", county="Sonoma",
        online=False, download=False,
        run_id=f"p25c_val_{RUN_ID}",
        abort_on_precondition_fail=False,
    )

def _chk_offline_build_runs():
    result = _run_offline_build()
    assert result is not None, "run_archive_build should return ArchiveBuildResult"
    assert isinstance(result, ArchiveBuildResult)

def _chk_directory_predictions_md_written():
    result = _run_offline_build()
    if result.directory_predictions_report:
        p = Path(result.directory_predictions_report)
        assert p.exists(), f"directory_predictions.md not found: {p}"
    else:
        # Report written separately -- check REPORTS_DIR
        matches = list(REPORTS_DIR.glob("*p25c_val*__directory_predictions.md"))
        assert len(matches) > 0, "directory_predictions.md not found in reports/"

def _chk_archive_discovery_report_written():
    result = _run_offline_build()
    if result.archive_discovery_report:
        p = Path(result.archive_discovery_report)
        assert p.exists(), f"archive_discovery_report.md not found: {p}"
    else:
        matches = list(REPORTS_DIR.glob("*p25c_val*__archive_discovery_report.md"))
        assert len(matches) > 0, "archive_discovery_report.md not found in reports/"

def _chk_predictor_result_metrics_structure():
    """Predictor offline result should have metrics dict (even if empty)."""
    r = predict_election_result_paths(DOMAIN, [2024, 2022], online=False)
    assert isinstance(r.metrics, dict), f"metrics should be dict, got {type(r.metrics)}"
    assert "predicted" in r.metrics, f"metrics missing 'predicted' key: {r.metrics}"

V.check(PHASE6, "offline build returns ArchiveBuildResult",        _chk_offline_build_runs)
V.check(PHASE6, "directory_predictions.md written",                _chk_directory_predictions_md_written)
V.check(PHASE6, "archive_discovery_report.md written",             _chk_archive_discovery_report_written)
V.check(PHASE6, "predictor metrics dict has 'predicted' key",      _chk_predictor_result_metrics_structure)


# =============================================================================
# Summary
# =============================================================================

summary = V.summary()
phase_order = [PHASE1, PHASE2, PHASE3, PHASE4, PHASE5, PHASE6]

print()
print("=" * 70)
print(f"  Prompt 25C Validation -- {RUN_ID}")
print("=" * 70)

for phase in phase_order:
    pr = [r for r in V.results if r["phase"] == phase]
    pp = sum(1 for r in pr if r["status"] == "PASS")
    label = f"PASS {pp}/{len(pr)}" if pp == len(pr) else f"FAIL {pp}/{len(pr)}"
    print(f"\n  {phase}  [{label}]")
    for r in pr:
        icon = "OK" if r["status"] == "PASS" else "FAIL"
        print(f"    [{icon}] {r['name']}")
        if r.get("error"):
            print(f"         => {r['error']}")

print()
print("-" * 70)
print(f"  TOTAL: {summary['passed']}/{summary['total']} PASS ({summary['pass_rate']}%)")
print("=" * 70)
print()

md = [
    f"# Prompt 25C Validation -- {RUN_ID}",
    f"**Generated:** {datetime.now().isoformat()}",
    "",
    f"## Summary: {summary['passed']}/{summary['total']} PASS ({summary['pass_rate']}%)",
    "",
    "| Phase | Pass | Total |",
    "|-------|------|-------|",
]
for phase in phase_order:
    pr = [r for r in V.results if r["phase"] == phase]
    pp = sum(1 for r in pr if r["status"] == "PASS")
    md.append(f"| {phase} | {pp} | {len(pr)} |")

md += ["", "## Details", ""]
for phase in phase_order:
    md.append(f"\n### {phase}\n")
    for r in [x for x in V.results if x["phase"] == phase]:
        icon = "PASS" if r["status"] == "PASS" else "FAIL"
        md.append(f"- [{icon}] {r['name']}")
        if r.get("error"):
            md.append(f"  - `{r['error']}`")

REPORT_MD.write_text("\n".join(md), encoding="utf-8")
REPORT_JSON.write_text(
    json.dumps({"run_id": RUN_ID, "summary": summary, "results": V.results}, indent=2),
    encoding="utf-8",
)
print(f"  Reports: {REPORT_MD.name}")
print()

if summary["passed"] < summary["total"]:
    sys.exit(1)
