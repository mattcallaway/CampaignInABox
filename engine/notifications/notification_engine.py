"""
engine/notifications/notification_engine.py — Prompt 20

Processes background events (tasks, approvals, strategies) and provides
a feed of notifications for the active user dashboard.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import json
import logging
from typing import List, Dict, Any, Optional

log = logging.getLogger(__name__)

class NotificationEngine:
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        
        # Paths to monitor
        self.tasks_path = self.root_dir / "derived" / "workflow" / "tasks.csv"
        self.approvals_path = self.root_dir / "derived" / "workflow" / "strategy_approvals.csv"

    def get_user_notifications(self, user_id: str) -> List[Dict[str, str]]:
        """
        Dynamically generates a list of notifications for the requested user_id
        based on open tasks, pending strategy approvals, or recent activity.
        """
        notifications = []
        
        # 1. Check open tasks
        if self.tasks_path.exists():
            try:
                tasks_df = pd.read_csv(self.tasks_path)
                my_open = tasks_df[(tasks_df["assigned_to"] == user_id) & (tasks_df["status"] == "open")]
                for _, task in my_open.iterrows():
                    notifications.append({
                        "type": "task",
                        "message": f"Assigned Task: {task['description']}",
                        "timestamp": str(task["created_at"]),
                        "priority": task["priority"]
                    })
            except Exception as e:
                log.warning(f"Error reading tasks for notification: {e}")

        # 2. Check pending approvals (if user represents an approver role, say Campaign Manager)
        # Note: True role check should happen in UI, but we can surface 'Pending Strategies' broadly
        if self.approvals_path.exists():
            try:
                app_df = pd.read_csv(self.approvals_path)
                if not app_df.empty:
                    latest = app_df.sort_values("approval_timestamp").groupby("strategy_id").tail(1)
                    pending_count = len(latest[latest["status"] == "pending"])
                    if pending_count > 0:
                        notifications.append({
                            "type": "approval",
                            "message": f"There are {pending_count} strategies pending approval.",
                            "timestamp": datetime.utcnow().isoformat(),
                            "priority": "high"
                        })
            except Exception as e:
                log.warning(f"Error reading approvals for notification: {e}")

        # Sort by timestamp descending
        notifications.sort(key=lambda x: x["timestamp"], reverse=True)
        return notifications
