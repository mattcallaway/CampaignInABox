"""
ui/components/metric_card.py
"""
import streamlit as st
from ui.components.badges import render_provenance_badge

def render_metric_card(title: str, value: str, subtitle: str = None, provenance: str = None, status: str = None):
    """
    Renders a standard metric card into the Streamlit session.
    Status can be 'success', 'danger', 'warning', 'info' or None to drive the top border color.
    """
    card_class = "metric-card"
    if status:
        card_class += f" status-{status}"
        
    prov_html = render_provenance_badge(provenance) if provenance else ""
    sub_html = f"<div class='metric-subtext'>{subtitle}</div>" if subtitle else ""
    
    html = f"""
    <div class="{card_class}">
        <div class="metric-label">{title} {prov_html}</div>
        <div class="metric-value">{value}</div>
        {sub_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
