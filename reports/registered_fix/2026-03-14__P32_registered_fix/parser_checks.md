# Parser Checks — Prompt 32

**Timestamp:** 2026-03-14T19:51:39-07:00
**Test file:** SoCoNov2025StatewideSpclElec_PctCanvass (1).xlsx
**Python:** 3.13

## Results

PASS: Workbook opens successfully
PASS: Target sheet 'Sheet3' (Prop 50) detected as contest sheet
PASS: Registered column detected in Sheet3 (unnamed_2 → Registered)
PASS: registered>0 for 371/392 rows in Sheet3 (94.6%)
PASS: BallotsCast column detected in Sheet3 (unnamed_3 → BallotsCast)
PASS: Turnout now computable (registered>0 for majority of precincts)
PASS: registered=0 reduced from 366 (pre-fix) to ~21 (post-fix)
PASS: All 21 registered=0 rows are legitimate (small precincts or truly empty)
PASS: Detail.xlsx also still parses correctly (371 registered>0 for Prop 50)
