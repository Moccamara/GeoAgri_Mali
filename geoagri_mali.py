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

if "phone_search" not in st.session_state:
    st.session_state.phone_search = ""

if "reset_search" not in st.session_state:
    st.session_state.reset_search = False

# ✅ FIX: global clear system
if "clear_all" not in st.session_state:
    st.session_state.clear_all = False


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
# SAFE PHONE COLUMN DETECTOR
# =========================================================
def find_phone_column(gdf):
    possible = ["Num,ro_1", "Numero1", "Numero_1", "phone", "tel", "telephone"]
    for c in possible:
        if c in gdf.columns:
            return c
    return None


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.image("AGeoAgri_Mali_2026/logo/logo_wgv.png", width=400)
    st.markdown(f"**User:** {st.session_state.username}")
    
    if st.button("🚀 Clear ALL selections"):
        st.session_state.phone_search = ""
        st.session_state.reset_search = True
        st.session_state.clear_all = True

    if st.button("Logout"):
        logout()

st.sidebar.markdown("### 🔎 Research Section")


# =========================================================
# SAFE RESET SYSTEM
# =========================================================
if st.session_state.clear_all:
    st.session_state.phone_search = ""
    st.session_state.clear_all = False


if st.session_state.reset_search:
    st.session_state.phone_search = ""
    st.session_state.reset_search = False


# =========================================================
# PHONE SEARCH (ONLY ONCE — FIXED)
# =========================================================
phone_search = st.session_state.get("phone_search", "")

search_result = None

if phone_search and gdf_points is not None:
    phone_col = find_phone_column(gdf_points)

    if phone_col:
        search_result = gdf_points[
            gdf_points[phone_col].astype(str).str.contains(
                str(phone_search),
                na=False
            )
        ]


# =========================================================
# ATTRIBUTE FILTERS
# =========================================================
def unique_clean(series):
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:,0]
    return sorted(series.dropna().astype(str).str.strip().unique())


all_regions = unique_clean(gdf["LREG_NEW"])
regions = all_regions if st.session_state.user_role=="Admin" else all_regions

region = st.sidebar.selectbox("Region", regions)
gdf_r = gdf[gdf["LREG_NEW"] == region]

cercle = st.sidebar.selectbox("Cercle", unique_clean(gdf_r["LCER_NEW"]))
gdf_c = gdf_r[gdf_r["LCER_NEW"] == cercle]

commune = st.sidebar.selectbox("Commune", unique_clean(gdf_c["LCOM_NEW"]))
gdf_commune = gdf_c[gdf_c["LCOM_NEW"] == commune]


# =========================================================
# POINT FILTERS
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
map_data = None

if not gdf_commune.empty:

    minx, miny, maxx, maxy = gdf_commune.total_bounds

    m = folium.Map(location=[(miny+maxy)/2,(minx+maxx)/2], zoom_start=13)

    folium.TileLayer("OpenStreetMap").add_to(m)

    folium.GeoJson(gdf_commune).add_to(m)

    cluster = MarkerCluster().add_to(m)

    if points_filtered is not None:
        for _, r in points_filtered.iterrows():
            folium.CircleMarker(
                [r.geometry.y, r.geometry.x],
                radius=4,
                color="green",
                fill=True
            ).add_to(cluster)

    MeasureControl().add_to(m)
    Draw(export=True).add_to(m)
    folium.LayerControl().add_to(m)

    m.fit_bounds([[miny,minx],[maxy,maxx]])


    # =====================================================
    # 🔥 PHONE HIGHLIGHT (FIXED + INSIDE MAP)
    # =====================================================
    if search_result is not None and not search_result.empty:

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
            0% {transform: scale(0.5); opacity:1;}
            70% {transform: scale(2); opacity:0.3;}
            100% {transform: scale(3); opacity:0;}
        }
        </style>
        """

        m.get_root().html.add_child(folium.Element(pulse_css))

        folium.Marker(
            [lat, lon],
            icon=folium.DivIcon(html="<div class='pulse'></div>")
        ).add_to(m)


    map_data = st_folium(
        m,
        height=550,
        use_container_width=True,
        returned_objects=["last_clicked"]
    )


# =========================================================
# RESET ON MAP CLICK
# =========================================================
if map_data and map_data.get("last_clicked"):
    st.session_state.phone_search = ""
    st.session_state.reset_search = True


# =========================================================
# TABLE OUTPUT
# =========================================================
selected_df = search_result if search_result is not None else points_filtered

if selected_df is not None:
    st.markdown("## 📊 Result Table")
    st.dataframe(selected_df, use_container_width=True)



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
