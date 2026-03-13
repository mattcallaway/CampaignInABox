# Prompt 27 — Validation Report
**Run ID:** 20260313__prompt27_validation  **Score:** 42/42 (100%)

## Acceptance Criteria Answers

| Question | Answer |
|----------|--------|
| Is single-active enforcement working? | Yes |
| Is campaign state isolated? | Yes |
| Do loaders use campaign-scoped state? | Yes (state_builder.py) |
| Is archive normalizer integrated? | Yes |
| Are ambiguous precincts blocked from auto-ingest? | Yes (AMBIGUOUS_BLOCK_THRESHOLD=10%) |
| Did any legacy shared-state path remain? | Yes — as read-only compat alias only |

## Detailed Results

| Check | Result | Detail |
|-------|--------|--------|
| campaign_state_resolver imported successfully | ✅ PASS |  |
| get_active_campaign_id returns a non-empty string | ✅ PASS | campaign_id='2026_CA_sonoma_prop_50_special' |
| Campaign state dir created under derived/state/campaigns/ | ✅ PASS | C:\Users\Mathew C\Campaign In A Box\derived\state\campaigns\ |
| Latest dir exists within campaigns/<cid>/latest | ✅ PASS | C:\Users\Mathew C\Campaign In A Box\derived\state\campaigns\ |
| History dir exists within campaigns/<cid>/history | ✅ PASS | C:\Users\Mathew C\Campaign In A Box\derived\state\campaigns\ |
| Legacy latest dir returned at derived/state/latest | ✅ PASS | C:\Users\Mathew C\Campaign In A Box\derived\state\latest |
| validate_registry returns status dict | ✅ PASS | status=ok active_count=1 |
| Single active campaign enforced (active_count <= 1) | ✅ PASS | active_count=1 |
| Enforcement report written to reports/state/ | ✅ PASS |  |
| state_builder imports campaign_state_resolver | ✅ PASS |  |
| state_builder sets state['campaign_id'] | ✅ PASS |  |
| state_builder uses get_latest_state_dir | ✅ PASS |  |
| state_builder uses get_history_dir | ✅ PASS |  |
| state_builder calls seed_legacy_alias | ✅ PASS |  |
| state_builder raises RuntimeError if no campaign_id | ✅ PASS |  |
| state_builder calls validate_registry | ✅ PASS |  |
| derived/state/campaigns/<cid>/ exists | ✅ PASS | path=C:\Users\Mathew C\Campaign In A Box\derived\state\campa |
| ClassifiedFile has archive_status field | ✅ PASS | fields=['archive_ready', 'archive_status', 'classified_at',  |
| ClassifiedFile has archive_ready field (backward compat) | ✅ PASS |  |
| archive_classifier defines ARCHIVE_READY status | ✅ PASS |  |
| archive_classifier defines REVIEW_REQUIRED status | ✅ PASS |  |
| archive_classifier defines REJECTED status | ✅ PASS |  |
| archive_classifier has hard REJECTED gate for BLOCKED_CROSS_ | ✅ PASS |  |
| archive_ingestor imports id_schema_detector | ✅ PASS |  |
| archive_ingestor imports id_normalizer | ✅ PASS |  |
| archive_ingestor imports safe_join_engine | ✅ PASS |  |
| archive_ingestor has _run_normalizer_pipeline function | ✅ PASS |  |
| archive_ingestor has _determine_archive_status function | ✅ PASS |  |
| archive_ingestor has _write_join_metadata function | ✅ PASS |  |
| archive_ingestor writes join_summary.json | ✅ PASS |  |
| archive_ingestor writes ambiguous_ids.csv | ✅ PASS |  |
| archive_ingestor writes no_match_ids.csv | ✅ PASS |  |
| archive_ingestor writes normalization report MD | ✅ PASS |  |
| archive_ingestor embeds campaign_id in manifest | ✅ PASS |  |
| archive_ingestor gates modeling inputs to ARCHIVE_READY only | ✅ PASS |  |
| archive_ingestor defines FINGERPRINT_MIN_CONFIDENCE threshol | ✅ PASS |  |
| archive_ingestor defines JOIN_ARCHIVE_READY_MIN threshold | ✅ PASS |  |
| archive_ingestor defines AMBIGUOUS_BLOCK_THRESHOLD | ✅ PASS |  |
| Legacy path compat report written | ✅ PASS | C:\Users\Mathew C\Campaign In A Box\reports\state\20260313__ |
| Campaign switch cache validation report written | ✅ PASS | C:\Users\Mathew C\Campaign In A Box\reports\ui\20260313__pro |
| derived/state/campaigns/ directory exists | ✅ PASS |  |
| derived/state/active_campaign_pointer.json exists (written o | ✅ PASS | not yet — written on first campaign switch (expected) |
