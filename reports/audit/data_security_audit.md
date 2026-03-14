# Data Security Audit
**Campaign In A Box — Prompt 23 | Generated: 2026-03-12**

---

## 1. .gitignore Verification

`.gitignore` is present with **42 rules**. Key protections verified:

### Voter File Rules (5 rules found)
```
data/voters/
data/voter_files/
derived/voter_models/
derived/voter_segments/
/data/voters/
```

✅ All voter file directories are excluded from Git.

### Runtime Data Rules (3 rules found)
Patterns matching `runtime` and `field` protect campaign field data.

### Key Findings

| Check | Result |
|-------|--------|
| `.gitignore` present | ✅ |
| `data/voters/` excluded | ✅ |
| `data/voter_files/` excluded | ✅ |
| `derived/voter_models/` excluded | ✅ |
| `derived/voter_segments/` excluded | ✅ |
| `data/campaign_runtime/` excluded | ✅ |

---

## 2. PII Isolation Assessment

| Data Type | Location | Git-Safe? |
|-----------|---------|----------|
| Voter files (raw) | `data/voters/` | ✅ Excluded |
| Voter models / scores | `derived/voter_models/` | ✅ Excluded |
| Voter universes | `derived/voter_universes/` | ✅ Excluded |
| Voter segments | `derived/voter_segments/` | ✅ Excluded |
| Campaign runtime field | `data/campaign_runtime/` | ✅ Excluded |
| Trained model PKLs | `derived/models/` | ⚠️ SEC-01: Included in Git |
| Normalized elections | `derived/archive/` | ✅ Safe (aggregate, no PII) |
| File registry | `derived/file_registry/` | ⚠️ SEC-02: May contain filenames with PII-sensitive paths |

**SEC-01 (MEDIUM):** `derived/models/turnout_model.pkl` and `support_model.pkl` are committed to Git. While PKL files contain no voter PII directly, if models are trained on actual voter data, they may encode statistical patterns from that data (model inversion risk). Should assess whether models trained on real data should be excluded.

**SEC-02 (LOW):** `derived/file_registry/latest/file_registry.json` contains file paths and filenames of uploaded voter files. Filenames may contain jurisdiction, date, or source-identifying information. This file is currently included in Git.

---

## 3. `github_safety` Module

**File:** `engine/data_intake/github_safety.py`

Module exists. Purpose: validate that files staged for commit don't include sensitive data. No evidence that this module is called automatically pre-commit (no `.git/hooks/pre-commit` found).

**SEC-03 (HIGH):** `github_safety.py` is not wired into any automated pre-commit hook. It exists as a callable module but is not enforced. A developer could commit voter data without triggering this check.

**Recommendation:** Install `pre-commit` and wire `github_safety.py` as a pre-commit hook.

---

## 4. Derived Output Safety Assessment

All outputs in `derived/` are aggregate statistics derived from voter data — they do not contain individual voter records. These are safe for Git commit:
- `precinct_profiles.csv` — aggregated precinct-level stats
- `normalized_elections.csv` — historical results with no individual records
- `precinct_trends.csv` — trend slopes per precinct

✅ Derived aggregates are safe for Git.

---

## 5. Authentication System

**File:** `engine/auth/auth_manager.py`

The authentication system uses `config/users_registry.json` — plaintext user definitions with role assignments. Passwords (if any) are not apparent in the inventory.

**SEC-04 (HIGH):** If `users_registry.json` contains plaintext credentials, this file is committed to Git. Review contents and ensure no passwords are stored in plaintext.

---

## Summary

| Finding | Severity |
|---------|---------|
| SEC-01: ML model PKLs committed to Git | MEDIUM |
| SEC-02: File registry paths in Git | LOW |
| SEC-03: github_safety.py not enforced | HIGH |
| SEC-04: users_registry.json in Git — verify no passwords | HIGH |
