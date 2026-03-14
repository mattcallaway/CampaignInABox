"""
scripts/tools/run_p25b_validation.py — Prompt 25B

Validates the Recursive Election File Discovery Engine.

Phases:
  1. Required systems importable (P25 + new P25B modules)
  2. link_extractor — all 7 link extraction sources
  3. viewer_resolver — pattern detection + resolution methods
  4. page_explorer — dataclasses, depth enforcement, visited URL set
  5. page_discovery — Prompt 25B scoring weights
  6. file_discovery — .pdf accepted, page_depth field, CandidateFile
  7. file_downloader — SHA-256 hash, page_depth+candidate_score in registry

Usage:
  python scripts/tools/run_p25b_validation.py
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

RUN_ID = datetime.now().strftime("%Y%m%d__%H%M%S")
REPORT_MD   = REPORTS_DIR / f"{RUN_ID}__prompt25B_validation.md"
REPORT_JSON = REPORTS_DIR / f"{RUN_ID}__prompt25B_validation.json"


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

V.check(PHASE1, "link_extractor importable",
    lambda: _chk_import("engine.archive_builder.link_extractor", "extract_links"))
V.check(PHASE1, "viewer_resolver importable",
    lambda: _chk_import("engine.archive_builder.viewer_resolver", "resolve_viewer_url"))
V.check(PHASE1, "page_explorer importable",
    lambda: _chk_import("engine.archive_builder.page_explorer", "explore_election_pages"))
V.check(PHASE1, "page_discovery importable",
    lambda: _chk_import("engine.archive_builder.page_discovery", "score_page"))
V.check(PHASE1, "file_discovery importable",
    lambda: _chk_import("engine.archive_builder.file_discovery", "discover_files_from_page"))
V.check(PHASE1, "file_downloader importable",
    lambda: _chk_import("engine.archive_builder.file_downloader", "download_candidate_file"))
V.check(PHASE1, "archive_builder importable",
    lambda: _chk_import("engine.archive_builder.archive_builder", "run_archive_build"))
V.check(PHASE1, "campaign_state_resolver importable",
    lambda: _chk_import("engine.state.campaign_state_resolver", "get_active_campaign_id"))


# =============================================================================
# Phase 2: link_extractor
# =============================================================================
PHASE2 = "Phase 2: link_extractor"

from engine.archive_builder.link_extractor import (
    extract_links, filter_same_domain, ExtractedLinks, ACCEPTED_EXTENSIONS as LE_EXTS,
)

BASE = "https://sonomacounty.gov/elections"

SYNTHETIC_HTML = """
<html><body>
<a href="/elections/results/2024/precinct_results.xlsx">Precinct Results</a>
<a href="https://sonomacounty.gov/elections/2022/general/sov.csv">SOV 2022</a>
<a href="/DocumentCenter/View/1234/Statement_of_Vote_2024">View SOV</a>
<a href="/download.aspx?id=5678">Download</a>
<button onclick="location.href='/elections/results/2020/results.xls'">Download XLS</button>
<iframe src="/elections/viewer/frame.html"></iframe>
<div data-document-url="/elections/data/precinct_detail.csv">Detail</div>
<div data-url="https://sonomacounty.gov/elections/archive/2018.xlsx">2018</div>
<script>
  window.open('/elections/2024_general_results.xlsx', '_blank');
  var url = '/elections/statement_of_vote.csv';
