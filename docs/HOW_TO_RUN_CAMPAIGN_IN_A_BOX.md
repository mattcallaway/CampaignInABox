# How to Run Campaign In A Box
### A Complete Guide for Campaign Staff

---

## Overview

Campaign In A Box is a data analysis and strategy platform that turns election results files into precinct-level maps, simulations, and field strategy. This guide walks you through every step from start to finish in plain English.

---

## 1. Creating a Campaign

Before anything else, you need to set up your campaign in the system.

**Steps:**
1. In the left sidebar, click **⚙️ Admin → Campaign Admin**
2. Click **"Create New Campaign"**
3. Fill in:
   - **Campaign Name** (e.g. "Prop 50 Special Election 2026")
   - **State** (e.g. CA)
   - **County** (e.g. Sonoma)
   - **Election Date**
4. Click **Save**

The system will activate your campaign and you'll see it displayed in the sidebar whenever you open the app.

> **Tip:** You can switch between campaigns at any time from Campaign Admin. Each campaign is completely isolated — data from one campaign cannot affect another.

---

## 2. Uploading Election Data

This is the most important step. The system needs at least one election results file to work.

**What file do you need?**

An election results file is a spreadsheet (XLS or CSV) from your County Registrar that shows, for each precinct, how many votes each candidate or measure received. Common names include:
- "Statement of Votes Cast"
- "Canvass Report"
- "Precinct Results"

**Steps:**
1. In the sidebar, click **📊 Data → Data Manager**
2. Click the **📤 Upload New File** tab
3. Drag or browse to your results file
4. The system will automatically detect the file type and show a preview
5. Verify or fill in:
   - **Campaign Data Type** — should auto-detect as "election_results"
   - **Year** — the election year (e.g. 2024)
   - **Contest Slug** — a short ID for the election (e.g. `nov2024_general`)
   - **State** and **County**
6. Click **Confirm & Save File**

> **Important:** Make sure the Year and Contest Slug are correct before saving. If they are wrong, the pipeline will not find the file. You can fix them later in the **File Registry** tab.

**Checking your files:**
- Click the **🗂️ File Registry** tab to see all uploaded files
- Files should show status `REGISTERED` or `ACTIVE`
- If a file shows the wrong year, select it from the dropdown, update the **Year** field, and click **💾 Save Changes**

---

## 3. Running the Pipeline

Once your data is uploaded, you need to run the pipeline to process it.

**What the pipeline does:**
- Reads your election file
- Matches precincts to geographic boundaries
- Builds a historical archive
- Generates a precinct map
- Prepares data for simulations and strategy

**Steps:**
1. In the sidebar, click **🏗️ System → Pipeline Runner**
2. In the **Contest** dropdown, select the election you want to process
3. Verify the green banner shows the correct state, county, year, and slug
4. Click **"Run Modeling Pipeline"**
5. Watch the log scroll by — this takes 1–5 minutes depending on file size

**What to look for in the log:**

| Log Line | Meaning |
|---|---|
| `DONE [OK] DATA_INTAKE_ANALYSIS` | File found and validated ✅ |
| `DONE [OK] LOAD_GEOMETRY` | Map boundaries loaded ✅ |
| `DONE [OK] LOAD_CROSSWALKS` | Precinct crosswalk ready ✅ |
| `DONE [OK] PARSE_CONTEST` | Results file parsed ✅ |
| `DONE [OK] ALLOCATE_VOTES` | Votes matched to precincts ✅ |
| `DONE [OK] ARCHIVE_INGEST` | Historical archive updated ✅ |
| `SKIP [SKIP] INGEST_STAGING` | Normal — only runs if staging dir provided |
| `FAIL` or `CRASH` | Something went wrong — download the log using the Download button and review |

> **If the pipeline fails:** Click the **Download Log** button, open it in a text editor, and look for the word `CRASH` or `AttributeError` or `FileNotFoundError`. This will tell you what went wrong.

---

## 4. Understanding the Archive

The Historical Archive is a database of precinct-level election history that the system builds automatically from your uploaded results.

**To view it:**
1. Click **📚 Intelligence → Historical Archive** in the sidebar
2. You will see a table showing each precinct with vote totals, turnout rates, and demographics

**What the archive powers:**
- Simulation scenarios
- Model calibration (gives simulations realistic numbers)
- Trend analysis across multiple elections

> The archive only exists after the pipeline has run successfully at least once. If the table is empty, run the pipeline first.

---

## 5. Using the Precinct Map

The Precinct Map shows a geographic view of your county color-coded by voting behavior.

**To view it:**
1. Click **🌍 Geography → Precinct Map** in the sidebar
2. The map loads automatically — you can zoom, pan, and click on precincts
3. The **Top 25 Precincts** chart on the right ranks precincts by strategic value

**If the map looks empty or shows only 1 precinct:**
- The pipeline has not run yet, or it did not complete the geometry join step
- Run the pipeline (step 3 above) and then refresh this page

---

## 6. Running Simulations

Simulations let you model different turnout scenarios and see how they affect the election outcome.

**To run simulations:**
1. Click **🎯 Field Operations → Simulations** in the sidebar
2. You'll see 4 pre-built scenarios (e.g. "Low Turnout", "Base Case", "High Enthusiasm")
3. Each row shows a projected outcome for that scenario

**If all simulation values show 0.0:**
- The model has not been calibrated yet
- This happens automatically after a successful pipeline run that reaches the MODEL_CALIBRATION step
- Run the pipeline and check that MODEL_CALIBRATION shows `DONE [OK]`

---

## 7. Generating Strategy

The Strategy page produces a written campaign strategy document based on your data.

**To generate a strategy:**
1. Click **📋 Strategy** in the sidebar
2. If no strategy documents exist, click the **"Generate Strategy"** button
3. The system will analyze your archive and produce a written strategy document

**What the strategy includes:**
- Top target precincts
- Recommended resource allocation
- Turnout vs. persuasion assessment
- Field operation priorities

---

## Troubleshooting Quick Reference

| Problem | Likely Cause | Fix |
|---|---|---|
| Pipeline can't find my file | Wrong year or contest slug | Fix in Data Manager → File Registry |
| Map is empty | Pipeline not run | Run pipeline |
| Simulations all show 0.0 | Model not calibrated | Run pipeline, check MODEL_CALIBRATION step |
| Archive is empty | Pipeline not run | Run pipeline |
| Strategy page is blank | No pipeline run for this contest | Run pipeline |
| Pipeline says "exit code 2" | Error in pipeline | Download log and look for CRASH or ERROR lines |
| File shows wrong year | Entered wrong during upload | Data Manager → File Registry → select file → edit Year → Save |

---

## Getting Help

- Check the **🔬 Diagnostics** page for a system health overview
- Download the pipeline log from Pipeline Runner for detailed error information
- Review `docs/SYSTEM_TECHNICAL_MAP.md` for deep technical documentation
- Review `reports/system_readiness.md` for a full readiness check
