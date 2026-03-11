"""
ui/components/badges.py
"""

def render_provenance_badge(provenance_type: str) -> str:
    """
    Returns an HTML span for a provenance badge.
    Types: REAL, SIMULATED, ESTIMATED, MISSING, EXTERNAL
    """
    t = provenance_type.upper()
    return f"<span class='badge-prov {t.lower()}'>{t}</span>"

def render_status_badge(status: str) -> str:
    """
    Returns a generic status badge.
    Categories: PASS, WARN, FAIL
    """
    color = "success" if status == "PASS" else ("warning" if status == "WARN" else "danger")
    return f"<span class='badge-prov' style='background:var(--color-{color}); color:white;'>{status}</span>"
