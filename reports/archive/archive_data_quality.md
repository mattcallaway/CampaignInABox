# Historical Archive Data Quality Report

## Overview
This report lists quality checks and data integrity warnings for the Historical Election Archive, ensuring historical data ingested into the campaign system meets standard metrics.

### Automated Checks
1. **Precinct Linkage Coverage:** 
   - Ensure `PCT_xxxx` matches against current canonical voter file shapes.
2. **Missing Contest Type Data:** 
   - Identifies any uploaded historical file missing a recognized contest type (`presidential`, `midterm`, `ballot_measure`, `municipal`).
3. **Turnout Rate Anomalies:** 
   - Flags turnout rates reported > 1.0 or < 0.05.
4. **Time Series Gaps:** 
   - Checks if a precinct has 2020 and 2024 results but is missing 2022 (assuming a full cycle sync).

### Current Diagnostics
- **Status:** PASS
- **Notes:** Simulated mock archive data is clean and fully continuous.
