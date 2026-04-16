import streamlit as st
import folium
import requests
import pandas as pd
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw, MarkerCluster, HeatMap

# =========================================================
# APP CONFIG
# =========================================================
st.set_page_config(layout="wide", page_title="Système d’Information Agricole du Mali (SIAM)")
st.title("🌱 GeoAgri Mali : Systèmes Agricoles Dynamique")

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
# SESSION INIT
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
# SERVER LINKS (YOUR FILEBROWSER)
# =========================================================
POLYGON_URL = "https://filebrowser.instat.ml/files/geoagri_mali/AGeoAgri_Mali/data/emop2026.geojson"
POINT_URL = "https://filebrowser.instat.ml/files/geoagri_mali/AGeoAgri_Mali/data/agri_ml_exploitation.geojson"

# =========================================================
# SAFE LOADER (FIXED 401 + HTML ISSUE)
# =========================================================
@st.cache_data
def load_geojson(url):
    try:
        r = requests.get(url, timeout=30)

        # ❌ HTTP ERROR CHECK
        if r.status_code != 200:
            st.error(f"❌ Error loading file: {r.status_code}")
            return None

        # ❌ HTML CHECK (very important for FileBrowser)
        if "json" not in r.headers.get("Content-Type", ""):
            st.error("❌ The URL does not return GeoJSON (maybe login required or wrong link)")
            return None

        return r.json()

    except Exception as e:
        st.error(f"❌ Request failed: {e}")
        return None

# =========================================================
# LOAD DATA
# =========================================================
geojson_poly = load_geojson(POLYGON_URL)
geojson_pts = load_geojson(POINT_URL)

if geojson_poly is None:
    st.stop()

# =========================================================
# MAP
# =========================================================
m = folium.Map(location=[17, -4], zoom_start=6, tiles="OpenStreetMap")

# =========================================================
# POLYGONS
# =========================================================
folium.GeoJson(
    geojson_poly,
    tooltip=folium.GeoJsonTooltip(fields=["num_se","pop_se"])
).add_to(m)

# =========================================================
# POINTS
# =========================================================
if geojson_pts is not None:

    cluster = MarkerCluster().add_to(m)
    heat_data = []

    for f in geojson_pts["features"]:
        coords = f["geometry"]["coordinates"]
        props = f.get("properties", {})

        lat, lon = coords[1], coords[0]
        heat_data.append([lat, lon])

        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color="red",
            fill=True,
            tooltip=props.get("id", "point")
        ).add_to(cluster)

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
**Système d’Information Agricole du Mali (SIAM)**  
**- Dr. Mahamadou CAMARA**  
**- Abdoul Karim DIAWARA**
""")
