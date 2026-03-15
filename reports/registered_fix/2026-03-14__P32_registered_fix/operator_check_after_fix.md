# Operator Check After Fix — Prompt 32

**For Matt — What Changed and How to Know The Fix Worked**

## What Changed

The canvass workbook has a special layout where column labels (Registered Voters, Voters Cast, YES, NO)
appear as data in the first row of each contest sheet rather than as proper column headers.
The pipeline now detects this pattern and extracts the Registered Voters column correctly.

## How To Know The Fix Worked

1. **Open Data Explorer** (Data section in sidebar)
2. Look at the egistered column — it should have non-zero values for almost every precinct
3. Look at 	urnout_pct — values should be in the range 0.3 to 1.0, not 0.0
4. **Open Diagnostics** → expand Data Integrity & Repairs — should say 'No integrity repairs needed'

## What Pages Should Look Different Now

| Page | Before Fix | After Fix |
|---|---|---|
| Data Explorer - registered col | 0 for all | Real numbers (e.g. 16, 44, 67) |
| Data Explorer - turnout_pct | 0.0 for all | 0.45 to 0.89 (real rates) |
| Diagnostics - Data Integrity | FAIL / CRITICAL | PASS / No repairs |
| Mission Control - Pipeline | SUCCESS (was misleading) | SUCCESS (now accurate) |

## Warnings That Are Still Expected (NOT Bugs)

- Campaign Health Index: WARNING — you haven't uploaded a voter file or entered field ops data
- support_pct = 0.0 — no voter file means no universe targeting
- target_score = 0 — same reason
- Join/Geometry: ⚠️ — expected without voter file
- 'Doors Pace: BEHIND' — no canvassing data entered

## What To Do Next

1. Upload a voter CSV (goes in data/voter_file/) to enable scoring
2. Run the pipeline again — scores will now use real turnout weights
3. Strategy pages will produce more accurate targeting recommendations
