# Guidance Engine Output Sample

**Generated:** 2026-03-14T13:50:00-07:00  
**Module:** `engine.ui.user_guidance`

## Current System State

Based on live `evaluate_guidance()` call output during Prompt 31 testing:

```
Overall Status: NEEDS_ACTION
Summary: System partially configured — action required before full operation.

Guidance Items:
  [IMPORTANT] Pipeline Run but Archive Empty
  Detail: The pipeline has been run (log files exist) but the derived/archive/ 
          directory is empty. This means the ARCHIVE_INGEST step may have 
          failed or the pipeline did not reach that step.
  Action: Check the pipeline log for ARCHIVE_INGEST DONE or FAIL.
  Where:  Sidebar → System → ▶️ Pipeline Runner → Last Run Log
```

## Sample — New Campaign (No Data)

```
Overall Status: NEEDS_ACTION

[CRITICAL] No Contest Data Found
Action: Upload election results file via Data Manager → Upload New File
Where:  Sidebar → Data → Data Manager → 📤 Upload New File
```

## Sample — Ready System

```
Overall Status: READY

[OK] System Ready
Detail: Archive present, crosswalks loaded, calibration complete.
Action: Review the Precinct Map and begin Strategy generation.
Where:  Sidebar → Geography → 🗺️ Precinct Map
```

## Mission Control Display

The banner at top of Mission Control always shows the **first guidance item**:

> ⚠️ Next Recommended Action  
> Check the pipeline log for ARCHIVE_INGEST DONE or FAIL.  
> 📍 Sidebar → System → ▶️ Pipeline Runner → Last Run Log

All guidance items are also accessible via the "All System Guidance Items" expander at the bottom of Mission Control.
