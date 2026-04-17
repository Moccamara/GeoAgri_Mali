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
# LOAD EMOP SE POLYGONS
# =========================================================
@st.cache_data(show_spinner=False)
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

try:
    gdf = load_se_data()
except Exception as e:
    st.error(f"❌ Unable to load EMOP GeoJSON: {e}")
    st.stop()

# =========================================================
# LOAD POINT SHP
# =========================================================
@st.cache_data(show_spinner=False)
def load_points():
    pts = gpd.read_file("AGeoAgri_Mali_2026/data/Exploitation_Agri_ml3.geojson")
    if pts.crs is None:
        pts = pts.set_crs(epsg=4326)
    else:
        pts = pts.to_crs(epsg=4326)

    pts = pts[pts.is_valid & ~pts.is_empty]
    return pts

try:
    gdf_points = load_points()
except Exception as e:
    st.warning(f"⚠️ Points not loaded: {e}")
    gdf_points = None

# =========================================================
# SIDEBAR HEADER
# =========================================================
with st.sidebar:
    st.image("AGeoAgri_Mali_2026/logo/logo_wgv.png", width=400)
    st.markdown(f"**User:** {st.session_state.username} ({st.session_state.user_role})")
    if st.button("Logout"):
        logout()

# =========================================================
# SAFE UNIQUE FUNCTION
# =========================================================
def unique_clean(series):
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:,0]
    return sorted(series.dropna().astype(str).str.strip().unique())

# =========================================================
# ATTRIBUTE FILTERS
# =========================================================
st.sidebar.markdown("### 🗂️ Attribute Query")

all_regions = unique_clean(gdf["LREG_NEW"])
regions = all_regions if st.session_state.user_role=="Admin" else [r for r in all_regions if r in st.session_state.accessible_regions]
region = st.sidebar.selectbox("Region", regions)
gdf_r = gdf[gdf["LREG_NEW"] == region]

cercles = unique_clean(gdf_r["LCER_NEW"])
cercle = st.sidebar.selectbox("Cercle", cercles)
gdf_c = gdf_r[gdf_r["LCER_NEW"] == cercle]

communes = unique_clean(gdf_c["LCOM_NEW"])
commune = st.sidebar.selectbox("Commune", communes)
gdf_commune = gdf_c[gdf_c["LCOM_NEW"] == commune]

se_list = ["No filter"] + unique_clean(gdf_commune["num_se"])
se_selected = st.sidebar.selectbox("SE (num_se)", se_list)
gdf_se = gdf_commune if se_selected=="No filter" else gdf_commune[gdf_commune["num_se"]==se_selected]

# =========================================================
# FILTER POINTS
# =========================================================
points_filtered = None
if gdf_points is not None and not gdf_commune.empty:
    gdf_commune_proj = gdf_commune.to_crs(gdf_points.crs)

    points_filtered = gpd.sjoin(
        gdf_points,
        gdf_commune_proj[["geometry"]],
        how="inner",
        predicate="within"
    )

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

    # POLYGONS
    se_group = folium.FeatureGroup(name="SE Polygons")
    folium.GeoJson(
        gdf_se,
        tooltip=folium.GeoJsonTooltip(fields=["num_se","pop_se"]),
        style_function=lambda x: {"color":"blue","weight":2,"fillOpacity":0.2}
    ).add_to(se_group)

    se_group.add_to(m)

   # =========================================================
# POINTS
# =========================================================
if points_filtered is not None and not points_filtered.empty:

    cluster = MarkerCluster(
        name="Points Agricoles",
        spiderfyOnMaxZoom=True,
        disableClusteringAtZoom=16
    ).add_to(m)

    for _, r in points_filtered.iterrows():

        point_id = (
            r.get("ID")
            or r.get("id")
            or r.get("Name")
            or r.get("Nom")
            or r.get("culture")
            or "Point Agricole"
        )

        folium.CircleMarker(
            location=[r.geometry.y, r.geometry.x],
            radius=5,
            color="#2E8B57",
            fill=True,
            fill_opacity=0.8,
            tooltip=str(point_id),
            popup=f"<b>{point_id}</b>"
        ).add_to(cluster)

    pts_group = folium.FeatureGroup(name="Points colorés")

    for _, r in points_filtered.iterrows():
        val = r.get("culture", "unknown")
        color = "gray"

        if val == "riz":
            color = "blue"
        elif val == "mais":
            color = "yellow"
        elif val == "coton":
            color = "green"

        folium.CircleMarker(
            [r.geometry.y, r.geometry.x],
            radius=5,
            color=color,
            fill=True
        ).add_to(pts_group)

    pts_group.add_to(m)

    # Aggregated cluster
    cluster2 = MarkerCluster(
        name="Points Agrégés",
        showCoverageOnHover=False,
        zoomToBoundsOnClick=True,
        spiderfyOnMaxZoom=True
    ).add_to(m)

    for _, r in points_filtered.iterrows():
        folium.CircleMarker(
            location=[r.geometry.y, r.geometry.x],
            radius=4,
            color="green",
            fill=True,
            fill_opacity=0.7
        ).add_to(cluster2)

    # Heatmap
    # heat_data = [[p.y, p.x] for p in points_filtered.geometry]
    # HeatMap(heat_data).add_to(m)

    MeasureControl().add_to(m)
    Draw(export=True).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)

    m.fit_bounds([[miny,minx],[maxy,maxx]])

    st_folium(m, height=550, use_container_width=True)

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

 
