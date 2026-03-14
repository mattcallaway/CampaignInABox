# Human Input Requests — Post Prompt 30 Live Audit

## Question 1: detail.xlsx year tag mismatch
**Question:** In the Data Manager, `detail.xlsx` is tagged as year 2020 but attached to the 2025 Special Election contest slot.
**Why it matters:** If the pipeline selects `detail.xlsx` for a 2020 run, it will use the wrong data. If it selects it for 2025, the year metadata is wrong.
**Options:**
- A) Re-upload `detail.xlsx` and tag it correctly as year 2025
- B) Delete the incorrect entry and re-upload
**Recommended:** Option A — re-tag to year 2025 in Data Manager ? File Registry ? Edit
**Impact if wrong:** 2025 pipeline may use correctly-tagged file but archive will record wrong year; 2020 pipeline may pick up wrong file.

## Question 2: Does nov2020_general contest have a real result file?
**Question:** The UI shows the contest `nov2020_general` exists and `StatementOfVotesCast-Webnov32020.xlsx` is in the registry, but is this file in the canonical path the pipeline resolver expects?
**Why it matters:** If the resolver cannot find it, PARSE_CONTEST will skip.
**Check:** Look for the file at: `data/contests/CA/Sonoma/2020/nov2020_general/raw/`
**Action needed from you:** Confirm whether this path contains the 2020 results file.

## Question 3: Should 2024 also be run?
**Question:** A `2024_general_test` entry appears in the Election Archive with 0.92 coverage. Should a formal 2024 pipeline run be done?
**Why it matters:** Good calibration for the 2025 campaign requires accurate 2024 base data.
**Recommended:** Yes, run nov2024_general after nov2020_general succeeds.

## Question 4: No voter file uploaded yet
**Question:** The banner says \"No real field data uploaded yet. Operations relying on models.\" Do you have a voter file (VAN export / county roll) to upload?
**Why it matters:** Without a voter file, universe modeling and targeting will be synthetic.
**Options:** Upload VAN export or skip and use area-weighted model.
