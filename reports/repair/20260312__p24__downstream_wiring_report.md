# Downstream Wiring Report — Prompt 24

**Run ID:** 20260312__p24  |  **Generated:** 2026-03-12 23:00

## What Now Uses Archive-Backed Historical Data

| System | Component | Status | Notes |
|--------|-----------|--------|-------|
| Archive Ingest | `engine/archive/archive_ingest.py` | ✅ REAL data (voter list) | Provenance=REAL from `data/election_archive/CA/Sonoma/2024/` |
| Precinct Profiles | `engine/archive/precinct_profiles.py` | ✅ Archive-backed | Built from `normalized_elections.csv` |
| Trend Analysis | `engine/archive/trend_analysis.py` | ✅ Archive-backed | OLS slopes from archive data |
| Election Similarity | `engine/archive/election_similarity.py` | ✅ Archive-backed + config | Reads `campaign_config.yaml` for active contest type |
| File Registry | `engine/data_intake/file_registry_pipeline.py` | ✅ ACTIVE | Scans all pipeline outputs, updates `campaign_state.json` |

## What Now Uses Calibrated Persuasion Scores

| System | Status | Notes |
|--------|--------|-------|
| Support Model | ⚠️ SKIPPED — no election result data | Voter list file in archive lacks `support_rate`/`turnout_rate` |
| Voter Parser | ✅ IMPROVED | Chunked reads for large files now active |

## What Still Falls Back to Priors / Defaults

| System | Fallback Behavior | Required Data |
|--------|-------------------|---------------|
| `train_support_model.py` | Uses raw regression, no calibration | Real election result files with precinct totals |
| Monte Carlo baseline uncertainty | Uses lift-only variance from `lift_models.py` | Precinct profiles with multi-year turnout variance |
| Persuasion model | No calibration wrapper yet | Calibration requires ≥50 clean rows with support_rate |
| Similar elections weighting | Single election ranked (voter list) | Multi-year election results files |

## Required to Unlock Full Accuracy

To unlock full historical variance and calibrated persuasion scores:

1. **Add real election result files** to `data/election_archive/CA/Sonoma/<YEAR>/`
   - Required columns: `precinct`, `registered`, `ballots_cast`, `yes_votes`/`no_votes` or `support_rate`
   - Sources: CA Secretary of State Statement of Vote, County Elections Portal
   - Years needed: 2016, 2018, 2020, 2022 (2024 already present as voter list)

2. **Re-run archive pipeline** to rebuild `normalized_elections.csv` with real contest data

3. **Re-run `train_support_model.py`** to train and calibrate the support model

4. **Re-run `file_registry_pipeline.py`** to update `campaign_state.json`
