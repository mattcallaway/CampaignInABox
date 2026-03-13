# Sonoma Registry Repair Report — 20260313__p25a2

**Run:** 2026-03-13T01:04:30.920103
**Contest Sources:** 16 | **Geometry Sources:** 11

## Invalid Domains Removed

| Domain | Action |
|--------|--------|
| `socoe.us` | Removed — not an official government domain |
| `electionstats.org` | Replaced by `electionstats.sonomacounty.ca.gov` (official) |

## New / Updated Sources

| Source ID | Domain | Page Type | Confidence |
|-----------|--------|-----------|------------|
| `sonoma_registrar_elections` | `sonomacounty.gov` | discovery_page | 0.95 |
| `sonoma_registrar_2024_general` | `sonomacounty.gov` | election_page | 0.95 |
| `sonoma_registrar_2022_general` | `sonomacounty.gov` | election_page | 0.95 |
| `sonoma_registrar_2020_general` | `sonomacounty.gov` | election_page | 0.95 |
| `sonoma_registrar_2018_general` | `sonomacounty.gov` | election_page | 0.90 |
| `sonoma_registrar_2016_general` | `sonomacounty.gov` | election_page | 0.90 |
| `sonoma_registrar_special_elections` | `sonomacounty.gov` | discovery_page | 0.75 |
| `sonoma_electionstats_database` | `electionstats.sonomacounty.ca.gov` | discovery_page | 0.92 |
| `clarity_sonoma` | `results.enr.clarityelections.com` | discovery_page | 0.70 |
| `ca_sos_elections` | `sos.ca.gov` | discovery_page | 0.92 |
| `ca_sos_2024_general` | `sos.ca.gov` | election_page | 0.92 |
| `ca_sos_2022_general` | `sos.ca.gov` | election_page | 0.92 |
| `ca_sos_2020_general` | `sos.ca.gov` | election_page | 0.92 |
| `ca_sos_cdn_precinct_data` | `elections.cdn.sos.ca.gov` | file_download | 0.93 |
| `ca_sos_ballot_measures` | `vig.cdn.sos.ca.gov` | discovery_page | 0.90 |
| `sonoma_manual_upload` | `` | file_download | 0.59 |
| `ca_statewide_mprec_statewidedatabase` | `statewidedatabase.org` | discovery_page | 0.85 |
| `ca_sos_mprec_gis` | `sos.ca.gov` | discovery_page | 0.95 |
| `ca_sonoma_srprec_local` | `` | file_download | 0.59 |
| `ca_sonoma_srprec_registrar` | `sonomacounty.gov` | discovery_page | 0.88 |
| `ca_statewide_srprec_statewidedatabase` | `statewidedatabase.org` | discovery_page | 0.85 |
| `ca_statewide_mprec_srprec_crosswalk` | `statewidedatabase.org` | file_download | 0.85 |
| `ca_sonoma_mprec_srprec_crosswalk_local` | `` | file_download | 0.59 |
| `ca_sonoma_srprec_city_crosswalk` | `` | file_download | 0.59 |
| `ca_sonoma_city_boundaries` | `data.sonoma.opendata.arcgis.com` | file_download | 0.88 |
| `ca_sonoma_supervisorial_boundaries` | `data.sonoma.opendata.arcgis.com` | file_download | 0.88 |
| `ca_sonoma_school_district_boundaries` | `nces.ed.gov` | file_download | 0.82 |

## Schema Extensions Added

| Field | Values | Purpose |
|-------|--------|---------|
| `page_type` | discovery_page, election_page, file_download, api_endpoint | Classify what URL type this entry represents |
| `discovery_mode` | direct, pattern_scan, manual_only, api | How the system finds data files |
| `discovery_patterns` | glob patterns | URL patterns to follow on discovery pages |

## Confidence Recalculations

| Source ID | Original | Recalculated | Tier | Reason |
|-----------|----------|--------------|------|--------|
| `sonoma_registrar_elections` | 0.95 | 0.95 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `sonoma_registrar_2024_general` | 0.95 | 0.95 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `sonoma_registrar_2022_general` | 0.95 | 0.95 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `sonoma_registrar_2020_general` | 0.95 | 0.95 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `sonoma_registrar_2018_general` | 0.90 | 0.90 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `sonoma_registrar_2016_general` | 0.90 | 0.90 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `sonoma_registrar_special_elections` | 0.75 | 0.75 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `sonoma_electionstats_database` | 0.92 | 0.92 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `clarity_sonoma` | 0.70 | 0.70 | official_tier | Official domain (official tier tier), ceiling=0.9 |
| `ca_sos_elections` | 0.92 | 0.92 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `ca_sos_2024_general` | 0.92 | 0.92 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `ca_sos_2022_general` | 0.92 | 0.92 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `ca_sos_2020_general` | 0.92 | 0.92 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `ca_sos_cdn_precinct_data` | 0.93 | 0.93 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `ca_sos_ballot_measures` | 0.90 | 0.90 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `sonoma_manual_upload` | 0.70 | 0.59 ⚠️ | not_allowlisted | Domain '' not in official allowlist: capped at 0.5 |
| `ca_statewide_mprec_statewidedatabase` | 0.97 | 0.85 ⚠️ | academic_tier | Official domain (academic tier tier), ceiling=0.85 |
| `ca_sos_mprec_gis` | 0.95 | 0.95 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `ca_sonoma_srprec_local` | 0.97 | 0.59 ⚠️ | not_allowlisted | Domain '' not in official allowlist: capped at 0.5 |
| `ca_sonoma_srprec_registrar` | 0.88 | 0.88 | gov_tier | Official domain (gov tier tier), ceiling=0.99 |
| `ca_statewide_srprec_statewidedatabase` | 0.92 | 0.85 ⚠️ | academic_tier | Official domain (academic tier tier), ceiling=0.85 |
| `ca_statewide_mprec_srprec_crosswalk` | 0.95 | 0.85 ⚠️ | academic_tier | Official domain (academic tier tier), ceiling=0.85 |
| `ca_sonoma_mprec_srprec_crosswalk_local` | 0.97 | 0.59 ⚠️ | not_allowlisted | Domain '' not in official allowlist: capped at 0.5 |
| `ca_sonoma_srprec_city_crosswalk` | 0.88 | 0.59 ⚠️ | not_allowlisted | Domain '' not in official allowlist: capped at 0.5 |
| `ca_sonoma_city_boundaries` | 0.88 | 0.88 | official_tier | Official domain (official tier tier), ceiling=0.9 |
| `ca_sonoma_supervisorial_boundaries` | 0.88 | 0.88 | official_tier | Official domain (official tier tier), ceiling=0.9 |
| `ca_sonoma_school_district_boundaries` | 0.82 | 0.82 | academic_tier | Official domain (academic tier tier), ceiling=0.85 |

**Coverage:** strong | **Verified:** 23/27