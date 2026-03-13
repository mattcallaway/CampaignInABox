"""
engine/auth/auth_manager.py — Prompt 20.8 (expanded from Prompt 20)

Handles user sessions, dynamic role resolution, permission checking,
user CRUD operations, and admin audit logging.

New in Prompt 20.8:
  create_user(actor_id, ...)       — create new user
  update_user(actor_id, target, …) — update any user field
  update_user_role(...)            — change role specifically
  disable_user(actor_id, target)   — set is_active=False + revoke sessions
  enable_user(actor_id, target)    — re-enable a user
  list_users()                     — return all users with role labels
  get_active_users()               — only is_active=True users

Audit trail written to: logs/admin/user_admin_log.csv
"""

import csv
import json
import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
ADMIN_LOG    = BASE_DIR / "logs" / "admin" / "user_admin_log.csv"
ADMIN_LOG.parent.mkdir(parents=True, exist_ok=True)

_LOG_HEADER = ["timestamp", "actor_user_id", "target_user_id", "action",
               "old_role", "new_role", "notes"]


def _ensure_log_header():
    if not ADMIN_LOG.exists() or ADMIN_LOG.stat().st_size == 0:
        with open(ADMIN_LOG, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(_LOG_HEADER)


def _write_audit(actor: str, target: str, action: str,
                 old_role: str = "", new_role: str = "", notes: str = ""):
    _ensure_log_header()
    with open(ADMIN_LOG, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.utcnow().isoformat(), actor, target,
            action, old_role, new_role, notes,
        ])


