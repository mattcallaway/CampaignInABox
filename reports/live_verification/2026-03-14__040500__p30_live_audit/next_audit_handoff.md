# Next Audit Handoff — After Prompt 30

## Current Status

| Component | Status |
|---|---|
| App startup | ? Working |
| Crosswalk detection | ? 6/6 files OK (repaired Prompt 29) |
| ALLOCATE_VOTES crash | ? Fixed (Prompt 30) |
| Full pipeline end-to-end | ? Not yet verified — fix applied but re-run needed |
| Geometry join | ? Pending re-run |
| Archive outputs | ? Pending re-run |
| Precinct map | ? Will populate after successful run |
| Strategy | ? Needs pipeline + user action |
| 2020 data in canonical path | ? Human input request #2 |

## What to Do Next (in order)
1. Confirm `data/contests/CA/Sonoma/2020/nov2020_general/raw/` has the 2020 results file
2. Run pipeline via UI for nov2020_general
3. Download the run log — check ALLOCATE_VOTES now shows DONE not CRASH
4. Check Precinct Map — should show full Sonoma coverage
5. Check Historical Archive — should show 2020 precinct profiles
6. Answer Human Input Requests 1-4 in human_input_requests.md

## Which Files/Logs to Check First
- `reports/live_verification/2026-03-14__040500__p30_live_audit/`
- `reports/crosswalk_repair/2026-03-14__032119__p29_repair/crosswalk_repair_summary.md`
- Latest pipeline run log under `logs/runs/`

## Remaining Uncertainties
- Does ALLOCATE_VOTES fully succeed now or does it hit another error further down?
- Is the 2020 contest file in the correct canonical path?
- Is the geometry file loaded correctly for MPREC join?
