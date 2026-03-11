"""
ui/components/alerts.py
"""
import streamlit as st

def render_alert(alert_type: str, message: str, icon: str = None):
    """
    Renders a semantic alert box.
    Types: info, warning, critical, success
    """
    icons = {
        "info": "ℹ️",
        "warning": "⚠️",
        "critical": "🚨",
        "success": "✅"
    }
    use_icon = icon if icon else icons.get(alert_type, "📌")
    
    html = f"""
    <div class="alert-box {alert_type}">
        <div class="alert-icon">{use_icon}</div>
        <div>{message}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
