"""
ui/components/empty_state.py
"""
import streamlit as st

def render_empty_state(title: str, description: str, icon: str = "📭", suggestion: str = None):
    """
    Renders a consistent empty state placeholder for areas missing data.
    """
    sug_html = f"<div style='margin-top:12px; font-weight: 500;'>💡 {suggestion}</div>" if suggestion else ""
    
    html = f"""
    <div class="empty-state">
        <div class="empty-state-icon">{icon}</div>
        <div class="empty-state-title">{title}</div>
        <div class="empty-state-desc">{description}</div>
        {sug_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
