"""
ui/dashboard/app.py — Prompt 9

Campaign Intelligence Dashboard entry point.

Launch with:
    streamlit run ui/dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# ── Bootstrap sys.path ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Campaign Intelligence Dashboard",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
from ui.theme import inject_theme
inject_theme(BASE_DIR)


# ── Version ───────────────────────────────────────────────────────────────────
import json
def _get_version():
    vfile = BASE_DIR / "config" / "version.json"
    if vfile.exists():
        try:
            return json.loads(vfile.read_text("utf-8")).get("version", "Unknown")
        except: pass
    return "0.4.0"

CIA_BOX_VERSION = _get_version()

# Startup Banner
if "startup_banner_shown" not in st.session_state:
    st.session_state["startup_banner_shown"] = True
    try:
        from ui.dashboard.state_loader import load_state_snapshot_meta
        snap = load_state_snapshot_meta()
        camp = snap.get('contest_id', 'Unknown Campaign')
        jur = snap.get('county', 'Unknown Jurisdiction')
        st.toast(f"**Campaign In A Box v{CIA_BOX_VERSION}**\n{camp}\n{jur}\nModel: Calibrated", icon="✅")
    except:
        st.toast(f"**Campaign In A Box v{CIA_BOX_VERSION}**\nStartup Successful", icon="✅")

# ── Data loading (cached) ─────────────────────────────────────────────────────

from ui.dashboard.data_loader import load_all


@st.cache_data(ttl=120, show_spinner="Loading campaign data…")
def get_data() -> dict:
    return load_all()


# ── Authentication Check ──────────────────────────────────────────────────────
from engine.auth.auth_manager import AuthManager
from engine.auth.session_manager import (
    validate_session, create_session, revoke_session, update_last_login
)
import json

if "auth_manager" not in st.session_state:
    st.session_state["auth_manager"] = AuthManager(BASE_DIR)

auth_mgr = st.session_state["auth_manager"]

if "current_user_id" not in st.session_state:
    st.session_state["current_user_id"] = None
if "session_token" not in st.session_state:
    st.session_state["session_token"] = None

# ── Session Bootstrap: auto-login if remembered session exists ─────────────────
if not st.session_state["current_user_id"]:
    # Check query param for session token (set on login with Remember Me)
    params = st.query_params
    token = params.get("session", "")
    if token:
        uid = validate_session(token)
        if uid and auth_mgr.get_user(uid):
            st.session_state["current_user_id"] = uid
            st.session_state["session_token"] = token
            update_last_login(uid)


def do_login(user_id: str, remember: bool = False):
    st.session_state["current_user_id"] = user_id
    update_last_login(user_id)
    if remember:
        token = create_session(user_id)
        if token:
            st.session_state["session_token"] = token
            st.query_params["session"] = token
    else:
        # Clear any stale token
        st.session_state["session_token"] = None
        st.query_params.clear()


if not st.session_state["current_user_id"]:
    st.title("🔒 Campaign In A Box Login")

    # Only show active users at login
    active_users = auth_mgr.get_active_users()
    if active_users:
        user_names = [u.get("full_name", u["name"]) for u in active_users]
        user_ids   = [u["user_id"] for u in active_users]
        selected_name = st.selectbox("Select User", user_names)
        remember_me   = st.checkbox("🔒 Remember me on this device", value=True,
                                    help="Keeps you logged in for 7 days. Uncheck on shared devices.")
        if st.button("Login", type="primary"):
            idx = user_names.index(selected_name)
            do_login(user_ids[idx], remember=remember_me)
            st.rerun()
    else:
        st.warning("No active users found in config/users_registry.json")
    st.stop()

current_user = auth_mgr.get_user(st.session_state["current_user_id"])
current_role = current_user.get("role") if current_user else "Unknown"
can_edit_strategy = auth_mgr.has_permission(st.session_state["current_user_id"], "edit_strategy")
can_upload = auth_mgr.has_permission(st.session_state["current_user_id"], "upload_data")
can_admin = auth_mgr.can_manage_users(st.session_state["current_user_id"]) or \
            auth_mgr.can_manage_campaigns(st.session_state["current_user_id"])

# ── Load active campaign pointer ──────────────────────────────────────────────
try:
    import yaml as _yaml
    _ac_path = BASE_DIR / "config" / "active_campaign.yaml"
    _active_campaign = _yaml.safe_load(_ac_path.read_text(encoding="utf-8")) if _ac_path.exists() else {}
except Exception:
    _active_campaign = {}

# ── Sidebar navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗳️ Campaign Intelligence")
    _user_display = current_user.get('full_name', current_user.get('name', '')) if current_user else 'Unknown'
    st.markdown(f"**User**: {_user_display}  \\n**Role**: `{current_role}`")
    if st.button("🚪 Logout"):
        # Revoke remembered session on logout
        _token = st.session_state.get("session_token")
        if _token:
            revoke_session(_token)
        st.session_state["current_user_id"] = None
        st.session_state["session_token"] = None
        st.query_params.clear()
        st.rerun()
    st.divider()

    # ── Load UI Registry ──────────────────────────────────────────────────────
    import yaml
    ui_cfg_path = BASE_DIR / "config" / "ui_pages.yaml"
    ui_registry = {}
    if ui_cfg_path.exists():
        with open(ui_cfg_path, "r", encoding="utf-8") as f:
            ui_registry = yaml.safe_load(f) or {}

    nav_options = []
    # Collect all available pages based on roles
    for group_key, group_data in ui_registry.items():
        for page_obj in group_data.get("pages", []):
            p_id = page_obj["id"]
            if not can_upload and p_id in ["📂 Data Manager", "📂 Upload Contest Data"]:
                continue
            if not can_edit_strategy and p_id in ["📋 Strategy", "🗳️ Campaign Setup"]:
                continue
            if not can_admin and p_id in ["👤 Users & Roles", "🏛️ Campaign Admin"]:
                continue
            nav_options.append(p_id)

    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "🏠 Overview"

    # Ensure active page is still allowed
    if st.session_state["active_page"] not in nav_options and nav_options:
        st.session_state["active_page"] = nav_options[0]

    # Render collapsible sections
    page = st.session_state["active_page"]
    active_category_label = ""
    active_page_label = ""
    
    for group_key, group_data in ui_registry.items():
        g_label = group_data.get("label", group_key)
        # Check if any page in this group is allowed
        allowed_pages = [p for p in group_data.get("pages", []) if p["id"] in nav_options]
        if not allowed_pages:
            continue
            
        # Determine if expanded (expand if active page is inside)
        is_active_group = any(p["id"] == st.session_state["active_page"] for p in allowed_pages)
        key_group = f"exp_{group_key}"
        if key_group not in st.session_state:
            st.session_state[key_group] = is_active_group
            
        with st.expander(g_label, expanded=st.session_state.get(key_group, is_active_group)):
            for p in allowed_pages:
                p_id = p["id"]
                p_label = p["label"]
                # If it's the active page, highlight it
                if p_id == st.session_state["active_page"]:
                    st.markdown(f"<div class='sidebar-active-page'><p>{p_label}</p></div>", unsafe_allow_html=True)
                    active_category_label = g_label
                    active_page_label = p_label
                else:
                    if st.button(p_label, key=f"btn_nav_{p_id}"):
                        st.session_state["active_page"] = p_id
                        # Log the navigation event
                        try:
                            from datetime import datetime
                            log_path = BASE_DIR / "logs" / "ui" / "navigation.log"
                            log_path.parent.mkdir(parents=True, exist_ok=True)
                            uid = current_user.get("user_id") if current_user else "unknown"
                            with open(log_path, "a", encoding="utf-8") as lf:
                                lf.write(f"{datetime.utcnow().isoformat()},{uid},{p_id},{g_label}\n")
                        except Exception as e:
                            pass
                        st.rerun()

    # Save context
    try:
        ctx_dir = BASE_DIR / "derived" / "ui"
        ctx_dir.mkdir(parents=True, exist_ok=True)
        ctx_file = ctx_dir / "navigation_context.json"
        with open(ctx_file, "w") as cf:
            json.dump({"category": active_category_label, "page": active_page_label}, cf)
    except:
        pass

    st.divider()
    st.divider()
    # Data Provenance Legend
    st.markdown("""
    <div style='font-size:0.72rem;color:#CBD5E1'>
    🟢 REAL &nbsp; 🔵 SIM &nbsp; 🟡 EST &nbsp; 🔴 MISSING
    </div>""", unsafe_allow_html=True)
    st.divider()

    # Refresh button
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # Run info
    try:
        data_preview = get_data()
        run_id = data_preview.get("run_id", "—")
        elapsed = data_preview.get("load_elapsed", 0)
        pm_rows = len(data_preview.get("precinct_model", []))
        st.markdown(f"**Run:** `{run_id[:20]}…`" if len(run_id) > 22 else f"**Run:** `{run_id}`")
        st.markdown(f"**Precincts:** {pm_rows:,}")
        st.markdown(f"**Load time:** {elapsed:.2f}s")
    except Exception:
        st.caption("Loading…")

    # ── State Snapshot panel (Prompt 14.5) ────────────────────────────────
    st.divider()
    st.markdown("#### 🗂️ State Snapshot")
    try:
        from ui.dashboard.state_loader import load_state_snapshot_meta
        snap = load_state_snapshot_meta()
        if snap.get("available"):
            risk_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
                snap.get("risk_level", "UNKNOWN"), "⬜")
            st.markdown(
                f"<div style='font-size:0.78rem;color:#CBD5E1'>"
                f"🏅 <b>Contest:</b> {snap.get('contest_id','—')}<br>"
                f"📍 {snap.get('county','—')}, {snap.get('state','—')}<br>"
                f"{'✅ War Room Ready' if snap.get('war_room_ready') else '🟡 Needs Real Data'}<br>"
                f"{risk_color} Risk: <b>{snap.get('risk_level','UNKNOWN')}</b><br>"
                f"🟢 REAL: {snap.get('real_metrics',0)} metric(s)<br>"
                f"{'📊 Diff available' if snap.get('diff_available') else '📊 First run'}"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("No state store yet. Run pipeline to generate.")
    except Exception:
        st.caption("State store loading…")

# ── Load data ─────────────────────────────────────────────────────────────────
try:
    data = get_data()
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

    # ── Sidebar Footer ────────────────────────────────────────────────────────────
    st.divider()
    st.markdown(
        f"<div class='sidebar-footer'>"
        f"<b>Campaign In A Box v{CIA_BOX_VERSION}</b><br>"
        f"Jurisdiction: {data_preview.get('county', '—')}<br>"
        f"Contest: {data_preview.get('contest_id', '—')}<br>"
        f"Run ID: {run_id[:13]}..."
        f"</div>",
        unsafe_allow_html=True
    )

# ── Global Command Bar ────────────────────────────────────────────────────────
try:
    from ui.dashboard.state_loader import load_state_snapshot_meta
    snap = load_state_snapshot_meta()

    _user_display_bar = current_user.get('full_name', current_user.get('name', '')) if current_user else 'Unknown'
    _ac_name  = _active_campaign.get('campaign_name', '—')
    _ac_stage = _active_campaign.get('stage', '—')
    _ac_status = _active_campaign.get('status', '—')

    if snap.get("available"):
        g_contest = snap.get('contest_id', '—')
        g_county  = snap.get('county', '—')
        g_health  = snap.get('risk_level', 'UNKNOWN')
        g_h_color = "#2E8B57" if g_health == "LOW" else ("#D9A441" if g_health == "MEDIUM" else "#C94C4C")
    else:
        g_contest = _ac_name
        g_county  = _active_campaign.get('state', '—')
        g_health  = '—'
        g_h_color = '#888'

    try:
        run_id_bar = get_data().get("run_id", "—")
    except Exception:
        run_id_bar = "—"

    bar_html = f"""
    <div class="command-bar">
        <span>👤 <b>{_user_display_bar}</b> &nbsp; <code>{current_role}</code></span>
        <span>🏛️ <b>{_ac_name}</b> · {_ac_stage} · {_ac_status}</span>
        <span><b>Contest:</b> {g_contest} | <b>Area:</b> {g_county}</span>
        <span><b>Health:</b> <span style="color:{g_h_color};font-weight:700">{g_health}</span></span>
    </div>
    """
    st.markdown(bar_html, unsafe_allow_html=True)
except Exception:
    pass

# ── Context Header ────────────────────────────────────────────────────────────
try:
    ctx_file = BASE_DIR / "derived" / "ui" / "navigation_context.json"
    if ctx_file.exists():
        with open(ctx_file, "r") as cf:
            ctx = json.load(cf)
            cat = ctx.get("category", "")
            pname = ctx.get("page", "")
            if cat and pname:
                st.caption(f"{cat} \u2192 **{pname}**")
except:
    pass

# ── Page routing ─────────────────────────────────────────────────────────────
if page == "🏠 Overview":
    from ui.dashboard.layout import render_overview
    render_overview(data)

elif page == "🌐 Jurisdiction Summary":
    from ui.dashboard.jurisdiction_view import render_jurisdiction_summary
    render_jurisdiction_summary(data)

elif page == "🪖 War Room":
    from ui.dashboard.war_room_view import render_war_room
    render_war_room(data)

elif page == "📋 Team Activity":
    from ui.dashboard.team_view import render_team_view
    render_team_view(data, auth_mgr, current_user)

elif page == "📐 Calibration":
    from ui.dashboard.calibration_view import render_calibration
    render_calibration(data)

elif page == "🧭 Political Intelligence":
    from ui.dashboard.political_intelligence_view import render_political_intelligence
    render_political_intelligence(data)

elif page == "📂 Data Manager":
    from ui.dashboard.data_manager_view import render_data_manager
    render_data_manager(data)

elif page == "🗳️ Campaign Setup":
    from ui.dashboard.campaign_setup_view import render_campaign_setup
    render_campaign_setup(data)

elif page == "📂 Upload Contest Data":
    from ui.dashboard.data_upload_view import render_upload
    render_upload()

elif page == "🗺️ Precinct Map":
    from ui.dashboard.map_view import render_map
    render_map(data)

elif page == "🎯 Targeting":
    from ui.dashboard.targeting_view import render_targeting
    render_targeting(data)

elif page == "📋 Strategy":
    from ui.dashboard.strategy_view import render_strategy
    render_strategy(data)

elif page == "🔬 Simulations":
    from ui.dashboard.simulation_view import render_simulation
    render_simulation(data)

elif page == "🏛️ Historical Archive":
    from ui.dashboard.archive_view import render_archive_view
    render_archive_view(data)

elif page == "⚡ Advanced Modeling":
    from ui.dashboard.advanced_view import render_advanced
    render_advanced(data)

elif page == "🧠 Voter Intelligence":
    from ui.dashboard.voter_intelligence_view import render_voter_intelligence
    render_voter_intelligence(data)

elif page == "🩺 Diagnostics":
    from ui.dashboard.diagnostics_view import render_diagnostics
    render_diagnostics(data)

elif page == "🗄️ Data Explorer":
    from ui.dashboard.data_explorer import render_explorer
    render_explorer(data)

elif page == "🗂️ Source Registry":
    from ui.dashboard.source_registry_view import render_source_registry
    render_source_registry(data)

elif page == "👤 Users & Roles":
    from ui.dashboard.user_admin_view import render_user_admin_view
    render_user_admin_view(auth_mgr, st.session_state["current_user_id"])

elif page == "🏛️ Campaign Admin":
    from ui.dashboard.campaign_admin_view import render_campaign_admin_view
    render_campaign_admin_view(auth_mgr, st.session_state["current_user_id"])

elif page == "📊 Swing Modeling":
    from ui.dashboard.swing_model_view import render_swing_model_view
    render_swing_model_view()
