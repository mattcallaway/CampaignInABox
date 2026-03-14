# Backtest Report — 20260313__p26val
**Jurisdiction:** CA / Sonoma
**Generated:** 2026-03-13T02:06:33.722745
**Overall verdict:** `validated`  |  **Strategy status:** `ACTIVE_VALIDATED`

## Aggregate Metrics

| Metric | Value |
|--------|-------|
| Folds run | 2 |
| Avg Precision | 0.450 |
| Avg Recall | 0.875 |
| Avg F1 | 0.594 |
| Avg Support MAE | 0.0514 |
| Top-10 True Rate | 35.0% |

## Fold-by-Fold Results

| Held-Out Year | Training Years | Precision | Recall | F1 | Support MAE | Verdict |
|---------------|----------------|-----------|--------|----|-------------|---------|
| 2022 | 2018, 2020 | 0.400 | 0.750 | 0.522 | 0.0608 | marginally_useful |
| 2024 | 2018, 2020, 2022 | 0.500 | 1.000 | 0.667 | 0.0420 | useful |

## Narrative Summary

**Would this model have helped?** Yes. Avg F1=0.59 across 2 folds. Top-10 precision=35.0%.

**Where would it have failed?** Top false positives (predicted swing, didn't): 0400101, 0400115, 0400101, 0400116. Top false negatives (missed actual swing): 0400111, 0400102.

## Data Sufficiency

Backtest validated across 2 folds. Avg F1=0.59