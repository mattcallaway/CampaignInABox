# Campaign In A Box — Data Pipeline Flow

> Auto-generated diagram of the end-to-end data lifecycle.  
> Updated by `engine/ui/ui_workflow_mapper.py` and Prompt 31.

---

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     USER UPLOADS FILE                       │
│         Data Manager → Upload New File tab                  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   CONTEST INTAKE (P28)                      │
│   engine/contest_data/contest_intake.py                     │
│   → Validates file                                          │
│   → Copies to canonical path:                               │
│     data/contests/{state}/{county}/{year}/{slug}/raw/       │
│   → Writes manifests/ingest_manifest.json                   │
│   → Writes manifests/primary_result_file.json               │
│   → Appends to data/contests/registry.json                  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              FILE WATCHER (Prompt 31)                       │
│   engine/ingestion/contest_file_watcher.py                  │
│   → Scans canonical paths for new files                     │
│   → Detects precinct column via fingerprint                 │
│   → Emits: READY_FOR_PIPELINE | NEEDS_REVIEW               │
│   → Triggers auto_pipeline_runner if eligible               │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   PIPELINE RUNNER                           │
│   scripts/run_pipeline.py                                   │
│   UI: Pipeline Runner page (Pipeline Runner tab)            │
└──────────────────────────────────────────────────────────── ┘
           │
     ┌─────┴─────────────────────────────────────────┐
     │         PIPELINE STEPS (in order)              │
     │                                                │
     │  1. DATA_INTAKE_ANALYSIS                       │
     │     → Scans contest dir, validates files       │
     │                                                │
     │  2. INGEST_STAGING (optional)                  │
     │     → Only if --staging-dir provided           │
     │                                                │
     │  3. LOAD_GEOMETRY                              │
     │     → Reads precinct_shapes/ GeoJSON/SHP       │
     │     → Builds spatial index                     │
     │                                                │
     │  4. LOAD_CROSSWALKS                            │
     │     → Reads data/{state}/counties/{county}/    │
     │         geography/crosswalks/                  │
     │     → detect_crosswalk_columns() (3-tier)      │
     │     → [P29-INTROSPECT] logs detection results  │
     │                                                │
     │  5. VALIDATE_VOTES                             │
     │     → Resolves primary result file             │
     │     → engine/contest_data/contest_resolver.py  │
     │     → SKIP if no file in canonical path        │
     │                                                │
     │  6. PARSE_CONTEST                              │
     │     → Reads XLS/CSV, detects precinct col      │
     │     → Produces per-sheet totals_df             │
     │                                                │
     │  7. ALLOCATE_VOTES  ← (Prompt 30 fix here)    │
     │     → xwalk dict → DataFrame conversion        │
     │     → safe_merge(left_on=precinct_col,         │
     │                  right_on=_xw_src)             │
     │     → Fallback: area_weighted if empty         │
     │                                                │
     │  8. BUILD_PRECINCT_PROFILES                    │
     │     → Per-precinct vote totals, margins        │
     │                                                │
     │  9. GEOMETRY_JOIN                              │
     │     → Joins vote data to GeoDataFrame          │
     │     → Produces derived/maps/*.geojson          │
     │                                                │
     │  10. ARCHIVE_INGEST                            │
     │     → engine/archive_builder/                  │
     │     → Writes derived/archive/{state}/{county}/ │
     │     → normalized_elections.json                │
     │     → precinct_profiles.json                   │
     │                                                │
     │  11. MODEL_VOTERS (optional)                   │
     │     → Requires voter file upload               │
     │                                                │
     │  12. MODEL_CALIBRATION (optional)              │
     │     → Calibrates simulation parameters         │
     │     → Writes derived/models/                   │
     │                                                │
     │  13. GENERATE_STRATEGY (optional)              │
     │     → engine/strategy/                         │
     │     → Writes derived/strategy/                 │
     └────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│               PIPELINE OBSERVER (Prompt 31)                 │
│   engine/diagnostics/pipeline_observer.py                   │
│   → Parses run log                                          │
│   → Writes reports/pipeline_runs/{run_id}/                  │
│     pipeline_summary.md + pipeline_summary.json             │
└────────────────────────────┬────────────────────────────────┘
                             │
           ┌─────────────────┼──────────────────┐
           │                 │                  │
           ▼                 ▼                  ▼
    ┌────────────┐   ┌────────────┐    ┌────────────────┐
    │ PRECINCT   │   │ HISTORICAL │    │   SIMULATIONS  │
    │ MAP PAGE   │   │ ARCHIVE    │    │   PAGE         │
    │            │   │ PAGE       │    │                │
    │ Reads:     │   │ Reads:     │    │ Reads:         │
    │ derived/   │   │ derived/   │    │ derived/       │
    │ maps/      │   │ archive/   │    │ models/        │
    └────────────┘   └────────────┘    └────────────────┘
```

---

## Data File Locations Reference

| Data Type | Canonical Path |
|---|---|
| Raw contest file | `data/contests/{state}/{county}/{year}/{slug}/raw/` |
| Contest manifests | `data/contests/{state}/{county}/{year}/{slug}/manifests/` |
| Precinct geometry | `data/{state}/counties/{county}/geography/precinct_shapes/` |
| Crosswalk files | `data/{state}/counties/{county}/geography/crosswalks/` |
| Map outputs | `derived/maps/` |
| Archive output | `derived/archive/{state}/{county}/{year}/{slug}/` |
| Model outputs | `derived/models/` |
| Pipeline logs | `logs/runs/` |
| Pipeline summaries | `reports/pipeline_runs/{run_id}/` |
| Crosswalk repair reports | `reports/crosswalk_repair/` |
| Precinct ID review | `derived/precinct_id_review/` |

---

## Key Engine Modules

| Module | Purpose |
|---|---|
| `engine/contest_data/contest_intake.py` | Canonical file ingestion + registry |
| `engine/contest_data/contest_resolver.py` | Finds primary result file for pipeline |
| `scripts/geography/crosswalk_resolver.py` | Loads and detects crosswalk columns |
| `scripts/run_pipeline.py` | Main pipeline orchestrator |
| `engine/ingestion/contest_file_watcher.py` | Auto-detects new contest files (P31) |
| `engine/ingestion/auto_pipeline_runner.py` | Suggests/triggers pipeline runs (P31) |
| `engine/ui/user_guidance.py` | System co-pilot guidance engine (P31) |
| `engine/diagnostics/system_readiness.py` | Readiness evaluator (P31) |
| `engine/diagnostics/pipeline_observer.py` | Run log parser + summary writer (P31) |
