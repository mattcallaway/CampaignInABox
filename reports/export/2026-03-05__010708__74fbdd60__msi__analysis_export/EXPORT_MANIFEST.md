# EXPORT MANIFEST — Campaign In A Box v2 Analysis
**Run ID:** 2026-03-05__010708__74fbdd60__msi  
**Audit ID:** 2026-03-05__011400__audit  
**Export Date:** 2026-03-05

## Description
This package contains technical diagnostics, run logs, and audit reports for the Campaign In A Box v2 modeling engine. The artifacts packaged here represent the successful verification of the political modeling layer (Sonoma 2024 campaign mode).

## Files Included
- [x] `2026-03-05__011400__audit__audit_report.md` — Detailed v2 audit report.
- [x] `2026-03-05__011400__audit__audit_report.json` — Structured audit findings.
- [x] `2026-03-05__010708__74fbdd60__msi__run.log` — Full execution log for the v2 pipeline.
- [x] `2026-03-05__010708__74fbdd60__msi__pathway.json` — Step-by-step diagnostic pathway.
- [x] `2026-03-05__010708__74fbdd60__msi__validation_report.md` — Data validation results (Sonoma).
- [x] `2026-03-05__010708__74fbdd60__msi__qa_sanity_checks.md` — Score distribution and QA report.
- [x] `needs.yaml` — Snapshot of current project needs.
- [x] `counties_ca.json` — Canonical CA county registry.
- [x] `cities_by_county_ca.json` — Canonical CA city registry (Sonoma).

## Repository Snapshot (CA Sonoma V2)
- **Total Files:** ~466
- **Python Files (*.py):** ~55
- **Geography Files:** 12 layers (MPREC, SRPREC, Crosswalks)
- **Vote Files:** 2 (detail.xlsx, contest.json)
- **Derived Artifacts:** Scoring, Forecasting, Universes, and Turfs generated.

## Warnings / Missing Files
- [ ] `voters.csv` — OMITTED (Graceful degradation mode; run succeeded using only vote-history-derived features).
- [ ] `kepler.geojson` — OMITTED (Requires `geopandas` installation on host).

---
**EXPORT COMPLETE**
Folder: `reports/export/2026-03-05__010708__74fbdd60__msi__analysis_export/`
