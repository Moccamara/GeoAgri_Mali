import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw, MarkerCluster, HeatMap
import pandas as pd
from pathlib import Path
import base64

# =========================================================
# APP CONFIG
# =========================================================
st.set_page_config(layout="wide", page_title="Système d’Information Agricole du Mali (SIAM)")
st.title("🌱 GeoAgri Mali : Analyse Dynamique des Systèmes Agricoles")

# =========================================================
# USERS AND REGIONS
# =========================================================
USERS = {
    "geoagriuser1": {"password": "geoagriuser12026", "role": "User", "regions": ["Kayes","Kita","Nioro","Sikasso","Koutiala"]},
    "geoagriuser2": {"password": "geoagriuser22026", "role": "User", "regions": ["Koulikoro","Bamako"]},
    "geoagriuser3": {"password": "geoagriuser32026", "role": "User", "regions": ["Dioila","Nara"]},
    "geoagriuser4": {"password": "geoagriuser42026", "role": "User", "regions": ["Bougouni","Segou","San","Mopti"]},
    "geoagriuser5": {"password": "geoagriuser52026", "role": "User", "regions": ["Bandiagara","Douentza","Tombouctou"]},
    "geoagriuser6": {"password": "geoagriuser62026", "role": "User", "regions": ["Taoudenit","Menaka","Kidal","Gao"]},
    "geoagriadmin": {"password": "geoagriadmin2026", "role": "Admin", "regions": []}
}

# =========================================================
# SESSION INIT
# =========================================================
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.accessible_regions = []
    st.session_state.points_gdf = None

# =========================================================
# LOGOUT FUNCTION
# =========================================================
def logout():
    st.session_state.clear()
    st.rerun()

# =========================================================
# LOGIN
# =========================================================
if not st.session_state.auth_ok:
    st.sidebar.header("🔐 Login")
    username = st.sidebar.text_input("Login")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        if username in USERS and password == USERS[username]["password"]:
            st.session_state.auth_ok = True
            st.session_state.username = username
            st.session_state.user_role = USERS[username]["role"]
            st.session_state.accessible_regions = USERS[username]["regions"]
            st.rerun()
        else:
            st.sidebar.error("❌ Invalid login or password")

    st.stop()

# =========================================================
# LOAD DATA
# =========================================================
@st.cache_data(show_spinner=False)
def load_se_data():
    gdf = gpd.read_file("AGeoAgri_Mali_2026/data/emop2026.geojson")
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)
    return gdf[gdf.is_valid & ~gdf.is_empty]

@st.cache_data(show_spinner=False)
def load_points():
    pts = gpd.read_file("AGeoAgri_Mali_2026/data/Exploitation_Agri_ml3.geojson")
    if pts.crs is None:
        pts = pts.set_crs(epsg=4326)
    else:
        pts = pts.to_crs(epsg=4326)
    return pts[pts.is_valid & ~pts.is_empty]

gdf = load_se_data()
gdf_points = load_points()

# =========================================================
# FILTERS
# =========================================================
def unique_clean(series):
    return sorted(series.dropna().astype(str).str.strip().unique())

region = st.sidebar.selectbox("Region", unique_clean(gdf["LREG_NEW"]))
gdf_r = gdf[gdf["LREG_NEW"] == region]

cercle = st.sidebar.selectbox("Cercle", unique_clean(gdf_r["LCER_NEW"]))
gdf_c = gdf_r[gdf_r["LCER_NEW"] == cercle]

commune = st.sidebar.selectbox("Commune", unique_clean(gdf_c["LCOM_NEW"]))
gdf_commune = gdf_c[gdf_c["LCOM_NEW"] == commune]

gdf_se = gdf_commune

points_filtered = gpd.sjoin(
    gdf_points,
    gdf_commune[["geometry"]],
    how="inner",
    predicate="within"
)

# =========================================================
# INIT MAP DATA (FIX)
# =========================================================
map_data = None
m = None

# =========================================================
# MAP
# =========================================================
if not gdf_se.empty:
    minx, miny, maxx, maxy = gdf_se.total_bounds

    m = folium.Map(location=[(miny+maxy)/2,(minx+maxx)/2], zoom_start=13, tiles=None)

    folium.TileLayer("OpenStreetMap").add_to(m)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Satellite"
    ).add_to(m)

    folium.GeoJson(gdf_se).add_to(m)

    if points_filtered is not None and not points_filtered.empty:
        cluster = MarkerCluster().add_to(m)
        for _, r in points_filtered.iterrows():
            folium.CircleMarker(
                [r.geometry.y, r.geometry.x],
                radius=5
            ).add_to(cluster)

    MeasureControl().add_to(m)
    Draw(export=True).add_to(m)
    folium.LayerControl().add_to(m)

    m.fit_bounds([[miny,minx],[maxy,maxx]])

    # ✅ FIX
    map_data = st_folium(
        m,
        height=550,
        use_container_width=True,
        returned_objects=["last_clicked","all_drawings"]
    )

# =========================================================
# TABLE
# =========================================================
if map_data and points_filtered is not None and not points_filtered.empty:
    st.success("Interaction détectée ✅")

# =========================================================
# FOOTER
# =========================================================
st.markdown(
"""
---
### Système d’Information Agricole du Mali (SIAM)
 
"""
)

logos_path = Path(__file__).parent / "AGeoAgri_Mali_2026" / "logos"
logo_files = sorted(list(logos_path.glob("*")))

if logo_files:
    cols = st.columns(len(logo_files))

    for col, logo in zip(cols, logo_files):
        with col:
            st.image(str(logo), width=150)
"""
---

 © Dr. Mahamadou CAMARA and Abdoul Karim DIAWARA
"""

 
