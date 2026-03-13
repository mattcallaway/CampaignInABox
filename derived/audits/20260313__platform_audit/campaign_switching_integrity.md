# Campaign Switching Safety Audit
**Score:** 0.33 (UNSAFE)  **Safe:** 4  **Warning:** 1  **Unsafe:** 1

| Check | Risk | Detail |
|-------|------|--------|
| campaign_state_has_campaign_identifier | SAFE | campaign_state.json has campaign identifier |
| session_does_not_cache_role | SAFE | Sessions contain no role data — role resolved fresh from registry on each request |
| role_change_revokes_sessions | SAFE | update_user_role() calls revoke_all_sessions() |
| single_active_campaign_enforced | UNSAFE | UNSAFE: No single-active enforcement found |
| state_directory_isolation | WARNING | Derived state uses 'latest/' pattern — state is overwritten on campaign switch rather than |
| active_campaign_pointer_has_timestamp | SAFE | active_campaign.yaml switched_at=2026-01-01T00:00:00 |
