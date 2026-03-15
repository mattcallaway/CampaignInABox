# Restart Report — Prompt 32

**Timestamp:** 2026-03-14T20:05:00-07:00

## Stop

- Method: `Stop-Process -Id 16504 -Force` (killed streamlit process on port 8501)
- Verification: `Get-NetTCPConnection -LocalPort 8501` → empty
- Status: APP_STOPPED

## Restart

- Command: `streamlit run ui\dashboard\app.py --server.port=8501 --server.headless=false`
- Entry point: `ui\dashboard\app.py` (found from Start Campaign In A Box.bat)
- Process ID: 14268
- Startup wait: ~35s

## Verification

- App URL: http://localhost:8501
- Status: APP_ONLINE (confirmed via Get-NetTCPConnection)
- Code version: commit 50f7b2b (merge of prompt32 registered fix)

## Code Version Confirmation

git log --oneline -3:
  50f7b2b Merge branch 'rollback/prompt32_pre_registered_fix'
  f1a698f fix(parser): repair registered voter extraction for Sonoma canvass workbook layout
  7bafa8a chore(rollback): create pre-prompt32 registered fix rollback point

All 3 targeted fixes running:
  1. contest_parser.py preamble-label detection (Prompt 32)
  2. run_pipeline.py DATA_QUALITY_WARNING guardrail (Prompt 32)
  3. join_guard.py left_on/right_on support (Prompt 30.5)
