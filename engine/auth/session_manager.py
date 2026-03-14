"""
engine/auth/session_manager.py — Prompt 20.8

Persistent remembered-session manager.

Sessions are stored in:
  data/local_sessions/sessions.json    (gitignored)

Session lifecycle:
  create_session(user_id) -> token (str)
  validate_session(token) -> user_id (str) | None
  revoke_session(token)
  revoke_all_sessions(user_id)
  update_last_login(user_id)

Security properties:
  - Token is 32-byte URL-safe random string
  - 7-day default expiry (configurable)
  - Disabled users cannot auto-login (checked against users_registry at validation time)
  - Role changes take effect on next session (session holds no role data)
  - All sessions are local filesystem only, never transmitted beyond localhost
  - Session store is NOT committed to Git (gitignored)
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SESSION_DIR  = BASE_DIR / "data" / "local_sessions"
SESSION_FILE = SESSION_DIR / "sessions.json"
USERS_PATH   = BASE_DIR / "config" / "users_registry.json"

DEFAULT_EXPIRY_DAYS = 7


def _load_sessions() -> dict:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    if not SESSION_FILE.exists():
        return {}
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"[SESSION] Could not read sessions.json: {e}")
        return {}


def _save_sessions(sessions: dict) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(sessions, indent=2), encoding="utf-8")


def _load_user(user_id: str) -> Optional[dict]:
    """Load a user dict from users_registry to check is_active + remember_login_allowed."""
    try:
        data = json.loads(USERS_PATH.read_text(encoding="utf-8"))
        for u in data.get("users", []):
            if u.get("user_id") == user_id:
                return u
    except Exception:
        pass
    return None


def create_session(
    user_id: str,
    expiry_days: int = DEFAULT_EXPIRY_DAYS,
) -> str:
    """
    Create a new persistent session for the given user.

    Returns the session token (opaque string).
    Returns empty string if the user is not allowed to use remembered sessions.
    """
    user = _load_user(user_id)
    if user is None:
        log.warning(f"[SESSION] create_session: user {user_id} not found")
        return ""
    if not user.get("is_active", True):
        log.warning(f"[SESSION] create_session: user {user_id} is inactive")
        return ""
    if not user.get("remember_login_allowed", True):
        log.info(f"[SESSION] create_session: remember_login_allowed=False for {user_id}")
        return ""

    sessions = _load_sessions()
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(days=expiry_days)).isoformat()
    sessions[token] = {
        "user_id":    user_id,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at,
    }
    _save_sessions(sessions)
    log.info(f"[SESSION] Created session for {user_id}, expires {expires_at}")
    return token


def validate_session(token: str) -> Optional[str]:
    """
    Validate a session token.

    Returns user_id if the session is valid, active, and not expired.
    Returns None for any failure condition (expired, user disabled, unknown token).
    """
    if not token:
        return None
    sessions = _load_sessions()
    entry = sessions.get(token)
    if not entry:
        return None

    # Check expiry
    try:
        expires_at = datetime.fromisoformat(entry["expires_at"])
        if datetime.utcnow() > expires_at:
            log.info(f"[SESSION] Token expired for {entry.get('user_id')}")
            # Clean up expired token
            sessions.pop(token, None)
            _save_sessions(sessions)
            return None
    except Exception:
        return None

    user_id = entry.get("user_id", "")

    # Re-check user is still active and remember_login_allowed
    user = _load_user(user_id)
    if user is None or not user.get("is_active", True):
        log.info(f"[SESSION] Auto-login blocked: user {user_id} inactive or missing")
        sessions.pop(token, None)
        _save_sessions(sessions)
        return None
    if not user.get("remember_login_allowed", True):
        sessions.pop(token, None)
        _save_sessions(sessions)
        return None

    return user_id


def revoke_session(token: str) -> None:
    """Revoke a specific session token."""
    sessions = _load_sessions()
    removed = sessions.pop(token, None)
    if removed:
        _save_sessions(sessions)
        log.info(f"[SESSION] Revoked token for user {removed.get('user_id')}")


def revoke_all_sessions(user_id: str) -> int:
    """
    Revoke all sessions for a specific user (e.g. when disabling user or changing role).
    Returns the number of sessions revoked.
    """
    sessions = _load_sessions()
    before_count = len(sessions)
    sessions = {t: s for t, s in sessions.items() if s.get("user_id") != user_id}
    revoked = before_count - len(sessions)
    _save_sessions(sessions)
    if revoked:
        log.info(f"[SESSION] Revoked {revoked} session(s) for user {user_id}")
    return revoked


def update_last_login(user_id: str) -> None:
    """
    Update last_login_at in users_registry.json for the given user.
    Non-fatal if it fails.
    """
    try:
        data = json.loads(USERS_PATH.read_text(encoding="utf-8"))
        for u in data.get("users", []):
            if u.get("user_id") == user_id:
                u["last_login_at"] = datetime.utcnow().isoformat()
                break
        USERS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        log.debug(f"[SESSION] Could not update last_login_at for {user_id}: {e}")


def purge_expired_sessions() -> int:
    """Remove all expired sessions from the store. Returns count removed."""
    sessions = _load_sessions()
    now = datetime.utcnow()
    before = len(sessions)
    valid = {}
    for token, entry in sessions.items():
        try:
            if datetime.fromisoformat(entry["expires_at"]) > now:
                valid[token] = entry
        except Exception:
            pass
    _save_sessions(valid)
    return before - len(valid)
