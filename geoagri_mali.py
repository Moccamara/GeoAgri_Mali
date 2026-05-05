import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw, MarkerCluster
import pandas as pd
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(layout="wide", page_title="SIAM")
st.title("🌱 GeoAgri Mali : Système d’Information Agricole du Mali (SIAM)")

MAX_POINTS = 4000  # 🔥 critical for performance

# =========================================================
# USERS
# =========================================================
USERS = {
    "geoagriuser1": {"password": "geoagriuser12026", "role": "User", "regions": ["Kayes","Kita","Nioro","Sikasso","Koutiala"]},
    "geoagriuser2": {"password": "geoagriuser22026", "role": "User", "regions": ["Koulikoro","Bamako"]},
    "geoagriadmin": {"password": "geoagriadmin2026", "role": "Admin", "regions": []}
}

# =========================================================
# SESSION
# =========================================================
if "auth_ok" not in st.session_state:
    st.session_state.update({
        "auth_ok": False,
        "username": None,
        "user_role": None,
        "accessible_regions": [],
        "phone_search": "",
        "full_zoom": False
    })

# =========================================================
# LOGIN
# =========================================================
if not st.session_state.auth_ok:
    st.sidebar.header("🔐 Login")
    u = st.sidebar.text_input("Login")
    p = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        if u in USERS and USERS[u]["password"] == p:
            st.session_state.auth_ok = True
            st.session_state.username = u
            st.session_state.user_role = USERS[u]["role"]
            st.session_state.accessible_regions = USERS[u]["regions"]
            st.rerun()
        else:
            st.sidebar.error("Invalid credentials")
    st.stop()

# =========================================================
# LOAD DATA (OPTIMIZED)
# =========================================================
@st.cache_data
def load_all():
    gdf = gpd.read_file("AGeoAgri_Mali_2026/data/emop2026.geojson", engine="pyogrio")
    pts = gpd.read_file("AGeoAgri_Mali_2026/data/Exploitation_Agri_ml3.geojson", engine="pyogrio")
    reg = gpd.read_file("AGeoAgri_Mali_2026/data/Region_Mali.geojson", engine="pyogrio")

    for df in [gdf, pts, reg]:
        if df.crs is None:
            df.set_crs(epsg=4326, inplace=True)
        else:
            df.to_crs(epsg=4326, inplace=True)

    # 🔥 simplify geometry (big speed gain)
    gdf["geometry"] = gdf["geometry"].simplify(0.001)
    reg["geometry"] = reg["geometry"].simplify(0.01)

    return gdf, pts, reg

gdf, gdf_points, gdf_regions = load_all()

# =========================================================
# FILTER (NO SJOIN 🔥)
# =========================================================
@st.cache_data
def filter_data(region):
    if region == "No filter":
        return gdf, gdf_points, gdf_regions
    return (
        gdf[gdf["LREG_NEW"] == region],
        gdf_points[gdf_points["LREG_NEW"] == region],
        gdf_regions[gdf_regions["LREG_NEW"] == region]
    )

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown(f"**User:** {st.session_state.username}")

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

    phone_search = st.text_input("📞 Search phone")

    regions = sorted(gdf_regions["LREG_NEW"].dropna().unique())

    if st.session_state.user_role == "Admin":
        allowed = regions
    else:
        allowed = [r for r in regions if r in st.session_state.accessible_regions]

    region = st.selectbox("Region", ["No filter"] + allowed)

# =========================================================
# APPLY FILTER
# =========================================================
gdf_se, points_filtered, region_display = filter_data(region)

# =========================================================
# PHONE SEARCH
# =========================================================
if phone_search:
    if "telephone" in gdf_points.columns:
        points_filtered = points_filtered[
            points_filtered["telephone"].astype(str).str.contains(phone_search, na=False)
        ]

# 🔥 LIMIT POINTS (CRITICAL)
if len(points_filtered) > MAX_POINTS:
    points_filtered = points_filtered.sample(MAX_POINTS)

# =========================================================
# MAP
# =========================================================
m = folium.Map(location=[17.5, -4], zoom_start=5)

folium.TileLayer("OpenStreetMap").add_to(m)
folium.TileLayer(
    tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    attr="Google",
    name="Google Satellite"
).add_to(m)

# Regions
folium.GeoJson(
    region_display,
    name="Regions",
    style_function=lambda x: {"color": "#444", "weight": 2, "fillOpacity": 0.1}
).add_to(m)

# SE
if not gdf_se.empty:
    folium.GeoJson(
        gdf_se,
        name="SE",
        style_function=lambda x: {"color": "blue", "weight": 0.3}
    ).add_to(m)

# Points (optimized)
if not points_filtered.empty:
    cluster = MarkerCluster().add_to(m)

    for _, r in points_filtered.iterrows():
        folium.CircleMarker(
            [r.geometry.y, r.geometry.x],
            radius=4,
            color="red",
            fill=True
        ).add_to(cluster)

MeasureControl().add_to(m)
Draw(export=False).add_to(m)
folium.LayerControl().add_to(m)

map_data = st_folium(m, height=600, use_container_width=True)

# =========================================================
# TABLE
# =========================================================
if map_data and not points_filtered.empty:

    cols = [
        "LREG_NEW","LCER_NEW","LCOM_NEW",
        "Prenom_du","Nom_du_Che",
        "Forme_juri","telephone","Super"
    ]

    cols = [c for c in cols if c in points_filtered.columns]

    st.markdown("## 📊 Exploitations sélectionnées")
    st.dataframe(points_filtered[cols], use_container_width=True)


# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
### Système d’Information Agricole du Mali (SIAM)
""")

logos_path = Path(__file__).parent / "AGeoAgri_Mali_2026" / "logos"
logo_files = sorted(list(logos_path.glob("*")))

if logo_files:
    cols = st.columns(len(logo_files))
    for col, logo in zip(cols, logo_files):
        with col:
            st.image(str(logo), width=150)

st.markdown("""
---

 © Dr. Mahamadou CAMARA and Abdoul Karim DIAWARA
""")
