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
# SERVER LINKS
# IMPORTANT: must be PUBLIC (no login page)
# =========================================================
POLYGON_URL = "https://filebrowser.instat.ml/files/geoagri_mali/AGeoAgri_Mali/data/emop2026.geojson"
POINT_URL   = "https://filebrowser.instat.ml/files/geoagri_mali/AGeoAgri_Mali/data/agri_ml_exploitation.geojson"

# =========================================================
# SAFE GEOJSON LOADER (ROBUST FOR FILEBROWSER)
# =========================================================
@st.cache_data
def load_geojson(url):
    try:
        r = requests.get(url, timeout=30)

        # HTTP check
        if r.status_code != 200:
            st.error(f"❌ Error loading file: HTTP {r.status_code}")
            return None

        text = r.text.strip()

        # HTML detection (FileBrowser login page problem)
        if text.startswith("<!DOCTYPE") or text.startswith("<html"):
            st.error("❌ Server returned HTML instead of GeoJSON (check access or permissions)")
            return None

        # JSON parsing safety
        try:
            return r.json()
        except Exception:
            st.error("❌ Invalid JSON format from server")
            return None

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
    tooltip=folium.GeoJsonTooltip(
        fields=["num_se", "pop_se"],
        aliases=["SE", "Population"]
    )
).add_to(m)

# =========================================================
# POINTS
# =========================================================
if geojson_pts and "features" in geojson_pts:

    cluster = MarkerCluster().add_to(m)
    heat_data = []

    for f in geojson_pts["features"]:
        coords = f.get("geometry", {}).get("coordinates", None)
        props = f.get("properties", {})

        if not coords:
            continue

        lon, lat = coords[0], coords[1]
        heat_data.append([lat, lon])

        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
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
# MAP
# =========================================================
if not gdf_se.empty:
    minx, miny, maxx, maxy = gdf_se.total_bounds

    m = folium.Map(location=[(miny+maxy)/2,(minx+maxx)/2], zoom_start=13, tiles=None)

    folium.TileLayer("OpenStreetMap").add_to(m)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Google Satellite"
    ).add_to(m)

    # POLYGONS
    folium.GeoJson(
        gdf_se,
        tooltip=folium.GeoJsonTooltip(fields=["num_se","pop_se"]),
        style_function=lambda x: {"color":"blue","weight":2,"fillOpacity":0.2}
    ).add_to(m)

    # POINTS
    if points_filtered is not None and not points_filtered.empty:

        cluster = MarkerCluster().add_to(m)

        for _, r in points_filtered.iterrows():
            folium.Marker(
                location=[r.geometry.y, r.geometry.x],
                tooltip=f"ID: {r.get('id','N/A')}"
            ).add_to(cluster)

        HeatMap([[r.geometry.y, r.geometry.x] for _, r in points_filtered.iterrows()]).add_to(m)

    MeasureControl().add_to(m)
    Draw(export=True).add_to(m)
    folium.LayerControl().add_to(m)

    m.fit_bounds([[miny,minx],[maxy,maxx]])
    st_folium(m, height=550, use_container_width=True)

# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**Système d’Information Agricole du Mali (SIAM)**  
**- Dr. Mahamadou CAMARA**  
**- Abdoul Karim DIAWARA**
""")
