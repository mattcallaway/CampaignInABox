# Archive Ingestion Trace — Deep Data Flow Audit
**RUN_ID:** `2026-03-14__000841__audit`  
**Generated:** 2026-03-14T07:48:41  
**Scope:** CA / Sonoma — 2020 & 2024 election results  
**Active Campaign:** `2026_CA_sonoma_prop_50_special`

---

## Phase 1 — Uploaded File Verification ✅ PARTIAL

### 2020 General Election
| Field | Value |
|---|---|
| Filename | `StatementOfVotesCast-Webnov32020.xlsx` |
| Path | `data/elections/CA/Sonoma/2020_general/` |
| Size | 4,049,704 bytes (3.9 MB) |
| SHA256 | `28eb1f9b312c387f...` |
| Upload Time | 2026-03-14T07:23:57 |
| Source | Manual upload (Data Manager UI) |
| Upload Count | **5 duplicate registry entries** (same file uploaded 3× + one copy with `(1)` in name) |

### 2024 General Election
| Field | Value |
|---|---|
| Location | `data/CA/counties/Sonoma/votes/2024/nov2024_general/detail.xlsx` |
| Size | 5,687 bytes (stub) |
| Status | Present in pipeline votes/ tree — real vote data at `2024/2024_general/detail.xlsx` (13.5 MB) |
| Archive synthetic | `data/election_archive/CA/Sonoma/2024/voter_file_synthetic.csv` (123 KB) |

> [!CAUTION]
> The pipeline's canonical vote path contains a known stub (`nov2024_general/detail.xlsx` = 5.7 KB), not the 13.5 MB real file. The real 2024 vote data is in `data/CA/counties/Sonoma/votes/2024/2024_general/detail.xlsx` but under a different slug.

---

## Phase 2 — Archive Classification Verification ⚠️ INCOMPLETE

**Registry path:** `derived/file_registry/latest/file_registry.json`

| file_id | filename | contest_id | uploaded_at | provenance | status |
|---|---|---|---|---|---|
| F_A7301251 | `...nov32020.xlsx` | 2020_general | 07:23:57 | REAL | ACTIVE |
| F_89408B43 | `...nov32020 (1).xlsx` | 2020_general | 07:25:28 | REAL | ACTIVE |
| F_77BB6B6C | `...nov32020.xlsx` | 2020_general | 07:27:53 | REAL | ACTIVE |
| F_A591D80B | `...nov32020.xlsx` | 2020_general | 07:30:29 | EXTERNAL | ACTIVE |
| F_0F119CF9 | `...nov32020.xlsx` | 2020_general | 07:31:41 | EXTERNAL | ACTIVE |

> [!WARNING]
> **5 duplicate registry entries** for the same physical file. None have been through fingerprinting, archive classification, or normalization. `archive_status` field is absent — these records only exist in the Data Manager UI registry, not in the archive pipeline's own registry.

**Archive pipeline's own normalized_elections.csv** (`data/election_archive/normalized/`):
- Shape: **(0 rows, 18 columns)** — empty header-only file
- The archive pipeline has never processed the 2020 upload

---

## Phase 3 — Normalization Audit ⚠️ MISMATCH

**Path:** `derived/archive/normalized_elections.csv`  
- Shape: **(3,000 rows × 18 columns)**  
- Years present: `[2024]`
- Counties present: `['Sonoma']`
- Source: **`voter_file_synthetic.csv`** (synthetic, not real election results)
- Content: 3,000 rows of duplicated synthetic voter file data, **not precinct-level election results**
- All `turnout`, `yes_votes`, `no_votes` columns are **null (100% null)**

> [!CAUTION]
> The archive normalization pipeline ran against synthetic voter file data, not election result files. It produced 3,000 rows of the same synthetic record repeated. This data is **not suitable for calibration or modeling**.

---

## Phase 4 — Precinct Join Audit ❌ NO JOIN HAS OCCURRED

| File | Shape | Status |
|---|---|---|
| `derived/archive/precinct_profiles.csv` | (0 rows, 8 cols) | **Empty** |
| `derived/archive/precinct_trends.csv` | (0 rows, 11 cols) | **Empty** |
| `derived/archive/similar_elections.csv` | (0 rows, 14 cols) | **Empty** |

No precinct join has ever been executed. The archive normalization step (`normalized_elections.csv`) produced synthetic voter data with no precinct IDs to join against geometry.

---

## Phase 5 — Modeling Input Audit ❌ 2020 DATA NOT USED

