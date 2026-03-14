# Workflow Stage Validation

**Generated:** 2026-03-14T13:50:00-07:00

## Stage 1 — Campaign Setup

| Check | Value |
|---|---|
| Reads campaign context dict | ✅ `data.get("campaign_name")` |
| Reads contest ID | ✅ `data.get("contest_id")` |
| Reads state/county | ✅ `data.get("state")`, `data.get("county")` |
| Reads campaign stage | ✅ `data.get("campaign_stage")` |
| Navigation → Campaign Admin | ✅ Button → `🏛️ Campaign Admin` |
| Navigation → Campaign Setup | ✅ Button → `🗳️ Campaign Setup` |
| Detects missing contest warning | ✅ Checks for `"—"` in contest_id |

## Stage 2 — Data Ingestion *(Most Critical)*

| Check | Value |
|---|---|
| Files detected via file watcher | ✅ `scan_for_new_contest_files()` |
| Shows file count | ✅ |
| Shows filename + contest + year | ✅ with status badge |
| Shows pipeline suggestions | ✅ `suggest_pipeline_runs()` |
| Shows latest run status | ✅ from `_load_latest_run()` |
| Upload data button | ✅ Primary action → `📂 Upload Contest Data` |
| File Registry button | ✅ → `📂 Data Manager` |
| Run Pipeline button | ✅ → `▶️ Pipeline Runner` |
| Expanded by default | ✅ `expanded=True` |
| Prominent "most critical stage" callout | ✅ |

## Stage 3 — Historical Analysis

| Check | Value |
|---|---|
| Archive readiness from system_readiness | ✅ checks `Archive` in readiness.checks |
| Precinct Join Rate displayed | ✅ badge |
| Model Calibration displayed | ✅ badge |
| Explains why archive is missing | ✅ plain-language text |
| Navigation → Archive | ✅ |
| Navigation → Precinct Map | ✅ |
| Navigation → Calibration | ✅ |

## Stage 4 — Targeting & Modeling

| Check | Value |
|---|---|
| Model calibration readiness | ✅ from readiness.checks |
| Historical election count | ✅ inferred from archive presence |
| Navigation → Targeting | ✅ |
| Navigation → Simulations | ✅ |
| Navigation → Advanced Modeling | ✅ |
| Navigation → Voter Intelligence | ✅ |

## Stage 5 — Strategy Planning

| Check | Value |
|---|---|
| Strategy docs presence check | ✅ `derived/strategy/*.md` glob |
| Simulations run status | ✅ from latest_run |
| Navigation → Strategy | ✅ |
| Navigation → Simulations | ✅ |
| Navigation → Political Intelligence | ✅ |

## Stage 6 — War Room Operations

| Check | Value |
|---|---|
| Campaign stage display | ✅ from context |
| Prerequisite check (strategy) | ✅ `if not strategy_ready: show info` |
| Navigation → War Room | ✅ |
| Navigation → Diagnostics | ✅ |

## Stage 7 — Advanced Tools

| Check | Value |
|---|---|
| All 6 advanced tool buttons | ✅ Data Explorer, Diagnostics, Calibration, Advanced Modeling, Source Registry, Swing Modeling |
| "Power users / debugging" label | ✅ |
