# Source Registry Notes — Campaign In A Box
# Human-readable documentation and data collection guidance
# ---

## What This Registry Is

The source registry is the first lookup layer for election data discovery.
Before running a web search or requesting a file from a user, the system
checks this registry for known high-confidence sources.

## How Sources Are Added

1. **Seeded entries** — pre-loaded known-good sources for Sonoma County and California
2. **User-approved entries** — when a user confirms a source in the UI it is marked `user_approved: true`
3. **Manual entries** — added via the Source Registry UI page or by editing `local_overrides.yaml`

## How the Registry Is Used

1. `engine/source_registry/source_registry.py` loads and queries the registry
2. `engine/source_registry/source_resolver.py` ranks matches by confidence
3. `engine/archive/archive_ingest.py` calls the resolver first when looking for election data
4. `engine/data_intake/file_registry_pipeline.py` surfaces registry findings in the file registry

## File Structure

```
config/source_registry/
├── source_registry_schema.yaml  — field definitions (documentation only)
├── contest_sources.yaml         — seeded election result sources
├── geometry_sources.yaml        — seeded geometry/crosswalk sources
├── local_overrides.yaml         — user approvals + manual additions (gitignored if PII)
└── source_registry_notes.md     — this file
```

## Adding a New Contest Source

Add an entry to `contest_sources.yaml` with at minimum:
- `source_id` (unique slug)
- `source_kind`
- `official_status`
- `state`
- `confidence_default`
- `auto_ingest_allowed`
- `requires_confirmation`

## Confidence Scale

| Value | Meaning |
|-------|---------|
| 0.95+ | Official certified result; exact match |
| 0.85–0.94 | Preliminary official or well-known database |
| 0.70–0.84 | Estimated match; source likely correct |
| 0.50–0.69 | Low confidence; requires user confirmation |
| < 0.50 | Do not auto-ingest; flag for manual review |

## Safety Rules

The registry may contain:
- Public URLs
- Public filenames
- Official source metadata

The registry must NOT contain:
- Voter file paths with PII
- Private credentials or API keys
- Local machine-specific private paths (except in `local_overrides.yaml` which is gitignored)

## Data Sources Reference

### Sonoma County
- Election results: https://socoe.us/elections
- Statement of Vote: https://socoe.us/elections/election-results
- ElectionStats: https://electionstats.org/county/sonoma

### California Statewide
- Secretary of State: https://www.sos.ca.gov/elections
- Precinct-level data: https://elections.cdn.sos.ca.gov/
- MPREC geometry: https://statewidedatabase.org

### National
- Clarity ENR: https://results.enr.clarityelections.com/
