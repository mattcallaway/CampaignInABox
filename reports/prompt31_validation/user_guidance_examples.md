# Prompt 31 Validation — User Guidance Examples

**Generated:** 2026-03-14

## Example 1: Fresh System (No Data)

```
System Status:
  Contest Data: ❌ MISSING
  Pipeline Run: ⏳ NO
  Archive: ⏳ NOT BUILT

Recommended Actions:
  🚨 CRITICAL — No Contest Data Found
  Action: Upload election results file via Data Manager → Upload New File
  Where: Sidebar → Data → Data Manager → 📤 Upload New File
```

## Example 2: Data Uploaded, Pipeline Not Run

```
System Status:
  Contest Data: ✅ PRESENT (3 files)
  Pipeline Run: ⏳ NO
  Archive: ⏳ NOT BUILT

Recommended Actions:
  ⚠️ IMPORTANT — Pipeline Not Yet Run
  Action: Go to Pipeline Runner, select your contest, click 'Run Modeling Pipeline'
  Where: Sidebar → System → 🛠️ Pipeline Runner
```

## Example 3: Post-Pipeline (Current State)

```
System Status:
  Contest Data: ✅ PRESENT
  Pipeline Run: ✅ YES (logs/runs/*.log found)
  Archive: ⏳ NOT BUILT (derived/archive/ empty)

Recommended Actions:
  ⚠️ IMPORTANT — Pipeline Run but Archive Empty
  Action: Check pipeline log for errors — look for ARCHIVE_INGEST DONE
  Where: Sidebar → System → 🛠️ Pipeline Runner → Last Run Log
```

## Example 4: Fully Ready System

```
System Status:
  Contest Data: ✅ PRESENT
  Pipeline Run: ✅ YES
  Archive: ✅ PRESENT
  Crosswalk Join Rate: 98.3%
  Geometry Coverage: ✅ OK
  Modeling Ready: ✅ YES

Recommended Actions:
  ✅ OK — System Ready
  Action: Review the Precinct Map and Historical Archive pages
  Where: Sidebar → Geography → 🗺️ Precinct Map
```
