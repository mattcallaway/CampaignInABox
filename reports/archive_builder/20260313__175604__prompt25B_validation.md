# Prompt 25B Validation — 20260313__175604
**Generated:** 2026-03-13T17:56:04.827531

## Summary: 58/58 PASS (100.0%)

| Phase | Pass | Total |
|-------|------|-------|
| Phase 1: Required systems | 8 | 8 |
| Phase 2: link_extractor | 10 | 10 |
| Phase 3: viewer_resolver | 9 | 9 |
| Phase 4: page_explorer | 7 | 7 |
| Phase 5: page_discovery scoring | 9 | 9 |
| Phase 6: file_discovery | 6 | 6 |
| Phase 7: file_downloader | 9 | 9 |

## Details


### Phase 1: Required systems

- [PASS] link_extractor importable
- [PASS] viewer_resolver importable
- [PASS] page_explorer importable
- [PASS] page_discovery importable
- [PASS] file_discovery importable
- [PASS] file_downloader importable
- [PASS] archive_builder importable
- [PASS] campaign_state_resolver importable

### Phase 2: link_extractor

- [PASS] extract_links returns ExtractedLinks
- [PASS] href links extracted
- [PASS] file links categorized (.xlsx/.csv)
- [PASS] DocumentCenter viewer links detected
- [PASS] onclick JS links extracted
- [PASS] data-document-url / data-url extracted
- [PASS] window.open() links extracted
- [PASS] all links normalized to absolute URLs
- [PASS] filter_same_domain works correctly
- [PASS] .pdf in link_extractor ACCEPTED_EXTENSIONS

### Phase 3: viewer_resolver

- [PASS] DocumentCenter/View detected as viewer
- [PASS] download.aspx detected as viewer
- [PASS] ViewFile.aspx detected as viewer
- [PASS] direct .xlsx not flagged as viewer
- [PASS] HTML page URL not flagged as viewer
- [PASS] direct file passthrough resolves immediately
- [PASS] resolve_batch returns list[ViewerResult]
- [PASS] ViewerResult has all required fields
- [PASS] CivicEngage /Download candidate generated

### Phase 4: page_explorer

- [PASS] ExplorationResult has all required fields
- [PASS] ExploredPage has all required fields
- [PASS] explore offline returns ExplorationResult
- [PASS] visited URL set prevents duplicate visits
- [PASS] MAX_PAGES_PER_DEPTH is 25
- [PASS] MIN_PAGE_SCORE is 0.10
- [PASS] offline: no false cross-jurisdiction errors

### Phase 5: page_discovery scoring

- [PASS] URL with 'results' scores 0.30
- [PASS] non-election URL scores 0.0
- [PASS] 'Statement of Vote' keyword += 0.30
- [PASS] 'Precinct Results' keyword += 0.20
- [PASS] 'Detailed Results' keyword += 0.20
- [PASS] all 3 content factors combined >= 0.65
- [PASS] election URL + all content terms >= 0.50
- [PASS] MIN_PAGE_SCORE is 0.20
- [PASS] irrelevant page scores below MIN_PAGE_SCORE

### Phase 6: file_discovery

- [PASS] .pdf in ACCEPTED_EXTENSIONS
- [PASS] .pdf not in REJECTED_EXTENSIONS
- [PASS] CandidateFile has page_depth field
- [PASS] CandidateFile has candidate_score field
- [PASS] xlsx scores higher than pdf for same filename
- [PASS] .jpeg remains in REJECTED_EXTENSIONS

### Phase 7: file_downloader

- [PASS] _compute_hash function exists
- [PASS] _compute_hash produces correct SHA-256
- [PASS] _register_file has page_depth param
- [PASS] _register_file has candidate_score param
- [PASS] _register_file has file_hash param
- [PASS] download_candidate_file has page_depth
- [PASS] download_candidate_file has candidate_score
- [PASS] .pdf in file_downloader ACCEPTED_EXTENSIONS
- [PASS] registry_summary() runs without error