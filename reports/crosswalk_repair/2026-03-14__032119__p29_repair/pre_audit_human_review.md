# Pre-Audit Human Review Worksheet
**Run:** `2026-03-14__032119__p29_repair`  **Generated:** 2026-03-14 03:37

> This document must be reviewed by a human before the next full audit.
> Fill in the **Human Decision** column for each item.

---

## 1. Crosswalk Detection Status

| File | Detection OK? | Source Col | Target Col | Action Needed |
|---|---|---|---|---|
| `blk_mprec_097_g24_v01.csv` | ✅ Yes | `block` | `mprec` | None |
| `c097_g24_rg_blk_map.csv` | ✅ Yes | `rgprec` | `block` | None |
| `c097_g24_sr_blk_map.csv` | ✅ Yes | `srprec` | `block` | None |
| `c097_g24_srprec_to_city.csv` | ✅ Yes | `srprec` | `city` | None |
| `c097_rg_rr_sr_svprec_g24.csv` | ✅ Yes | `rgprec` | `svprec` | None |
| `mprec_srprec_097_g24.csv` | ✅ Yes | `mprec` | `srprec` | None |

---

## 2. Join Quality Summary

- Verdict: **FAILED**
- % Joined: 0.0%
- Identity fallbacks: 0

**Human Decision:** Is this join rate acceptable for the next audit? ____

---

## 3. Questions for Human Review

1. Are all 5 crosswalk files the correct vintage (g24) for this contest year?
   - **Answer:** ____

2. Do any precinct IDs in the uploaded contest file look like truncated/stripped values?
   - Check `precinct_join_diagnostics.csv` column `raw_precinct_value`
   - **Answer:** ____

3. If identity fallback was used, do any map points appear at wrong locations?
   - **Answer:** ____

4. Is the crosswalk repair complete, or are further manual overrides needed?
   - If yes, add entries to `config/precinct_id/manual_mapping_overrides.yaml`
   - **Answer:** ____

---

## 4. Files to Inspect

- `reports/crosswalk_repair/2026-03-14__032119__p29_repair/crosswalk_repair_summary.md`
- `reports/crosswalk_repair/2026-03-14__032119__p29_repair/crosswalk_repair_trace.json`
- `reports/crosswalk_repair/2026-03-14__032119__p29_repair/precinct_join_diagnostics.csv`
- `derived/precinct_id_review/2026-03-14__032119__p29_repair__crosswalk_review.csv`
- `derived/precinct_id_review/2026-03-14__032119__p29_repair__join_review.csv`
- `config/precinct_id/crosswalk_column_hints.yaml`
- `config/precinct_id/manual_mapping_overrides.yaml`

---

## 5. Platform Readiness for Next Audit

**Current join quality:** FAILED
**Ready for full audit?** ____
**Reviewer:** ____
**Review date:** ____