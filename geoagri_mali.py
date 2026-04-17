import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw, MarkerCluster
import pandas as pd
from pathlib import Path
from shapely.geometry import shape

# =========================================================
# APP CONFIG
# =========================================================
st.set_page_config(layout="wide", page_title="Système d’Information Agricole du Mali (SIAM)")
st.title("🌱 GeoAgri Mali : Analyse Dynamique des Systèmes Agricoles")

# =========================================================
# USERS
# =========================================================
USERS = {
    "geoagriuser1": {"password": "geoagriuser12026", "role": "User",
                     "regions": ["Kayes","Kita","Nioro","Sikasso","Koutiala"]},
    "geoagriuser2": {"password": "geoagriuser22026", "role": "User",
                     "regions": ["Koulikoro","Bamako"]},
    "geoagriuser3": {"password": "geoagriuser32026", "role": "User",
                     "regions": ["Dioila","Nara"]},
    "geoagriadmin": {"password": "geoagriadmin2026", "role": "Admin", "regions": []}
}

# =========================================================
# SESSION
# =========================================================
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
    st.session_state.phone_search = ""
    st.session_state.last_clicked = None

# =========================================================
# LOGIN
# =========================================================
if not st.session_state.auth_ok:
    st.sidebar.header("Login")
    u = st.sidebar.text_input("User")
    p = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        if u in USERS and USERS[u]["password"] == p:
            st.session_state.auth_ok = True
            st.session_state.user = u
            st.rerun()
        else:
            st.error("Wrong credentials")
    st.stop()

# =========================================================
# LOAD DATA
# =========================================================
@st.cache_data
def load_data():
    gdf = gpd.read_file("AGeoAgri_Mali_2026/data/emop2026.geojson")
    pts = gpd.read_file("AGeoAgri_Mali_2026/data/Exploitation_Agri_ml3.geojson")

    gdf = gdf.to_crs(4326)
    pts = pts.to_crs(4326)

    return gdf, pts

gdf, gdf_points = load_data()

# =========================================================
# PHONE COLUMN
# =========================================================
def find_phone_column(gdf):
    for c in ["telephone","phone","tel","Numero_1","Numero1"]:
        if c in gdf.columns:
            return c
    return None

# =========================================================
# LINK POINT → POLYGON (CRITICAL FIX)
# =========================================================
@st.cache_data
def link_points(points, polygons):
    poly = polygons[["LCOM_NEW","LCER_NEW","LREG_NEW","geometry"]].copy()
    return gpd.sjoin(points, poly, predicate="within", how="left")

gdf_points_linked = link_points(gdf_points, gdf)

# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.image("AGeoAgri_Mali_2026/logo/logo_wgv.png", width=300)

if st.sidebar.button("Clear selection"):
    st.session_state.phone_search = ""
    st.session_state.last_clicked = None

phone_search = st.sidebar.text_input("Search phone", key="phone_search")

# =========================================================
# PHONE SEARCH → GET POLYGON
# =========================================================
search_result = None
selected_commune = None

if phone_search:
    phone_col = find_phone_column(gdf_points_linked)

    if phone_col:
        search_result = gdf_points_linked[
            gdf_points_linked[phone_col].astype(str).str.contains(phone_search, na=False)
        ]

        if not search_result.empty:
            selected_commune = search_result.iloc[0]["LCOM_NEW"]

# =========================================================
# FILTER POLYGONS
# =========================================================
if selected_commune:
    gdf_commune = gdf[gdf["LCOM_NEW"] == selected_commune]
else:
    gdf_commune = gdf

# =========================================================
# MAP
# =========================================================
minx, miny, maxx, maxy = gdf_commune.total_bounds
m = folium.Map(location=[(miny+maxy)/2, (minx+maxx)/2], zoom_start=12)

folium.GeoJson(
    gdf_commune,
    style_function=lambda x: {"color":"blue","weight":2,"fillOpacity":0.2}
).add_to(m)

# POINTS (ONLY INSIDE POLYGON)
points_filtered = gdf_points_linked

if selected_commune:
    points_filtered = points_filtered[
        points_filtered["LCOM_NEW"] == selected_commune
    ]

cluster = MarkerCluster().add_to(m)

for _, r in points_filtered.iterrows():
    folium.CircleMarker(
        [r.geometry.y, r.geometry.x],
        radius=5,
        color="green",
        fill=True
    ).add_to(cluster)

# SEARCH HIGHLIGHT
if search_result is not None and not search_result.empty:
    p = search_result.iloc[0].geometry
    folium.Marker([p.y, p.x], icon=folium.Icon(color="red")).add_to(m)
    m.location = [p.y, p.x]

# DRAW TOOL
draw = Draw(export=True)
draw.add_to(m)
MeasureControl().add_to(m)

map_data = st_folium(m, height=600, returned_objects=["all_drawings","last_clicked"])

# =========================================================
# TABLE LOGIC (FIXED)
# =========================================================
selected_df = None

# CASE 1: PHONE SEARCH → ALL POINTS IN SAME COMMUNE
if search_result is not None and not search_result.empty:
    selected_df = gdf_points_linked[
        gdf_points_linked["LCOM_NEW"] == selected_commune
    ]

# CASE 2: DRAW SELECTION (RECTANGLE / POLYGON)
elif map_data and map_data.get("all_drawings"):

    selected = []

    for d in map_data["all_drawings"]:
        geom = shape(d["geometry"])
        inside = gdf_points_linked[gdf_points_linked.intersects(geom)]
        if not inside.empty:
            selected.append(inside)

    if selected:
        selected_df = pd.concat(selected).drop_duplicates()

# CASE 3: CLICK SELECTION
elif map_data and map_data.get("last_clicked"):

    click = map_data["last_clicked"]
    lat, lon = click["lat"], click["lng"]

    df = gdf_points_linked.copy()
    df["dist"] = (df.geometry.y-lat)**2 + (df.geometry.x-lon)**2
    selected_df = df.sort_values("dist").head(1)

# =========================================================
# DISPLAY TABLE
# =========================================================
if selected_df is not None and not selected_df.empty:
    cols = [c for c in ["LCOM_NEW","LCER_NEW","LREG_NEW","telephone"] if c in selected_df.columns]

    st.markdown("## 📊 Result Table")
    st.dataframe(selected_df[cols], use_container_width=True)

# =========================================================
# FOOTER
# =========================================================
st.markdown("---")
st.markdown("### SIAM - Mali GIS System")

logos_path = Path(__file__).parent / "AGeoAgri_Mali_2026" / "logos"
if logos_path.exists():
    cols = st.columns(3)
    for i, logo in enumerate(logos_path.glob("*")):
        with cols[i % 3]:
            st.image(str(logo), width=120)
