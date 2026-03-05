# Schema Mapping Report

**Context:** Sheet1  **Contest:** `2024_CA_sonoma_nov2024_general`  **Run:** `2026-03-05__033602__f4a083ab__msi`

**Inferred Contest Type:** `ballot_measure`


## Column Mappings

| Original | Canonical |
|---|---|
| `MPREC_ID` | `canonical_precinct_id` |
| `Registered` | `registered` |
| `BallotsCast` | `ballots_cast` |
| `YES` | `yes_votes` |
| `NO` | `no_votes` |

**Inferred (computed):** `turnout_pct`, `support_pct`

**Missing optional:** `support_pct`, `turnout_pct`