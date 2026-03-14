"""
ui/dashboard/user_admin_view.py — Prompt 20.8

User Administration dashboard page.

Displays all users in a table, allows creating and editing users.
Role dropdown populated from roles_permissions.yaml.

Permission gate: manage_users permission required for any write operation.
Viewers (and roles without manage_users) see a read-only table.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def render_user_admin_view(auth_mgr, current_user_id: str):
    """Render the User Administration page."""
    st.header("👤 Users & Roles")

    can_manage = auth_mgr.can_manage_users(current_user_id)

    if not can_manage:
        st.info("🔒 You have read-only access. Only Campaign Managers can create or edit users.")

    # ── Load users ────────────────────────────────────────────────────────────
    users = auth_mgr.list_users()
    all_roles = auth_mgr.get_all_roles()

    # ── Summary metrics ───────────────────────────────────────────────────────
    total = len(users)
    active = sum(1 for u in users if u.get("is_active", True))
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Users", total)
    m2.metric("Active Users", active)
    m3.metric("Roles Available", len(all_roles))

    # ── Admin audit log preview ───────────────────────────────────────────────
    log_path = BASE_DIR / "logs" / "admin" / "user_admin_log.csv"

    # ── Tabs ──────────────────────────────────────────────────────────────────
    if can_manage:
        tab_list, tab_create, tab_edit, tab_log = st.tabs([
            "👥 All Users", "➕ Create User", "✏️ Edit User", "📋 Audit Log"
        ])
    else:
        tab_list, tab_log = st.tabs(["👥 All Users", "📋 Audit Log"])

    # ── Tab: All Users ────────────────────────────────────────────────────────
    with tab_list:
        st.subheader("All Users")
        if users:
            df = pd.DataFrame(users)
            display_cols = [c for c in [
                "user_id", "full_name", "role_label", "is_active",
                "remember_login_allowed", "last_login_at", "notes"
            ] if c in df.columns]
            # Color active/inactive
            def _row_color(row):
                if not row.get("is_active", True):
                    return ["background-color: #3a1a1a"] * len(display_cols)
                return [""] * len(display_cols)

            styled = df[display_cols].rename(columns={
                "user_id": "User ID", "full_name": "Name", "role_label": "Role",
                "is_active": "Active", "remember_login_allowed": "Remember Login",
                "last_login_at": "Last Login", "notes": "Notes"
            })
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.warning("No users found.")

    # ── Tab: Create User ──────────────────────────────────────────────────────
    if can_manage:
        with tab_create:
            st.subheader("Create New User")
            with st.form("create_user_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                new_uid   = c1.text_input("User ID*", placeholder="e.g. jsmith", key="new_uid")
                new_name  = c2.text_input("Full Name*", placeholder="Jane Smith", key="new_name")
                new_role  = st.selectbox("Role*", all_roles,
                                         format_func=lambda r: r.replace("_", " ").title(),
                                         key="new_role")
                new_active = st.checkbox("Active", value=True, key="new_active")
                new_remember = st.checkbox("Allow Remembered Login", value=True, key="new_remember")
                new_notes = st.text_area("Notes", key="new_notes")
                submitted = st.form_submit_button("Create User", type="primary")
                if submitted:
                    if not new_uid.strip() or not new_name.strip():
                        st.error("User ID and Full Name are required.")
                    elif " " in new_uid:
                        st.error("User ID must not contain spaces.")
                    else:
                        try:
                            auth_mgr.create_user(
                                actor_user_id=current_user_id,
                                user_id=new_uid.strip(),
                                full_name=new_name.strip(),
                                role=new_role,
                                is_active=new_active,
                                remember_login_allowed=new_remember,
                                notes=new_notes.strip(),
                            )
                            st.success(f"User '{new_uid}' created with role '{new_role}'.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating user: {e}")

        # ── Tab: Edit User ────────────────────────────────────────────────────
        with tab_edit:
            st.subheader("Edit Existing User")
            user_ids = [u["user_id"] for u in users]
            sel_uid = st.selectbox("Select User to Edit", user_ids,
                                   format_func=lambda uid: next(
                                       (u["full_name"] for u in users if u["user_id"] == uid), uid),
                                   key="edit_sel_uid")
            if sel_uid:
                sel_user = next((u for u in users if u["user_id"] == sel_uid), {})
                st.caption(f"Editing: **{sel_user.get('full_name', sel_uid)}** — current role: `{sel_user.get('role','')}`")

                with st.form("edit_user_form"):
                    e1, e2 = st.columns(2)
                    edit_name = e1.text_input("Full Name", value=sel_user.get("full_name", ""))
                    edit_role = e2.selectbox(
                        "Role",
                        all_roles,
                        index=all_roles.index(sel_user.get("role", all_roles[0])) if sel_user.get("role") in all_roles else 0,
                        format_func=lambda r: r.replace("_", " ").title(),
                    )
                    r1, r2 = st.columns(2)
                    edit_active   = r1.checkbox("Active",
                                                value=sel_user.get("is_active", True),
                                                disabled=(sel_uid == current_user_id))
                    edit_remember = r2.checkbox("Allow Remembered Login",
                                                value=sel_user.get("remember_login_allowed", True))
                    edit_notes = st.text_area("Notes", value=sel_user.get("notes", ""))
                    edit_submit = st.form_submit_button("Save Changes", type="primary")
                    if edit_submit:
                        try:
                            # Role change
                            if edit_role != sel_user.get("role"):
                                auth_mgr.update_user_role(current_user_id, sel_uid, edit_role,
                                                          notes="Changed via UI")
                                st.success(f"Role updated to '{edit_role}'. Sessions revoked — user must re-login.")

                            # Name / notes / remember_login changes
                            auth_mgr.update_user(current_user_id, sel_uid,
                                                 full_name=edit_name.strip(),
                                                 remember_login_allowed=edit_remember,
                                                 notes=edit_notes.strip())

                            # Active / inactive
                            if not edit_active and sel_user.get("is_active", True):
                                auth_mgr.disable_user(current_user_id, sel_uid,
                                                      notes="Disabled via UI")
                                st.warning(f"User '{sel_uid}' has been disabled.")
                            elif edit_active and not sel_user.get("is_active", True):
                                auth_mgr.enable_user(current_user_id, sel_uid,
                                                     notes="Re-enabled via UI")
                                st.success(f"User '{sel_uid}' re-enabled.")

                            st.success("Changes saved.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error saving changes: {e}")

    # ── Tab: Audit Log ────────────────────────────────────────────────────────
    with (tab_log if can_manage else tab_log):
        st.subheader("User Admin Audit Log")
        if log_path.exists() and log_path.stat().st_size > 50:
            try:
                log_df = pd.read_csv(log_path)
                st.dataframe(log_df.tail(50).iloc[::-1], use_container_width=True, hide_index=True)
            except Exception as e:
                st.caption(f"Could not load log: {e}")
        else:
            st.caption("No admin actions logged yet.")
