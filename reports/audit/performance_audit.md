# Performance Audit
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

---

## 1. Large Voter File Handling

**File:** `engine/voters/voter_parser.py`

### Assessment

Voter files are read with `pd.read_csv()`. For California counties, voter files can be 50,000–500,000+ rows.

| Size Range | Risk |
|-----------|------|
| < 50K rows | ✅ No issue |
| 50K–200K rows | ⚠️ May be slow without chunking |
| > 200K rows | 🔴 Likely memory-constrained without chunking |

**PERF-01 (HIGH):** `voter_parser.py` reads entire voter file into memory in one shot. No chunked reading (`pd.read_csv(chunksize=...)`) or dtype optimization is used. For large counties (e.g., Sonoma County with ~240K registered voters), this will cause high memory usage and slow parse times.

**Recommendation:** Add `dtype` spec and consider chunked reads for files > 100K rows.

---

## 2. Simulation Performance

**File:** `engine/advanced_modeling/scenarios.py` + `lift_models.py`

Monte Carlo default: **2,000 iterations** × 4 scenarios = 8,000 `apply_lifts()` calls.

Each `apply_lifts()` operates on the full precinct DataFrame. For a 300-precinct election (typical CA special district):

| Operation | Estimated Time |
|-----------|----------------|
| Single `apply_lifts()` on 300 precincts | ~5ms |
| 2,000 × 4 scenarios | ~40 seconds |
| With overhead | ~60 seconds |

**PERF-02 (MEDIUM):** Monte Carlo runs serially in a single loop. For contests with 2,000+ precincts (large cities/statewide), simulation time could exceed 10 minutes. No parallelism (multiprocessing/joblib) is implemented.

**Recommendation:** Use `joblib.Parallel` to parallelize MC iterations, or reduce default iteration count with a configurable override.

---

## 3. Model Training Runtime

**Files:** `engine/archive/train_turnout_model.py`, `engine/archive/train_support_model.py`

Models trained on `normalized_elections.csv` — currently mock data with ~50–200 records.

For real historical data across a California statewide contest (100K+ precinct-year records):

| Stage | Estimated Time |
|-------|----------------|
| Random Forest (turnout) on 100K rows | ~30–120 seconds |
| Gradient Boost (support) on 100K rows | ~60–240 seconds |

**PERF-03 (MEDIUM):** Training scripts have no `n_jobs=-1` or parallel setting — scikit-learn defaults to single-threaded. Add `n_jobs=-1` to all estimators.

---

## 4. Data Loading Bottlenecks

**File:** `ui/dashboard/data_loader.py`

The Streamlit data loader reads from `derived/` on every cache miss. With 30+ derived directories, each containing multiple CSVs:

**PERF-04 (MEDIUM):** `data_loader.py` reads all available derived data regardless of which page is loaded. A user visiting only the "Overview" page triggers loading of strategy, simulations, war room, voter model data — most of which is unused on that page.

**Recommendation:** Lazy-load data per page using page-specific loaders rather than `load_all()`.

---

## 5. Arrow Serialization Warning

Server logs show:
```
Serialization of dataframe to Arrow table was unsuccessful.
ArrowTypeError: ("Expected bytes, got a 'int' object", 
  'Conversion failed for column Unnamed: 0 with type object')
```

**PERF-05 (MEDIUM):** DataFrames being passed to `st.dataframe()` contain mixed-type columns (`Unnamed: 0` as object). Streamlit cannot Arrow-serialize these — it falls back to slower Python serialization. Fix: `df.reset_index(drop=True)` before display, or `pd.read_csv(..., index_col=0)` to suppress the unnamed index column.

---

## 6. Memory Usage Summary

| Component | Estimated RAM |
|-----------|-------------|
| Voter file (200K rows) | ~150MB |
| Precinct model (5K rows) | <5MB |
| MC simulation (2K iterations) | ~20MB |
| Streamlit session state | ~10MB |
| Total estimated session load | ~200MB |

Acceptable for single-user local deployment. Multi-user cloud deployment would need session isolation.

---

## Summary

| Finding | Severity |
|---------|---------|
| PERF-01: Voter file read without chunking | HIGH |
| PERF-02: MC runs serially, no parallelism | MEDIUM |
| PERF-03: Model training single-threaded | MEDIUM |
| PERF-04: `load_all()` reads all data on every page | MEDIUM |
| PERF-05: Arrow serialization failure on unnamed index | MEDIUM |
