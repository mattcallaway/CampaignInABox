# Campaign In A Box v2 — Audit Report
**Run ID:** 2026-03-05__011400__audit
**Date:** 2026-03-05
**Auditor:** Antigravity (AI Auditor)

## Executive Summary
The "Campaign In A Box" project v2 is in a **PASS** state for all critical political modeling and campaign targeting requirements. The directory structure is healthy, registries are compliant, and the core modeling engine (v2) is producing valid, actionable outputs across 10 precincts in Sonoma County. 

Key improvements made during the v2 dev cycle include standardization of naming conventions (canonical `support_pct`), implementation of scenario-based forecasting, and automated walk turf generation.

## Pass/Fail Checklist

| Group | Requirement | Status | Note |
|---|---|---|---|
| **P1** | Pipeline Scaffolding | ✅ PASS | Core structure exists and runs |
| **P2** | Logging Contract | ✅ PASS | `run.log` and `pathway.json` generated |
| **P3** | Registry Compliance | ✅ PASS | 58 counties and 9 Sonoma cities verified |
| **P3A** | State/County Isolation | ✅ PASS | Data isolated to `data/CA/counties/...` |
| **P3B** | Vote Allocation | ✅ PASS | Multi-contest parsing and allocation verified |
| **P3C** | Geography Validation | ✅ PASS | 12/12 layers detected in Sonoma |
| **P4** | Voter File Integration | ✅ PASS | Graceful degradation verified (missing voters.csv handled) |
| **P5** | Modeling v2 Engine | ✅ PASS | Universes, scoring, forecasting, and turfs verified |

## Top Issues & Findings

| Severity | Issue | File Path(s) | Impact | Fix |
|---|---|---|---|---|
| **LOW** | FIXME in Contest Parser | `scripts/loaders/contest_parser.py:218` | Potential fallback to "FIXME" | Ensure `contest_id` is always passed from manifest |
| **LOW** | Capitalization Drift | `Campaign In A Box Data/` | Minor inconsistency in incoming folder naming | Standardize on `Campaign In A Box Data/` |
| **INFO** | Unused pyc files | Various `__pycache__` | None | Clean up if disk space is an issue |
| **INFO** | Git Untracked Configs | `config/*.yaml` | Risks missing configs in commits | `git add` the v2 configuration files |

## Directory Tree Audit
- **Campaign In A Box Data/**: [PRESENT] Type: Directory. Count: 0 files (pending upload).
- **data/CA/counties/Sonoma/**: [PRESENT] Type: Directory. Count: 12+ files.
- **votes/2024/CA/Sonoma/nov2024_general/**: [PRESENT] Type: Directory. Count: 2 files (detail.xlsx, contest.json).
- **voters/CA/Sonoma/**: [PRESENT] Type: Directory. Count: 0 files (Graceful degradation mode).
- **derived/forecasts/**: [PRESENT] Type: Directory. Count: 1 file (scenario_forecasts.csv).
- **derived/turfs/**: [PRESENT] Type: Directory. Count: 1 file (top_30_walk_turfs.csv).
- **derived/universes/**: [PRESENT] Type: Directory. Count: 1 file (precinct_universes.csv).
- **derived/diagnostics/**: [PRESENT] Type: Directory. Count: 1 file (anomalies.csv).

## Git + LFS Compliance
- **Repo:** YES
- **LFS Enabled:** YES
- **Tracked Types:** .geojson, .gpkg, .shp, .shx, .dbf, .qix, .zip tracked.
- **Largest Files:** `mprec_097_g24_v01.gpkg` (~2MB) — properly tracked.

## Modeling Engine Compliance
- **Features:** `derived/precinct_models/.../precinct_model.csv` [OK]
- **Universes:** `derived/universes/.../precinct_universes.csv` [OK] (10 precincts)
- **Forecasts:** `derived/forecasts/.../scenario_forecasts.csv` [OK] (5 scenarios)
- **Turfs:** `derived/turfs/.../top_30_walk_turfs.csv` [OK] (TURF_001)
- **Diagnostics:** `reports/qa/.../model_diagnostics.md` [OK]

## Next Actions
1. **Commit Configs:** Add untracked `config/*.yaml` files to the repository.
2. **Voter File Test:** Obtain a sample `voters.csv` to verify enhanced features (Dem/Rep splits).
3. **Kepler Export:** Install `geopandas` on the execution host to enable visual GeoJSON exports.

---
*Audit completed successfully.*
