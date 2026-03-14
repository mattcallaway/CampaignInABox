"""
ui/dashboard/campaign_admin_view.py — Prompt 20.8

Campaign Administration dashboard page.

Allows authorized users to:
  - View all campaigns in a table with status badges
  - Create a new campaign (generates campaign_id + per-campaign config)
  - Edit campaign metadata
  - Set stage (setup → data_ingest → modeling → field → gotv → post_election → archived)
  - Set active / deactivate / archive campaigns
  - View active campaign summary card with stage warnings

Permission gate: manage_campaigns required for write operations.
Analysts and viewers see read-only campaign list.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent

VALID_STAGES   = ["setup", "data_ingest", "modeling", "field", "gotv", "post_election", "archived"]
VALID_STATUSES = ["active", "inactive", "archived"]
CONTEST_TYPES  = ["ballot_measure", "general", "primary", "special", "runoff"]

STAGE_ICONS = {
    "setup":        "🔧",
    "data_ingest":  "📂",
    "modeling":     "🔬",
    "field":        "🗺️",
    "gotv":         "🚪",
    "post_election": "📊",
    "archived":     "📦",
}


def render_campaign_admin_view(auth_mgr, current_user_id: str):
    """Render the Campaign Administration page."""
    from engine.admin.campaign_manager import CampaignManager

    st.header("🏛️ Campaign Admin")

    can_manage = auth_mgr.can_manage_campaigns(current_user_id)
    if not can_manage:
        st.info("🔒 You have read-only access. Campaign Managers and Data Directors can manage campaigns.")

    mgr = CampaignManager(auth_mgr)

    # ── Load data ─────────────────────────────────────────────────────────────
    campaigns = mgr.list_campaigns()
    active_ptr = mgr.get_active_campaign_pointer()
    active_id  = active_ptr.get("campaign_id", "")

    # ── Summary metrics ───────────────────────────────────────────────────────
    total_c     = len(campaigns)
    active_c    = sum(1 for c in campaigns if c.get("is_active"))
    archived_c  = sum(1 for c in campaigns if c.get("status") == "archived")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Campaigns", total_c)
    m2.metric("Active Campaign", active_c)
    m3.metric("Archived", archived_c)

    # ── Active Campaign Summary Card ──────────────────────────────────────────
    active_campaign = mgr.get_active_campaign()
    if active_campaign:
        stage     = active_campaign.get("stage", "")
        icon      = STAGE_ICONS.get(stage, "📋")
        st.markdown(
            f"""<div style="background:#1e3a5f;border-radius:8px;padding:12px 18px;margin-bottom:8px">
            <b>✅ Active Campaign</b> &nbsp; <code>{active_campaign.get('campaign_id','')}</code><br>
            <b>{active_campaign.get('campaign_name','')}</b> — {active_campaign.get('contest_name','')}<br>
            <b>Jurisdiction:</b> {active_campaign.get('county','')}, {active_campaign.get('state','')} &nbsp;|&nbsp;
            <b>Election:</b> {active_campaign.get('election_date','')} &nbsp;|&nbsp;
            {icon} <b>Stage:</b> {stage}
            </div>""",
            unsafe_allow_html=True,
        )
        warnings = CampaignManager.stage_warnings(active_campaign)
        for w in warnings:
            st.warning(f"⚠️ {w}")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    if can_manage:
        tab_list, tab_create, tab_manage, tab_log = st.tabs([
            "📋 All Campaigns", "➕ New Campaign", "⚙️ Manage Campaign", "📋 Audit Log"
        ])
    else:
        tab_list, tab_log = st.tabs(["📋 All Campaigns", "📋 Audit Log"])

    # ── Tab: All Campaigns ────────────────────────────────────────────────────
    with tab_list:
        st.subheader("Campaign Registry")
        if campaigns:
            rows = []
            for c in campaigns:
                rows.append({
                    "Active":         "✅" if c.get("is_active") else "",
                    "Campaign":       c.get("campaign_name", ""),
                    "ID":             c.get("campaign_id", ""),
                    "Contest":        c.get("contest_name", ""),
                    "Jurisdiction":   f"{c.get('county','')}, {c.get('state','')}",
                    "Election Date":  c.get("election_date", ""),
                    "Stage":          f"{STAGE_ICONS.get(c.get('stage',''), '')} {c.get('stage','')}",
                    "Status":         c.get("status", ""),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No campaigns in registry yet. Create one below.")

    # ── Tab: Create Campaign ──────────────────────────────────────────────────
    if can_manage:
        with tab_create:
            st.subheader("Create New Campaign")
            with st.form("create_campaign_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                cname   = c1.text_input("Campaign Name*", placeholder="Prop 50 Yes Campaign 2027")
                ccontest = c2.text_input("Contest Name*", placeholder="Prop 50 — Special Election")
                c3, c4 = st.columns(2)
                cctype  = c3.selectbox("Contest Type", CONTEST_TYPES)
                cedate  = c4.text_input("Election Date*", placeholder="YYYY-MM-DD")
                c5, c6, c7 = st.columns(3)
                cstate  = c5.text_input("State", "CA")
                ccounty = c6.text_input("County", "Sonoma")
                cjuris  = c7.text_input("Jurisdiction", placeholder="Sonoma County")
                cstage  = st.selectbox("Starting Stage", VALID_STAGES,
                                       format_func=lambda s: f"{STAGE_ICONS.get(s,'📋')} {s}")
                cnotes  = st.text_area("Notes")
                cset_active = st.checkbox("Set as Active Campaign immediately", value=False)

                if cset_active and active_campaign:
                    st.warning(f"⚠️ Setting this campaign active will deactivate "
                               f"**{active_campaign.get('campaign_name','')}**.")

                submitted = st.form_submit_button("Create Campaign", type="primary")
                if submitted:
                    if not cname.strip() or not ccontest.strip() or not cedate.strip():
                        st.error("Campaign Name, Contest Name, and Election Date are required.")
                    else:
                        try:
                            result = mgr.create_campaign(
                                actor_user_id=current_user_id,
                                campaign_name=cname.strip(),
                                contest_name=ccontest.strip(),
                                contest_type=cctype,
                                state=cstate.strip(),
                                county=ccounty.strip(),
                                jurisdiction=cjuris.strip() or f"{ccounty.strip()} County",
                                election_date=cedate.strip(),
                                stage=cstage,
                                notes=cnotes.strip(),
                                set_active=cset_active,
                            )
                            st.success(
                                f"Campaign '{result['campaign_id']}' created! "
                                f"{'Set as active.' if cset_active else 'Status: inactive.'}"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating campaign: {e}")

        # ── Tab: Manage Campaign ──────────────────────────────────────────────
        with tab_manage:
            st.subheader("Manage Campaign")
            if not campaigns:
                st.info("No campaigns to manage yet.")
            else:
                campaign_ids = [c["campaign_id"] for c in campaigns]
                sel_cid = st.selectbox(
                    "Select Campaign",
                    campaign_ids,
                    format_func=lambda cid: next(
                        (f"{'✅ ' if c.get('is_active') else ''}{c['campaign_name']}"
                         for c in campaigns if c["campaign_id"] == cid), cid),
                    key="manage_sel_cid",
                )
                if sel_cid:
                    sel_c = next((c for c in campaigns if c["campaign_id"] == sel_cid), {})
                    st.caption(f"Campaign ID: `{sel_cid}` · Status: **{sel_c.get('status','')}** · Stage: **{sel_c.get('stage','')}**")

                    # ── Metadata edit ──────────────────────────────────────────
                    with st.expander("✏️ Edit Metadata", expanded=False):
                        with st.form("edit_campaign_form"):
                            m1, m2 = st.columns(2)
                            em_name    = m1.text_input("Campaign Name", sel_c.get("campaign_name", ""))
                            em_contest = m2.text_input("Contest Name",  sel_c.get("contest_name", ""))
                            em_date    = st.text_input("Election Date", sel_c.get("election_date", ""))
                            em_notes   = st.text_area("Notes",          sel_c.get("notes", ""))
                            if st.form_submit_button("Save Metadata"):
                                try:
                                    mgr.update_campaign(
                                        current_user_id, sel_cid,
                                        campaign_name=em_name.strip(),
                                        contest_name=em_contest.strip(),
                                        election_date=em_date.strip(),
                                        notes=em_notes.strip(),
                                    )
                                    st.success("Metadata updated.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"{e}")

                    # ── Stage change ───────────────────────────────────────────
                    with st.expander("🔄 Change Stage", expanded=False):
                        with st.form("stage_form"):
                            cur_stage_idx = VALID_STAGES.index(sel_c.get("stage", VALID_STAGES[0])) \
                                if sel_c.get("stage") in VALID_STAGES else 0
                            new_stage = st.selectbox(
                                "New Stage", VALID_STAGES,
                                index=cur_stage_idx,
                                format_func=lambda s: f"{STAGE_ICONS.get(s,'📋')} {s}",
                            )
                            stage_notes = st.text_input("Notes (optional)")
                            if st.form_submit_button("Update Stage"):
                                try:
                                    mgr.set_stage(current_user_id, sel_cid, new_stage, stage_notes)
                                    st.success(f"Stage updated to '{new_stage}'.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"{e}")

                    # ── Activation controls ────────────────────────────────────
                    st.markdown("**Campaign Activation**")
                    act_col, deact_col, arch_col = st.columns(3)

                    if act_col.button("✅ Set as Active", disabled=sel_c.get("is_active", False),
                                      key="btn_set_active"):
                        try:
                            mgr.set_active(current_user_id, sel_cid)
                            st.success(f"'{sel_cid}' is now the active campaign.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"{e}")

                    if deact_col.button("⬜ Deactivate", disabled=not sel_c.get("is_active", False),
                                        key="btn_deactivate"):
                        try:
                            mgr.deactivate(current_user_id, sel_cid)
                            st.success(f"'{sel_cid}' deactivated.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"{e}")

                    # Archive with confirmation
                    if arch_col.button("📦 Archive", disabled=(sel_c.get("status") == "archived"),
                                       key="btn_archive"):
                        st.session_state["archive_confirm_id"] = sel_cid

                    if st.session_state.get("archive_confirm_id") == sel_cid:
                        st.warning(f"⚠️ Archiving **{sel_c.get('campaign_name','')}** is permanent. Confirm?")
                        conf1, conf2 = st.columns(2)
                        if conf1.button("✅ Yes, Archive", key="confirm_archive"):
                            try:
                                mgr.archive_campaign(current_user_id, sel_cid,
                                                     notes="Archived via UI")
                                st.success("Campaign archived.")
                                st.session_state.pop("archive_confirm_id", None)
                                st.rerun()
                            except Exception as e:
                                st.error(f"{e}")
                        if conf2.button("❌ Cancel", key="cancel_archive"):
                            st.session_state.pop("archive_confirm_id", None)
                            st.rerun()

    # ── Tab: Audit Log ────────────────────────────────────────────────────────
    log_path = BASE_DIR / "logs" / "admin" / "campaign_admin_log.csv"
    with tab_log:
        st.subheader("Campaign Admin Audit Log")
        if log_path.exists() and log_path.stat().st_size > 50:
            try:
                log_df = pd.read_csv(log_path)
                st.dataframe(log_df.tail(50).iloc[::-1], use_container_width=True, hide_index=True)
            except Exception as e:
                st.caption(f"Could not load log: {e}")
        else:
            st.caption("No campaign admin actions logged yet.")