| Component | Data Used | Years | Notes |
|---|---|---|---|
| `lift_models.py` | `scored_df` from pipeline run | 2024 (stub) | Uses `nov2024_general/detail.xlsx` (5.7 KB stub) |
| `forecast_engine` | Pipeline precinct model | 2024 | Based on stub data |
| `calibration_engine` | No calibration data found | — | `derived/archive/precinct_profiles.csv` is empty |
| `scoring_engine_v2` | 4 precincts from stub xlsx | 2024 | Pipeline ran with stub producing 4 precinct rows |

**2020 data: NOT USED by any modeling component.**  
**2024 data: Used only from a 5.7 KB stub file producing 4 precinct rows.**

---

## Phase 6 — Campaign State Audit

**Campaign:** `2026_CA_sonoma_prop_50_special`  
**Latest state:** `derived/state/campaigns/2026_CA_sonoma_prop_50_special/latest/archive_summary.json`

```json
{
  "run_id": "20260314__0037",
  "predicted_directories": 34,
  "directories_confirmed": 0,
  "files_found": 2,
  "files_ingested": 0,
  "archive_ready": 0,
  "review_required": 0
}
```

> [!IMPORTANT]
> The archive builder (P25C) ran and **found 2 files** but ingested **0 files**. This means the discovery worked but the ingestion/classification step did not complete. Campaign isolation is not the issue — the files were found but rejected or not processed.

---

## Phase 7 — UI Data Visibility Audit

| UI Page | Data Source | 2020 Visible | 2024 Visible | Notes |
|---|---|---|---|---|
| Precinct Map | `scored_df` from pipeline | ❌ | ⚠️ 4 rows (stub) | Runs on stub data |
| Strategy | `precinct_profiles.csv` | ❌ | ❌ | Empty — no modeling basis |
| Political Intelligence | `archive_summary.json` | ❌ | ⚠️ Synthetic | Synthetic voter data only |
| Simulations | MC on `lift_models` | ❌ | ⚠️ Stub | Turnout = 0 (registered=0 in stub) |
| Diagnostics | Pipeline log | ❌ | ⚠️ | Reports on stub run |
| Data Manager | `file_registry.json` | ✅ 5 entries | ✅ | Visible but not pipeline-connected |
| Pipeline Runner | `_discover_contests()` | ✅ | ✅ | Now discovers both data trees |

---

## Phase 8 — Failure Point Detection

| # | Failure Point | Severity | Description |
|---|---|---|---|
| FP-01 | 2020 file not in pipeline votes/ tree | 🔴 CRITICAL | File at `data/elections/CA/Sonoma/2020_general/` is never read by `run_pipeline.py` which reads from `data/CA/counties/{county}/votes/{year}/{slug}/detail.xlsx` |
| FP-02 | 5 duplicate registry entries | 🟡 HIGH | Same file uploaded multiple times during debug. Should be deduplicated. |
| FP-03 | Archive normalization produced synthetic data | 🔴 CRITICAL | `derived/archive/normalized_elections.csv` contains 3,000 rows of voter_file_synthetic — not election results |
| FP-04 | Precinct join never executed | 🔴 CRITICAL | `precinct_profiles.csv`, `precinct_trends.csv`, `similar_elections.csv` all empty (0 rows) |
| FP-05 | Archive ingestion returned 0 files ingested | 🔴 CRITICAL | Archive builder found 2 files but ingested 0 |
| FP-06 | Pipeline running on 5.7 KB stub | 🟡 HIGH | `votes/2024/CA/Sonoma/nov2024_general/detail.xlsx` is a stub; real 13.5 MB file is at `2024_general/` |
| FP-07 | `registered=0` in all precinct rows | 🟡 HIGH | Integrity enforcement flagged this but pipeline continued — produces zero turnout_pct |

---

## Recommended Remediation

1. **Copy 2020 xlsx to votes/ tree:**
   ```
   votes/2020/CA/Sonoma/nov2020_general/detail.xlsx
   ```
   Then run pipeline with `--state CA --county Sonoma --year 2020 --contest-slug nov2020_general`

2. **Fix 2024 stub:** Replace `votes/2024/CA/Sonoma/nov2024_general/detail.xlsx` (5.7 KB) with the real 13.5 MB file from `data/CA/counties/Sonoma/votes/2024/2024_general/detail.xlsx`

3. **Re-run archive normalization** after real election data is in place so `precinct_profiles.csv` and `precinct_trends.csv` populate with real precinct data

4. **Deduplicate file_registry.json** — remove the 4 duplicate 2020 entries

5. **Run calibration** once archive normalization produces real election result rows
