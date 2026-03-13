# Data Provenance Audit
**Score:** 0.30 (UNSAFE)

## Coverage
| Metric | Value |
|--------|-------|
| Provenance files found | 1 |
| Complete (all 5 fields) | 0 |
| Incomplete | 1 |
| Coverage | 0% |
| Provenance engine module present | Yes |

**Required fields:** `source_url`, `download_timestamp`, `fingerprint_type`, `normalization_method`, `confidence`

## Sample — Incomplete Records
- `2026-03-10__152246__e84498d7__msi__metric_provenance.json`: missing ['source_url', 'download_timestamp', 'fingerprint_type', 'normalization_method', 'confidence']
