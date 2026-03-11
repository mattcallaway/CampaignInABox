"""
engine/auth/auth_manager.py — Prompt 20

Handles simulated user sessions, dynamic role resolution, and
permission checking for all campaign application layers.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

log = logging.getLogger(__name__)

class AuthManager:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.users_path = root_dir / "config" / "users_registry.json"
        self.roles_path = root_dir / "config" / "roles_permissions.yaml"
        self._users: List[Dict[str, Any]] = []
        self._roles: Dict[str, Dict[str, bool]] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Loads user registry and role permissions cautiously."""
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
            else:
                log.warning(f"Roles file not found at {self.roles_path}")

        except Exception as e:
            log.error(f"Failed to load Auth config: {e}")

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user context by user_id."""
        for user in self._users:
            if user.get("user_id") == user_id:
                return user
        return None

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Return full user list."""
        return self._users

    def has_permission(self, user_id: str, permission: str) -> bool:
        """Check if a specific user possesses a permission flag in their assigned role."""
        user = self.get_user(user_id)
        if not user:
            return False

        role_id = user.get("role")
        if not role_id or role_id not in self._roles:
            return False

        permissions = self._roles[role_id]
        return bool(permissions.get(permission, False))

    def require_permission(self, user_id: str, permission: str) -> None:
        """Strict assertion for a capability, raising ValueError if denied."""
        if not self.has_permission(user_id, permission):
            user = self.get_user(user_id)
            name = user.get("name", "Unknown") if user else "Unknown User"
            role = user.get("role", "None") if user else "None"
            log.warning(f"Permission denied: {name} ({role}) attempted to access {permission}")
            raise PermissionError(f"User {user_id} lacks permission: {permission}")
