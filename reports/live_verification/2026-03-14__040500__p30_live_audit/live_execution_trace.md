# Live Execution Trace — Prompt 30
**Run ID:** `2026-03-14__040500__p30_live_audit`  **Time:** 2026-03-14T04:05-07:00

## 1. App Startup
- **Command:** `streamlit run ui\dashboard\app.py --server.port 8501 --server.headless true`
- **Working Dir:** `C:\Users\Mathew C\Campaign In A Box`
- **Python:** `C:\Users\Mathew C\AppData\Local\Programs\Python\Python313\Scripts\streamlit.exe`
- **PID:** 16268
- **HTTP check:** `GET http://localhost:8501 ? 200 OK` (after 6s startup)
- **Startup warnings:** None observed

## 2. Campaign Admin Inspection
- Navigated to Campaign Setup via sidebar
- **Active Campaign:** Prop 50 Special Election 2026
- **Contest ID:** `2025_CA_sonoma_nov2025_special`
- **State/County:** CA / Sonoma
- **User:** Matthew Callaway (campaign_manager)
- **Health:** MEDIUM
- **Persistent banner:** "No real field data uploaded yet. Operations relying on models."

## 3. Data Manager Inspection
**File Registry tab — 3 entries:**
| File | Data Type | Year | Status |
|---|---|---|---|
| StatementOfVotesCast-Webnov32020.xlsx | election_results | 2020 | REGISTERED |
| SoCoNov2025StatewideSpclElec_PctCanvass (1).xlsx | election_results | 2025 | REGISTERED |
| detail.xlsx | (2025 contest slot) | 2020 ?? | REGISTERED |

**Issue detected:** `detail.xlsx` has year tag 2020 but is in the 2025 contest slot.

**Election Archive tab:** 1 entry: `2024_general_test` with 0.92 coverage

## 4. Pipeline Runner Pre-Run State
- Contest dropdown had multiple options including nov2020_general and nov2025_special
- Selected: **nov2020_general**
- Green banner: "Pipeline will run with: state=CA county=Sonoma year=2020 slug=nov2020_general"
- No pre-run warnings for 2020 contest

## 5. Historical Archive
- 1 precinct row visible: Precinct 7004 (2024 General), turnout=0.42
- Warning: "Model training history not found"

## 6. Precinct Map
- Map rendered (Mapbox North Bay region)
- Only 1 precinct highlighted
- Top 25 chart empty/blank

## 7. Strategy Page
- Empty: "No core strategy documents found in data/campaign/strategy/"

## 8. Simulations Page
- 4 scenarios loaded (Baseline/Light/Medium/Heavy)
- All values: 0.0 (no completed model run)

## 9. Diagnostics Page
- System Health: GREEN / HEALTHY
- Geometry: WARN
- Join Guard: PASS
- All required artifacts: present ?

## 10. Pipeline Run — nov2020_general
- Clicked Run at approximately 04:26 AM PDT
- PARSE_CONTEST: completed 41.1s ?
- ALLOCATE_VOTES: CRASHED at 48s ?
- Error: `AttributeError: 'dict' object has no attribute 'columns'`
- Location: `scripts/run_pipeline.py` line 565
- Browser showed error log with traceback

## 11. Targeted Fix Applied
- Diagnosed: `xwalk` is `dict` returned by `load_crosswalk_from_category()`
- Old code: `xwalk.columns[0]` ? invalid on dict
- Fix: convert dict to DataFrame `[{_xw_src, _xw_tgt, _xw_wt}]` before safe_merge
- Fallback: area_weighted if dict empty or conversion fails
- File changed: `scripts/run_pipeline.py` lines 558-600
