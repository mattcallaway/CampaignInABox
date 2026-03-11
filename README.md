# Campaign In A Box

**California Election Modeling Platform** — A self-improving, deterministic campaign intelligence platform that turns raw election data into field plans, targeting lists, and win probability forecasts.

---

## Table of Contents

1. [What This Platform Does](#what-this-platform-does)
2. [Quick Start](#quick-start)
3. [Step-by-Step Usage Guide](#step-by-step-usage-guide)
   - [Step 1 — Install & Setup](#step-1--install--setup)
   - [Step 2 — Load Your Election Data](#step-2--load-your-election-data)
   - [Step 3 — Configure Your Campaign](#step-3--configure-your-campaign)
   - [Step 4 — Run the Pipeline](#step-4--run-the-pipeline)
   - [Step 5 — Launch the Dashboard](#step-5--launch-the-dashboard)
   - [Step 6 — Read Your Results](#step-6--read-your-results)
   - [Step 7 — Run the War Room](#step-7--run-the-war-room)
   - [Step 8 — Feed Real Field Data Back In](#step-8--feed-real-field-data-back-in)
4. [Reading & Interpreting Your Results](#reading--interpreting-your-results)
5. [Using Results in the Real World](#using-results-in-the-real-world)
6. [Dashboard Pages Reference](#dashboard-pages-reference)
7. [Directory Structure](#directory-structure)
8. [Pipeline Steps](#pipeline-steps)
9. [Setup & Requirements](#setup--requirements)
10. [Data Requirements](#data-requirements)
11. [Security & Privacy](#security--privacy)

---

## What This Platform Does

Campaign In A Box models your race from precinct-level data and produces:

| Output | What It Gives You |
|--------|-------------------|
| **Win Number** | The exact vote total you must reach |
| **Vote Path Analysis** | Which precincts deliver those votes |
| **Field Plan** | How many doors to knock, where, when |
| **Targeting Lists** | Ranked precincts + voter universes by priority |
| **Persuasion Universe** | Voters most likely to swing your direction |
| **GOTV Universe** | Your soft supporters who need a nudge to vote |
| **Walk Turfs** | Pre-clustered neighborhoods for canvassers |
| **Win Probability** | Monte Carlo simulation with confidence ranges |
| **War Room Status** | Real-time campaign health as election day approaches |
| **Calibration** | Parameters that self-improve as you add historical data |

---

## Quick Start

```powershell
# 1. Install dependencies
pip install -r app/requirements.txt

# 2. Run the modeling pipeline
cd "Campaign In A Box"
python scripts/run_pipeline.py --state CA --county Sonoma --contest-slug prop_50_special

# 3. Launch the dashboard
streamlit run ui/dashboard/app.py
```

---

## Step-by-Step Usage Guide

### Step 1 — Install & Setup

```powershell
pip install streamlit pandas openpyxl pyyaml plotly scikit-learn numpy
pip install geopandas shapely pyogrio pyproj   # Optional: enables the map view
```

Verify Python ≥ 3.10 is installed:
```powershell
python --version
```

---

### Step 2 — Load Your Election Data

Place your county election results file in the canonical directory:

```
data/CA/counties/<County>/votes/<year>/<contest-slug>/detail.xlsx
```

**Example for Sonoma County Prop 50:**
```
data/CA/counties/Sonoma/votes/2025/prop_50_special/detail.xlsx
```

The `detail.xlsx` file must be the **official county election results workbook** — the same format used by Sonoma County's Elections Division, which includes:
- Precinct ID column
- Registered voters column
- Ballots cast column
- Yes/No vote columns (for ballot measures) or candidate columns (for candidate races)

**For historical calibration (optional but highly recommended):**
```
data/elections/CA/Sonoma/2022/detail.xls
data/elections/CA/Sonoma/2020/detail.xls
data/elections/CA/Sonoma/2018/detail.xls
```
Each additional year improves your calibration from `none → low → medium → high` confidence.

---

### Step 3 — Configure Your Campaign

Edit `config/campaign_config.yaml` to set your race specifics:

```yaml
campaign:
  contest_name: "Prop 50 — Safe Streets Initiative"
  contest_type: ballot_measure       # ballot_measure | candidate
  jurisdiction: "Sonoma County"
  election_date: "2026-11-03"        # ISO format

targets:
  target_vote_share: 0.55            # You need 55% YES to win
  win_margin: 0.05

budget:
  total_budget: 150000
  field_budget: 60000
  mail_budget: 50000
  digital_budget: 25000
  direct_contact_budget: 15000

field:
  total_volunteers: 80
  canvassing_days: 45
  doors_per_volunteer_per_day: 30
  phone_bank_nights: 20

turnout:
  baseline_turnout_pct: 0.42         # Expected overall turnout rate
  campaign_target_universe: gotv     # gotv | persuasion | both
```

> **Tip:** If you are unsure about any of these numbers, use the Campaign Setup page in the dashboard to fill them in visually.

---

### Step 4 — Run the Pipeline

```powershell
cd "Campaign In A Box"
python scripts/run_pipeline.py --state CA --county Sonoma --contest-slug prop_50_special
```

**Optional flags:**
```powershell
--year 2026                  # Override election year
--contest-mode measure       # measure | candidate | auto
--detail-path "path/to/detail.xlsx"   # Override file path
```

**What happens:** The pipeline runs ~30+ steps in order. You will see step-by-step logs like:

```
[START] → VALIDATE_GEOGRAPHY
[DONE]  [OK] VALIDATE_GEOGRAPHY (0.1s)
[START] → BUILD_MODEL
[DONE]  [OK] BUILD_MODEL — 390 precincts
[START] → SIMULATION
[DONE]  [OK] SIMULATION — 10,000 Monte Carlo scenarios
[START] → CALIBRATION
[DONE]  [OK] CALIBRATION — status=active, confidence=medium
...
[DONE]  ✅ Pipeline complete. Run ID: 2026-03-10__...
```

A full run takes **30–90 seconds** depending on your data size.

---

### Step 5 — Data Intake & File Management

Use the **📂 Data Manager** page in the dashboard to safely upload and manage files.
- **Upload:** Drop CSVs, Excel files, shapefiles, or documents. It will auto-detect the likely type (e.g. `voter_file`, `polling`, `election_results`), suggest a canonical path, and add it to the active file registry.
- **Manage & Archive:** Rename or relabel files without breaking paths. Old files are safely sent to `archive/` rather than permanently destroyed.
- **Missing Data Assistant:** Check the "Missing Data" tab to see what critical files your campaign lacks (e.g. no polling data, no voter file) and get exact recommendations on where to find them on the internet.
- **GitHub Safety:** The system explicitly guards against committing raw voter files to GitHub using an automatic pre-commit scanner.

---

### Step 6 — Launch the Dashboard

```powershell
streamlit run ui/dashboard/app.py
```

Your browser will open automatically at `http://localhost:8501`.

You will see the **Campaign Intelligence Dashboard** with a sidebar showing your campaign name, current run ID, and the State Snapshot panel.

---

### Step 6 — Read Your Results

Navigate through the sidebar pages. Start with these in order:

1. **🏠 Overview** — Your campaign at a glance
2. **📋 Strategy** — The full written strategy plan
3. **🎯 Targeting** — Precinct-level priority lists
4. **🔬 Simulations** — Win probability + scenarios

See [Reading & Interpreting Your Results](#reading--interpreting-your-results) below for detailed guidance.

---

### Step 7 — Run the War Room

As your campaign progresses, use the **🪖 War Room** to track live operations:

1. Click **"🪖 War Room"** in the sidebar
2. Go to the **"📋 Data Gaps"** tab to see what data is missing
3. Go to **"🌿 Field Ops"** to log field results
4. Update volunteer counts, budget actuals, and contact totals

---

### Step 8 — Feed Real Field Data Back In

Log your field results to improve model accuracy:

```
data/campaign_runtime/CA/Sonoma/prop_50_special/field_results.csv
data/campaign_runtime/CA/Sonoma/prop_50_special/contact_results.csv
data/campaign_runtime/CA/Sonoma/prop_50_special/volunteer_log.csv
```

Then rerun the pipeline. Your win probability and parameter estimates will update automatically based on real contact rates and canvassing performance.

---

## Reading & Interpreting Your Results

### Overview Page

| Metric | What It Means | Good Sign |
|--------|---------------|-----------|
| **Win Number** | Exact votes needed to win | Fixed. This is your target. |
| **Vote Path Coverage** | % of win number reachable through your identified universe | ≥ 100% means your universe is large enough |
| **Simulated Win Probability** | % of 10,000 simulated elections you win | > 60% comfortable; < 40% requires strategy change |
| **Field Pace** | Are you on track to knock all needed doors? | Green if on pace; red if you need more resources |
| **Precincts in Tier 1** | Highest-priority precincts (score ≥ 75th percentile) | Your canvassers should start here |

### Strategy Page

The strategy document shows:

- **Baseline Support** — Without any field work, this is your estimated YES vote share based on historical patterns
- **Required Lift** — How many percentage points your field operation must move to cross the win threshold
- **Recommended Channel Mix** — Whether you should prioritize mail, phones, doors, or digital based on your budget and timeline
- **Field Plan Table** — Exact doors/calls/mail pieces per precinct, per week

**Interpreting baseline support:**
- **> 55% baseline** — You are favored. Focus on GOTV; protect soft supporters.
- **48–55% baseline** — Toss-up. You need both persuasion AND GOTV.
- **< 48% baseline** — Behind. Prioritize persuasion in swing precincts; do not waste resources on long-shot precincts.

### Targeting Page

Each precinct has a **priority score (0–100)** and is assigned to a tier:

| Tier | Score Range | Meaning | What To Do |
|------|-------------|---------|------------|
| **Tier 1** | 75–100 | High-value, winnable | Heavy canvassing + mail |
| **Tier 2** | 50–75 | Reachable with effort | Phone bank + mail |
| **Tier 3** | 25–50 | Lower priority | Mail only |
| **Tier 4** | 0–25 | Not worth resources | Skip or minimal |

The score is calculated from:
- **Historical turnout** (30%) — precincts that vote reliably
- **Historical support rate** (35%) — precincts that lean your direction
- **Raw voter pool size** (15%) — larger precincts contribute more raw votes
- **Swing index** (20%) — estimated persuadability

**Voter universes:**
- **GOTV Universe** — These voters agree with you but may not vote. A door knock or phone call that reminds them to vote has the greatest impact here.
- **Persuasion Universe** — These voters are undecided or lean against you. A quality conversation can move them. Requires more time per contact.

### Simulation Page

The **Win Probability Histogram** shows the distribution of outcomes across 10,000 simulated elections:

- The **blue vertical line** is the win threshold (50% +1 votes)
- The **percentage above the line** is your win probability
- A **narrow histogram** = more certain outcome
- A **wide histogram** = highly volatile race; small changes can flip the result

**Turnout Scenarios:**

| Scenario | Meaning | Your Response |
|----------|---------|---------------|
| **Low turnout** | Fewer voters show up | GOTV becomes more critical; small universes can swing it |
| **Baseline turnout** | Model's central estimate | Your planned operation is calibrated for this |
| **High turnout** | More voters show | Typically helps incumbents; check if this helps or hurts your side |

### Calibration Page

| Status | Meaning |
|--------|---------|
| 🟡 **PRIOR ONLY** | No historical data yet. Parameters are literature defaults (Gerber & Green). |
| ✅ **ACTIVE — LOW** | 1 election parsed. Estimates have improved but with uncertainty. |
| ✅ **ACTIVE — MEDIUM** | 3+ elections, 50+ precincts. Reliable estimates. |
| ✅ **ACTIVE — HIGH** | 5+ elections, 100+ precincts. High-confidence estimates. |

**Parameter interpretation:**

| Parameter | Default | If Calibrated Higher | If Calibrated Lower |
|-----------|---------|---------------------|---------------------|
| **Baseline Turnout** | 45% | This electorate votes more than average — you need a larger win number | Lower electorate engagement — GOTV will have bigger impact |
| **Turnout Lift/Contact** | 6pp | Your contacts are very effective at driving turnout | Less effective — need more contacts per voter |
| **Persuasion Lift/Contact** | 0.6pp | Swing voters are moving — persuasion strategy is working | Hard to move — prioritize base GOTV instead |

---

## Using Results in the Real World

### Scenario A: Ballot Measure Campaign (8 weeks out)

**Situation:** You have 8 weeks, 60 volunteers, $120K budget.

1. Open **🏠 Overview** → Note your **Win Number** (e.g., 42,000 YES votes)
2. Check **Vote Path Coverage** — if < 100%, you don't have enough universe to win; expand your contact radius
3. Open **🎯 Targeting** → Export Tier 1 + Tier 2 precincts to CSV → give to field director
4. Open **📋 Strategy** → The field plan table shows exactly how many doors/precinct/week
5. Open **🔬 Simulations** → If baseline win probability < 50%, look at what turnout scenario gets you over — that becomes your GOTV priority

**Decision example:** Simulation shows you win in "high turnout" but lose in "low turnout" → **GOTV is your #1 priority.** Shift budget from persuasion mail to GOTV phone bank and late weekend canvassing.

---

### Scenario B: Candidate Race (12 weeks out)

**Situation:** Candidate race, tight margin, precinct-level data available.

1. Set `contest_type: candidate` in `campaign_config.yaml`
2. Run pipeline → Check **Swing Index** in Targeting page — highest swing precincts are your persuasion targets
3. Compare your **Persuasion Universe** size to your **contact capacity** (volunteers × days × doors/day)
4. If persuasion universe >> contact capacity: you must prioritize. Use **Tier 1 and Tier 2 precincts only** and focus on the **highest swing_index** rows first
5. Use **Walk Turfs** (Strategy page) to give each volunteer a pre-clustered neighborhood — reduces driving time, increases efficiency

**Decision example:** Tier 1 has 18 precincts, your team can realistically knock 15 in 10 weeks → **drop the 3 lowest-scoring Tier 1 precincts from your plan** and log the change in your campaign tracking sheet.

---

### Scenario C: Using the War Room During a Live Campaign

**Situation:** 3 weeks out, your team has been knocking doors for 4 weeks.

1. Log your actual doors knocked and phone contacts in War Room → **Field Ops** tab
2. Rerun the pipeline → check **War Room → Snapshot**
3. If actual contact rate < modeled rate: the pipeline will flag you as **behind pace** → you need to surge volunteers
4. If your support IDs are coming in higher than expected: the **Persuasion Lift** parameter will increase → the model will improve your win probability estimate
5. Check **Data Gaps** tab for open requests — these are the specific data points the model needs to upgrade from SIMULATED → REAL

**Decision example:** War Room shows "GOTV contact pace: 72% of goal with 3 weeks left." You're behind on your GOTV universe. Options:
- Add a weekend phone bank: adds ~2,000 contacts
- Narrow your universe to highest-propensity voters only (use TPS ≥ 70 filter in Targeting)
- Increase mail drops to compensate for missed door contacts

---

### Scenario D: Post-Election Learning

After election day, add the actual results to `data/elections/CA/<county>/<year>/detail.xls`.

Rerun the pipeline. The **Calibration page** will now show:
- **Forecast Accuracy** — how close were your predictions to actual results?
- Updated **MAE (Mean Absolute Error)** — the smaller, the better
- Revised parameter estimates that will make your **next campaign more accurate**

---

## Dashboard Pages Reference

| Page | Key Content | Primary Use |
|------|-------------|-------------|
| 🏠 **Overview** | Win number, vote path, KPIs, data provenance legend | Morning briefing |
| 🪖 **War Room** | Live campaign status, data gaps, field pace | Daily operations |
| 📐 **Calibration** | Parameter estimates, forecast accuracy, confidence level | Strategic calibration |
| 🗳️ **Campaign Setup** | Input form for campaign configuration | Initial/weekly setup |
| 🗺️ **Precinct Map** | Choropleth by score/tier/turnout/support | Area planning |
| 🎯 **Targeting** | Filterable targeting table + CSV export | Field list generation |
| 📋 **Strategy** | Full written strategy plan + field plan table | Briefings, donors |
| 🔬 **Simulations** | Win probability, outcome histogram, scenarios | Scenario planning |
| ⚡ **Advanced Modeling** | Universe allocation, lift models, optimizer | Data team use |
| 🧠 **Voter Intelligence** | TPS/PS distributions, universe quality | Voter file analysis |
| 🩺 **Diagnostics** | System health, join guard, artifact status | Technical QA |
| 🗄️ **Data Explorer** | Browse any dataset — sort, filter, export CSV | Data verification |

---

## Directory Structure

```
Campaign In A Box/
├── config/                         # Campaign configuration
│   ├── campaign_config.yaml        # Your campaign parameters (edit this)
│   ├── model_parameters.yaml       # Calibration parameters (auto-updated)
│   ├── field_ops.yaml              # Field operations defaults
│   └── advanced_modeling.yaml      # Modeling priors and weights
│
├── data/                           # Raw input data (gitignored where sensitive)
│   ├── CA/counties/Sonoma/votes/   # Election results detail workbooks
│   ├── elections/CA/Sonoma/        # Historical elections for calibration
│   └── campaign_runtime/           # Live field/contact data (gitignored)
│
├── engine/                         # Core modeling modules
│   ├── calibration/                # Calibration engine + sub-calibrators
│   ├── state/                      # Campaign State Store
│   ├── war_room/                   # War Room status + runtime loader
│   ├── provenance/                 # Data provenance tracking
│   ├── strategy/                   # Strategy generator
│   ├── voters/                     # Voter propensity + persuasion models
│   ├── audit/                      # Artifact validation
│   ├── integrity/                  # Join guard + repair engine
│   └── advanced_modeling/          # Universe allocation + lift models
│
├── scripts/
│   ├── run_pipeline.py             # Main pipeline entry point (run this)
│   ├── lib/                        # Schema, crosswalks, discovery
│   ├── aggregation/                # Vote allocator
│   ├── modeling/                   # Precinct model, scoring
│   ├── ops/                        # Field plan, region builder
│   └── tools/                      # Export + audit utilities
│
├── ui/dashboard/                   # Campaign Intelligence Dashboard
│   ├── app.py                      # Dashboard entry point
│   ├── data_loader.py              # State-store-aware artifact loader
│   ├── state_loader.py             # Campaign State Store reader
│   ├── calibration_view.py         # Calibration dashboard
│   ├── war_room_view.py            # War Room dashboard
│   └── ...                         # Other page views
│
├── derived/                        # Pipeline outputs (auto-generated)
│   ├── state/latest/               # Canonical current state (stable pointers)
│   ├── state/history/              # Per-run state snapshots
│   ├── calibration/                # Calibration parameters + summary
│   ├── precinct_models/            # Scored precinct model
│   ├── strategy_packs/             # STRATEGY_META + field plan + targets
│   ├── universes/                  # GOTV, persuasion, mail universes
│   ├── voter_models/               # TPS + PS scores (aggregated)
│   └── war_room/                   # War room status outputs
│
└── reports/                        # Generated reports
    ├── calibration/                # Calibration reports + comparisons
    ├── qa/                         # QA + diagnostics
    ├── state/                      # State diff reports
    ├── audit/                      # System audit reports
    └── validation/                 # Validation markdowns
```

---

## Pipeline Steps

The pipeline (`scripts/run_pipeline.py`) runs the following steps in order:

| Step | Purpose |
|------|---------|
| `INGEST_STAGING` | Optional: imports raw data from staging directory |
| `VALIDATE_GEOGRAPHY` | Checks precinct boundary files are present and valid |
| `VALIDATE_VOTES` | Confirms election results file can be found |
| `LOAD_CROSSWALKS` | Maps MPREC precinct IDs ↔ SRPREC IDs |
| `BUILD_MODEL` | Constructs the core precinct model DataFrame |
| `INTEGRITY_ENFORCEMENT` | Validates data constraints (turnout ≤ registered, etc.) |
| `FEATURE_ENGINEERING` | Computes swing index, support pct, targeting features |
| `UNIVERSE_BUILDING` | Builds GOTV, persuasion, and mail precinct universes |
| `SCORING_V2` | Assigns 0–100 priority scores to each precinct |
| `SIMULATION` | Runs 10,000 Monte Carlo election simulations |
| `FORECAST_GENERATION` | Computes scenario-based vote forecasts |
| `TURF_GENERATION` | Clusters precincts into walk turfs |
| `STRATEGY_GENERATOR` | Produces the full strategy pack |
| `CAMPAIGN_STRATEGY` | AI-assisted strategy generation and report writing |
| `CALIBRATION` | Runs the calibration engine (all 3 data sources) |
| `BUILD_PROVENANCE` | Tags every metric as REAL/SIMULATED/ESTIMATED/MISSING |
| `GENERATE_DATA_REQUESTS` | Identifies missing data gaps with priorities |
| `WAR_ROOM_STATUS` | Computes daily campaign status summary |
| `WAR_ROOM_FORECAST_UPDATE` | Compares baseline vs runtime forecast |
| `POST_RUN_AUDIT` | Runs full system health audit |
| `STATE_BUILD` | Assembles canonical Campaign State into state store |
| `STATE_DIFF` | Compares current state against previous run |

---

## Setup & Requirements

### Install Python dependencies

```powershell
pip install -r app/requirements.txt

# Or individually:
pip install streamlit pandas openpyxl pyyaml numpy scikit-learn   # Core (required)
pip install plotly                                                  # Charts
pip install geopandas shapely pyogrio pyproj                       # Map view (optional)
```

### Verified package versions (March 2026)

| Package | Version | Purpose |
|---------|---------|---------|
| `streamlit` | ≥ 1.30 | Dashboard UI |
| `pandas` | ≥ 2.0 | Data processing |
| `openpyxl` | ≥ 3.0 | Excel file reading |
| `numpy` | ≥ 1.26 | Numerical computing |
| `scikit-learn` | ≥ 1.4 | Calibration (logistic regression) |
| `plotly` | 6.6.0 | Charts and histograms |
| `pyyaml` | ≥ 6.0 | Configuration parsing |
| `geopandas` | 1.1.3 | Precinct map (optional) |
| `shapely` | 2.1.2 | Geometry operations (optional) |

---

## Data Requirements

### Election Results (required)
```
data/CA/counties/<County>/votes/<year>/<contest-slug>/detail.xlsx
```
Source: Official county elections department — same Excel workbook released on election night and updated during the canvass period.

### Historical Elections (recommended — enables calibration)
```
data/elections/CA/<County>/<year>/detail.xls
```
Each additional election year improves calibration confidence. 3+ years = medium confidence. 5+ years = high confidence.

### Geography Files (optional — enables map view)
```
data/CA/counties/<County>/geography/precinct_shapes/MPREC_GeoJSON/*.geojson
```

### Field Runtime Data (optional — improves War Room accuracy)
```
data/campaign_runtime/CA/<County>/<contest-slug>/field_results.csv
data/campaign_runtime/CA/<County>/<contest-slug>/contact_results.csv
data/campaign_runtime/CA/<County>/<contest-slug>/volunteer_log.csv
```

---

## Security & Privacy

| Scenario | Policy |
|----------|--------|
| **Voter names, addresses, VAN IDs** | Never stored. Never committed to GitHub. |
| **Individual voter scores** | Kept locally. Never pushed to repository. |
| **Historical election results** | Aggregated precinct-level only — safe to commit. |
| **Calibration parameters** | Aggregated statistics only — safe to commit. |
| **Campaign runtime data** | Stored locally in `data/campaign_runtime/` (gitignored). |
| **State store** | Aggregated precinct-level counts only — safe to commit. |

All voter-level data paths are covered by `.gitignore`. You can safely push this repository to GitHub without exposing individual voter data.

---

*Campaign In A Box — California Election Modeling Platform*  
*Built for field-first, data-driven campaigns.*
