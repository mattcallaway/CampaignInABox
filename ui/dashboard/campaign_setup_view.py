"""
ui/dashboard/campaign_setup_view.py — Prompt 13

Campaign Setup dashboard page. Collects all campaign inputs and saves
them to config/campaign_config.yaml. This is the primary entry point
for configuring Campaign In A Box for a specific race.

Sections:
  1. Campaign Basics
  2. Vote Targets
  3. Budget
  4. Field Program Assumptions
  5. Volunteer Capacity
  6. Strategy Priorities
"""
from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Any

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "campaign_config.yaml"
LOG_PATH    = BASE_DIR / "logs" / "config_changes.log"

log = logging.getLogger(__name__)


# ── YAML helpers ─────────────────────────────────────────────────────────────

def _load_config() -> dict:
    try:
        import yaml
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        st.warning(f"Could not load campaign config: {e}")
    return {}


def _save_config(cfg: dict) -> bool:
    try:
        import yaml
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        # Append change log
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().isoformat()
        with open(LOG_PATH, "a", encoding="utf-8") as lf:
            lf.write(f"[{ts}] Campaign config updated via dashboard\n")
        return True
    except Exception as e:
        st.error(f"Failed to save campaign config: {e}")
        return False


def _g(cfg: dict, *keys, default=None) -> Any:
    """Safe nested dict get."""
    d = cfg
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


# ── Main Page ─────────────────────────────────────────────────────────────────