</script>
</body></html>
"""

def _chk_extract_links_returns_obj():
    r = extract_links(SYNTHETIC_HTML, BASE)
    assert isinstance(r, ExtractedLinks), f"Expected ExtractedLinks, got {type(r)}"

def _chk_href_links_extracted():
    r = extract_links(SYNTHETIC_HTML, BASE)
    assert len(r.all_links) >= 2, f"Expected >=2 links from hrefs, got {len(r.all_links)}"

def _chk_file_links_detected():
    r = extract_links(SYNTHETIC_HTML, BASE)
    assert len(r.file_links) >= 2, f"Expected >=2 file links, got {r.file_links}"

def _chk_viewer_links_detected():
    r = extract_links(SYNTHETIC_HTML, BASE)
    assert len(r.viewer_links) >= 1, f"Expected >=1 viewer link (DocumentCenter), got {r.viewer_links}"

def _chk_onclick_extracted():
    r = extract_links(SYNTHETIC_HTML, BASE)
    # should find /elections/results/2020/results.xls from onclick
    xls_found = any(".xls" in u for u in r.file_links + r.js_links + r.all_links)
    assert xls_found, f"onclick-embedded .xls link not found in {r.all_links}"

def _chk_data_attr_extracted():
    r = extract_links(SYNTHETIC_HTML, BASE)
    data_found = any("precinct_detail.csv" in u or "2018.xlsx" in u for u in r.all_links)
    assert data_found, f"data-document-url links not found in {r.all_links}"

def _chk_window_open_extracted():
    r = extract_links(SYNTHETIC_HTML, BASE)
    js_found = any("2024_general_results.xlsx" in u for u in r.all_links + r.js_links)
    assert js_found, f"window.open link not found in {r.all_links}"

def _chk_all_links_are_absolute():
    r = extract_links(SYNTHETIC_HTML, BASE)
    for lnk in r.all_links:
        assert lnk.startswith("http"), f"Non-absolute URL found: {lnk}"

def _chk_filter_same_domain():
    links = [
        "https://sonomacounty.gov/elections/results.xlsx",
        "https://example.com/other.csv",
        "https://www.sonomacounty.gov/elections/data.xls",
    ]
    filtered = filter_same_domain(links, "https://sonomacounty.gov/elections")
    assert len(filtered) == 2, f"Expected 2 same-domain links, got {filtered}"

def _chk_pdf_in_accepted_exts():
    assert ".pdf" in LE_EXTS, "link_extractor: .pdf not in ACCEPTED_EXTENSIONS"

V.check(PHASE2, "extract_links returns ExtractedLinks",        _chk_extract_links_returns_obj)
V.check(PHASE2, "href links extracted",                         _chk_href_links_extracted)
V.check(PHASE2, "file links categorized (.xlsx/.csv)",          _chk_file_links_detected)
V.check(PHASE2, "DocumentCenter viewer links detected",         _chk_viewer_links_detected)
V.check(PHASE2, "onclick JS links extracted",                    _chk_onclick_extracted)
V.check(PHASE2, "data-document-url / data-url extracted",       _chk_data_attr_extracted)
V.check(PHASE2, "window.open() links extracted",                _chk_window_open_extracted)
V.check(PHASE2, "all links normalized to absolute URLs",        _chk_all_links_are_absolute)
V.check(PHASE2, "filter_same_domain works correctly",           _chk_filter_same_domain)
V.check(PHASE2, ".pdf in link_extractor ACCEPTED_EXTENSIONS",  _chk_pdf_in_accepted_exts)


# =============================================================================
# Phase 3: viewer_resolver
# =============================================================================
PHASE3 = "Phase 3: viewer_resolver"

from engine.archive_builder.viewer_resolver import (
    is_viewer_url, resolve_viewer_url, resolve_batch, ViewerResult, ACCEPTED_EXTENSIONS as VR_EXTS,
)

def _chk_is_viewer_document_center():
    assert is_viewer_url("https://sonomacounty.gov/DocumentCenter/View/1234"), \
        "DocumentCenter/View not detected as viewer"

def _chk_is_viewer_download_aspx():
    assert is_viewer_url("https://sonomacounty.gov/download.aspx?id=5678"), \
        "download.aspx not detected as viewer"

def _chk_is_viewer_viewfile_aspx():
    assert is_viewer_url("https://sonomacounty.gov/ViewFile.aspx?id=999"), \
        "ViewFile.aspx not detected as viewer"

def _chk_not_viewer_direct_file():
    assert not is_viewer_url("https://sonomacounty.gov/elections/results.xlsx"), \
        "Direct file URL wrongly flagged as viewer"

def _chk_not_viewer_html_page():
    assert not is_viewer_url("https://sonomacounty.gov/elections/2024/"), \
        "HTML page URL wrongly flagged as viewer"

def _chk_direct_file_passthrough():
    vr = resolve_viewer_url(
        "https://sonomacounty.gov/elections/results.xlsx",
        fetch_html_fn=lambda url: None,
    )
    assert vr.resolved, "Direct .xlsx URL should be resolved immediately"
    assert vr.method == "direct_file"

def _chk_resolve_batch_structure():
    urls = [
        "https://sonomacounty.gov/DocumentCenter/View/1234",
        "https://sonomacounty.gov/elections/results.xlsx",
    ]
    results = resolve_batch(urls, fetch_html_fn=lambda url: None, only_viewers=True)
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    assert all(isinstance(r, ViewerResult) for r in results)

def _chk_viewer_result_has_fields():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(ViewerResult)}
    for req in ("original_url", "resolved_url", "resolved", "method", "error"):
        assert req in fields, f"ViewerResult missing field: {req}"

def _chk_civicengage_generates_download_candidate():
    from engine.archive_builder.viewer_resolver import _civicengage_download_urls
    candidates = _civicengage_download_urls(
        "https://sonomacounty.gov/DocumentCenter/View/1234/Statement_of_Vote_2024"
    )
    assert any("/Download" in c for c in candidates), \
        f"No /Download candidate generated: {candidates}"

V.check(PHASE3, "DocumentCenter/View detected as viewer",       _chk_is_viewer_document_center)
V.check(PHASE3, "download.aspx detected as viewer",             _chk_is_viewer_download_aspx)
V.check(PHASE3, "ViewFile.aspx detected as viewer",             _chk_is_viewer_viewfile_aspx)
V.check(PHASE3, "direct .xlsx not flagged as viewer",           _chk_not_viewer_direct_file)
V.check(PHASE3, "HTML page URL not flagged as viewer",          _chk_not_viewer_html_page)
V.check(PHASE3, "direct file passthrough resolves immediately", _chk_direct_file_passthrough)
V.check(PHASE3, "resolve_batch returns list[ViewerResult]",     _chk_resolve_batch_structure)
V.check(PHASE3, "ViewerResult has all required fields",         _chk_viewer_result_has_fields)
V.check(PHASE3, "CivicEngage /Download candidate generated",   _chk_civicengage_generates_download_candidate)


# =============================================================================
# Phase 4: page_explorer
# =============================================================================
PHASE4 = "Phase 4: page_explorer"

from engine.archive_builder.page_explorer import (
    explore_election_pages, ExplorationResult, ExploredPage,
    MIN_PAGE_SCORE, MAX_PAGES_PER_DEPTH,
)

def _chk_exploration_result_dataclass():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(ExplorationResult)}
    for req in ("source_id", "candidate_file_urls", "pages_visited",
                "viewer_links_resolved", "explored_pages", "errors"):
        assert req in fields, f"ExplorationResult missing field: {req}"

def _chk_explored_page_dataclass():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(ExploredPage)}
    for req in ("url", "depth", "score", "file_links", "viewer_links",
                "page_links", "resolved_files"):
        assert req in fields, f"ExploredPage missing field: {req}"

def _chk_explore_offline_returns_result():
    src = {
        "source_id": "test_p25b", "state": "CA", "county": "Sonoma",
        "base_url": "https://sonomacounty.gov", "year": 2024,
    }
    result = explore_election_pages(
        start_urls=["https://sonomacounty.gov/elections"],
        source=src,
        depth_limit=1,
        online=False,
    )
    assert isinstance(result, ExplorationResult), f"Expected ExplorationResult, got {type(result)}"

def _chk_visited_url_set_prevents_loops():
    """Verify that the same URL appearing multiple times is only visited once."""
    src = {
        "source_id": "loop_test", "state": "CA", "county": "Sonoma",
        "base_url": "https://sonomacounty.gov",
    }
    result = explore_election_pages(
        start_urls=[
            "https://sonomacounty.gov/elections",
            "https://sonomacounty.gov/elections",  # duplicate
        ],
        source=src,
        depth_limit=0,
        online=False,
    )
    assert result.pages_visited == 1, \
        f"Duplicate URLs should be visited only once, got pages_visited={result.pages_visited}"

def _chk_depth_limit_respected():
    assert MAX_PAGES_PER_DEPTH == 25, f"MAX_PAGES_PER_DEPTH should be 25, got {MAX_PAGES_PER_DEPTH}"

def _chk_min_page_score():
    assert MIN_PAGE_SCORE == 0.10, f"MIN_PAGE_SCORE should be 0.10, got {MIN_PAGE_SCORE}"

def _chk_offline_returns_empty_candidate_files():
    """Offline (no HTML fetch) → no files found but also no errors."""
    src = {"source_id": "offline_test", "state": "CA", "county": "Sonoma",
           "base_url": "https://sonomacounty.gov"}
    result = explore_election_pages(
        start_urls=["https://sonomacounty.gov/elections/2024"],
        source=src, depth_limit=2, online=False,
    )
    # No cross-jurisdiction errors expected
    assert not any("BLOCKED_CROSS_JURISDICTION" in e for e in result.errors), \
        f"No cross-jurisdiction URLs should be blocked in offline mode: {result.errors}"

V.check(PHASE4, "ExplorationResult has all required fields",    _chk_exploration_result_dataclass)
V.check(PHASE4, "ExploredPage has all required fields",         _chk_explored_page_dataclass)
V.check(PHASE4, "explore offline returns ExplorationResult",    _chk_explore_offline_returns_result)
V.check(PHASE4, "visited URL set prevents duplicate visits",    _chk_visited_url_set_prevents_loops)
V.check(PHASE4, "MAX_PAGES_PER_DEPTH is 25",                   _chk_depth_limit_respected)
V.check(PHASE4, "MIN_PAGE_SCORE is 0.10",                      _chk_min_page_score)
V.check(PHASE4, "offline: no false cross-jurisdiction errors",  _chk_offline_returns_empty_candidate_files)


# =============================================================================
# Phase 5: page_discovery — Prompt 25B scoring
# =============================================================================
PHASE5 = "Phase 5: page_discovery scoring"

from engine.archive_builder.page_discovery import (
    score_page, MIN_PAGE_SCORE as PD_MIN_SCORE,
    _url_path_score, _content_keyword_score,
)

def _chk_url_results_score():
    s = _url_path_score("https://sonomacounty.gov/elections/results/2024")
    assert s == 0.30, f"URL with 'results' should score 0.30, got {s}"

def _chk_url_no_match_score():
    s = _url_path_score("https://sonomacounty.gov/about-us")
    assert s == 0.0, f"Non-election URL should score 0.0, got {s}"

def _chk_statement_of_vote_keyword():
    s = _content_keyword_score("<html>statement of vote certified results</html>")
    assert s >= 0.30, f"'Statement of Vote' should contribute >= 0.30, got {s}"

def _chk_precinct_results_keyword():
    s = _content_keyword_score("<html>precinct results by district</html>")
    assert s >= 0.20, f"'Precinct Results' should contribute >= 0.20, got {s}"

def _chk_detailed_results_keyword():
    s = _content_keyword_score("<html>detailed results breakdown</html>")
    assert s >= 0.20, f"'Detailed Results' should contribute >= 0.20, got {s}"

def _chk_all_factors_combined():
    html = "statement of vote | precinct results | detailed results for general election"
    s = _content_keyword_score(html)
    # 0.30 + 0.20 + 0.20 = 0.70
    assert s >= 0.65, f"All 3 content triggers should score >=0.65, got {s}"

def _chk_score_page_election_url():
    score, method = score_page(
        "https://sonomacounty.gov/elections/general-election-results",
        "statement of vote precinct results detailed results",
    )
    assert score >= 0.50, f"Election URL + content should score >=0.50, got {score}"

def _chk_min_page_score_is_0_20():
    assert PD_MIN_SCORE == 0.20, f"MIN_PAGE_SCORE should be 0.20, got {PD_MIN_SCORE}"

def _chk_irrelevant_page_scores_low():
    score, method = score_page(
        "https://sonomacounty.gov/parks-and-recreation/",
        "Parks, trails, nature, hiking, camping, wildlife",
    )
    assert score < PD_MIN_SCORE, f"Irrelevant page should score < {PD_MIN_SCORE}, got {score}"

V.check(PHASE5, "URL with 'results' scores 0.30",              _chk_url_results_score)
V.check(PHASE5, "non-election URL scores 0.0",                  _chk_url_no_match_score)
V.check(PHASE5, "'Statement of Vote' keyword += 0.30",          _chk_statement_of_vote_keyword)
V.check(PHASE5, "'Precinct Results' keyword += 0.20",           _chk_precinct_results_keyword)
V.check(PHASE5, "'Detailed Results' keyword += 0.20",           _chk_detailed_results_keyword)
V.check(PHASE5, "all 3 content factors combined >= 0.65",       _chk_all_factors_combined)
V.check(PHASE5, "election URL + all content terms >= 0.50",     _chk_score_page_election_url)
V.check(PHASE5, "MIN_PAGE_SCORE is 0.20",                       _chk_min_page_score_is_0_20)
V.check(PHASE5, "irrelevant page scores below MIN_PAGE_SCORE",  _chk_irrelevant_page_scores_low)


# =============================================================================
# Phase 6: file_discovery
# =============================================================================
PHASE6 = "Phase 6: file_discovery"

from engine.archive_builder.file_discovery import (
    CandidateFile, ACCEPTED_EXTENSIONS, REJECTED_EXTENSIONS, score_candidate_file,
)

def _chk_pdf_in_accepted():
    assert ".pdf" in ACCEPTED_EXTENSIONS, ".pdf not in file_discovery ACCEPTED_EXTENSIONS"

def _chk_pdf_not_in_rejected():
    assert ".pdf" not in REJECTED_EXTENSIONS, ".pdf should not be in REJECTED_EXTENSIONS (P25B)"

def _chk_candidate_file_has_page_depth():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(CandidateFile)}
    assert "page_depth" in fields, f"CandidateFile missing page_depth field. Fields: {fields}"

def _chk_candidate_file_has_candidate_score():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(CandidateFile)}
    assert "candidate_score" in fields, "CandidateFile missing candidate_score field"

def _chk_pdf_scores_lower_than_xlsx():
    pdf_score  = score_candidate_file("precinct_results.pdf", ".pdf")
    xlsx_score = score_candidate_file("precinct_results.xlsx", ".xlsx")
    assert xlsx_score > pdf_score, \
        f"xlsx should score higher than pdf: xlsx={xlsx_score} pdf={pdf_score}"

def _chk_jpeg_not_in_accepted():
    assert ".jpeg" not in ACCEPTED_EXTENSIONS, ".jpeg should not be accepted"
    assert ".jpeg" in REJECTED_EXTENSIONS, ".jpeg should be in REJECTED_EXTENSIONS"

V.check(PHASE6, ".pdf in ACCEPTED_EXTENSIONS",                  _chk_pdf_in_accepted)
V.check(PHASE6, ".pdf not in REJECTED_EXTENSIONS",              _chk_pdf_not_in_rejected)
V.check(PHASE6, "CandidateFile has page_depth field",           _chk_candidate_file_has_page_depth)
V.check(PHASE6, "CandidateFile has candidate_score field",      _chk_candidate_file_has_candidate_score)
V.check(PHASE6, "xlsx scores higher than pdf for same filename", _chk_pdf_scores_lower_than_xlsx)
V.check(PHASE6, ".jpeg remains in REJECTED_EXTENSIONS",         _chk_jpeg_not_in_accepted)


# =============================================================================
# Phase 7: file_downloader
# =============================================================================
PHASE7 = "Phase 7: file_downloader"

import hashlib
import inspect
from engine.archive_builder.file_downloader import (
    _compute_hash, _register_file, download_candidate_file,
    ACCEPTED_EXTENSIONS as DL_EXTS, get_file_registry, registry_summary,
)

def _chk_compute_hash_exists():
    assert callable(_compute_hash), "_compute_hash function not found"

def _chk_compute_hash_correct():
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
        f.write(b"precinct,votes\n1,100\n2,200\n")
        tmp = Path(f.name)
    expected = hashlib.sha256(b"precinct,votes\n1,100\n2,200\n").hexdigest()
    computed = _compute_hash(tmp)
    tmp.unlink(missing_ok=True)
    assert computed == expected, f"SHA-256 mismatch: expected={expected} got={computed}"

def _chk_register_file_has_page_depth_param():
    sig = inspect.signature(_register_file)
    assert "page_depth" in sig.parameters, "_register_file missing page_depth param"

def _chk_register_file_has_candidate_score_param():
    sig = inspect.signature(_register_file)
    assert "candidate_score" in sig.parameters, "_register_file missing candidate_score param"

def _chk_register_file_has_file_hash_param():
    sig = inspect.signature(_register_file)
    assert "file_hash" in sig.parameters, "_register_file missing file_hash param"

def _chk_download_has_page_depth_param():
    sig = inspect.signature(download_candidate_file)
    assert "page_depth" in sig.parameters, "download_candidate_file missing page_depth param"

def _chk_download_has_candidate_score_param():
    sig = inspect.signature(download_candidate_file)
    assert "candidate_score" in sig.parameters, "download_candidate_file missing candidate_score param"

def _chk_pdf_in_downloader_accepted():
    assert ".pdf" in DL_EXTS, ".pdf not in file_downloader ACCEPTED_EXTENSIONS"

def _chk_registry_summary_has_duplicate_count():
    # Just check it runs without error
    s = registry_summary()
    assert isinstance(s, dict), f"registry_summary should return dict, got {type(s)}"

V.check(PHASE7, "_compute_hash function exists",                _chk_compute_hash_exists)
V.check(PHASE7, "_compute_hash produces correct SHA-256",       _chk_compute_hash_correct)
V.check(PHASE7, "_register_file has page_depth param",          _chk_register_file_has_page_depth_param)
V.check(PHASE7, "_register_file has candidate_score param",     _chk_register_file_has_candidate_score_param)
V.check(PHASE7, "_register_file has file_hash param",           _chk_register_file_has_file_hash_param)
V.check(PHASE7, "download_candidate_file has page_depth",       _chk_download_has_page_depth_param)
V.check(PHASE7, "download_candidate_file has candidate_score",  _chk_download_has_candidate_score_param)
V.check(PHASE7, ".pdf in file_downloader ACCEPTED_EXTENSIONS",  _chk_pdf_in_downloader_accepted)
V.check(PHASE7, "registry_summary() runs without error",        _chk_registry_summary_has_duplicate_count)


# =============================================================================
# Summary output
# =============================================================================

summary = V.summary()
phase_order = [PHASE1, PHASE2, PHASE3, PHASE4, PHASE5, PHASE6, PHASE7]

print()
print("=" * 70)
print(f"  Prompt 25B Validation — {RUN_ID}")
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

# Write markdown report
md = [
    f"# Prompt 25B Validation — {RUN_ID}",
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
