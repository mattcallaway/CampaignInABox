"""
ui/dashboard/team_view.py — Prompt 20

Unified Collaboration UI mapping over Tasks, Approvals, and Notes.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from engine.workflow.task_manager import TaskManager
from engine.workflow.strategy_approval import StrategyApprovalManager
from engine.notifications.notification_engine import NotificationEngine
from pathlib import Path

def render_team_view(data: dict, auth_mgr, current_user: dict):
    st.header(f"🤝 Team Collaboration Center")
    user_id = current_user.get("user_id")
    role_name = current_user.get("role")
    
    # Init managers
    tm = TaskManager(auth_mgr.root_dir)
    app_mgr = StrategyApprovalManager(auth_mgr.root_dir)
    ne = NotificationEngine(auth_mgr.root_dir)
    
    st.markdown(f"**Welcome back, {current_user.get('name')}**. Your role is `{role_name}`.")
    
    tabs = st.tabs(["Tasks", "Approvals", "Activity & Notes", "Notifications"])
    
    # ── Tasks Tab ─────────────────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("📌 Task Management")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("##### ➕ Assign New Task")
            can_assign = auth_mgr.has_permission(user_id, "manage_tasks")
            if can_assign:
                with st.form("new_task_form"):
                    desc = st.text_input("Task Description")
                    users = auth_mgr.get_all_users()
                    user_opts = {u["name"]: u["user_id"] for u in users}
                    assignee = st.selectbox("Assign To", list(user_opts.keys()))
                    prio = st.selectbox("Priority", ["high", "medium", "low"], index=1)
                    due = st.date_input("Due Date")
                    
                    if st.form_submit_button("Create Task"):
                        if desc:
                            tm.create_task(desc, user_opts[assignee], user_id, priority=prio, due_date=str(due))
                            st.success("Task assigned!")
                            st.rerun()
                        else:
                            st.error("Description required")
            else:
                st.warning("You do not have permission to assign tasks.")
        
        with col2:
            st.markdown("##### 📥 Your Tasks")
            my_tasks = tm.get_tasks_for_user(user_id)
            if not my_tasks:
                st.info("You have zero open tasks.")
            else:
                for t in my_tasks:
                    with st.container(border=True):
                        st.markdown(f"**{t['description']}**")
                        st.caption(f"Priority: {t['priority'].upper()} | Due: {t['due_date']}")
                        if st.button("Mark Complete", key=f"btn_close_{t['task_id']}"):
                            tm.update_task_status(t['task_id'], "closed", user_id)
                            st.rerun()
    
    # ── Approvals Tab ─────────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("✅ Strategy Approvals")
        pending = app_mgr.get_pending_strategies()
        
        can_approve = auth_mgr.has_permission(user_id, "approve_strategy")
        
        if not pending:
            st.success("All active strategies have been reviewed.")
        else:
            st.markdown(f"You have **{len(pending)}** strategies awaiting review.")
            for p_id in pending:
                with st.container(border=True):
                    st.markdown(f"**Strategy ID:** `{p_id}`")
                    if can_approve:
                        cols = st.columns([2, 1, 1])
                        notes = cols[0].text_input("Review Notes", key=f"notes_{p_id}")
                        if cols[1].button("Approve", type="primary", key=f"app_{p_id}"):
                            app_mgr.submit_approval(p_id, user_id, "approved", notes)
                            st.rerun()
                        if cols[2].button("Reject", key=f"rej_{p_id}"):
                            app_mgr.submit_approval(p_id, user_id, "rejected", notes)
                            st.rerun()
                    else:
                        st.warning("You do not have permission to approve strategies.")
                        
    # ── Activity & Notes Tab ──────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("📚 Campaign Change Log")
        log_path = auth_mgr.root_dir / "logs" / "collaboration" / "change_log.csv"
        if log_path.exists():
            cdf = pd.read_csv(log_path)
            st.dataframe(cdf.tail(10), use_container_width=True)
        else:
            st.caption("No change log found yet.")
            
    # ── Notifications Tab ─────────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("🔔 Your Notifications")
        nots = ne.get_user_notifications(user_id)
        if not nots:
            st.info("You're all caught up!")
        else:
            for n in nots:
                icon = "🔥" if n.get("priority") == "high" else "✉️"
                st.markdown(f"**{icon} {n.get('type').upper()}** - {n.get('message')}")
                st.caption(f"Time: {n.get('timestamp')}")
                st.divider()

