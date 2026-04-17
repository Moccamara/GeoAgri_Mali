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
    st.session_state.phone_search = ""   # IMPORTANT

# =========================================================
# SAFE RESET FUNCTION (FIX STREAMLIT ERROR)
# =========================================================
def reset_search():
    st.session_state.update({"phone_search": ""})

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
# LOAD DATA
# =========================================================
@st.cache_data
def load_se():
    gdf = gpd.read_file("AGeoAgri_Mali_2026/data/emop2026.geojson")
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    gdf.columns = [c.strip() for c in gdf.columns]
    return gdf

@st.cache_data
def load_points():
    pts = gpd.read_file("AGeoAgri_Mali_2026/data/Exploitation_Agri_ml3.geojson")

    if pts.crs is None:
        pts = pts.set_crs(epsg=4326)
    else:
        pts = pts.to_crs(epsg=4326)

    pts.columns = [c.strip() for c in pts.columns]
    return pts

gdf = load_se()
gdf_points = load_points()

# =========================================================
# SAFE FUNCTIONS
# =========================================================
def unique_clean(series):
    return sorted(series.dropna().astype(str).str.strip().unique())

def find_phone_column(gdf):
    possible = ["Num,ro_1", "Numero1", "Numero_1", "phone", "tel", "telephone"]
    for c in possible:
        if c in gdf.columns:
            return c
    return None

# =========================================================
# SEARCH SECTION
# =========================================================
st.sidebar.markdown("### 🔎 Search")

phone_search = st.sidebar.text_input(
    "Search by phone",
    key="phone_search"
)

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
st.sidebar.markdown("### 🗂️ Filters")

region = st.sidebar.selectbox("Region", unique_clean(gdf["LREG_NEW"]))
gdf_r = gdf[gdf["LREG_NEW"] == region]

cercle = st.sidebar.selectbox("Cercle", unique_clean(gdf_r["LCER_NEW"]))
gdf_c = gdf_r[gdf_r["LCER_NEW"] == cercle]

commune = st.sidebar.selectbox("Commune", unique_clean(gdf_c["LCOM_NEW"]))
gdf_commune = gdf_c[gdf_c["LCOM_NEW"] == commune]

# =========================================================
# FILTER POINTS
# =========================================================
points_filtered = None
if gdf_points is not None:
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
map_data = None

m = folium.Map(location=[12.6, -8.0], zoom_start=6, tiles="OpenStreetMap")

# =========================
# SEARCH HIGHLIGHT + ZOOM
# =========================
if search_result is not None and not search_result.empty:

    pt = search_result.iloc[0].geometry
    lat, lon = pt.y, pt.x

    m.location = [lat, lon]
    m.zoom_start = 18

    folium.Marker(
        [lat, lon],
        icon=folium.DivIcon(html="""
        <div style="
            width:15px;height:15px;
            background:yellow;
            border-radius:50%;
            border:3px solid orange;
            animation:pulse 1.5s infinite;">
        </div>

        <style>
        @keyframes pulse {
          0% {transform: scale(0.7); opacity: 1;}
          70% {transform: scale(2.2); opacity: 0;}
          100% {transform: scale(0.7); opacity: 1;}
        }
        </style>
        """)
    ).add_to(m)

# =========================
# POINTS
# =========================
if points_filtered is not None:
    cluster = MarkerCluster().add_to(m)

    for _, r in points_filtered.iterrows():
        folium.CircleMarker(
            [r.geometry.y, r.geometry.x],
            radius=5,
            color="green",
            fill=True,
            fill_opacity=0.7
        ).add_to(cluster)

MeasureControl().add_to(m)
Draw(export=True).add_to(m)

map_data = st_folium(
    m,
    height=550,
    use_container_width=True,
    returned_objects=["last_clicked", "all_drawings"]
)

# =========================================================
# 🔥 SAFE AUTO RESET SEARCH (NO STREAMLIT ERROR)
# =========================================================
if map_data:
    if map_data.get("last_clicked") or map_data.get("all_drawings"):
        reset_search()
        phone_search = ""
        search_result = None

# =========================================================
# TABLE (ONLY ONE DISPLAYED)
# =========================================================

columns_to_show = [
    "LREG_NEW",
    "LCER_NEW",
    "LARR",
    "LCOM_NEW",
    "Prenom_du",
    "Nom_du_Che",
    "Forme_juri",
    "telephone",
    "Super"
]

def cols(df):
    return [c for c in columns_to_show if c in df.columns]

# =========================
# SEARCH TABLE (PRIORITY)
# =========================
if search_result is not None and not search_result.empty:

    st.markdown("## 🔎 Search Result")

    st.dataframe(search_result[cols(search_result)], use_container_width=True)
    st.metric("Matched points", len(search_result))

# =========================
# MAP SELECTION TABLE
# =========================
elif map_data and points_filtered is not None:

    selected = []
    pf = points_filtered.copy()

    clicked = map_data.get("last_clicked")

    if clicked:
        lat, lon = clicked["lat"], clicked["lng"]
        pf["dist"] = (pf.geometry.y - lat)**2 + (pf.geometry.x - lon)**2
        selected.append(pf.sort_values("dist").head(1))

    drawn = map_data.get("all_drawings")

    if drawn:
        from shapely.geometry import shape

        for obj in drawn:
            geom = obj.get("geometry")
            if geom and geom["type"] == "Polygon":
                poly = shape(geom)
                inside = pf[pf.geometry.within(poly)]
                selected.append(inside)

    if selected:

        final = pd.concat(selected).drop_duplicates()

        st.markdown("## 📊 Selected Points")

        st.dataframe(final[cols(final)], use_container_width=True)
        st.metric("Selected", len(final))


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