class AuthManager:
    def __init__(self, root_dir: Path):
        self.root_dir   = root_dir
        self.users_path = root_dir / "config" / "users_registry.json"
        self.roles_path = root_dir / "config" / "roles_permissions.yaml"
        self._users: List[Dict[str, Any]] = []
        self._roles: Dict[str, Dict[str, bool]] = {}
        self._load_config()

    # ── Config Loading ─────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        try:
            if self.users_path.exists():
                with open(self.users_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._users = data.get("users", [])
            else:
                log.warning(f"User registry not found at {self.users_path}")

            if self.roles_path.exists():
                with open(self.roles_path, "r", encoding="utf-8") as f:
                    self._roles = yaml.safe_load(f) or {}
        except Exception as e:
            log.error(f"Failed to load Auth config: {e}")

    def reload(self) -> None:
        """Reload config from disk (call after any write)."""
        self._load_config()

    def _save_users(self) -> None:
        with open(self.users_path, "w", encoding="utf-8") as f:
            json.dump({"users": self._users}, f, indent=2)
        self.reload()

    # ── Read Operations ────────────────────────────────────────────────────────

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        for user in self._users:
            if user.get("user_id") == user_id:
                return user
        return None

    def get_all_users(self) -> List[Dict[str, Any]]:
        return list(self._users)

    def get_active_users(self) -> List[Dict[str, Any]]:
        return [u for u in self._users if u.get("is_active", True)]

    def list_users(self) -> List[Dict[str, Any]]:
        """Return all users with role display labels."""
        return [
            {**u, "role_label": u.get("role", "").replace("_", " ").title()}
            for u in self._users
        ]

    def get_all_roles(self) -> List[str]:
        """Return list of available role IDs from roles_permissions.yaml."""
        return list(self._roles.keys())

    # ── Permission Checks ──────────────────────────────────────────────────────

    def has_permission(self, user_id: str, permission: str) -> bool:
        user = self.get_user(user_id)
        if not user or not user.get("is_active", True):
            return False
        role_id = user.get("role")
        if not role_id or role_id not in self._roles:
            return False
        return bool(self._roles[role_id].get(permission, False))

    def require_permission(self, user_id: str, permission: str) -> None:
        if not self.has_permission(user_id, permission):
            user = self.get_user(user_id)
            name = user.get("full_name", "Unknown") if user else "Unknown User"
            role = user.get("role", "None") if user else "None"
            log.warning(f"Permission denied: {name} ({role}) attempted {permission}")
            raise PermissionError(f"User {user_id} lacks permission: {permission}")

    def can_manage_users(self, user_id: str) -> bool:
        return self.has_permission(user_id, "manage_users")

    def can_manage_campaigns(self, user_id: str) -> bool:
        return self.has_permission(user_id, "manage_campaigns")

    # ── User CRUD ──────────────────────────────────────────────────────────────

    def create_user(
        self,
        actor_user_id: str,
        user_id: str,
        full_name: str,
        role: str,
        is_active: bool = True,
        remember_login_allowed: bool = True,
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Create a new user.

        Args:
            actor_user_id:  ID of the admin performing the action
            user_id:        New user's login ID
            full_name:      Display name
            role:           Role ID from roles_permissions.yaml
            is_active:      Whether user starts active
            remember_login_allowed: Whether persistent sessions are allowed
            notes:          Optional notes

        Returns:
            The new user dict

        Raises:
            PermissionError if actor lacks manage_users
            ValueError if user_id already exists or role is invalid
        """
        self.require_permission(actor_user_id, "manage_users")

        if self.get_user(user_id):
            raise ValueError(f"User ID '{user_id}' already exists")
        if role not in self._roles:
            raise ValueError(f"Role '{role}' not found in roles_permissions.yaml. "
                             f"Valid: {list(self._roles.keys())}")

        now = datetime.utcnow().isoformat()
        new_user = {
            "user_id":               user_id,
            "full_name":             full_name,
            "name":                  full_name,     # backward compat
            "role":                  role,
            "is_active":             is_active,
            "remember_login_allowed": remember_login_allowed,
            "created_at":            now,
            "last_login_at":         None,
            "notes":                 notes,
        }
        self._users.append(new_user)
        self._save_users()
        _write_audit(actor_user_id, user_id, "create_user",
                     new_role=role, notes=f"Created: {full_name}")
        log.info(f"[AUTH] User created: {user_id} ({role}) by {actor_user_id}")
        return new_user

    def update_user(
        self,
        actor_user_id: str,
        target_user_id: str,
        **updates,
    ) -> Dict[str, Any]:
        """
        Update any user fields.

        Updatable fields: full_name, remember_login_allowed, notes.
        Use update_user_role() for role changes and disable_user()/enable_user()
        for activation changes (they have extra side effects).

        Raises:
            PermissionError if actor lacks manage_users
            ValueError if target not found
        """
        self.require_permission(actor_user_id, "manage_users")
        user = self.get_user(target_user_id)
        if not user:
            raise ValueError(f"User '{target_user_id}' not found")

        SAFE_FIELDS = {"full_name", "remember_login_allowed", "notes"}
        changed = {}
        for field, value in updates.items():
            if field in SAFE_FIELDS:
                old = user.get(field)
                if old != value:
                    user[field] = value
                    if field == "full_name":
                        user["name"] = value   # keep backward compat
                    changed[field] = (old, value)

        if changed:
            self._save_users()
            _write_audit(actor_user_id, target_user_id, "update_user",
                         notes=str(changed))
        return user

    def update_user_role(
        self,
        actor_user_id: str,
        target_user_id: str,
        new_role: str,
        notes: str = "",
    ) -> None:
        """
        Change a user's role.

        Role changes are logged and all existing sessions are revoked
        (user must re-login for new permissions to take effect).

        Raises:
            PermissionError if actor lacks manage_users
            ValueError if role invalid or user not found
        """
        self.require_permission(actor_user_id, "manage_users")
        if new_role not in self._roles:
            raise ValueError(f"Role '{new_role}' not in roles_permissions.yaml")

        user = self.get_user(target_user_id)
        if not user:
            raise ValueError(f"User '{target_user_id}' not found")

        old_role = user.get("role", "")
        if old_role == new_role:
            return   # no-op

        user["role"] = new_role
        self._save_users()

        # Revoke all sessions — role takes effect on next login
        try:
            from engine.auth.session_manager import revoke_all_sessions
            revoke_all_sessions(target_user_id)
        except Exception as e:
            log.debug(f"[AUTH] Could not revoke sessions after role change: {e}")

        _write_audit(actor_user_id, target_user_id, "update_role",
                     old_role=old_role, new_role=new_role, notes=notes)
        log.info(f"[AUTH] Role changed: {target_user_id} {old_role} → {new_role} by {actor_user_id}")

    def disable_user(
        self,
        actor_user_id: str,
        target_user_id: str,
        notes: str = "",
    ) -> None:
        """
        Disable a user and revoke all their sessions.

        Raises:
            PermissionError if actor lacks manage_users
            ValueError if user not found or actor tries to disable themselves
        """
        self.require_permission(actor_user_id, "manage_users")
        if actor_user_id == target_user_id:
            raise ValueError("Cannot disable your own account")

        user = self.get_user(target_user_id)
        if not user:
            raise ValueError(f"User '{target_user_id}' not found")

        user["is_active"] = False
        self._save_users()

        try:
            from engine.auth.session_manager import revoke_all_sessions
            revoke_all_sessions(target_user_id)
        except Exception as e:
            log.debug(f"[AUTH] Could not revoke sessions on disable: {e}")

        _write_audit(actor_user_id, target_user_id, "disable_user", notes=notes)
        log.info(f"[AUTH] User disabled: {target_user_id} by {actor_user_id}")

    def enable_user(
        self,
        actor_user_id: str,
        target_user_id: str,
        notes: str = "",
    ) -> None:
        """Re-enable a previously disabled user."""
        self.require_permission(actor_user_id, "manage_users")
        user = self.get_user(target_user_id)
        if not user:
            raise ValueError(f"User '{target_user_id}' not found")

        user["is_active"] = True
        self._save_users()
        _write_audit(actor_user_id, target_user_id, "enable_user", notes=notes)
        log.info(f"[AUTH] User enabled: {target_user_id} by {actor_user_id}")
