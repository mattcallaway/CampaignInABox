# Model Input Inventory — Deep Archive Audit
**RUN_ID:** `2026-03-14__000841__audit`  
**Generated:** 2026-03-14T07:48:41  
**Campaign:** `2026_CA_sonoma_prop_50_special`

---

## What the Modeling System Is Actually Using

### Vote Data (Primary Modeling Input)

| Parameter | Value |
|---|---|
| File | `votes/2024/CA/Sonoma/nov2024_general/detail.xlsx` |
| Size | **5,687 bytes (5.7 KB — stub file)** |
| Precinct rows produced | ~4 rows |
| Real election data | ❌ No — this is a stub/placeholder |
| Registered voters | 0 (all rows have registered=0) |
| Derived turnout_pct | 0.0 (cannot divide by registered=0) |

> [!CAUTION]
> The real 2024 election data (13.5 MB, actual Sonoma SOV) is at:
> `data/CA/counties/Sonoma/votes/2024/2024_general/detail.xlsx`
> It is NOT being used by the pipeline because the slug is `2024_general` not `nov2024_general`.

### Archive Normalization Data

| File | Rows | Years | Real Data? |
|---|---|---|---|
| `derived/archive/normalized_elections.csv` | 3,000 | 2024 | ❌ Synthetic voter file rows |
| `data/election_archive/normalized/normalized_elections.csv` | 0 | — | N/A (header only) |

### Calibration Inputs

| Dataset | Status |
|---|---|
| `derived/archive/precinct_profiles.csv` | Empty (0 rows) |
| `derived/archive/precinct_trends.csv` | Empty (0 rows) |
| `derived/archive/similar_elections.csv` | Empty (0 rows) |
| Calibration outputs | **None available** — no real historical data ingested |

### Crosswalks Available (not yet used)

| File | Size | Type |
|---|---|---|
| `blk_mprec_097_g24_v01.csv` | 466 KB | Block → MPREC |
| `c097_g24_rg_blk_map.csv` | 540 KB | RG Block Map |
| `c097_g24_srprec_to_city.csv` | 18 KB | SRPREC → City |
| `c097_g24_sr_blk_map.csv` | 482 KB | SR Block Map |
| `c097_rg_rr_sr_svprec_g24.csv` | 89 KB | Multi-type crosswalk |
| `mprec_srprec_097_g24.csv` | 27 KB | MPREC ↔ SRPREC |

Crosswalks are present and valid for g24 (2024 geometry) but have not been applied because the precinct join step has never executed.

### Lift Model Inputs

| Component | Columns Present | Missing Critical Cols |
|---|---|---|
| `apply_lifts()` | `registered`, `ballots_cast`, `support_pct`, `contacts_estimated` | `turnout_pct` (now derived from ballots_cast/registered), `turnout_rate` |
| `apply_lifts_mc()` | Same as above | Pre-computed in pre-loop step (fix applied 2026-03-14) |

### Geography Inputs

| Type | Status |
|---|---|
| MPREC GeoJSON | ✅ Present |
| MPREC GeoPackage | ✅ Present |
| MPREC Shapefile | ✅ Present |
| SRPREC GeoJSON | ✅ Present |
| Boundary Index | ✅ Present (scaffolded, no boundary files matched) |

---

## Summary Answer Table

| Question | Answer |
|---|---|
| Were the 2020 files uploaded? | ✅ Yes — 4 MB xlsx in `data/elections/CA/Sonoma/2020_general/` |
| Were they classified? | ⚠️ In Data Manager registry only — not by archive pipeline |
| Were they normalized? | ❌ No |
| Did they join to precinct geometry? | ❌ No |
| Are they used by modeling? | ❌ No |
| Are they visible to the UI? | ✅ Data Manager only; Pipeline Runner now discovers them |
| Were the 2024 files used? | ⚠️ Stub only (5.7 KB) — real 13.5 MB file not connected to pipeline |
| Is calibration data available? | ❌ No — precinct_profiles and precinct_trends empty |
