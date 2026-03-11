# Campaign Collaboration Audit Report

## Purpose
This document provides a trace of collaborative actions within the Campaign In A Box system, demonstrating compliance with role-based restrictions, task assignment, and strategy approvals.

## Identity & Access Management
- **Registry Source**: `config/users_registry.json`
- **Permissions Source**: `config/roles_permissions.yaml`
- **Enforcement Layer**: `engine/auth/auth_manager.py`

### Active Roles
- `campaign_manager`: Full access, including strategy approval and task creation.
- `data_director`: Data upload and strategy generation, no approval rights.
- `field_director`: Runtime updates, task tracking, isolated to field plans.
- `finance_director`: Financial views and task tracking.
- `communications_director`: Read-only views and task tracking.
- `analyst`: Cross-sectional read views.

## Component Verification
1. **Task Manager** (`engine/workflow/task_manager.py`)
   - Logs task ID, assignee, creator, priority, due date.
   - Status transitions (open -> closed) enforce accountability.
2. **Strategy Approvals** (`engine/workflow/strategy_approval.py`)
   - Requires explicit sign-off from `campaign_manager`.
   - Strategies remain `pending` until formally flipped.
3. **Change Logging** (`logs/collaboration/change_log.csv`)
   - Tracks timestamp, user_id, action, file_affected, old/new values.
4. **Notifications** (`engine/notifications/notification_engine.py`)
   - Alerts users to pending assignments or pending strategy approvals upon dashboard load.

## Data Protection Compliance
- Raw voter data, campaign runtime logs, and strategy notes remain strictly confined to local storage.
- GitHub tracking is strictly configured to only commit structural schema updates and aggregate metrics.
