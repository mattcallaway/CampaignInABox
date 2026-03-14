# UI DOM Observations — Prompt 30

## Campaign Overview Page (Home)
- Banner: "No real field data uploaded yet. Operations relying on models." (yellow)
- Campaign card shows: Prop 50 Special Election 2026, CA/Sonoma, MEDIUM health
- Role: campaign_manager / Matthew Callaway

## Data Manager
- **Upload New File tab:** File picker, data type dropdown, year/contest fields, Save button
- **File Registry tab:** 3 rows with edit/delete buttons per row
  - Row 1: StatementOfVotesCast-Webnov32020.xlsx | election_results | 2020 | REGISTERED
  - Row 2: SoCoNov2025StatewideSpclElec_PctCanvass (1).xlsx | election_results | 2025 | REGISTERED
  - Row 3: detail.xlsx | (type unclear) | year=2020 in 2025 slot | REGISTERED
- **Precinct ID Review tab:** No flagged IDs
- **Election Archive tab:** One row: 2024_general_test | coverage=0.92
- **Missing Data Assistant tab:** No critical missing items flagged

## Pipeline Runner
- Contest dropdown: shows multiple contests (nov2020_general selected for test)
- Green summary banner when nov2020_general selected: "state=CA county=Sonoma year=2020 slug=nov2020_general"
- Run button: "Run Modeling Pipeline" (primary button)
- After click: log streaming area appeared, showing PARSE_CONTEST progress
- Crash displayed as red error box with AttributeError traceback
- Download buttons: appeared after run completion/crash

## Historical Archive
- Shows 1 precinct: Precinct #7004, 2024 General, turnout score 0.42
- Warning box: "Model training history not found. Ensure models have been run at least once."
- Bar charts for precinct performance: present but sparse (1 data point)

## Precinct Map
- Mapbox rendered North Bay region (Sonoma/Napa/Marin)
- One precinct polygon highlighted
- "Top 25 Precincts by Target Score" bar chart: empty / no bars
- Filter panel on left: county/precinct selectors present

## Strategy Page
- Red/yellow info box: "No core strategy documents found in data/campaign/strategy/ for the current contest"
- "Generate Strategy (AI)" button present — not clicked in this audit
- No strategy content visible

## Simulations Page
- 4 rows: Baseline, Light, Medium, Heavy
- All projections show 0.0 for Net Vote Gain, Support Votes, Win Margin
- Appears to load scenario config but has no model output to display

## Diagnostics Page
- System Health: GREEN / HEALTHY ?
- Geometry: WARN (yellow) ??
- Join Guard: PASS ?
- "All required artifacts are present" ?
- No NEEDS warnings shown