def render_campaign_setup(data: dict) -> None:
    """Render the Campaign Setup page."""

    st.markdown("""
    <div style='background:linear-gradient(135deg,#064E3B 0%,#065F46 100%);
         border-radius:14px;padding:24px 32px;margin-bottom:24px;color:white'>
      <h1 style='margin:0;color:white;font-size:2rem'>&#128379; Campaign Setup</h1>
      <p style='margin:6px 0 0 0;color:#A7F3D0;font-size:1rem'>
        Configure your campaign — these settings drive all simulations, targeting, and strategy generation.
      </p>
    </div>""", unsafe_allow_html=True)

    cfg = _load_config()

    # ── Status Banner ────────────────────────────────────────────────────────
    if CONFIG_PATH.exists():
        import os
        mtime = datetime.datetime.fromtimestamp(CONFIG_PATH.stat().st_mtime)
        st.success(f"Campaign config loaded — last saved {mtime.strftime('%b %d, %Y at %I:%M %p')}")
    else:
        st.info("No campaign config yet. Fill in the form below and click **Save Campaign Setup**.")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # Section 1: Campaign Basics
    # ══════════════════════════════════════════════════════════════════════════
    with st.expander("**📋 Campaign Basics**", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            contest_name = st.text_input(
                "Contest Name",
                value=_g(cfg, "campaign", "contest_name", default=""),
                placeholder="e.g. Prop 50 — Parks & Roads Measure",
                key="cs_contest_name",
            )
            jurisdiction = st.text_input(
                "Jurisdiction",
                value=_g(cfg, "campaign", "jurisdiction", default=""),
                placeholder="e.g. Sonoma County, CA",
                key="cs_jurisdiction",
            )
            election_date_str = _g(cfg, "campaign", "election_date", default="2025-06-03")
            try:
                election_date_default = datetime.date.fromisoformat(str(election_date_str))
            except Exception:
                election_date_default = datetime.date(2025, 6, 3)
            election_date = st.date_input(
                "Election Date",
                value=election_date_default,
                key="cs_election_date",
            )

        with col2:
            contest_type = st.selectbox(
                "Contest Type",
                options=["ballot_measure", "candidate"],
                index=0 if _g(cfg, "campaign", "contest_type", default="ballot_measure") == "ballot_measure" else 1,
                key="cs_contest_type",
            )
            candidate_name = st.text_input(
                "Candidate Name (if applicable)",
                value=_g(cfg, "campaign", "candidate_name", default=""),
                placeholder="Leave blank for ballot measures",
                key="cs_candidate_name",
            )
            party = st.selectbox(
                "Party (if candidate race)",
                options=["", "D", "R", "N", "L", "G"],
                index=0,
                key="cs_party",
            )

        primary_message = st.text_area(
            "Primary Campaign Message (1 sentence)",
            value=_g(cfg, "strategy", "primary_message", default=""),
            placeholder="e.g. Prop 50 fixes our roads without raising taxes.",
            height=68,
            key="cs_message",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Section 2: Vote Targets
    # ══════════════════════════════════════════════════════════════════════════
    with st.expander("**🎯 Vote Targets**", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            target_vote_share = st.slider(
                "Target Vote Share (%)",
                min_value=50.0, max_value=75.0,
                value=float(_g(cfg, "targets", "target_vote_share", default=0.52)) * 100,
                step=0.5,
                format="%.1f%%",
                key="cs_target_vote_share",
                help="Minimum vote share needed to win. Usually 50%+1 for ballot measures.",
            )
            win_margin = st.slider(
                "Target Win Margin (%)",
                min_value=0.5, max_value=20.0,
                value=float(_g(cfg, "targets", "win_margin", default=0.04)) * 100,
                step=0.5,
                format="%.1f%%",
                key="cs_win_margin",
                help="Desired margin above threshold — builds in a safety buffer.",
            )

        with col2:
            days_to_election = (election_date - datetime.date.today()).days
            st.metric("Days to Election", f"{days_to_election:,}")
            weeks_to_election = max(days_to_election / 7, 1)
            st.metric("Weeks to Election", f"{weeks_to_election:.1f}")
            st.metric("Win Number Strategy", f"{target_vote_share:.1f}% + {win_margin:.1f}% buffer")

    # ══════════════════════════════════════════════════════════════════════════
    # Section 3: Budget
    # ══════════════════════════════════════════════════════════════════════════
    with st.expander("**💰 Campaign Budget**", expanded=True):
        total_budget = st.number_input(
            "Total Budget ($)",
            min_value=0, max_value=10_000_000,
            value=int(_g(cfg, "budget", "total_budget", default=150000)),
            step=5000,
            format="%d",
            key="cs_total_budget",
        )
        st.caption("Allocate your budget across programs:")
        bc1, bc2, bc3, bc4 = st.columns(4)
        with bc1:
            field_budget = st.number_input("Field ($)", min_value=0,
                value=int(_g(cfg, "budget", "field_budget", default=60000)),
                step=1000, format="%d", key="cs_field_budget")
        with bc2:
            mail_budget = st.number_input("Mail ($)", min_value=0,
                value=int(_g(cfg, "budget", "mail_budget", default=40000)),
                step=1000, format="%d", key="cs_mail_budget")
        with bc3:
            digital_budget = st.number_input("Digital ($)", min_value=0,
                value=int(_g(cfg, "budget", "digital_budget", default=30000)),
                step=1000, format="%d", key="cs_digital_budget")
        with bc4:
            research_budget = st.number_input("Research ($)", min_value=0,
                value=int(_g(cfg, "budget", "research_budget", default=20000)),
                step=1000, format="%d", key="cs_research_budget")

        allocated = field_budget + mail_budget + digital_budget + research_budget
        remaining = total_budget - allocated
        alloc_pct = allocated / total_budget * 100 if total_budget else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Allocated", f"${allocated:,}")
        col2.metric("Remaining", f"${remaining:,}", delta=f"${remaining:,}")
        col3.metric("Allocation %", f"{alloc_pct:.1f}%")

        if abs(remaining) > 100:
            st.warning(f"Budget mismatch: {'+' if remaining>0 else ''}{remaining:,} unallocated. Program budgets should sum to total.")
        else:
            st.success("Budget balanced ✅")

    # ══════════════════════════════════════════════════════════════════════════
    # Section 4: Field Program Assumptions
    # ══════════════════════════════════════════════════════════════════════════
    with st.expander("**🚪 Field Program Assumptions**"):
        fp1, fp2 = st.columns(2)
        with fp1:
            doors_per_day = st.number_input(
                "Doors per Canvasser per Day",
                min_value=10, max_value=100,
                value=int(_g(cfg, "field_program", "doors_per_canvasser_per_day", default=40)),
                key="cs_doors_per_day",
                help="Typical: 40 suburban, 60 urban, 25 rural",
            )
            persuasion_rate = st.slider(
                "Persuasion Rate per Contact (%)",
                min_value=0.5, max_value=15.0,
                value=float(_g(cfg, "field_program", "persuasion_rate_per_contact", default=0.04)) * 100,
                step=0.5, format="%.1f%%",
                key="cs_persuasion_rate",
                help="% of contacts that shift to YES; typical 2-8%",
            )
            turnout_lift = st.slider(
                "Turnout Lift per Contact (%)",
                min_value=0.5, max_value=20.0,
                value=float(_g(cfg, "field_program", "turnout_lift_per_contact", default=0.06)) * 100,
                step=0.5, format="%.1f%%",
                key="cs_turnout_lift",
                help="% turnout increase from contact; typical 4-8%",
            )
        with fp2:
            contact_success = st.slider(
                "Contact Success Rate (%)",
                min_value=5.0, max_value=60.0,
                value=float(_g(cfg, "field_program", "contact_success_rate", default=0.22)) * 100,
                step=1.0, format="%.0f%%",
                key="cs_contact_success",
                help="% of doors where someone actually speaks with canvasser; typical 15-30%",
            )
            days_per_week = st.number_input(
                "Canvassing Days per Week",
                min_value=1, max_value=7,
                value=int(_g(cfg, "field_program", "days_per_week", default=5)),
                key="cs_days_per_week",
            )
            st.markdown("---")
            # Compute effective contacts per 100 doors
            contacts_per_100 = contact_success
            st.metric("Contacts per 100 Doors", f"{contacts_per_100:.0f}")

    # ══════════════════════════════════════════════════════════════════════════
    # Section 5: Volunteer Capacity
    # ══════════════════════════════════════════════════════════════════════════
    with st.expander("**🙋 Volunteer Capacity**"):
        vc1, vc2 = st.columns(2)
        with vc1:
            volunteers_per_week = st.number_input(
                "Volunteers per Week",
                min_value=1, max_value=5000,
                value=int(_g(cfg, "volunteers", "volunteers_per_week", default=10)),
                key="cs_volunteers",
            )
            shifts_per_volunteer = st.number_input(
                "Avg Shifts per Volunteer per Week",
                min_value=1, max_value=14,
                value=int(_g(cfg, "volunteers", "avg_shifts_per_volunteer", default=2)),
                key="cs_shifts",
            )
            shift_length = st.number_input(
                "Shift Length (hours)",
                min_value=1, max_value=10,
                value=int(_g(cfg, "volunteers", "shift_length_hours", default=3)),
                key="cs_shift_length",
            )
            contacts_per_hour = st.number_input(
                "Contacts per Hour",
                min_value=1, max_value=30,
                value=int(_g(cfg, "volunteers", "contacts_per_hour", default=8)),
                key="cs_contacts_per_hour",
            )
        with vc2:
            # Computed metrics
            total_volunteer_hours_per_week = volunteers_per_week * shifts_per_volunteer * shift_length
            total_contacts_per_week = total_volunteer_hours_per_week * contacts_per_hour
            total_doors_per_week = total_contacts_per_week / (contact_success / 100) if contact_success else 0
            total_persuasion_per_week = total_contacts_per_week * (persuasion_rate / 100)
            st.metric("Hours/Week", f"{total_volunteer_hours_per_week:,.0f}")
            st.metric("Contacts/Week", f"{total_contacts_per_week:,.0f}")
            st.metric("Doors/Week (est.)", f"{total_doors_per_week:,.0f}")
            st.metric("Persuasion Contacts/Week", f"{total_persuasion_per_week:,.0f}")

    # ══════════════════════════════════════════════════════════════════════════
    # Section 6: Strategy Priorities
    # ══════════════════════════════════════════════════════════════════════════
    with st.expander("**⚡ Strategy Priorities**"):
        sp1, sp2 = st.columns(2)
        with sp1:
            priority_opts = ["Low", "Medium", "High"]
            persuasion_priority = st.select_slider(
                "Persuasion Priority",
                options=priority_opts,
                value=_g(cfg, "strategy", "persuasion_priority", default="High"),
                key="cs_persuasion_priority",
                help="How much of field effort to focus on persuading soft opponents",
            )
            turnout_priority = st.select_slider(
                "GOTV / Turnout Priority",
                options=priority_opts,
                value=_g(cfg, "strategy", "turnout_priority", default="Medium"),
                key="cs_turnout_priority",
                help="How much effort to focus on turning out low-propensity supporters",
            )
            base_priority = st.select_slider(
                "Base Mobilization Priority",
                options=priority_opts,
                value=_g(cfg, "strategy", "base_mobilization_priority", default="Medium"),
                key="cs_base_priority",
            )
            mail_priority = st.select_slider(
                "Mail Program Priority",
                options=priority_opts,
                value=_g(cfg, "strategy", "mail_priority", default="Medium"),
                key="cs_mail_priority",
            )
            digital_priority = st.select_slider(
                "Digital Program Priority",
                options=priority_opts,
                value=_g(cfg, "strategy", "digital_priority", default="Low"),
                key="cs_digital_priority",
            )

        with sp2:
            coalition_text = st.text_area(
                "Coalition Targets (one per line)",
                value="\n".join(_g(cfg, "strategy", "coalition_targets", default=[])),
                placeholder="Labor Council\nTeachers Union\nNAACP Chapter",
                height=100,
                key="cs_coalition",
            )
            demographic_text = st.text_area(
                "Key Demographics (one per line)",
                value="\n".join(_g(cfg, "strategy", "key_demographics", default=[])),
                placeholder="Seniors 65+\nLatino voters\nHomeowners",
                height=80,
                key="cs_demographics",
            )
            geo_targets_text = st.text_area(
                "Key Geographic Targets (one per line)",
                value="\n".join(_g(cfg, "strategy", "key_geographic_targets", default=[])),
                placeholder="Santa Rosa Southwest\nPetaluma\nRohnert Park",
                height=60,
                key="cs_geo_targets",
            )

    st.divider()

    # ── Save Button ───────────────────────────────────────────────────────────
    col_save, col_info = st.columns([1, 3])
    with col_save:
        save_pressed = st.button("💾 Save Campaign Setup", type="primary",
                                  use_container_width=True, key="cs_save_btn")

    if save_pressed:
        new_cfg = {
            "campaign": {
                "contest_name": contest_name,
                "contest_type": contest_type,
                "jurisdiction": jurisdiction,
                "election_date": str(election_date),
                "candidate_name": candidate_name,
                "party": party,
            },
            "targets": {
                "target_vote_share": round(target_vote_share / 100, 4),
                "win_margin": round(win_margin / 100, 4),
                "registration_target": 0,
            },
            "budget": {
                "total_budget": total_budget,
                "field_budget": field_budget,
                "mail_budget": mail_budget,
                "digital_budget": digital_budget,
                "research_budget": research_budget,
            },
            "field_program": {
                "doors_per_canvasser_per_day": doors_per_day,
                "persuasion_rate_per_contact": round(persuasion_rate / 100, 4),
                "turnout_lift_per_contact": round(turnout_lift / 100, 4),
                "contact_success_rate": round(contact_success / 100, 4),
                "days_per_week": days_per_week,
                "weeks_before_election": None,
            },
            "volunteers": {
                "volunteers_per_week": volunteers_per_week,
                "avg_shifts_per_volunteer": shifts_per_volunteer,
                "shift_length_hours": shift_length,
                "contacts_per_hour": contacts_per_hour,
            },
            "strategy": {
                "persuasion_priority": persuasion_priority,
                "turnout_priority": turnout_priority,
                "base_mobilization_priority": base_priority,
                "mail_priority": mail_priority,
                "digital_priority": digital_priority,
                "coalition_targets": [t.strip() for t in coalition_text.splitlines() if t.strip()],
                "key_demographics": [t.strip() for t in demographic_text.splitlines() if t.strip()],
                "key_geographic_targets": [t.strip() for t in geo_targets_text.splitlines() if t.strip()],
                "primary_message": primary_message,
            },
        }
        if _save_config(new_cfg):
            st.success("Campaign configuration saved! Re-run the pipeline to update all strategy outputs.")
            st.balloons()

    with col_info:
        st.markdown("""
        **After saving:** run the pipeline to regenerate strategy outputs:
        ```
        python scripts/run_pipeline.py --state CA --county Sonoma --year 2025 --contest-slug prop_50_special
        ```
        Then refresh the **Strategy** dashboard page to see updated plans.
        """)
