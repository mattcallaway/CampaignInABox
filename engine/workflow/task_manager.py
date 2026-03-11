"""
engine/workflow/task_manager.py — Prompt 20

Handles the creation, assignment, and status tracking of campaign tasks.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import uuid
import logging
from typing import List, Dict, Any, Optional

log = logging.getLogger(__name__)

class TaskManager:
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.tasks_path = self.root_dir / "derived" / "workflow" / "tasks.csv"
        self._ensure_file()

    def _ensure_file(self):
        self.tasks_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.tasks_path.exists():
            df = pd.DataFrame(columns=[
                "task_id", "assigned_to", "created_by", "description", 
                "status", "priority", "created_at", "due_date", "updated_at"
            ])
            df.to_csv(self.tasks_path, index=False)

    def load_tasks(self) -> pd.DataFrame:
        if self.tasks_path.exists():
            df = pd.read_csv(self.tasks_path)
            # Ensure proper schema
            if df.empty:
                return pd.DataFrame(columns=[
                    "task_id", "assigned_to", "created_by", "description", 
                    "status", "priority", "created_at", "due_date", "updated_at"
                ])
            return df
        return pd.DataFrame()

    def create_task(self, description: str, assigned_to: str, created_by: str, 
                    priority: str = "medium", due_date: str = "") -> str:
        """Create a new task and assign it."""
        task_id = f"tsk_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()
        
        new_task = {
            "task_id": task_id,
            "assigned_to": assigned_to,
            "created_by": created_by,
            "description": description,
            "status": "open",
            "priority": priority,
            "created_at": now,
            "due_date": due_date,
            "updated_at": now
        }
        
        df = self.load_tasks()
        df = pd.concat([df, pd.DataFrame([new_task])], ignore_index=True)
        df.to_csv(self.tasks_path, index=False)
        log.info(f"Task {task_id} created by {created_by} assigned to {assigned_to}")
        return task_id

    def update_task_status(self, task_id: str, new_status: str, user_id: str) -> bool:
        """Update the status of an existing task."""
        df = self.load_tasks()
        if df.empty or task_id not in df["task_id"].values:
            log.warning(f"Task {task_id} not found.")
            return False
            
        mask = df["task_id"] == task_id
        df.loc[mask, "status"] = new_status
        df.loc[mask, "updated_at"] = datetime.utcnow().isoformat()
        df.to_csv(self.tasks_path, index=False)
        log.info(f"Task {task_id} updated to {new_status} by {user_id}")
        return True

    def get_tasks_for_user(self, user_id: str, include_closed: bool = False) -> List[Dict[str, Any]]:
        """Fetch tasks assigned to a specific user."""
        df = self.load_tasks()
        if df.empty:
            return []
            
        user_tasks = df[df["assigned_to"] == user_id]
        if not include_closed:
            user_tasks = user_tasks[user_tasks["status"] != "closed"]
            
        return user_tasks.to_dict("records")
