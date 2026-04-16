import streamlit as st
import folium
import requests
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw, MarkerCluster, HeatMap

# =========================================================
# APP CONFIG
# =========================================================
st.set_page_config(layout="wide", page_title="SIAM Mali")
st.title("🌱 GeoAgri Mali : Systèmes Agricoles Dynamiques")

# =========================================================
# USERS
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
# SESSION
# =========================================================
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.accessible_regions = []

# =========================================================
# LOGIN
# =========================================================
if not st.session_state.auth_ok:
    st.sidebar.header("🔐 Login")
    username = st.sidebar.text_input("Login")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        if username in USERS and USERS[username]["password"] == password:
            st.session_state.auth_ok = True
            st.session_state.username = username
            st.session_state.user_role = USERS[username]["role"]
            st.session_state.accessible_regions = USERS[username]["regions"]
            st.rerun()
        else:
            st.sidebar.error("❌ Invalid login")
    st.stop()

# =========================================================
# DATA LINKS (PUBLIC ONLY)
# =========================================================
POLYGON_URL = "https://filebrowser.instat.ml/files/geoagri_mali/AGeoAgri_Mali/data/emop2026.geojson"
POINT_URL   = "https://filebrowser.instat.ml/files/geoagri_mali/AGeoAgri_Mali/data/agri_ml_exploitation.geojson"

# =========================================================
# SAFE GEOJSON LOADER (IMPORTANT FIX)
# =========================================================
@st.cache_data
def load_geojson(url):
    try:
        r = requests.get(url, timeout=40)
        r.raise_for_status()

        text = r.text.strip()

        # avoid HTML login pages
        if text.startswith("<"):
            st.error("❌ Server returned HTML (check access permissions)")
            return None

        return r.json()

    except Exception as e:
        st.error(f"❌ Loading error: {e}")
        return None

# =========================================================
# LOAD DATA
# =========================================================
geo_polygons = load_geojson(POLYGON_URL)
geo_points = load_geojson(POINT_URL)

if not geo_polygons:
    st.stop()

# =========================================================
# MAP INIT
# =========================================================
m = folium.Map(location=[17, -4], zoom_start=6, tiles="OpenStreetMap")

# =========================================================
# POLYGONS
# =========================================================
folium.GeoJson(
    geo_polygons,
    tooltip=folium.GeoJsonTooltip(fields=["num_se", "pop_se"])
).add_to(m)

# =========================================================
# POINTS
# =========================================================
if geo_points and "features" in geo_points:

    cluster = MarkerCluster().add_to(m)
    heat_data = []

    for f in geo_points["features"]:
        coords = f.get("geometry", {}).get("coordinates", None)
        props = f.get("properties", {})

        if not coords:
            continue

        lon, lat = coords
        heat_data.append([lat, lon])

        folium.CircleMarker(
            location=[lat, lon],
            radius=4,
            color="red",
            fill=True,
            tooltip=props.get("id", "point")
        ).add_to(cluster)

    if heat_data:
        HeatMap(heat_data).add_to(m)

# =========================================================
# TOOLS
# =========================================================
MeasureControl().add_to(m)
Draw(export=True).add_to(m)
folium.LayerControl().add_to(m)

st_folium(m, height=600, use_container_width=True)

# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**SIAM Mali - GeoAgri System**  
**Dr. Mahamadou CAMARA**
""")
