# Map Render Diagnostics
**Run:** `2026-03-14__032119__p29_repair`  **Generated:** 2026-03-14 03:37

## Geometry File Used
- State: `CA`, County: `Sonoma`
- Geometry type: MPREC (preferred) → SRPREC (fallback)
- Source directory: `data/CA/counties/Sonoma/geography/precinct_shapes/`

## Join Coverage
- Contest rows with precinct data: 0
- Joined to geometry: 0 (0.0%)
- Not joined: 0
- Identity fallbacks used: 0

## Why Scattered/Wrong Precincts Appeared Previously

Before Prompt 29 repair:
- `detect_crosswalk_columns()` expected uppercase column names (BLOCK20, MPREC_ID, SRPREC_ID)
- Sonoma crosswalk files use lowercase short names (block, mprec, srprec)
- Every crosswalk silently failed with `return {}, False`
- Contest precinct strings were used **as-is** as geometry join keys
- If any raw precinct strings accidentally matched geometry IDs, those
  precincts appeared on the map — hence the 'random scattered' pattern

## After Prompt 29 Repair
- Crosswalk detection: 6/6 files OK
- Join quality: **FAILED** (0.0% joined)

## Action Required If Map Is Still Sparse
1. Check `crosswalk_repair_summary.md` for remaining detection failures
2. Open `derived/precinct_id_review/*__crosswalk_review.csv` for specifics
3. Add missing hints to `config/precinct_id/crosswalk_column_hints.yaml`