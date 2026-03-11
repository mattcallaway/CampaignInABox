"""
ui/theme.py - Global Theme System (Prompt 20.7)
"""

import streamlit as st
from pathlib import Path
from datetime import datetime

# Define color constants for Plotly
COLORS = {
    "background": "#F4F7FB",
    "surface": "#FFFFFF",
    "primary_text": "#1A2A3A",
    "secondary_text": "#5B6B7D",
    "success": "#2E8B57",
    "warning": "#D9A441",
    "danger": "#C94C4C",
    "info": "#3C78D8",
    "estimated": "#8E7CC3",
    "missing": "#B85450",
    "accent": "#1F4E79",
}

def inject_theme(base_dir: Path):
    """
    Reads theme.css and injects it into the Streamlit session.
    Also logs the theme load event.
    """
    css_path = base_dir / "ui" / "theme.css"
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    
        # Log theme application
        try:
            log_dir = base_dir / "logs" / "ui"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "ui_theme.log"
            if not log_file.exists():
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write("timestamp,event,status\\n")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{datetime.utcnow().isoformat()},theme_load,success\\n")
        except Exception:
            pass

def apply_chart_theme(fig):
    """
    Takes a Plotly figure and applies the standard Campaign In A Box theme.
    """
    fig.update_layout(
        font=dict(family="sans-serif", color=COLORS["secondary_text"]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor=COLORS["surface"], font_color=COLORS["primary_text"]),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#E2E8F0")
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0", zeroline=False, linecolor="#E2E8F0")
    return fig

