# Prompt 25C Validation -- 20260313__185028
**Generated:** 2026-03-13T18:50:28.512308

## Summary: 44/46 PASS (95.7%)

| Phase | Pass | Total |
|-------|------|-------|
| Phase 1: Required systems | 8 | 8 |
| Phase 2: Predictor URL generation | 8 | 8 |
| Phase 3: Offline mode / dataclasses / jurisdiction guard | 10 | 10 |
| Phase 4: file_discovery Prompt 25C scoring | 9 | 9 |
| Phase 5: archive_builder integration | 7 | 7 |
| Phase 6: Report generation (offline build) | 2 | 4 |

## Details


### Phase 1: Required systems

- [PASS] election_directory_predictor importable
- [PASS] link_extractor importable
- [PASS] viewer_resolver importable
- [PASS] page_explorer importable
- [PASS] file_discovery importable
- [PASS] file_downloader importable
- [PASS] archive_builder importable
- [PASS] campaign_state_resolver importable

### Phase 2: Predictor URL generation

- [PASS] 10 PATH_TEMPLATES defined
- [PASS] DEFAULT_YEARS = [2024..2020]
- [PASS] URL generation produces >=30 candidates
- [PASS] all generated URLs are absolute https://
- [PASS] year-parameterized templates include year
- [PASS] no duplicate URLs in generated set
- [PASS] {year}-general-election template present
- [PASS] registrar-of-voters template present

### Phase 3: Offline mode / dataclasses / jurisdiction guard

- [PASS] offline returns PredictionResult
- [PASS] offline has no confirmed_dirs
- [PASS] offline has predicted_urls
- [PASS] PredictionResult has all required fields
- [PASS] ConfirmedDirectory has all required fields
- [PASS] directory_priority default = HIGH
- [PASS] cross-jurisdiction domain blocked
- [PASS] >=5 ELECTION_PAGE_KEYWORDS defined
- [PASS] SoV keyword -> ELECTION_RESULTS_PAGE
- [PASS] unrelated page -> OTHER

### Phase 4: file_discovery Prompt 25C scoring

- [PASS] MIN_CANDIDATE_SCORE = 0.60
- [PASS] HIGH_PRIORITY_BONUS = 0.10
- [PASS] structured ext .xlsx scores exactly +0.35
- [PASS] 'precinct' in pdf scores +0.25
- [PASS] 'statement_of_vote' + xlsx >= 0.60
- [PASS] HIGH priority adds +0.10 bonus
- [PASS] full match xlsx+precinct+sov+HIGH >= 0.90
- [PASS] plain pdf scores below threshold (no keywords)
- [PASS] directory_priority param in score_candidate_file

### Phase 5: archive_builder integration

- [PASS] election_directory_predictor in REQUIRED_SYSTEMS
- [PASS] REQUIRED_SYSTEMS has >=10 entries
- [PASS] _write_predictor_reports is callable
- [PASS] _write_discovery_report is callable
- [PASS] _write_archive_summary_json is callable
- [PASS] ArchiveBuildResult has predictor fields
- [PASS] check_preconditions() runs without error

### Phase 6: Report generation (offline build)

- [PASS] offline build returns ArchiveBuildResult
- [FAIL] directory_predictions.md written
  - `directory_predictions.md not found in reports/`
- [FAIL] archive_discovery_report.md written
  - `archive_discovery_report.md not found in reports/`
- [PASS] predictor metrics dict has 'predicted' key