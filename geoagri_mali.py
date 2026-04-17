import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw, MarkerCluster
import pandas as pd
from pathlib import Path

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
# SESSION STATE (SAFE)
# =========================================================
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.accessible_regions = []

if "phone_search" not in st.session_state:
    st.session_state.phone_search = ""

# =========================================================
# FUNCTIONS
# =========================================================
def logout():
    st.session_state.clear()
    st.rerun()

def find_phone_column(gdf):
    possible = ["Num,ro_1", "Numero1", "Numero_1", "phone", "tel", "telephone"]
    for c in possible:
        if c in gdf.columns:
            return c
    return None

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
    gdf.columns = [c.strip() for c in gdf.columns]
    return gdf

@st.cache_data(show_spinner=False)
def load_points():
    pts = gpd.read_file("AGeoAgri_Mali_2026/data/Exploitation_Agri_ml3.geojson")
    if pts.crs is None:
        pts = pts.set_crs(epsg=4326)
    else:
        pts = pts.to_crs(epsg=4326)
    pts.columns = [c.strip() for c in pts.columns]
    return pts

gdf = load_se_data()
gdf_points = load_points()

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.image("AGeoAgri_Mali_2026/logo/logo_wgv.png", width=300)
    st.markdown(f"**User:** {st.session_state.username}")
    if st.button("Logout"):
        logout()

st.sidebar.markdown("### 🔎 Research Section")

# =========================================================
# PHONE SEARCH
# =========================================================
phone_search = st.sidebar.text_input("Search by phone", key="phone_search")

search_result = None
if phone_search and gdf_points is not None:
    phone_col = find_phone_column(gdf_points)
    if phone_col:
        search_result = gdf_points[
            gdf_points[phone_col].astype(str).str.contains(phone_search, na=False)
        ]

# =========================================================
# FILTERS
# =========================================================
def unique_clean(series):
    return sorted(series.dropna().astype(str).unique())

region = st.sidebar.selectbox("Region", unique_clean(gdf["LREG_NEW"]))
gdf_r = gdf[gdf["LREG_NEW"] == region]

cercle = st.sidebar.selectbox("Cercle", unique_clean(gdf_r["LCER_NEW"]))
gdf_c = gdf_r[gdf_r["LCER_NEW"] == cercle]

commune = st.sidebar.selectbox("Commune", unique_clean(gdf_c["LCOM_NEW"]))
gdf_commune = gdf_c[gdf_c["LCOM_NEW"] == commune]

# =========================================================
# POINT FILTER
# =========================================================
points_filtered = None
if not gdf_commune.empty:
    gdf_commune_proj = gdf_commune.to_crs(gdf_points.crs)
    points_filtered = gpd.sjoin(
        gdf_points,
        gdf_commune_proj[["geometry"]],
        how="inner",
        predicate="within"
    )

# =========================================================
# MAP CREATION (ONLY ONCE)
# =========================================================
map_data = None
m = None

if not gdf_commune.empty:

    minx, miny, maxx, maxy = gdf_commune.total_bounds

    m = folium.Map(location=[(miny+maxy)/2,(minx+maxx)/2], zoom_start=13)

    folium.TileLayer("OpenStreetMap").add_to(m)
    folium.GeoJson(gdf_commune).add_to(m)

    if points_filtered is not None:
        cluster = MarkerCluster().add_to(m)
        for _, r in points_filtered.iterrows():
            folium.CircleMarker(
                [r.geometry.y, r.geometry.x],
                radius=4,
                color="#2E8B57",
                fill=True,
                fill_opacity=0.8
            ).add_to(cluster)

    MeasureControl().add_to(m)
    Draw(export=True).add_to(m)
    folium.LayerControl().add_to(m)

    map_data = st_folium(
        m,
        height=550,
        use_container_width=True,
        returned_objects=["last_clicked"]
    )

# =========================================================
# 🔥 PHONE HIGHLIGHT (FIXED + SAFE)
# =========================================================
if m is not None and search_result is not None and not search_result.empty:

    pt = search_result.iloc[0].geometry
    lat, lon = pt.y, pt.x

    m.fit_bounds([[lat, lon], [lat, lon]])

    pulse_css = """
    <style>
    .pulse {
        width: 18px;
        height: 18px;
        background: yellow;
        border-radius: 50%;
        border: 2px solid orange;
        animation: pulse 1.5s infinite ease-out;
    }
    @keyframes pulse {
        0% {transform: scale(0.5); opacity: 1;}
        70% {transform: scale(2); opacity: 0.3;}
        100% {transform: scale(3); opacity: 0;}
    }
    </style>
    """

    m.get_root().html.add_child(folium.Element(pulse_css))

    folium.Marker(
        [lat, lon],
        icon=folium.DivIcon(html="<div class='pulse'></div>")
    ).add_to(m)

# =========================================================
# RESET SEARCH ON MAP CLICK
# =========================================================
if map_data and map_data.get("last_clicked"):
    st.session_state.phone_search = ""

# =========================================================
# TABLE OUTPUT
# =========================================================
if search_result is not None:
    st.markdown("## 📊 Result Table")
    st.dataframe(search_result, use_container_width=True)

# =========================================================
# FOOTER
# =========================================================
st.markdown("---")
st.markdown("### Système d’Information Agricole du Mali (SIAM)")
