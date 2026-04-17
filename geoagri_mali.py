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
# LOAD EMOP SE
# =========================================================
@st.cache_data
def load_se_data():
    gdf = gpd.read_file("AGeoAgri_Mali_2026/data/emop2026.geojson")

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    gdf.columns = [c.strip() for c in gdf.columns]

    for col in ["LREG_NEW","LCER_NEW","LCOM_NEW","num_se","pop_se"]:
        if col not in gdf.columns:
            gdf[col] = None

    gdf = gdf[gdf.is_valid & ~gdf.is_empty]

    return gdf

gdf = load_se_data()

# =========================================================
# LOAD POINTS
# =========================================================
@st.cache_data
def load_points():
    pts = gpd.read_file("AGeoAgri_Mali_2026/data/Exploitation_Agri_ml3.geojson")

    if pts.crs is None:
        pts = pts.set_crs(epsg=4326)
    else:
        pts = pts.to_crs(epsg=4326)

    return pts

try:
    gdf_points = load_points()
except:
    gdf_points = None

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.image("AGeoAgri_Mali_2026/logo/logo_wgv.png", width=400)
    st.markdown(f"**User:** {st.session_state.username}")

    if st.button("Logout"):
        logout()

# =========================================================
# FILTERS
# =========================================================
def unique_clean(series):
    return sorted(series.dropna().astype(str).unique())

st.sidebar.markdown("### 🗂️ Attribute Query")

regions = unique_clean(gdf["LREG_NEW"])
region = st.sidebar.selectbox("Region", regions)

gdf_r = gdf[gdf["LREG_NEW"]==region]

cercles = unique_clean(gdf_r["LCER_NEW"])
cercle = st.sidebar.selectbox("Cercle", cercles)

gdf_c = gdf_r[gdf_r["LCER_NEW"]==cercle]

communes = unique_clean(gdf_c["LCOM_NEW"])
commune = st.sidebar.selectbox("Commune", communes)

gdf_commune = gdf_c[gdf_c["LCOM_NEW"]==commune]

# =========================================================
# FILTER POINTS
# =========================================================
points_filtered = None

if gdf_points is not None:
    points_filtered = gpd.sjoin(
        gdf_points,
        gdf_commune,
        predicate="within"
    )

# =========================================================
# MAP
# =========================================================
minx, miny, maxx, maxy = gdf_commune.total_bounds

m = folium.Map(
    location=[(miny+maxy)/2,(minx+maxx)/2],
    zoom_start=12
)

# Polygons
folium.GeoJson(
    gdf_commune,
    name="SE"
).add_to(m)

# =========================================================
# POINTS
# =========================================================
if points_filtered is not None and not points_filtered.empty:

    cluster = MarkerCluster(
        name="Points Agricoles",
        showCoverageOnHover=False,
        spiderfyOnMaxZoom=True
    ).add_to(m)

    for _, r in points_filtered.iterrows():
        folium.Marker(
            [r.geometry.y, r.geometry.x]
        ).add_to(cluster)

    # Colored
    pts_group = folium.FeatureGroup(name="Points colorés")

    for _, r in points_filtered.iterrows():

        color="green"

        folium.CircleMarker(
            [r.geometry.y, r.geometry.x],
            radius=4,
            color=color,
            fill=True
        ).add_to(pts_group)

    pts_group.add_to(m)

    # Heatmap
    heat_data = [[p.y,p.x] for p in points_filtered.geometry]

    HeatMap(
        heat_data,
        name="Heatmap"
    ).add_to(m)

# Tools
MeasureControl().add_to(m)
Draw().add_to(m)

folium.LayerControl().add_to(m)

st_folium(m, height=600)

# =========================================================
# FOOTER
# =========================================================
st.markdown(
"""
---
### Système d’Information Agricole du Mali (SIAM)

Abdoul Karim DIAWARA  
Dr. Mahamadou CAMARA
"""
)

logos_path = Path("AGeoAgri_Mali_2026/logos")

logo_files = sorted(list(logos_path.glob("*")))

if logo_files:

    cols = st.columns(len(logo_files))

    for col, logo in zip(cols, logo_files):

        with col:
            st.image(str(logo), width=120)
