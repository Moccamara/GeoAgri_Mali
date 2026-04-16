import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw, MarkerCluster, HeatMap
import pandas as pd

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
            st.sidebar.error("❌ Invalid login")
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

    gdf.columns = [c.strip() for c in gdf.columns]

    for col in ["LREG_NEW","LCER_NEW","LCOM_NEW","num_se","pop_se"]:
        if col not in gdf.columns:
            gdf[col] = None

    gdf = gdf[gdf.is_valid & ~gdf.is_empty]
    return gdf

@st.cache_data(show_spinner=False)
def load_points():
    pts = gpd.read_file("AGeoAgri_Mali_2026/data/data/Exploitation_Agri_ml3.geojson")

    if pts.crs is None:
        pts = pts.set_crs(epsg=4326)
    else:
        pts = pts.to_crs(epsg=4326)

    pts = pts[pts.is_valid & ~pts.is_empty]
    return pts

gdf = load_se_data()
gdf_points = load_points()

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.image("AGeoAgri_Mali_2026/logo/logo_wgv.png", width=200)
    st.markdown(f"**User:** {st.session_state.username} ({st.session_state.user_role})")

# =========================================================
# FILTERS
# =========================================================
def unique_clean(series):
    return sorted(series.dropna().astype(str).str.strip().unique())

all_regions = unique_clean(gdf["LREG_NEW"])

regions = all_regions if st.session_state.user_role == "Admin" else [
    r for r in all_regions if r in st.session_state.accessible_regions
]

region = st.sidebar.selectbox("Region", regions)
gdf_r = gdf[gdf["LREG_NEW"] == region]

cercle = st.sidebar.selectbox("Cercle", unique_clean(gdf_r["LCER_NEW"]))
gdf_c = gdf_r[gdf_r["LCER_NEW"] == cercle]

commune = st.sidebar.selectbox("Commune", unique_clean(gdf_c["LCOM_NEW"]))
gdf_commune = gdf_c[gdf_c["LCOM_NEW"] == commune]

# =========================================================
# POINT FILTER
# =========================================================
points_filtered = gdf_points.copy()

# =========================================================
# MAP
# =========================================================
if not gdf_commune.empty:

    minx, miny, maxx, maxy = gdf_commune.total_bounds

    m = folium.Map(location=[(miny+maxy)/2, (minx+maxx)/2], zoom_start=13)

    folium.TileLayer("OpenStreetMap").add_to(m)

    # POLYGONS
    folium.GeoJson(
        gdf_commune,
        tooltip=folium.GeoJsonTooltip(fields=["num_se","pop_se"])
    ).add_to(m)

    # POINTS
    if points_filtered is not None:

        cluster = MarkerCluster().add_to(m)

        for _, r in points_filtered.iterrows():
            folium.CircleMarker(
                location=[r.geometry.y, r.geometry.x],
                radius=5,
                color="red",
                fill=True
            ).add_to(cluster)

        HeatMap([[r.geometry.y, r.geometry.x] for _, r in points_filtered.iterrows()]).add_to(m)

    MeasureControl().add_to(m)
    Draw(export=True).add_to(m)
    folium.LayerControl().add_to(m)

    st_folium(m, height=600, use_container_width=True)

# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**Système d’Information Agricole du Mali (SIAM)**  
**- Dr. Mahamadou CAMARA**  
**- Abdoul Karim DIAWARA**
""")
