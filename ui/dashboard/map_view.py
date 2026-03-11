"""
ui/dashboard/map_view.py — Prompt 9

Precinct map visualization.
Uses Plotly when geopandas is unavailable (choropleth fallback).
Uses Plotly Express + GeoPandas when available.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd


_LAYER_COLS = {
    "Target Score":          "target_score",
    "Turnout Opportunity":   "turnout_opportunity",
    "Persuasion Potential":  "persuasion_potential",
    "Support %":             "support_pct",
    "Turnout Rate":          "turnout_pct",
}

_COLOR_SCALES = {
    "Target Score":        "RdYlGn",
    "Turnout Opportunity": "Blues",
    "Persuasion Potential":"Purples",
    "Support %":           "RdYlGn",
    "Turnout Rate":        "Blues",
}

def render_map(data: dict) -> None:
    from ui.theme import apply_chart_theme
    
    st.markdown("<h1 class='page-title'>Precinct Map</h1>", unsafe_allow_html=True)
    st.caption("Geographic targeting and data overlay visualization.")

    pm = data.get("precinct_model", pd.DataFrame())
    if pm.empty:
        st.warning("No precinct model data to display. Run the pipeline first.")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        layer = st.selectbox("Map Layer", list(_LAYER_COLS.keys()), key="map_layer")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        show_table = st.checkbox("Show data table", value=False)

    col_name = _LAYER_COLS[layer]
    cscale   = _COLOR_SCALES[layer]

    _try_geo_map(pm, col_name, layer, cscale)
    _render_bar_summary(pm, col_name, layer)

    if show_table:
        display_cols = ["canonical_precinct_id"] + [c for c in [
            "registered", "turnout_pct", "support_pct",
            "target_score", "target_tier", "walk_priority",
        ] if c in pm.columns]
        st.dataframe(pm[display_cols].sort_values(
            by=col_name if col_name in pm.columns else display_cols[-1],
            ascending=False, na_position="last"
        ).head(100), use_container_width=True, hide_index=True)


def _try_geo_map(pm: pd.DataFrame, col_name: str, layer: str, cscale: str) -> None:
    from pathlib import Path
    import json
    from ui.theme import apply_chart_theme

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    geo_root = BASE_DIR / "data" / "CA" / "counties" / "Sonoma" / "geography" / "precinct_shapes" / "MPREC_GeoJSON"
    geojson_path = next(geo_root.glob("*.geojson"), None) if geo_root.exists() else None

    if geojson_path is None:
        st.info("ℹ️ Geometry file not found — showing bar chart summary only.")
        return

    try:
        import geopandas as gpd
        import plotly.express as px

        gdf = gpd.read_file(geojson_path)
        geo_id = next((c for c in ["canonical_precinct_id", "MPREC_ID", "PRECINCT", "precinct", "id", "GEOID"] if c in gdf.columns), gdf.columns[0])
        pm_id = "canonical_precinct_id" if "canonical_precinct_id" in pm.columns else pm.columns[0]

        gdf = gdf.copy()
        gdf[geo_id] = gdf[geo_id].astype(str).str.strip()
        pm = pm.copy()
        pm[pm_id] = pm[pm_id].astype(str).str.strip()

        merged = gdf.merge(pm, left_on=geo_id, right_on=pm_id, how="left")
        if col_name not in merged.columns:
            st.warning(f"Column `{col_name}` not available in data — try another layer.")
            return

        geojson = json.loads(merged.to_json())
        fig = px.choropleth_mapbox(
            merged, geojson=geojson, locations=merged.index, color=col_name,
            color_continuous_scale=cscale, mapbox_style="carto-positron",
            zoom=9, center={"lat": 38.4, "lon": -122.7}, opacity=0.75,
            hover_data={
                "canonical_precinct_id": True, "registered": True,
                "turnout_pct": ":.2f", "support_pct": ":.2f", "target_score": ":.4f",
            } if all(c in merged.columns for c in ["canonical_precinct_id", "registered"]) else {},
            labels={col_name: layer}, title=f"Precinct {layer}", height=600,
        )
        fig.update_layout(margin={"l": 0, "r": 0, "t": 30, "b": 0})
        fig = apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True)

    except ImportError:
        pass
    except Exception as e:
        st.warning(f"Map render error: {e}")


def _render_bar_summary(pm: pd.DataFrame, col_name: str, layer: str) -> None:
    import plotly.express as px
    from ui.theme import apply_chart_theme

    if col_name not in pm.columns:
        for fallback in ["target_score", "support_pct", "turnout_pct"]:
            if fallback in pm.columns:
                col_name = fallback
                layer = fallback.replace("_", " ").title()
                break
        else:
            return

    pid = "canonical_precinct_id" if "canonical_precinct_id" in pm.columns else pm.columns[0]
    top25 = pm[[pid, col_name]].dropna().sort_values(col_name, ascending=False).head(25)
    top25.columns = ["Precinct", layer]

    fig = px.bar(top25, x="Precinct", y=layer, title=f"Top 25 Precincts by {layer}", color=layer, color_continuous_scale="Blues", height=380)
    fig.update_layout(xaxis_tickangle=-45, showlegend=False, margin={"t": 40, "b": 100})
    fig = apply_chart_theme(fig)
    st.plotly_chart(fig, use_container_width=True)
