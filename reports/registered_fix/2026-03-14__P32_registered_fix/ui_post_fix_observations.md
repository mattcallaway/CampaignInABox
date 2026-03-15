# UI Post-Fix Observations — Prompt 32

**Observed via automated browser verification (201s pipeline run)**

## Data Explorer

Real registered voter counts now visible per precinct:
- 0100250: registered=16, ballots=13, turnout=0.8125
- 0100267: registered=11, ballots=5, turnout=0.4545
- 0200029: registered=23, ballots=17, turnout=0.7391
- 0200048: registered=4, ballots=3, turnout=0.75
- 0200117: registered=10, ballots=4, turnout=0.40

Features now populated: canonical_precinct_id, registered, ballots_cast, turnout_pct, log_registered, sqrt_registered, ballots_cast_per_registered

## Diagnostics Page

- System Health: HEALTHY
- Data Integrity & Repairs: PASS (✅ checked)
- 'No integrity repairs needed.' — **0 CRITICAL rows vs 366 pre-fix**
- Join / Geometry: still showing ⚠️ (voter file not loaded — expected)

## Mission Control

- Last run: nov2025_special SUCCESS
- Archive: Built
- Stage 3 Historical Analysis: Archive Built

## Remaining Yellow/Orange UI Status

| Item | Status | Normal? |
|---|---|---|
| Campaign Health Index: WARNING (-0.76) | Yellow | Normal (no field ops data or voter file) |
| Doors Pace: BEHIND | Yellow | Normal (no canvassing data) |
| Data Integrity & Repairs | PASS (green) | Fixed! |
| support_pct | 0.0 | Normal (no voter file) |
| target_score | 0 | Normal (no voter file) |
| Join / Geometry | ⚠️ | Normal (no voter file loaded) |

## Any Regressions?

None detected. Previously working sheets (detail.xlsx, 2020 archive) not impacted by the preamble-label fix.
