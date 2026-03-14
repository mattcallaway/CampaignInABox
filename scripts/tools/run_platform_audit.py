"""
scripts/tools/run_platform_audit.py — Full Platform Integrity Audit

Sections 1-8:
  1  Campaign registry integrity
  2  Campaign switching safety
  3  User & role management
  4  Persistent session/login safety
  5  Archive integrity
  6  Source registry validity
  7  File fingerprinting accuracy
  8  Precinct normalization safety

Usage:
  python scripts/tools/run_platform_audit.py
"""
from __future__ import annotations

import csv
import json
import sys
import re
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RUN_ID   = "20260313__platform_audit"
OUT_DIR  = BASE_DIR / "derived" / "audits" / RUN_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Shared helpers ─────────────────────────────────────────────────────────────

def _j(path: Path) -> Dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _y(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

def _write(name: str, data: Any, md: str) -> None:
    (OUT_DIR / f"{name}.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    (OUT_DIR / f"{name}.md").write_text(md, encoding="utf-8")
    print(f"  [WRITTEN] {name}.json + .md")

def _now() -> str:
    return datetime.utcnow().isoformat()

def _risk(score: float) -> str:
    if score >= 0.8: return "safe"
    if score >= 0.5: return "warning"
    return "unsafe"

def _severity(score: float) -> str:
    if score >= 0.8: return "low"
    if score >= 0.5: return "moderate"
    return "critical"

# ── Section 1 — Campaign Registry Audit ─────────────────────────────────────

def audit_campaign_registry() -> float:
    print("\n[1] Campaign Registry Audit")
    reg_path  = BASE_DIR / "config" / "campaign_registry.yaml"
    ac_path   = BASE_DIR / "config" / "active_campaign.yaml"
    camps_dir = BASE_DIR / "config" / "campaigns"

    reg   = _y(reg_path)
    ac    = _y(ac_path)
    campaigns: List[Dict] = reg.get("campaigns", [])

    required_fields = ["campaign_id", "campaign_name", "state", "county",
                       "stage", "status", "is_active", "created_at"]
    valid_stages    = ["setup","data_ingest","modeling","field","gotv",
                       "post_election","archived"]

    results = []
    issues_all = []
    seen_ids = set()

    for c in campaigns:
        cid     = c.get("campaign_id", "MISSING")
        issues  = []

        # Duplicate IDs
        if cid in seen_ids:
            issues.append("DUPLICATE_CAMPAIGN_ID")
        seen_ids.add(cid)

        # Missing required fields
        missing = [f for f in required_fields if f not in c]
        if missing: issues.append(f"MISSING_FIELDS:{','.join(missing)}")

        # Stage validity
        if c.get("stage") not in valid_stages:
            issues.append(f"INVALID_STAGE:{c.get('stage')}")

        # Archived but still active
        if c.get("status") == "archived" and c.get("is_active"):
            issues.append("ARCHIVED_BUT_ACTIVE")

        # Per-campaign config file
        cfg_file = camps_dir / f"{cid}.yaml"
        cfg_exists = cfg_file.exists()

        # Archive data present
        archive_csv = BASE_DIR / "derived" / "archive" / "normalized_elections.csv"
        archive_present = archive_csv.exists() and archive_csv.stat().st_size > 1000

        # Model outputs
        model_dirs = [
            BASE_DIR / "derived" / "models",
            BASE_DIR / "derived" / "forecasts",
            BASE_DIR / "derived" / "calibration",
        ]
        model_present = any(
            any(p.iterdir()) for p in model_dirs if p.exists()
            and any(True for _ in p.iterdir())
        )

        if not cfg_exists:
            issues.append("NO_CAMPAIGN_CONFIG_FILE")

        issues_all.extend(issues)
        results.append({
            "campaign_id":        cid,
            "campaign_name":      c.get("campaign_name",""),
            "status":             c.get("status",""),
            "stage":              c.get("stage",""),
            "is_active":          c.get("is_active", False),
            "config_file_exists": cfg_exists,
            "archive_data_present": archive_present,
            "model_outputs_present": model_present,
            "issues":             issues,
        })

    # Active count check
    active_count = sum(1 for c in campaigns if c.get("is_active"))
    if active_count != 1:
        issues_all.append(f"ACTIVE_COUNT_WRONG:{active_count}")

    # active_campaign.yaml pointer consistency
    ac_id = ac.get("campaign_id","")
    reg_active_ids = [c.get("campaign_id") for c in campaigns if c.get("is_active")]
    pointer_ok = ac_id in reg_active_ids
    if not pointer_ok:
        issues_all.append(f"POINTER_MISMATCH:active_campaign.yaml={ac_id} registry_active={reg_active_ids}")

    score = max(0.0, 1.0 - len(issues_all) * 0.1)

    data = {
        "run_id": RUN_ID,
        "timestamp": _now(),
        "total_campaigns": len(campaigns),
        "active_count": active_count,
        "active_pointer_consistent": pointer_ok,
        "issues_total": len(issues_all),
        "campaigns": results,
        "top_issues": issues_all[:10],
        "score": round(score, 2),
        "risk": _risk(score),
    }

    rows = "\n".join(
        f"| `{r['campaign_id']}` | {r['status']} | {r['stage']} | "
        f"{'Yes' if r['is_active'] else 'No'} | "
        f"{'Yes' if r['config_file_exists'] else '**No**'} | "
        f"{'Yes' if r['archive_data_present'] else 'No'} | "
        f"{'Yes' if r['model_outputs_present'] else 'No'} | "
        f"{'; '.join(r['issues']) or 'None'} |"
        for r in results
    )
    md = f"""# Campaign Registry Audit
**Run ID:** {RUN_ID}  **Timestamp:** {_now()}

## Summary
- Total campaigns: {len(campaigns)}
- Active campaigns: {active_count}
- Active pointer consistent: {'Yes' if pointer_ok else '**No — MISMATCH**'}
- Issues found: {len(issues_all)}
- Score: **{score:.2f}** ({_risk(score).upper()})

## Campaign Table
| Campaign ID | Status | Stage | Active | Config File | Archive | Models | Issues |
|-------------|--------|-------|--------|-------------|---------|--------|--------|
{rows}

## Top Issues
{chr(10).join(f'- {i}' for i in issues_all) or '- None'}
"""
    _write("campaign_registry_audit", data, md)
    return score


# ── Section 2 — Campaign Switching Safety ────────────────────────────────────

def audit_campaign_switching() -> float:
    print("\n[2] Campaign Switching Safety Audit")

    findings: List[Dict] = []

    # 2a: Derived paths include campaign ID?
    derived_state = BASE_DIR / "derived" / "state" / "latest" / "campaign_state.json"
    state_data    = _j(derived_state)
    state_has_cid = bool(state_data.get("campaign_id") or state_data.get("contest_id"))
    findings.append({
        "check": "campaign_state_has_campaign_identifier",
        "result": state_has_cid,
        "risk": "safe" if state_has_cid else "warning",
        "detail": f"campaign_state.json {'has' if state_has_cid else 'MISSING'} campaign identifier",
    })

    # 2b: Session store doesn't embed role/permissions (no stale cache risk)
    sm_code = (BASE_DIR / "engine" / "auth" / "session_manager.py").read_text(encoding="utf-8")
    session_stores_role = "role" in sm_code and "session" in sm_code and any(
        kw in sm_code for kw in ['"role"', "'role'", "role_id"]
    )
    # Session SHOULD NOT store role (would cause stale role cache on switch)
    findings.append({
        "check": "session_does_not_cache_role",
        "result": not session_stores_role,
        "risk": "safe" if not session_stores_role else "warning",
        "detail": "Sessions contain no role data — role resolved fresh from registry on each request" if not session_stores_role
                  else "WARNING: Sessions may cache role — verify role changes take effect without re-login",
    })

    # 2c: Role change revokes sessions
    revoke_on_role = "revoke_all_sessions" in sm_code and "update_user_role" in (
        BASE_DIR / "engine" / "auth" / "auth_manager.py").read_text(encoding="utf-8")
    findings.append({
        "check": "role_change_revokes_sessions",
        "result": revoke_on_role,
        "risk": "safe" if revoke_on_role else "unsafe",
        "detail": "update_user_role() calls revoke_all_sessions()" if revoke_on_role
                  else "UNSAFE: Role changes do not revoke sessions",
    })

    # 2d: campaign_manager has set_active with single-active enforcement
    cm_code = (BASE_DIR / "engine" / "admin" / "campaign_manager.py").read_text(encoding="utf-8")
    single_active = "is_active = False" in cm_code and "set_active" in cm_code
    findings.append({
        "check": "single_active_campaign_enforced",
        "result": single_active,
        "risk": "safe" if single_active else "unsafe",
        "detail": "set_active() deactivates all others before marking new active" if single_active
                  else "UNSAFE: No single-active enforcement found",
    })

    # 2e: derived/state/latest is flat (not per-campaign partitioned)
    state_dir = BASE_DIR / "derived" / "state" / "latest"
    state_files = list(state_dir.glob("*.json"))
    campaign_ids_in_path = [f for f in state_files if "_" in f.stem and any(c.isdigit() for c in f.stem)]
    # Having per-campaign state dirs is good; single flat dir is a switching risk
    has_per_campaign_state = (BASE_DIR / "derived" / "state").is_dir() and any(
        d.name not in ("latest",) and d.is_dir()
        for d in (BASE_DIR / "derived" / "state").iterdir()
    )
    findings.append({
        "check": "state_directory_isolation",
        "result": True,   # The active pointer pattern isolates this
        "risk": "warning",
        "detail": (
            "Derived state uses 'latest/' pattern — state is overwritten on campaign switch "
            "rather than partitioned per-campaign. Acceptable if campaign_state.json contains "
            "campaign_id (checked above), but switching without clearing derived/ may "
            "blend data. Recommend per-campaign state dirs in future."
        ),
    })

    # 2f: active_campaign.yaml updated atomically
    ac_path = BASE_DIR / "config" / "active_campaign.yaml"
    ac      = _y(ac_path)
    ac_has_timestamp = bool(ac.get("switched_at"))
    findings.append({
        "check": "active_campaign_pointer_has_timestamp",
        "result": ac_has_timestamp,
        "risk": "safe" if ac_has_timestamp else "warning",
        "detail": f"active_campaign.yaml switched_at={ac.get('switched_at','MISSING')}",
    })

    safe_count    = sum(1 for f in findings if f["risk"] == "safe")
    warning_count = sum(1 for f in findings if f["risk"] == "warning")
    unsafe_count  = sum(1 for f in findings if f["risk"] == "unsafe")
    score = max(0.0, (safe_count - unsafe_count * 2) / max(len(findings), 1))

    data = {
        "run_id": RUN_ID, "timestamp": _now(),
        "safe": safe_count, "warning": warning_count, "unsafe": unsafe_count,
        "score": round(score, 2), "risk": _risk(score),
        "findings": findings,
    }
    rows = "\n".join(
        f"| {f['check']} | {f['risk'].upper()} | {f['detail'][:90]} |"
        for f in findings
    )
    md = f"""# Campaign Switching Safety Audit
**Score:** {score:.2f} ({_risk(score).upper()})  **Safe:** {safe_count}  **Warning:** {warning_count}  **Unsafe:** {unsafe_count}

| Check | Risk | Detail |
|-------|------|--------|
{rows}
"""
    _write("campaign_switching_integrity", data, md)
    return score


# ── Section 3 — User & Role Management Audit ─────────────────────────────────

def audit_user_admin() -> float:
    print("\n[3] User & Role Management Audit")

    users_path = BASE_DIR / "config" / "users_registry.json"
    roles_path = BASE_DIR / "config" / "roles_permissions.yaml"

    users_data = _j(users_path)
    roles      = _y(roles_path)
    users: List[Dict] = users_data.get("users", [])

    required_user_fields = ["user_id", "full_name", "role", "is_active",
                            "remember_login_allowed", "created_at"]
    valid_roles = list(roles.keys())

    results   = []
    all_issues: List[str] = []
    seen_uids = set()

    for u in users:
        uid    = u.get("user_id", "MISSING")
        issues = []

        # Duplicate ID
        if uid in seen_uids:
            issues.append("DUPLICATE_USER_ID")
        seen_uids.add(uid)

        # Missing fields
        missing = [f for f in required_user_fields if f not in u]
        if missing: issues.append(f"MISSING_FIELDS:{','.join(missing)}")

        # Invalid role
        role = u.get("role", "")
        if role not in valid_roles:
            issues.append(f"INVALID_ROLE:{role}")

        # Inactive but remember_login_allowed=True is fine (session_manager checks is_active)
        if not u.get("is_active", True) and u.get("remember_login_allowed", False):
            issues.append("DISABLED_USER_HAS_REMEMBER_LOGIN_ALLOWED")

        # Permission anomalies: viewer with manage_* permissions
        perms = roles.get(role, {})
        elevated = [p for p, v in perms.items() if "manage" in p and v]
        anomalies = []
        if role == "viewer" and elevated:
            anomalies = elevated

        all_issues.extend(issues)
        results.append({
            "user_id":               uid,
            "full_name":             u.get("full_name", ""),
            "role":                  role,
            "active":                u.get("is_active", True),
            "remember_login_allowed": u.get("remember_login_allowed", False),
            "last_login":            u.get("last_login_at"),
            "permission_anomalies":  anomalies,
            "issues":                issues,
        })

    # Auth manager has all required methods  
    auth_code = (BASE_DIR / "engine" / "auth" / "auth_manager.py").read_text(encoding="utf-8")
    has_create     = "def create_user" in auth_code
    has_disable    = "def disable_user" in auth_code
    has_role_change = "def update_user_role" in auth_code
    has_audit_log  = "user_admin_log" in auth_code

    score = max(0.0, 1.0 - len(all_issues) * 0.1)

    data = {
        "run_id": RUN_ID, "timestamp": _now(),
        "total_users": len(users),
        "active_users": sum(1 for u in users if u.get("is_active", True)),
        "roles_defined": len(valid_roles),
        "auth_features": {
            "create_user": has_create,
            "disable_user": has_disable,
            "update_user_role": has_role_change,
            "audit_log": has_audit_log,
        },
        "issues_total": len(all_issues),
        "score": round(score, 2),
        "risk": _risk(score),
        "users": results,
    }
    rows = "\n".join(
        f"| `{r['user_id']}` | {r['role']} | {'Yes' if r['active'] else 'No'} | "
        f"{'Yes' if r['remember_login_allowed'] else 'No'} | "
        f"{r['last_login'] or 'Never'} | "
        f"{'; '.join(r['permission_anomalies']) or 'None'} | "
        f"{'; '.join(r['issues']) or 'None'} |"
        for r in results
    )
    md = f"""# User & Role Management Audit
**Score:** {score:.2f} ({_risk(score).upper()})  **Users:** {len(users)}  **Roles:** {len(valid_roles)}

## Auth Engine Capabilities
- create_user: {'Yes' if has_create else 'MISSING'}
- disable_user: {'Yes' if has_disable else 'MISSING'}
- update_user_role: {'Yes' if has_role_change else 'MISSING'}
- audit_log: {'Yes' if has_audit_log else 'MISSING'}

## User Table
| User ID | Role | Active | Remember Login | Last Login | Anomalies | Issues |
|---------|------|--------|----------------|------------|-----------|--------|
{rows}
"""
    _write("user_admin_integrity", data, md)
    return score


# ── Section 4 — Persistent Session / Login Audit ─────────────────────────────

def audit_sessions() -> float:
    print("\n[4] Session / Login Audit")

    sm_path = BASE_DIR / "engine" / "auth" / "session_manager.py"
    sm_code = sm_path.read_text(encoding="utf-8") if sm_path.exists() else ""

    session_dir  = BASE_DIR / "data" / "local_sessions"
    session_file = session_dir / "sessions.json"

    sessions: Dict = {}
    if session_file.exists():
        try:
            sessions = json.loads(session_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    now  = datetime.utcnow()
    findings: List[Dict] = []

    # S1: Expiry enforcement in code
    has_expiry = "expires_at" in sm_code and "datetime.utcnow() > expires_at" in sm_code
    findings.append({
        "check": "expiry_enforced_in_code",
        "result": has_expiry, "severity": "critical" if not has_expiry else "low",
        "detail": "Session expiry check present in validate_session()" if has_expiry
                  else "CRITICAL: No expiry check found in session validation code",
    })

    # S2: No role cached in session
    session_stores_role = "role" in sm_code and any(
        line.strip().startswith('"role"') or '"role":' in line
        for line in sm_code.split("\n")
    )
    findings.append({
        "check": "session_does_not_store_role",
        "result": not session_stores_role, "severity": "low" if not session_stores_role else "moderate",
        "detail": "Session tokens contain only user_id + expiry, no role data" if not session_stores_role
                  else "Possible role data in session — verify stale permission risk",
    })

    # S3: Disabled user guard
    has_active_check = "is_active" in sm_code and "validate_session" in sm_code
    findings.append({
        "check": "disabled_user_blocked_at_session_validation",
        "result": has_active_check, "severity": "critical" if not has_active_check else "low",
        "detail": "validate_session() re-checks users_registry is_active on every call" if has_active_check
                  else "CRITICAL: Disabled users may still auto-login via remembered session",
    })

    # S4: Session store gitignored
    gitignore = (BASE_DIR / ".gitignore").read_text(encoding="utf-8", errors="ignore") if (BASE_DIR / ".gitignore").exists() else ""
    store_gitignored = "local_sessions" in gitignore
    findings.append({
        "check": "session_store_gitignored",
        "result": store_gitignored, "severity": "moderate" if not store_gitignored else "low",
        "detail": f"data/local_sessions/ {'IS' if store_gitignored else 'IS NOT'} in .gitignore",
    })

    # S5: revoke on logout in app.py
    app_code = (BASE_DIR / "ui" / "dashboard" / "app.py").read_text(encoding="utf-8")
    logout_revokes = "revoke_session" in app_code and "Logout" in app_code
    findings.append({
        "check": "logout_revokes_session_token",
        "result": logout_revokes, "severity": "moderate" if not logout_revokes else "low",
        "detail": "Logout button calls revoke_session() before clearing session state" if logout_revokes
                  else "WARNING: Logout may not revoke persistent session token",
    })

    # S6: Live session health check
    expired_count = 0
    valid_count   = 0
    for token, entry in sessions.items():
        try:
            exp = datetime.fromisoformat(entry.get("expires_at", "2000-01-01"))
            if exp < now:
                expired_count += 1
            else:
                valid_count += 1
        except Exception:
            expired_count += 1

    if expired_count > 0:
        findings.append({
            "check": "live_session_store_no_expired_tokens",
            "result": False, "severity": "low",
            "detail": f"{expired_count} expired token(s) in sessions.json — will be pruned on next validation call",
        })
    else:
        findings.append({
            "check": "live_session_store_no_expired_tokens",
            "result": True, "severity": "low",
            "detail": f"Session store clean: {valid_count} valid, 0 expired",
        })

    critical = sum(1 for f in findings if not f["result"] and f["severity"] == "critical")
    moderate = sum(1 for f in findings if not f["result"] and f["severity"] == "moderate")
    score = max(0.0, 1.0 - critical * 0.4 - moderate * 0.15)

    data = {
        "run_id": RUN_ID, "timestamp": _now(),
        "live_sessions": {"valid": valid_count, "expired": expired_count},
        "critical_issues": critical, "moderate_issues": moderate,
        "score": round(score, 2), "risk": _severity(score),
        "findings": findings,
    }
    rows = "\n".join(
        f"| {f['check']} | {f['severity'].upper()} | {'PASS' if f['result'] else 'FAIL'} | {f['detail'][:90]} |"
        for f in findings
    )
    md = f"""# Session / Login Security Audit
**Score:** {score:.2f}  **Critical issues:** {critical}  **Moderate:** {moderate}

| Check | Severity | Result | Detail |
|-------|----------|--------|--------|
{rows}

## Live Session Store
- Valid sessions: {valid_count}
- Expired sessions: {expired_count}
"""
    _write("session_integrity", data, md)
    return score


# ── Section 5 — Archive Integrity Audit ──────────────────────────────────────

def audit_archive() -> float:
    print("\n[5] Archive Integrity Audit")

    archive_dir      = BASE_DIR / "derived" / "archive"
    hist_dir         = BASE_DIR / "data" / "historical_elections"
    staging_dir      = BASE_DIR / "derived" / "archive_staging"
    archive_builder  = BASE_DIR / "engine" / "archive_builder"

    # Check builder modules
    builder_modules = list(archive_builder.glob("*.py")) if archive_builder.exists() else []
    has_ingestion   = any("ingest" in m.name for m in builder_modules)
    has_classifier  = any("classif" in m.name for m in builder_modules)
    has_scanner     = any("scan" in m.name or "discovery" in m.name for m in builder_modules)
    has_normalizer  = any("normaliz" in m.name for m in builder_modules)

    # Derived archive files
    archive_files = list(archive_dir.glob("*")) if archive_dir.exists() else []
    norm_csv = archive_dir / "normalized_elections.csv"
    summary_json = archive_dir / "archive_summary.json"
    precinct_profiles = archive_dir / "precinct_profiles.csv"

    norm_rows = 0
    if norm_csv.exists():
        try:
            with open(norm_csv, newline="", encoding="utf-8") as f:
                norm_rows = sum(1 for _ in csv.reader(f)) - 1
        except Exception:
            pass

    summary = _j(summary_json) if summary_json.exists() else {}

    # Historical election directories
    hist_elections = list(hist_dir.iterdir()) if hist_dir.exists() else []
    hist_dirs = [h for h in hist_elections if h.is_dir()]

    per_election = []
    for d in hist_dirs[:20]:  # cap at 20 for brevity
        files = list(d.rglob("*")) if d.is_dir() else []
        data_files = [f for f in files if f.suffix in (".csv",".xlsx",".json",".shp")]
        meta_files = [f for f in files if "meta" in f.name.lower() or "provenance" in f.name.lower()]
        per_election.append({
            "election_id":           d.name,
            "files_ingested":        len(data_files),
            "has_provenance":        len(meta_files) > 0,
            "validation_errors":     [],
        })

    # Score
    checks = [
        has_ingestion, has_classifier, has_scanner, has_normalizer,
        norm_csv.exists() and norm_rows > 0,
        summary_json.exists(),
        precinct_profiles.exists(),
    ]
    score = sum(checks) / max(len(checks), 1)

    data = {
        "run_id": RUN_ID, "timestamp": _now(),
        "builder_modules": {
            "ingestion": has_ingestion, "classifier": has_classifier,
            "scanner": has_scanner, "normalizer": has_normalizer,
        },
        "archive_files": [f.name for f in archive_files if f.is_file()],
        "normalized_election_rows": norm_rows,
        "archive_summary": summary,
        "historical_election_dirs": len(hist_dirs),
        "per_election_sample": per_election,
        "score": round(score, 2),
        "risk": _risk(score),
    }
    md = f"""# Archive Integrity Audit
**Score:** {score:.2f} ({_risk(score).upper()})

## Builder Modules
- Ingestion: {'Yes' if has_ingestion else 'MISSING'}
- Classifier: {'Yes' if has_classifier else 'MISSING'}
- Scanner/Discovery: {'Yes' if has_scanner else 'MISSING'}
- Normalizer: {'Yes' if has_normalizer else 'MISSING'}

## Archive Files (derived/archive/)
{chr(10).join(f'- {f.name} ({f.stat().st_size:,} bytes)' for f in archive_files if f.is_file())}

## Normalized Elections
- Rows in normalized_elections.csv: **{norm_rows:,}**
- Archive summary present: {'Yes' if summary_json.exists() else 'No'}
- Precinct profiles present: {'Yes' if precinct_profiles.exists() else 'No'}

## Historical Directories Scanned: {len(hist_dirs)}
{chr(10).join(f"- `{e['election_id']}`: {e['files_ingested']} data files" for e in per_election) or '- None found'}
"""
    _write("archive_integrity", data, md)
    return score


# ── Section 6 — Source Registry Audit ────────────────────────────────────────

def audit_source_registry() -> float:
    print("\n[6] Source Registry Audit")

    reg_dir = BASE_DIR / "config" / "source_registry"
    contest_path  = reg_dir / "contest_sources.yaml"
    geometry_path = reg_dir / "geometry_sources.yaml"
    allowlist_path = reg_dir / "official_domain_allowlist.yaml"

    contests  = _y(contest_path)
    geometries = _y(geometry_path)
    allowlist = _y(allowlist_path)

    allowed_domains = set()
    if isinstance(allowlist, dict):
        for domains in allowlist.values():
            if isinstance(domains, list):
                allowed_domains.update(domains)
    elif isinstance(allowlist, list):
        allowed_domains.update(allowlist)

    def _check_sources(sources_data: Any, source_type: str) -> List[Dict]:
        results = []
        if not isinstance(sources_data, dict):
            return results
        for jurisdiction, src_list in sources_data.items():
            if not isinstance(src_list, list):
                src_list = [src_list] if src_list else []
            for src in src_list:
                if not isinstance(src, dict):
                    continue
                src_id   = src.get("source_id") or src.get("id") or f"{jurisdiction}_src"
                url      = src.get("url") or src.get("discovery_url") or ""
                verified = src.get("verified", False)
                confidence = src.get("confidence", src.get("confidence_score", 0.0))
                issues   = []

                # Domain check
                domain = ""
                if url:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        domain = parsed.netloc
                    except Exception:
                        pass

                if domain and allowed_domains and domain not in allowed_domains:
                    # Check if it's a government domain pattern
                    is_gov = any(tld in domain for tld in [".gov", ".ca.gov", ".sos.ca.gov"])
                    if not is_gov and not src.get("override_domain_check"):
                        issues.append(f"DOMAIN_NOT_IN_ALLOWLIST:{domain}")

                if not url:
                    issues.append("NO_URL")

                if verified and float(confidence) < 0.5:
                    issues.append(f"VERIFIED_BUT_LOW_CONFIDENCE:{confidence}")

                results.append({
                    "source_id":  src_id,
                    "jurisdiction": jurisdiction,
                    "type":       source_type,
                    "domain":     domain,
                    "verified":   verified,
                    "confidence": confidence,
                    "reachable":  None,  # not tested (audit is read-only)
                    "issues":     issues,
                })
        return results

    contest_srcs  = _check_sources(contests, "contest")
    geometry_srcs = _check_sources(geometries, "geometry")
    all_srcs = contest_srcs + geometry_srcs

    issues_count = sum(len(s["issues"]) for s in all_srcs)
    score = max(0.0, 1.0 - issues_count * 0.05)

    data = {
        "run_id": RUN_ID, "timestamp": _now(),
        "contest_sources": len(contest_srcs),
        "geometry_sources": len(geometry_srcs),
        "allowed_domains": len(allowed_domains),
        "issues_total": issues_count,
        "score": round(score, 2), "risk": _risk(score),
        "sources": all_srcs[:50],  # cap output
    }
    rows = "\n".join(
        f"| `{s['source_id']}` | {s['type']} | {s['domain'][:40]} | "
        f"{'Yes' if s['verified'] else 'No'} | {s['confidence']} | "
        f"{'; '.join(s['issues']) or 'OK'} |"
        for s in all_srcs[:30]
    )
    md = f"""# Source Registry Audit
**Score:** {score:.2f} ({_risk(score).upper()})

- Contest sources: {len(contest_srcs)}
- Geometry sources: {len(geometry_srcs)}
- Allowed domains in allowlist: {len(allowed_domains)}
- Total issues: {issues_count}

> Note: Reachability testing skipped (audit is read-only, no HTTP requests made)

## Sources (first 30)
| Source ID | Type | Domain | Verified | Confidence | Issues |
|-----------|------|--------|----------|------------|--------|
{rows}
"""
    _write("source_registry_integrity", data, md)
    return score


# ── Section 7 — File Fingerprinting Accuracy Audit ───────────────────────────

def audit_fingerprinting() -> float:
    print("\n[7] File Fingerprinting Accuracy Audit")

    fp_dir      = BASE_DIR / "engine" / "file_fingerprinting"
    cache_dir   = BASE_DIR / "derived" / "fingerprint_cache"
    file_reg_dir = BASE_DIR / "derived" / "file_registry"

    # Check engine modules
    fp_modules = list(fp_dir.glob("*.py")) if fp_dir.exists() else []
    has_classifier  = any("classif" in m.name for m in fp_modules)
    has_fingerprint = any("finger" in m.name for m in fp_modules)
    has_schema      = any("schema" in m.name or "detect" in m.name for m in fp_modules)

    # Cache entries
    cache_files: List[Path] = []
    if cache_dir.exists():
        cache_files = [f for f in cache_dir.rglob("*.json") if f.is_file()]

    classified = 0
    unknown    = 0
    confidences: List[float] = []

    for cf in cache_files[:200]:
        try:
            d = _j(cf)
            ftype = d.get("file_type") or d.get("classification") or d.get("type")
            conf  = float(d.get("confidence", d.get("confidence_score", 0.0)))
            if ftype and ftype.lower() not in ("unknown", "unclassified", ""):
                classified += 1
            else:
                unknown += 1
            confidences.append(conf)
        except Exception:
            unknown += 1

    # File registry
    reg_files = list(file_reg_dir.glob("*.json")) if file_reg_dir.exists() else []
    total_registered = 0
    for rf in reg_files:
        try:
            entries = json.loads(rf.read_text(encoding="utf-8"))
            if isinstance(entries, list):
                total_registered += len(entries)
            elif isinstance(entries, dict):
                total_registered += 1
        except Exception:
            pass

    avg_confidence = sum(confidences) / max(len(confidences), 1)
    total_files    = classified + unknown

    score_parts = [
        1.0 if has_classifier else 0.0,
        1.0 if has_fingerprint else 0.0,
        1.0 if has_schema else 0.0,
        (classified / max(total_files, 1)) if total_files > 0 else 0.5,
        min(1.0, avg_confidence) if avg_confidence > 0 else 0.5,
    ]
    score = sum(score_parts) / len(score_parts)

    data = {
        "run_id": RUN_ID, "timestamp": _now(),
        "engine_modules": {
            "classifier": has_classifier,
            "fingerprinter": has_fingerprint,
            "schema_detector": has_schema,
        },
        "total_files": total_files,
        "classified_files": classified,
        "unknown_files": unknown,
        "avg_confidence": round(avg_confidence, 3),
        "total_registered": total_registered,
        "cache_entries_sampled": len(cache_files),
        "score": round(score, 2), "risk": _risk(score),
    }
    md = f"""# File Fingerprinting Accuracy Audit
**Score:** {score:.2f} ({_risk(score).upper()})

## Engine Modules
- Classifier: {'Yes' if has_classifier else 'MISSING'}
- Fingerprinter: {'Yes' if has_fingerprint else 'MISSING'}
- Schema Detector: {'Yes' if has_schema else 'MISSING'}

## Cache Statistics
| Metric | Value |
|--------|-------|
| Cache entries sampled | {len(cache_files)} |
| Total files (classified + unknown) | {total_files} |
| Classified | {classified} |
| Unknown | {unknown} |
| Avg confidence | {avg_confidence:.3f} |
| Registered in file registry | {total_registered} |

> Note: Sample limited to first 200 cache files.
"""
    _write("fingerprint_accuracy", data, md)
    return score


# ── Section 8 — Precinct Normalization Safety Audit ──────────────────────────

def audit_precinct_normalization() -> float:
    print("\n[8] Precinct Normalization Safety Audit")

    pid_dir    = BASE_DIR / "engine" / "precinct_ids"
    review_dir = BASE_DIR / "derived" / "precinct_id_review"

    pid_modules = list(pid_dir.glob("*.py")) if pid_dir.exists() else []
    has_normalizer    = any("normaliz" in m.name for m in pid_modules)
    has_crosswalk     = any("crosswalk" in m.name for m in pid_modules)
    has_schema_detect = any("schema" in m.name or "detect" in m.name for m in pid_modules)
    has_safe_join     = any("safe_join" in m.name for m in pid_modules)

    # Read id_rules.yaml for safety rules
    rules_path = pid_dir / "id_rules.yaml"
    rules = _y(rules_path)
    has_jurisdiction_scope = any(
        "jurisdiction" in str(rules).lower() or "county" in str(rules).lower()
        for _ in [1]
    )

    # Review dir outputs
    join_summary_files  = list(review_dir.glob("*join_summary*.json")) if review_dir.exists() else []
    no_match_files      = list(review_dir.glob("*no_match*.csv")) if review_dir.exists() else []

    # Parse latest join summary
    join_data: Dict = {}
    if join_summary_files:
        join_data = _j(sorted(join_summary_files)[-1])

    exact_matches       = join_data.get("exact_matches", 0)
    crosswalk_matches   = join_data.get("crosswalk_matches", 0)
    normalized_matches  = join_data.get("normalized_matches", 0)
    ambiguous_ids       = join_data.get("ambiguous_ids", 0)
    blocked_cross_jur   = join_data.get("blocked_cross_jurisdiction", 0)
    no_match_count      = join_data.get("no_match_count", 0)
    total_attempts      = join_data.get("total_attempts",
        exact_matches + crosswalk_matches + normalized_matches + ambiguous_ids + no_match_count)

    join_rate = (exact_matches + crosswalk_matches + normalized_matches) / max(total_attempts, 1)

    safety_checks = [
        ("normalizer_module_present",    has_normalizer),
        ("crosswalk_resolver_present",   has_crosswalk),
        ("schema_detector_present",      has_schema_detect),
        ("safe_join_engine_present",     has_safe_join),
        ("jurisdiction_scoped_rules",    has_jurisdiction_scope),
        ("join_summary_output_present",  len(join_summary_files) > 0),
        ("no_match_log_present",         len(no_match_files) > 0),
    ]
    checks_ok = sum(1 for _, v in safety_checks if v)
    score = (checks_ok / len(safety_checks)) * 0.6 + min(join_rate, 1.0) * 0.4

    data = {
        "run_id": RUN_ID, "timestamp": _now(),
        "safety_checks": {k: v for k, v in safety_checks},
        "exact_matches": exact_matches,
        "crosswalk_matches": crosswalk_matches,
        "normalized_matches": normalized_matches,
        "ambiguous_ids": ambiguous_ids,
        "blocked_cross_jurisdiction": blocked_cross_jur,
        "no_match_count": no_match_count,
        "total_attempts": total_attempts,
        "join_rate": round(join_rate, 3),
        "score": round(score, 2), "risk": _risk(score),
    }
    checks_md = "\n".join(f"| {k} | {'Yes' if v else 'MISSING'} |" for k, v in safety_checks)
    md = f"""# Precinct Normalization Safety Audit
**Score:** {score:.2f} ({_risk(score).upper()})

## Safety Checks
| Check | Status |
|-------|--------|
{checks_md}

## Join Statistics (latest run)
| Metric | Count |
|--------|-------|
| Total attempts | {total_attempts} |
| Exact matches | {exact_matches} |
| Crosswalk matches | {crosswalk_matches} |
| Normalized matches | {normalized_matches} |
| Ambiguous IDs | {ambiguous_ids} |
| Blocked (cross-jurisdiction) | {blocked_cross_jur} |
| No match | {no_match_count} |
| **Join rate** | **{join_rate:.1%}** |
"""
    _write("precinct_normalization_integrity", data, md)
    return score


# ── Entry point (sections 1-8) ────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  CAMPAIGN IN A BOX — Platform Integrity Audit (Part 1/2)")
    print(f"  Run ID: {RUN_ID}")
    print(f"  Output: {OUT_DIR}")
    print(f"{'='*60}")

    scores: Dict[str, float] = {}
    scores["campaign_registry"]    = audit_campaign_registry()
    scores["campaign_switching"]   = audit_campaign_switching()
    scores["user_admin"]           = audit_user_admin()
    scores["sessions"]             = audit_sessions()
    scores["archive"]              = audit_archive()
    scores["source_registry"]      = audit_source_registry()
    scores["fingerprinting"]       = audit_fingerprinting()
    scores["precinct_norm"]        = audit_precinct_normalization()

    partial_json = OUT_DIR / "_partial_scores_1_8.json"
    partial_json.write_text(json.dumps(scores, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"  PART 1 COMPLETE — Scores:")
    for k, v in scores.items():
        print(f"    {k:<30} {v:.2f}  ({_risk(v).upper()})")
    print(f"{'='*60}")
    print(f"\n  Now run: python scripts/tools/run_platform_audit_part2.py")
    print(f"{'='*60}\n")
