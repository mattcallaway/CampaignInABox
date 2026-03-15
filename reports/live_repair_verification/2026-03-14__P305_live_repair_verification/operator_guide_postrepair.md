# Operator Guide — Post P30.5 Repair

**Updated:** 2026-03-14

This is a practical guide for Matt — how to use Campaign In A Box correctly right now,
what Mission Control means, and what messages are normal vs. real problems.

## Starting the App

1. Double-click **Campaign In A Box** shortcut on Desktop
   OR open terminal and run: Start Campaign In A Box.bat from project root
2. Wait for browser to open http://localhost:8501
3. Log in as Matthew Callaway

## Campaign Mission Control — What It Means

Mission Control is your home base. Here's what each section means:

### System Readiness (right column)
| Row | What it checks | Normal if... |
|---|---|---|
| Contest Data | data/contests/ folder has .xlsx files | Always PRESENT once files are uploaded |
| Pipeline Run | Any .log file exists in logs/runs/ | OK after first pipeline run |
| Archive | derived/archive/ has content | PRESENT after first successful full run |
| Crosswalk Files | data/CA/counties/Sonoma/geography/crosswalks/ | PRESENT (always) |
| Precinct Geometry | data/CA/counties/Sonoma/geography/precinct_shapes/ | PRESENT (always) |
| Precinct Join Rate | Reads derived/precinct_id_review/*_join_quality.json | UNKNOWN until voter-file-based step runs |
| Model Calibration | derived/models/ has JSON files | OK after pipeline run |

### Stage 3 Historical Analysis
- **Archive Built** — pipeline has run DOWNLOAD_HISTORICAL_ELECTIONS. Contest outputs are available.
- **Not Built** — run the pipeline from Pipeline Runner page.

The archive is separate from your live contest pipeline outputs.
A successful pipeline run on nov2025_special does NOT mean the 2020 archive is populated.
The archive builds from historical data downloads — those require manual download since
automated downloads for Sonoma 2016-2024 were blocked (see download_status.json).

### NEEDS_REVIEW on Contest Files
- This means the file scanner couldn't detect a precinct column at first glance
- It does NOT mean the pipeline failed — the pipeline correctly parsed all 3 files
- This will clear after the app is restarted (file watcher fix is now live)

## Workflow — Step by Step

1. **Open Mission Control** — check System Readiness status
2. **If Archive NOT BUILT** — run the pipeline from Pipeline Runner
3. **After pipeline runs** — reload Mission Control within a few seconds
4. **Check Stage 2 Data Ingestion** — confirm pipeline logged SUCCESS
5. **Navigate to Precinct Map** — verify precincts are showing correctly
6. **Navigate to Strategy** — review generated strategy documents
7. **Navigate to Simulations** — run scenario analysis
8. **Navigate to Diagnostics** — check for any data quality warnings

## Messages That Are Normal (NOT Problems)

- "NEEDS_REVIEW" on contest files — pipeline still works, just a scanner limitation
- "Voter file not found" skips in pipeline log — no voter CSV uploaded yet (normal)
- "automatic download failed" for historical years — manual download required for Sonoma
- "registered=0 but ballots>0" warnings — data quality issue in workbook, being investigated

## Messages That Indicate a Real Problem

- "INGEST_STAGING DONE" showing FAIL — file ingestion error
- "ALLOCATE_VOTES FAIL" — contest file could not be parsed
- "SANITY FAIL" — vote totals violate constraints
- Any "CRASH" step status in the pipeline log

## The registered=0 Issue

Currently, 366 precincts show registered=0 while ballots>0.
This means voter turnout calculations are unreliable.
This is a data extraction issue in how the contest workbook's Registered column is read.
The NORMALIZE_SCHEMA step maps 'Registered' -> 'registered' but the column values are 0.
This needs investigation in scripts/lib/schema_normalize.py.
