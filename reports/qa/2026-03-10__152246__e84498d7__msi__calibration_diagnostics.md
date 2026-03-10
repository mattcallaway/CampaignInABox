# Calibration Diagnostics — Prompt 15
**Run:** `2026-03-10__152246__e84498d7__msi`  **Generated:** 2026-03-10 23:27 UTC

## Data Coverage

| Check | Value |
|-------|-------|
| Historical contests | 0 |
| Historical precinct-year records | 0 |
| Precincts in historical data | 0 |
| Precincts in precinct model | 0 |
| Historical precinct match rate | 0.0% |
| GOTV universe size | 0 |
| Persuasion universe size | 0 |
| Runtime data available | ❌ No |

## Confidence Assessment

**Calibration Status:** prior_only
**Confidence Level:** none

| Level | Requirement |
|-------|-------------|
| high | ≥5 elections, ≥100 precincts |
| medium | ≥3 elections, ≥50 precincts |
| low | ≥1 election |
| none | No historical data |

## Recommendations

- ❌ Add historical election files to `data/elections/CA/<county>/<year>/detail.xls`
- ⚠️ No campaign runtime data — enter field results in War Room to calibrate turnout lift

---
*Calibration diagnostics by engine/calibration/calibration_engine.py — Prompt 15*