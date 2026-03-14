# Persuasion Model Calibration Report
**Run ID:** 20260312__p24  |  **Generated:** 2026-03-12 23:05

## Status: SKIPPED — Insufficient Training Data

The support model could not be trained because the archive data in `derived/archive/normalized_elections.csv` does not contain enough rows with
valid `support_rate`, `turnout_rate`, and feature columns (need ≥ 50 clean rows).

### Current Archive Status
The archive currently contains voter-list data (individual records) not
precinct-level election results. To enable model training:

1. Place real election result files in `data/election_archive/<STATE>/<COUNTY>/<YEAR>/`
2. Result files must contain columns: `precinct`, `registered`, `ballots_cast` or `turnout_rate`,
   `yes_votes`/`no_votes` or `support_rate`
3. Re-run `engine/archive/archive_ingest.py` to rebuild `normalized_elections.csv`
4. Re-run `engine/archive/train_support_model.py` to train the calibrated model

### Fallback Behavior
Strategy and voter intelligence pages will use raw regression outputs without
isotonic calibration until a proper election archive is available.