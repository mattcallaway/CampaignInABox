# How to Run Campaign In A Box Correctly
**Written from live testing — 2026-03-14**

## Prerequisites
- App must be running at http://localhost:8501
- Start with: `streamlit run ui\dashboard\app.py` from the project root

## Step 1: Confirm Active Campaign
- Sidebar ? top section shows active campaign
- Should show: **Prop 50 Special Election 2026** (CA / Sonoma)
- If wrong, go to Campaign Admin and activate the correct campaign

## Step 2: Upload Contest Data (if not done)
1. Sidebar ? **Data Manager**
2. Click **Upload New File** tab
3. Upload your election results XLS/XLSX file
4. Set **Data Type** = `election_results`
5. Set **Year** = correct election year (2020, 2024, etc.)
6. Set **Contest** = the correct contest slug
7. Click Save / Register
8. Verify the file appears in the **File Registry** tab with correct metadata

> ??  **Common mistake:** The system does NOT automatically pick up uploaded files
> for the pipeline. Files must be in the canonical path AND the pipeline
> contest slug must match exactly.

## Step 3: Run the Pipeline
1. Sidebar ? **Pipeline Runner** (under System)
2. Select the correct contest from the dropdown
3. Check the green banner: verify state, county, year, slug are correct
4. Click **Run Modeling Pipeline**
5. Watch the log output — confirm these steps complete:
   - DATA_INTAKE_ANALYSIS ?
   - LOAD_GEOMETRY ?
   - LOAD_CROSSWALKS ? (should show 6 detection OK)
   - PARSE_CONTEST ?
   - ALLOCATE_VOTES ? (was crashing — now fixed)
   - ARCHIVE_INGEST ?
   - BUILD_PRECINCT_PROFILES ?

## Step 4: Verify Outputs After Run
After a successful pipeline run, within 30 seconds:
- **Precinct Map** — should show precinct coverage across Sonoma (~400 precincts)
- **Historical Archive** — should show rows for the contest you ran
- **Simulations** — numbers should update from zeros
- **Strategy** — only populates after running AI strategy generator

## What Each Section Needs to Populate
| Page | Needs |
|---|---|
| Precinct Map | Completed pipeline with geometry join |
| Historical Archive | Completed ARCHIVE_INGEST step |
| Simulations | Completed MODEL_VOTERS + MODEL_CALIBRATION steps |
| Strategy | Completed pipeline + user clicks Generate Strategy |

## Normal vs Bad Warnings
| Warning | Normal? |
|---|---|
| "No real field data uploaded" | Normal until voter file uploaded |
| "Model training history not found" | Normal on first run |
| Geometry: warn in Diagnostics | Investigate — may mean geometry file missing |
| LOAD_CROSSWALKS SKIP | Bad — means no crosswalk files found; check data/CA/counties/Sonoma/geography/crosswalks/ |
| ALLOCATE_VOTES AttributeError | Was a bug — fixed in Prompt 30 |
