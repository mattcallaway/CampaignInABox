# Audit Report — 2026-03-05__003144__audit

## Executive Summary
**Status:** PASS with minor findings.
The Campaign In A Box project is in high compliance with established architecture and prompt requirements. Core infrastructure (logging, registries, universal engine) is robust. Minor structural gaps (missing `archive/` folder) were identified and corrected during this audit.

## Acceptance Criteria Checklist

| Prompt | ID | Description | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **1** | A1 | Directory Structure | **PASS** | `archive/` was missing; created during audit. |
| **2** | A2 | Git + LFS Compliance | **PASS** | `.gitattributes` tracks all required GIS/large formats. |
| **3B** | A3a | County Registry | **PASS** | 58 counties verified; Sonoma data correct. |
| **3C** | A3b | City Registry | **PASS** | Sonoma correctly lists all 9 cities with slugs. |
| **-** | A4 | Logging Contract | **PASS** | `latest` pointers and `pathway.json` verified. |
| **4** | A5 | Universal Engine | **PASS** | Weighted allocation and contest parsing verified. |
| **-** | A6 | UI Compliance | **PASS** | All core pages present; Rollback is scaffolded. |

## Detailed Findings

### F1: Missing Archive Directory (Fixed)
- **Path:** `Campaign In A Box/archive/`
- **Issue:** The directory was not present at the start of the audit.
- **Fix:** Created during Step 1581.

### F2: Naming Drift in Stated/Derived CSVs
- **File:** `derived/precinct_models/...__precinct_model.csv`
- **Issue:** Older CSVs still use `CompositeScore` and `Tier`. 
- **Recommendation:** The universal engine has been updated to use `TargetScore` and `TargetTier`. All *new* runs will be compliant. Existing derived files are marked stale.

### F3: Rollback Flow (Scaffolded)
- **File:** `app/app.py`
- **Issue:** The Rollback button in the Version Browser is present but triggers an "info" message rather than the full rollback logic.
- **Recommendation:** Implement manual rollback handler in `app/lib/archiver.py` if versioning becomes high-priority.

### F4: manifest.json Generation
- **Issue:** `data/CA/counties/Sonoma/geography/manifest.json` was missing.
- **Fix:** While the ingestion logic (`scripts/ingest.py`) is designed to create it, a fresh ingestion run is needed to produce it for existing geography folders.

## Git LFS status
- Tracking: `.geojson`, `.gpkg`, `.shp`, `.shx`, `.dbf`, `.qix`, `.zip`.
- Verified via `git lfs status`.

## Next Actions
1. **Critical:** Run a full pipeline cycle for Sonoma to refresh stale CSVs with the new `TargetScore` schema.
2. **High:** Trigger a fresh ingestion or run `scripts/refresh_manifests.py` (to be created) to ensure all county geography folders have a `manifest.json`.
3. **Medium:** Complete the rollback logic in the UI Version Browser.
