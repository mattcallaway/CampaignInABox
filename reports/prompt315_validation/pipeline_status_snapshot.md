# Pipeline Status Snapshot

**Generated:** 2026-03-14T13:50:00-07:00  
**Module:** `engine.diagnostics.pipeline_observer`

## How Pipeline Status is Loaded

Mission Control calls `_load_latest_run(base_dir)` which:
1. Looks in `reports/pipeline_runs/` for run directories
2. Reads the newest `pipeline_summary.json` file produced by `pipeline_observer.write_run_summary()`
3. Falls back to using the directory name as run_id if JSON unavailable

## Pipeline Run Directories (current session)

The pipeline was run during Prompt 30/31 testing. 
Reports were generated at:

```
reports/pipeline_runs/{run_id}/
  pipeline_summary.md
  pipeline_summary.json
```

## Sample pipeline_summary.json

```json
{
  "run_id": "2026-03-14__044900__9b7d76d6__msi",
  "contest_slug": "nov2025_special",
  "overall": "SUCCESS",
  "rows_loaded": 0,
  "precinct_join_rate": null,
  "archive_built": false,
  "steps": {
    "DATA_INTAKE_ANALYSIS": "DONE",
    "LOAD_GEOMETRY": "DONE",
    "LOAD_CROSSWALKS": "DONE",
    "PARSE_CONTEST": "DONE",
    "ALLOCATE_VOTES": "DONE",
    "ARCHIVE_INGEST": "SKIP"
  }
}
```

## Mission Control Display

In the right panel of Mission Control:

```
🔄 Latest Pipeline Run

nov2025_special  [SUCCESS]
Rows: —
Archive: ⏳ No
```

When no pipeline runs exist:

```
No pipeline runs recorded yet.
```
