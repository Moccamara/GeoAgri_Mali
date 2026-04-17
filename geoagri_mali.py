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
# LOAD EMOP SE POLYGONS
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

gdf = load_se_data()

# =========================================================
# LOAD POINTS
# =========================================================
@st.cache_data(show_spinner=False)
def load_points():
    pts = gpd.read_file("AGeoAgri_Mali_2026/data/Exploitation_Agri_ml3.geojson")

    if pts.crs is None:
        pts = pts.set_crs(epsg=4326)
    else:
        pts = pts.to_crs(epsg=4326)

    pts = pts[pts.is_valid & ~pts.is_empty]
    pts.columns = [c.strip() for c in pts.columns]  # 🔥 FIX
    return pts

gdf_points = load_points()

# =========================================================
# SAFE COLUMN DETECTOR
# =========================================================
def find_phone_column(gdf):
    possible = ["Num,ro_1", "Numero1", "Numero_1", "phone", "tel", "telephone"]
    for c in possible:
        if c in gdf.columns:
            return c
    return None

# =========================================================
# SEARCH SECTION
# =========================================================
# st.sidebar.markdown("### 🔎 Research Section")

# phone_search = st.sidebar.text_input("Search by phone")

# search_result = None
# phone_col = None

# if phone_search and gdf_points is not None:
#     phone_col = find_phone_column(gdf_points)

#     if phone_col:
#         search_result = gdf_points[
#             gdf_points[phone_col].astype(str).str.contains(str(phone_search), na=False)
#         ]
#     else:
#         st.sidebar.error("❌ Phone column not found")

# =========================================================
# ATTRIBUTE FILTERS
# =========================================================
st.sidebar.markdown("### 🗂️ Attribute Query")

def unique_clean(series):
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:,0]
    return sorted(series.dropna().astype(str).str.strip().unique())

all_regions = unique_clean(gdf["LREG_NEW"])
regions = all_regions if st.session_state.user_role=="Admin" else [r for r in all_regions if r in st.session_state.accessible_regions]

region = st.sidebar.selectbox("Region", regions)
gdf_r = gdf[gdf["LREG_NEW"] == region]

cercles = unique_clean(gdf_r["LCER_NEW"])
cercle = st.sidebar.selectbox("Cercle", cercles)
gdf_c = gdf_r[gdf_r["LCER_NEW"] == cercle]

communes = unique_clean(gdf_c["LCOM_NEW"])
commune = st.sidebar.selectbox("Commune", communes)
gdf_commune = gdf_c[gdf_c["LCOM_NEW"] == commune]

se_list = ["No filter"] + unique_clean(gdf_commune["num_se"])
se_selected = st.sidebar.selectbox("SE (num_se)", se_list)
gdf_se = gdf_commune if se_selected=="No filter" else gdf_commune[gdf_commune["num_se"]==se_selected]

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
map_data = None

if not gdf_se.empty:

    minx, miny, maxx, maxy = gdf_se.total_bounds

    m = folium.Map(location=[(miny+maxy)/2,(minx+maxx)/2], zoom_start=13, tiles=None)

    folium.TileLayer("OpenStreetMap").add_to(m)

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Satellite"
    ).add_to(m)

    # ===============================
    # 🔥 SEARCH HIGHLIGHT + PULSE
    # ===============================
    if search_result is not None and not search_result.empty:

        pt = search_result.iloc[0].geometry
        lat, lon = pt.y, pt.x

        # zoom to searched point
        m.location = [lat, lon]

        # pulse CSS
        pulse_css = """
        <style>
        .pulse {
          width: 20px;
          height: 20px;
          background: yellow;
          border-radius: 50%;
          animation: pulse 1.5s infinite;
          border: 2px solid orange;
        }
        @keyframes pulse {
          0% {transform: scale(0.5); opacity: 0.8;}
          70% {transform: scale(2); opacity: 0;}
          100% {transform: scale(0.5); opacity: 0;}
        }
        </style>
        """

        m.get_root().html.add_child(folium.Element(pulse_css))

        folium.Marker(
            [lat, lon],
            icon=folium.DivIcon(html="<div class='pulse'></div>")
        ).add_to(m)

    # ===============================
    # POLYGONS
    # ===============================
    se_group = folium.FeatureGroup(name="SE Polygons")
    folium.GeoJson(
        gdf_se,
        tooltip=folium.GeoJsonTooltip(fields=["num_se","pop_se"]),
        style_function=lambda x: {"color":"blue","weight":2,"fillOpacity":0.2}
    ).add_to(se_group)

    se_group.add_to(m)

    # ===============================
    # POINTS
    # ===============================
    if points_filtered is not None and not points_filtered.empty:

        cluster = MarkerCluster(name="Points Agricoles").add_to(m)

        for _, r in points_filtered.iterrows():
            folium.CircleMarker(
                [r.geometry.y, r.geometry.x],
                radius=5,
                color="#2E8B57",
                fill=True,
                fill_opacity=0.8
            ).add_to(cluster)

    MeasureControl().add_to(m)
    Draw(export=True).add_to(m)
    folium.LayerControl().add_to(m)

    m.fit_bounds([[miny,minx],[maxy,maxx]])

    map_data = st_folium(
        m,
        height=550,
        use_container_width=True,
        returned_objects=["last_clicked", "all_drawings"]
    )

# =========================================================
# TABLE — SWITCH MODE (SEARCH vs SELECTION)
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

def filter_cols(df):
    cols = [c for c in columns_to_show if c in df.columns]
    return df[cols] if not df.empty else df

# ===============================
# MODE 1: SEARCH (PRIORITY)
# ===============================
if phone_search and search_result is not None and not search_result.empty:

    st.markdown("## 🔎 Search Result")

    st.dataframe(
        filter_cols(search_result),
        use_container_width=True
    )

    st.metric("Matched points", len(search_result))

# ===============================
# MODE 2: MAP SELECTION (ONLY IF NO SEARCH)
# ===============================
elif map_data and points_filtered is not None and not points_filtered.empty:

    selected_points = []
    pf = points_filtered.copy()

    clicked = map_data.get("last_clicked")

    if clicked:
        lat = clicked["lat"]
        lon = clicked["lng"]

        pf["distance"] = (pf.geometry.y - lat)**2 + (pf.geometry.x - lon)**2
        selected_points.append(pf.sort_values("distance").head(1))

    drawn = map_data.get("all_drawings")

    if drawn:
        from shapely.geometry import shape

        for obj in drawn:
            geom = obj.get("geometry")
            if geom and geom["type"] == "Polygon":
                poly = shape(geom)
                inside = pf[pf.geometry.within(poly)]
                if not inside.empty:
                    selected_points.append(inside)

    if selected_points:

        final_selection = pd.concat(selected_points).drop_duplicates()

        st.markdown("## 📊 Map Selection Result")

        st.dataframe(
            filter_cols(final_selection),
            use_container_width=True
        )

        st.metric("Selected points", len(final_selection))

# ===============================
# NO RESULT
# ===============================
else:
    st.info("No selection or search performed yet")

# =========================================================
# SEARCH RESULTS
# =========================================================
if phone_search:

    st.markdown("## 🔎 Search Results")

    if search_result is not None and not search_result.empty:
        st.dataframe(search_result, use_container_width=True)
        st.metric("Matched points", len(search_result))
    else:
        st.warning("No point found")


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
