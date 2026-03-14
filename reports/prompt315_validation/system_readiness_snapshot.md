# System Readiness Snapshot

**Generated:** 2026-03-14T13:50:00-07:00  
**Module:** `engine.diagnostics.system_readiness`

## Active Campaign Context

```
Campaign Name:  [loaded from active_campaign.yaml]
Contest:        [loaded from data state]
State:          CA
County:         Sonoma
Stage:          Planning
Status:         Active
```

## Readiness Check Results (from live run during Prompt 31)

| Check | Status | Notes |
|---|---|---|
| Contest Data | PRESENT | 3 files detected in canonical path |
| Pipeline Run | UNKNOWN | Log files exist but archive not built |
| Archive | NOT BUILT | derived/archive/ is empty |
| Crosswalks | PRESENT | Sonoma crosswalk resolves |
| Geometry | WARN | Potential missing boundary files |
| Model Calibration | PENDING | Archive needed before calibration |

## How This Appears in Mission Control

The System Readiness panel (right sidebar of Mission Control) renders each check as a key-value row:

```
🩺 System Readiness
[PARTIAL]

Contest Data     PRESENT   ← green
Pipeline Run     UNKNOWN   ← grey
Archive          NOT BUILT ← red
Crosswalks       PRESENT   ← green
Geometry         WARN      ← amber
Model Calibration PENDING  ← amber
```

## Expected Fully-Ready Snapshot

```
Contest Data     PRESENT   ← green
Pipeline Run     SUCCESS   ← green
Archive          PRESENT   ← green
Crosswalks       PRESENT   ← green
Geometry         OK        ← green
Model Calibration OK       ← green
```
