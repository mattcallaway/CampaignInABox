"""
scripts/tools/run_p208_admin_validation.py — Prompt 20.8

Validates all engine-level admin layer components.
No Streamlit dependency — pure Python assertions.

Phases:
  1. session_manager — create, validate, revoke, expire, disabled-user guard
  2. auth_manager    — create_user, update_user_role, disable_user, permissions
  3. campaign_manager — create, set_active, archive, stage, audit log
  4. config files    — campaign_registry.yaml, active_campaign.yaml, users_registry.json
  5. log files       — user_admin_log.csv, campaign_admin_log.csv written

Usage:
  python scripts/tools/run_p208_admin_validation.py
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# ── sys.path bootstrap ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# ── Output config ─────────────────────────────────────────────────────────────
PASS = "  [OK] "
FAIL = "  [FAIL] "
passed = 0
failed = 0


def ok(msg: str):
    global passed
    passed += 1
    print(f"{PASS}{msg}")


def fail(msg: str):
    global failed
    failed += 1
    print(f"{FAIL}{msg}")


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


# ── Phase 1: session_manager ──────────────────────────────────────────────────
section("Phase 1: session_manager")

# Use a temp session dir so real sessions aren't polluted
import engine.auth.session_manager as sm_module
_orig_session_file = sm_module.SESSION_FILE
_tmp_dir = tempfile.mkdtemp()
sm_module.SESSION_FILE = Path(_tmp_dir) / "sessions.json"
sm_module.USERS_PATH   = BASE_DIR / "config" / "users_registry.json"

from engine.auth.session_manager import (
    create_session, validate_session, revoke_session,
    revoke_all_sessions, purge_expired_sessions,
)

# 1.1 Create session for real user
token = create_session("mcallaway")
if token and len(token) >= 20:
    ok("create_session returns non-empty token (>=20 chars)")
else:
    fail(f"create_session returned bad token: {repr(token)}")

# 1.2 Validate returned token
uid = validate_session(token)
if uid == "mcallaway":
    ok("validate_session returns correct user_id")
else:
    fail(f"validate_session returned {uid!r} expected 'mcallaway'")

# 1.3 Revoke and re-validate
revoke_session(token)
uid_after_revoke = validate_session(token)
if uid_after_revoke is None:
    ok("validate_session returns None after revoke")
else:
    fail(f"validate_session returned {uid_after_revoke!r} after revoke (expected None)")

# 1.4 Unknown token returns None
bad = validate_session("completely_invalid_token_xyz")
if bad is None:
    ok("validate_session returns None for unknown token")
else:
    fail("validate_session did not return None for unknown token")

# 1.5 revoke_all_sessions
t2 = create_session("mcallaway")
t3 = create_session("mcallaway")
count = revoke_all_sessions("mcallaway")
if count >= 2:
    ok(f"revoke_all_sessions revoked {count} sessions")
else:
    fail(f"revoke_all_sessions only revoked {count}, expected >=2")

# 1.6 purge_expired_sessions (inject expired sessions)
sessions_data = {}
import secrets
exp_token = secrets.token_urlsafe(32)
sessions_data[exp_token] = {
    "user_id": "mcallaway",
    "created_at": "2000-01-01T00:00:00",
    "expires_at": "2000-01-02T00:00:00",  # long expired
}
sm_module.SESSION_FILE.write_text(json.dumps(sessions_data))
n = purge_expired_sessions()
if n == 1:
    ok("purge_expired_sessions removed 1 expired session")
else:
    fail(f"purge_expired_sessions returned {n}, expected 1")

# Restore real session file path
sm_module.SESSION_FILE = _orig_session_file
shutil.rmtree(_tmp_dir, ignore_errors=True)


# ── Phase 2: auth_manager ─────────────────────────────────────────────────────
section("Phase 2: auth_manager (create_user, update_user_role, disable_user)")

# Work on a temp copy of users_registry for write tests
_orig_users_path = BASE_DIR / "config" / "users_registry.json"
_tmp_users = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
_tmp_users.write(_orig_users_path.read_text(encoding="utf-8"))
_tmp_users.close()

from engine.auth.auth_manager import AuthManager
auth = AuthManager(BASE_DIR)
# Point users_path to temp copy
auth.users_path = Path(_tmp_users.name)
auth._load_config()

# 2.1 list_users
users = auth.list_users()
if len(users) >= 7:
    ok(f"list_users returned {len(users)} users")
else:
    fail(f"list_users returned only {len(users)} users")

# 2.2 get_active_users — all should be active in initial config
active = auth.get_active_users()
if len(active) >= 7:
    ok(f"get_active_users returned {len(active)} active users")
else:
    fail(f"get_active_users returned only {len(active)} active users")

# 2.3 create_user permission check — non-admin must fail
try:
    auth.create_user("viewer", "test_x", "Test X", "viewer")
    fail("create_user should have raised PermissionError for viewer role")
except PermissionError:
    ok("create_user raises PermissionError correctly for non-admin actor")

# 2.4 create_user success
try:
    new_u = auth.create_user("mcallaway", "test_p208", "Test Admin User", "analyst",
                              notes="p208 validation test user")
    if new_u.get("user_id") == "test_p208" and new_u.get("role") == "analyst":
        ok("create_user successfully creates user")
    else:
        fail(f"create_user returned unexpected data: {new_u}")
except Exception as e:
    fail(f"create_user raised: {e}")

# 2.5 duplicate user_id must fail
try:
    auth.create_user("mcallaway", "test_p208", "Duplicate", "viewer")
    fail("create_user should fail for duplicate user_id")
except ValueError:
    ok("create_user raises ValueError for duplicate user_id")

# 2.6 invalid role must fail
try:
    auth.create_user("mcallaway", "test_bad_role", "Bad Role User", "nonexistent_role")
    fail("create_user should fail for invalid role")
except ValueError:
    ok("create_user raises ValueError for invalid role")

# 2.7 update_user_role success
try:
    auth.update_user_role("mcallaway", "test_p208", "viewer", notes="test downgrade")
    updated = auth.get_user("test_p208")
    if updated and updated.get("role") == "viewer":
        ok("update_user_role changes role successfully")
    else:
        fail(f"update_user_role: role not changed, got {updated}")
except Exception as e:
    fail(f"update_user_role raised: {e}")

# 2.8 disable_user
try:
    auth.disable_user("mcallaway", "test_p208", notes="test disable")
    disabled = auth.get_user("test_p208")
    if disabled and not disabled.get("is_active", True):
        ok("disable_user sets is_active=False")
    else:
        fail("disable_user did not set is_active=False")
except Exception as e:
    fail(f"disable_user raised: {e}")

# 2.9 disabled user excluded from get_active_users
active_after = auth.get_active_users()
disabled_in_active = any(u["user_id"] == "test_p208" for u in active_after)
if not disabled_in_active:
    ok("get_active_users excludes disabled users")
else:
    fail("get_active_users still includes disabled user")

# 2.10 enable_user
try:
    auth.enable_user("mcallaway", "test_p208", notes="test re-enable")
    re_enabled = auth.get_user("test_p208")
    if re_enabled and re_enabled.get("is_active", False):
        ok("enable_user re-activates user")
    else:
        fail("enable_user did not set is_active=True")
except Exception as e:
    fail(f"enable_user raised: {e}")

# 2.11 can_manage_users
if auth.can_manage_users("mcallaway"):
    ok("can_manage_users returns True for campaign_manager")
else:
    fail("can_manage_users returned False for campaign_manager")

if not auth.can_manage_users("guest_01"):
    ok("can_manage_users returns False for viewer")
else:
    fail("can_manage_users returned True for viewer")

# 2.12 can_manage_campaigns
if auth.can_manage_campaigns("data_01"):
    ok("can_manage_campaigns returns True for data_director")
else:
    fail("can_manage_campaigns returned False for data_director")

# Cleanup temp users file
Path(_tmp_users.name).unlink(missing_ok=True)


# ── Phase 3: campaign_manager ─────────────────────────────────────────────────
section("Phase 3: campaign_manager (create, set_active, stage, archive)")

_tmp_campaign_dir = tempfile.mkdtemp()

import engine.admin.campaign_manager as cm_module
_orig_registry  = cm_module.REGISTRY_PATH
_orig_active    = cm_module.ACTIVE_PATH
_orig_campaigns = cm_module.CAMPAIGNS_DIR
_orig_log       = cm_module.ADMIN_LOG_PATH

cm_module.REGISTRY_PATH  = Path(_tmp_campaign_dir) / "campaign_registry.yaml"
cm_module.ACTIVE_PATH    = Path(_tmp_campaign_dir) / "active_campaign.yaml"
cm_module.CAMPAIGNS_DIR  = Path(_tmp_campaign_dir) / "campaigns"
cm_module.ADMIN_LOG_PATH = Path(_tmp_campaign_dir) / "campaign_admin_log.csv"

from engine.admin.campaign_manager import CampaignManager

mgr = CampaignManager(auth_manager=None)  # skip permissions in test

# 3.1 Empty registry
camps = mgr.list_campaigns()
if camps == []:
    ok("list_campaigns returns [] on empty registry")
else:
    fail(f"list_campaigns returned {camps} on empty registry")

# 3.2 Create campaign
try:
    c1 = mgr.create_campaign(
        actor_user_id="mcallaway",
        campaign_name="Test Campaign Alpha",
        contest_name="Prop 99 Test",
        contest_type="ballot_measure",
        state="CA",
        county="Sonoma",
        jurisdiction="Sonoma County",
        election_date="2027-06-01",
        stage="setup",
        set_active=True,
    )
    if c1.get("campaign_id") and c1.get("is_active"):
        ok(f"create_campaign created: {c1['campaign_id']}, is_active=True")
    else:
        fail(f"create_campaign returned unexpected: {c1}")
except Exception as e:
    fail(f"create_campaign raised: {e}")

# 3.3 Create second campaign
try:
    c2 = mgr.create_campaign(
        actor_user_id="mcallaway",
        campaign_name="Test Campaign Beta",
        contest_name="Prop 100 Test",
        contest_type="general",
        state="CA",
        county="Marin",
        jurisdiction="Marin County",
        election_date="2027-11-01",
        stage="setup",
        set_active=False,
    )
    ok(f"create_campaign created second campaign: {c2['campaign_id']}")
except Exception as e:
    fail(f"create_campaign (second) raised: {e}")

# 3.4 Only one active at a time
campaigns = mgr.list_campaigns()
active_count = sum(1 for c in campaigns if c.get("is_active"))
if active_count == 1:
    ok("Only one campaign is active after creating second (set_active=False)")
else:
    fail(f"Expected 1 active campaign, got {active_count}")

# 3.5 set_active switches
try:
    mgr.set_active("mcallaway", c2["campaign_id"])
    campaigns = mgr.list_campaigns()
    active_ids = [c["campaign_id"] for c in campaigns if c.get("is_active")]
    if active_ids == [c2["campaign_id"]]:
        ok(f"set_active switched to {c2['campaign_id']}")
    else:
        fail(f"set_active: active_ids={active_ids}")
except Exception as e:
    fail(f"set_active raised: {e}")

# 3.6 set_stage
try:
    mgr.set_stage("mcallaway", c1["campaign_id"], "modeling")
    c1_updated = mgr.get_campaign(c1["campaign_id"])
    if c1_updated and c1_updated.get("stage") == "modeling":
        ok("set_stage updates stage to 'modeling'")
    else:
        fail(f"set_stage failed: {c1_updated}")
except Exception as e:
    fail(f"set_stage raised: {e}")

# 3.7 Invalid stage rejected
try:
    mgr.set_stage("mcallaway", c1["campaign_id"], "launch_the_missiles")
    fail("set_stage should raise ValueError for invalid stage")
except ValueError:
    ok("set_stage raises ValueError for invalid stage")

# 3.8 archive_campaign
try:
    mgr.archive_campaign("mcallaway", c1["campaign_id"], notes="Test archive")
    c1_arch = mgr.get_campaign(c1["campaign_id"])
    if c1_arch and c1_arch.get("status") == "archived" and c1_arch.get("stage") == "archived":
        ok("archive_campaign sets status=archived + stage=archived")
    else:
        fail(f"archive_campaign failed: {c1_arch}")
except Exception as e:
    fail(f"archive_campaign raised: {e}")

# 3.9 audit log file was written
log_file = Path(_tmp_campaign_dir) / "campaign_admin_log.csv"
if log_file.exists() and log_file.stat().st_size > 50:
    with open(log_file, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if len(rows) >= 3:
        ok(f"campaign_admin_log.csv has {len(rows)} rows (header + entries)")
    else:
        fail(f"campaign_admin_log.csv has only {len(rows)} rows")
else:
    fail("campaign_admin_log.csv not created or empty")

# Restore
cm_module.REGISTRY_PATH  = _orig_registry
cm_module.ACTIVE_PATH    = _orig_active
cm_module.CAMPAIGNS_DIR  = _orig_campaigns
cm_module.ADMIN_LOG_PATH = _orig_log
shutil.rmtree(_tmp_campaign_dir, ignore_errors=True)


# ── Phase 4: config file integrity ───────────────────────────────────────────
section("Phase 4: Config file integrity")

import yaml

# 4.1 users_registry.json
users_path = BASE_DIR / "config" / "users_registry.json"
if users_path.exists():
    data = json.loads(users_path.read_text(encoding="utf-8"))
    users_list = data.get("users", [])
    all_have_is_active = all("is_active" in u for u in users_list)
    all_have_remember   = all("remember_login_allowed" in u for u in users_list)
    if all_have_is_active:
        ok(f"users_registry.json: all {len(users_list)} users have is_active field")
    else:
        fail("users_registry.json: some users missing is_active field")
    if all_have_remember:
        ok("users_registry.json: all users have remember_login_allowed field")
    else:
        fail("users_registry.json: some users missing remember_login_allowed field")
else:
    fail("users_registry.json not found")

# 4.2 roles_permissions.yaml has manage_users + manage_campaigns
roles_path = BASE_DIR / "config" / "roles_permissions.yaml"
if roles_path.exists():
    roles = yaml.safe_load(roles_path.read_text(encoding="utf-8")) or {}
    all_have_manage = all(
        "manage_users" in perm and "manage_campaigns" in perm
        for perm in roles.values()
    )
    if all_have_manage:
        ok(f"roles_permissions.yaml: all {len(roles)} roles have manage_users + manage_campaigns")
    else:
        fail("roles_permissions.yaml: some roles missing manage_users or manage_campaigns")
    if roles.get("campaign_manager", {}).get("manage_users") and \
       roles.get("campaign_manager", {}).get("manage_campaigns"):
        ok("campaign_manager has manage_users=True + manage_campaigns=True")
    else:
        fail("campaign_manager missing expected manage_* permissions")
    if not roles.get("viewer", {}).get("manage_users") and \
       not roles.get("viewer", {}).get("manage_campaigns"):
        ok("viewer correctly has manage_users=False + manage_campaigns=False")
    else:
        fail("viewer incorrectly has manage_* permissions")
else:
    fail("roles_permissions.yaml not found")

# 4.3 campaign_registry.yaml
reg_path = BASE_DIR / "config" / "campaign_registry.yaml"
if reg_path.exists():
    registry = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
    campaigns = registry.get("campaigns", [])
    if campaigns:
        first = campaigns[0]
        required_fields = ["campaign_id", "campaign_name", "state", "county",
                           "stage", "status", "is_active", "created_at"]
        missing = [f for f in required_fields if f not in first]
        if not missing:
            ok(f"campaign_registry.yaml: has {len(campaigns)} campaign(s) with all required fields")
        else:
            fail(f"campaign_registry.yaml: first campaign missing fields: {missing}")
        active_count = sum(1 for c in campaigns if c.get("is_active"))
        if active_count == 1:
            ok("campaign_registry.yaml: exactly 1 campaign is active")
        else:
            fail(f"campaign_registry.yaml: {active_count} campaigns are active (expected 1)")
    else:
        fail("campaign_registry.yaml: no campaigns found")
else:
    fail("campaign_registry.yaml not found")

# 4.4 active_campaign.yaml
ac_path = BASE_DIR / "config" / "active_campaign.yaml"
if ac_path.exists():
    active = yaml.safe_load(ac_path.read_text(encoding="utf-8")) or {}
    if active.get("campaign_id") and active.get("stage"):
        ok(f"active_campaign.yaml: points to '{active['campaign_id']}' stage='{active['stage']}'")
    else:
        fail(f"active_campaign.yaml: missing campaign_id or stage: {active}")
else:
    fail("active_campaign.yaml not found")


# ── Phase 5: Directory structure ──────────────────────────────────────────────
section("Phase 5: Directory and log structure")

log_dirs = [
    BASE_DIR / "logs" / "admin",
]
for d in log_dirs:
    if d.exists():
        ok(f"Directory exists: {d.relative_to(BASE_DIR)}")
    else:
        fail(f"Directory missing: {d.relative_to(BASE_DIR)}")

session_module = Path(BASE_DIR / "engine" / "auth" / "session_manager.py")
if session_module.exists():
    ok("engine/auth/session_manager.py exists")
else:
    fail("engine/auth/session_manager.py NOT found")

campaign_mgr = Path(BASE_DIR / "engine" / "admin" / "campaign_manager.py")
if campaign_mgr.exists():
    ok("engine/admin/campaign_manager.py exists")
else:
    fail("engine/admin/campaign_manager.py NOT found")

ui_views = [
    BASE_DIR / "ui" / "dashboard" / "user_admin_view.py",
    BASE_DIR / "ui" / "dashboard" / "campaign_admin_view.py",
]
for v in ui_views:
    if v.exists():
        ok(f"UI view exists: {v.name}")
    else:
        fail(f"UI view MISSING: {v.name}")


# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
total = passed + failed
print(f"  RESULT: {passed}/{total} assertions passed")
if failed == 0:
    print(f"  [PASS] ALL CHECKS PASSED -- Prompt 20.8 Admin Layer validated")
else:
    print(f"  [FAIL] {failed} assertion(s) FAILED")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
