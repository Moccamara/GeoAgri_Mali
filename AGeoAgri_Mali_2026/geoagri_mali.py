```python
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw, MarkerCluster, HeatMap
import pandas as pd

# =========================================================
# APP CONFIG
# =========================================================
st.set_page_config(
    layout="wide",
    page_title="Système d’Information Agricole du Mali (SIAM)"
)

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
# LOAD EMOP SE POLYGONS (GITHUB RAW)
# =========================================================
@st.cache_data(show_spinner=False)
def load_se_data():

    url = "https://raw.githubusercontent.com/Moccamara/GeoAgri_Mali/main/AGeoAgri_Mali_2026/data/emop2026.geojson"
    
    gdf = gpd.read_file(url)

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    gdf.columns = [c.strip() for c in gdf.columns]

    gdf = gdf[gdf.is_valid & ~gdf.is_empty]

    return gdf

try:
    gdf = load_se_data()
except Exception as e:
    st.exception(e)
    st.stop()

# =========================================================
# LOAD POINTS (GITHUB RAW)
# =========================================================
@st.cache_data(show_spinner=False)
def load_points():

    url = "https://raw.githubusercontent.com/Moccamara/GeoAgri_Mali/main/AGeoAgri_Mali_2026/data/Exploitation_Agri_ml3.geojson"
    
    pts = gpd.read_file(url)

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
# SIDEBAR
# =========================================================
with st.sidebar:

    st.markdown(f"**User:** {st.session_state.username} ({st.session_state.user_role})")

    if st.button("Logout"):
        logout()

# =========================================================
# SAFE UNIQUE
# =========================================================
def unique_clean(series):

    if isinstance(series, pd.DataFrame):
        series = series.iloc[:,0]

    return sorted(
        series.dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

# =========================================================
# FILTERS
# =========================================================
st.sidebar.markdown("### 🗂️ Attribute Query")

all_regions = unique_clean(gdf["LREG_NEW"])

regions = (
    all_regions
    if st.session_state.user_role == "Admin"
    else [
        r for r in all_regions
        if r in st.session_state.accessible_regions
    ]
)

region = st.sidebar.selectbox("Region", regions)


gdf_r = gdf[gdf["LREG_NEW"] == region]

cercles = unique_clean(gdf_r["LCER_NEW"])
cercle = st.sidebar.selectbox("Cercle", cercles)


gdf_c = gdf_r[gdf_r["LCER_NEW"] == cercle]

communes = unique_clean(gdf_c["LCOM_NEW"])
commune = st.sidebar.selectbox("Commune", communes)


gdf_commune = gdf_c[gdf_c["LCOM_NEW"] == commune]

se_list = ["No filter"] + unique_clean(gdf_commune["num_se"])

se_selected = st.sidebar.selectbox("SE", se_list)


gdf_se = (
    gdf_commune
    if se_selected == "No filter"
    else gdf_commune[gdf_commune["num_se"] == se_selected]
)

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

    m = folium.Map(
        location=[(miny+maxy)/2,(minx+maxx)/2],
        zoom_start=12,
        tiles=None
    )

    folium.TileLayer("OpenStreetMap",name="OSM").add_to(m)

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Satellite"
    ).add_to(m)

    # POLYGONS
    folium.GeoJson(
        gdf_se,
        tooltip=folium.GeoJsonTooltip(
            fields=["num_se","pop_se"]
        ),
        style_function=lambda x: {
            "color":"blue",
            "weight":2,
            "fillOpacity":0.2
        }
    ).add_to(m)

    # POINTS
    if points_filtered is not None and not points_filtered.empty:

        points_filtered = points_filtered.copy()

        cluster = MarkerCluster().add_to(m)

        for _, r in points_filtered.iterrows():
            folium.Marker(
                [r.geometry.y, r.geometry.x]
            ).add_to(cluster)

        HeatMap([
            [r.geometry.y, r.geometry.x]
            for _, r in points_filtered.iterrows()
        ]).add_to(m)

    MeasureControl().add_to(m)
    Draw(export=True).add_to(m)

    folium.LayerControl().add_to(m)

    m.fit_bounds([[miny,minx],[maxy,maxx]])

    st_folium(
        m,
        height=600,
        use_container_width=True
    )

# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**GeoAgri Mali - EMOP 2026**  
**Abdoul Karim DIAWARA**  
**Dr. Mahamadou CAMARA**
""")
```
