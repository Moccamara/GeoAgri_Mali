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
st.title("🌱 GeoAgri Mali : Système d’Information Agricole du Mali (SIAM)")

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

# ✅ NEW: store map click selection
if "last_clicked" not in st.session_state:
    st.session_state.last_clicked = None

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

gdf = load_se_data()

@st.cache_data(show_spinner=False)
def load_points():
    pts = gpd.read_file("AGeoAgri_Mali_2026/data/Exploitation_Agri_ml3.geojson")

    if pts.crs is None:
        pts = pts.set_crs(epsg=4326)
    else:
        pts = pts.to_crs(epsg=4326)

    pts.columns = [c.strip() for c in pts.columns]
    return pts

gdf_points = load_points()

#....................................
@st.cache_data(show_spinner=False)
def load_regions():
    reg = gpd.read_file(
        "AGeoAgri_Mali_2026/data/Region_Mali.geojson"
    )

    if reg.crs is None:
        reg = reg.set_crs(epsg=4326)
    else:
        reg = reg.to_crs(epsg=4326)

    reg.columns = [c.strip() for c in reg.columns]

    return reg

gdf_regions = load_regions()

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
# SIDEBAR
# =========================================================

if "full_zoom" not in st.session_state:
    st.session_state.full_zoom = False

if "clear_all" not in st.session_state:
    st.session_state.clear_all = False


with st.sidebar:

    st.image(
        "AGeoAgri_Mali_2026/logo/logo_wgv.png",
        width=400
    )

    st.markdown(
        f"**User:** {st.session_state.username}"
    )
    # ---------------------------------
    # Reset all filters + searches
    # ---------------------------------
    if st.button("🚀 Clear ALL selections"):
        st.session_state.phone_search = ""
        st.session_state.last_clicked = None
        st.session_state.clear_all = True
        st.rerun()

    # ---------------------------------
    # Full national zoom only
    # ---------------------------------
    if st.button("🌍 Full Zoom Mali"):
        st.session_state.full_zoom = True
        st.rerun()
    if st.button("Logout"):
        logout()
st.sidebar.markdown(
    "### 🔎 Research Section"
)
# =========================================================
# SEARCH RESET
# =========================================================
if st.session_state.reset_search:
    st.session_state.phone_search = ""
    st.session_state.reset_search = False
phone_search = st.sidebar.text_input(
    "Search by phone",
    key="phone_search"
)
# =========================================================
# PHONE SEARCH
# =========================================================
search_result = None
search_region = None
search_cercle = None
search_commune = None
if phone_search and gdf_points is not None:
    phone_col = find_phone_column(gdf_points)
    if phone_col:
        search_result = gdf_points[
            gdf_points[phone_col].astype(str).str.contains(str(phone_search), na=False)
        ]
        # Auto detect region/cercle/commune
        if search_result is not None and not search_result.empty:
            search_region = search_result.iloc[0].get("LREG_NEW")
            search_cercle = search_result.iloc[0].get("LCER_NEW")
            search_commune = search_result.iloc[0].get("LCOM_NEW")

# =========================================================
# ATTRIBUTE FILTERS
# =========================================================
# def unique_clean(series):
#     if isinstance(series, pd.DataFrame):
#         series = series.iloc[:,0]
#     return sorted(series.dropna().astype(str).str.strip().unique())

# st.sidebar.markdown("### 🗂️ Attribute Query")

# all_regions = unique_clean(gdf["LREG_NEW"])
# regions = all_regions if st.session_state.user_role=="Admin" else [
#     r for r in all_regions if r in st.session_state.accessible_regions
# ]

# # AUTO REGION
# if search_region and search_region in regions:
#     region = search_region
# else:
#     region = st.sidebar.selectbox("Region", regions)

# gdf_r = gdf[gdf["LREG_NEW"] == region]

# # AUTO CERCLE
# cercles = unique_clean(gdf_r["LCER_NEW"])

# if search_cercle and search_cercle in cercles:
#     cercle = search_cercle
# else:
#     cercle = st.sidebar.selectbox("Cercle", cercles)

# gdf_c = gdf_r[gdf_r["LCER_NEW"] == cercle]

# # AUTO COMMUNE
# communes = unique_clean(gdf_c["LCOM_NEW"])

# if search_commune and search_commune in communes:
#     commune = search_commune
# else:
#     commune = st.sidebar.selectbox("Commune", communes)

# gdf_commune = gdf_c[gdf_c["LCOM_NEW"] == commune]

# # SE FILTER
# se_list = ["No filter"] + unique_clean(gdf_commune["num_se"])
# se_selected = st.sidebar.selectbox("SE (num_se)", se_list)

# gdf_se = gdf_commune if se_selected=="No filter" else gdf_commune[gdf_commune["num_se"]==se_selected]

# =========================================================
# REGION (SPATIAL FILTER ONLY)
# =========================================================

def unique(series):
    return sorted(series.dropna().astype(str).unique())

# -------------------------------
# REGION LIST (ONLY FOR SELECTION)
# -------------------------------
regions_list = unique(gdf_regions["LREG_NEW"])

if st.session_state.user_role != "Admin":
    regions_list = [
        r for r in regions_list
        if r in st.session_state.accessible_regions
    ]

if search_region and search_region in regions_list:
    region = search_region
else:
    region = st.sidebar.selectbox("Region", regions_list)

# -------------------------------
# REGION GEOMETRY FILTER
# -------------------------------
region_geom = gdf_regions[gdf_regions["LREG_NEW"] == region]

# =========================================================
# APPLY REGION FILTER TO SE DATA (NOT ATTRIBUTE SOURCE)
# =========================================================
gdf_region_se = gpd.sjoin(
    gdf,
    region_geom[["geometry"]],
    how="inner",
    predicate="within"
).drop(columns=["index_right"], errors="ignore")

# =========================================================
# ATTRIBUTE FILTERS (BASED ON SE DATA)
# =========================================================

# -------------------------------
# CERCL
# -------------------------------
cercles = unique(gdf_region_se["LCER_NEW"])

if search_cercle and search_cercle in cercles:
    cercle = search_cercle
else:
    cercle = st.sidebar.selectbox("Cercle", cercles)

gdf_c = gdf_region_se[gdf_region_se["LCER_NEW"] == cercle]

# -------------------------------
# COMMUNE
# -------------------------------
communes = unique(gdf_c["LCOM_NEW"])

if search_commune and search_commune in communes:
    commune = search_commune
else:
    commune = st.sidebar.selectbox("Commune", communes)

gdf_commune = gdf_c[gdf_c["LCOM_NEW"] == commune]

# -------------------------------
# SE FILTER
# -------------------------------
se_list = ["No filter"] + unique(gdf_commune["num_se"])

se_selected = st.sidebar.selectbox("SE (num_se)", se_list)

gdf_se = (
    gdf_commune
    if se_selected == "No filter"
    else gdf_commune[gdf_commune["num_se"] == se_selected]
)

# =========================================================
# FILTER POINTS
# =========================================================
points_filtered = None

# If search → show only searched points
if search_result is not None and not search_result.empty:
    points_filtered = search_result

# Otherwise normal filtering
elif gdf_points is not None and not gdf_commune.empty:

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
# -----------------------------------------------
# FULL COUNTRY VIEW (button triggered)
# -----------------------------------------------
if st.session_state.full_zoom:

    minx, miny, maxx, maxy = gdf_regions.total_bounds

    m = folium.Map(
        location=[17.5, -4],
        zoom_start=5,
        tiles=None
    )
# -----------------------------------------------
# Default country view (before filters)
# -----------------------------------------------
elif search_result is None and se_selected=="No filter":
    minx, miny, maxx, maxy = gdf_regions.total_bounds
    m = folium.Map(
        location=[17.5, -4],
        zoom_start=5,
        tiles=None
    )
# -----------------------------------------------
# Filtered zoom
# -----------------------------------------------
else:
    minx, miny, maxx, maxy = gdf_se.total_bounds

    m = folium.Map(
        location=[
            (miny+maxy)/2,
            (minx+maxx)/2
        ],
        zoom_start=12,
        tiles=None
    )
# -------------------------------
# Basemaps
# -------------------------------
folium.TileLayer(
    "OpenStreetMap",
    name="OpenStreetMap"
).add_to(m)

folium.TileLayer(
    tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    attr="Google",
    name="Google Satellite"
).add_to(m)

# =====================================================
# NATIONAL REGIONS LAYER
# =====================================================
folium.GeoJson(
    gdf_regions,
    name="Régions du Mali",
    tooltip=folium.GeoJsonTooltip(
        fields=["LREG_NEW"],
        aliases=["Région :"]
    ),
    style_function=lambda x:{
        "color":"#444444",
        "weight":2,
        "fillColor":"#90EE90",
        "fillOpacity":0.15
    }
).add_to(m)

# =====================================================
# SE LAYER (only after filters)
# =====================================================
if not gdf_se.empty:

    folium.GeoJson(
        gdf_se,
        name="Limite SE",
        tooltip=folium.GeoJsonTooltip(
            fields=["num_se","pop_se"]
        ),
        style_function=lambda x:{
            "color":"blue",
            "weight":2,
            "fillOpacity":0.20
        }
    ).add_to(m)

# =====================================================
# SEARCH HIGHLIGHT
# =====================================================
if search_result is not None and not search_result.empty:

    pt = search_result.iloc[0].geometry
    lat,lon = pt.y,pt.x

    m.location=[lat,lon]

    pulse_css="""
    <style>
    .pulse{
      width:20px;
      height:20px;
      background:yellow;
      border-radius:50%;
      animation:pulse 1.5s infinite;
      border:2px solid orange;
    }
    @keyframes pulse{
      0%{transform:scale(.5);opacity:.8;}
      70%{transform:scale(2);opacity:0;}
      100%{transform:scale(.5);opacity:.8;}
    }
    </style>
    """

    m.get_root().html.add_child(
        folium.Element(pulse_css)
    )

    folium.Marker(
        [lat,lon],
        icon=folium.DivIcon(
            html="<div class='pulse'></div>"
        )
    ).add_to(m)

# =====================================================
# POINTS
# =====================================================
if points_filtered is not None and not points_filtered.empty:

    cluster=MarkerCluster(
        name="Points des Exploitations"
    ).add_to(m)

    for _,r in points_filtered.iterrows():

        folium.CircleMarker(
            [r.geometry.y,r.geometry.x],
            radius=5,
            color="#FF0000",
            fill=True,
            fill_opacity=0.8
        ).add_to(cluster)

MeasureControl().add_to(m)
Draw(export=True).add_to(m)

folium.LayerControl(
    collapsed=False
).add_to(m)

map_data = st_folium(
    m,
    height=600,
    use_container_width=True,
    returned_objects=[
        "last_clicked",
        "all_drawings"
    ]
)
# reset after zooming
st.session_state.full_zoom = False

# if map_data and map_data.get("last_clicked"):
#     st.session_state.last_clicked=map_data["last_clicked"]

# =========================================================
# TABLE LOGIC (ONLY ONE TABLE)
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
selected_df = None

if map_data and points_filtered is not None:

    selected_points = []
    pf = points_filtered.copy()

    # -------------------------------
    # Click selection
    # -------------------------------
    clicked = map_data.get("last_clicked")

    if clicked:
        lat = clicked["lat"]
        lon = clicked["lng"]

        pf["distance"] = (
            (pf.geometry.y - lat)**2 +
            (pf.geometry.x - lon)**2
        )

        selected_points.append(
            pf.sort_values("distance").head(1)
        )

    # -------------------------------
    # Polygon draw selection
    # -------------------------------
    drawn = map_data.get("all_drawings")

    if drawn:
        from shapely.geometry import shape

        for obj in drawn:
            geom = obj.get("geometry")

            if geom and geom["type"] == "Polygon":

                poly = shape(geom)

                inside = pf[
                    pf.geometry.within(poly)
                ]

                if not inside.empty:
                    selected_points.append(inside)

    # Merge selections
    if selected_points:
        selected_df = (
            pd.concat(selected_points)
            .drop_duplicates()
        )

# Fallback from phone search
if selected_df is None and search_result is not None:
    selected_df = search_result

# =========================================================
# DISPLAY TABLE
# =========================================================
if selected_df is not None:

    cols = [
        c for c in columns_to_show
        if c in selected_df.columns
    ]

    display_df = selected_df[cols].rename(columns={
        "LREG_NEW":"Région",
        "LCER_NEW":"Cercle",
        "LARR":"Arrondissement",
        "LCOM_NEW":"Commune",
        "Prenom_du":"Prénom",
        "Nom_du_Che":"Nom du Chef",
        "Forme_juri":"Forme Juridique",
        "telephone":"Téléphone",
        "Super":"Superficie (m²)"
    })

    st.markdown("## 📊 Exploitations sélectionnées")

    st.dataframe(
        display_df,
        use_container_width=True
    )


#..............................
map_data = st_folium(
    m,
    height=600,
    use_container_width=True,
    returned_objects=[
        "last_clicked",
        "all_drawings"
    ]
)
    # =====================================================
# FULL ZOOM BUTTON
# =====================================================

minx, miny, maxx, maxy = gdf_regions.total_bounds

zoom_button = f"""
<script>
function zoomMali(){{
    map.fitBounds(
        [
            [{miny},{minx}],
            [{maxy},{maxx}]
        ]
    );
}}
</script>

<style>
.zoom-button {{
position:absolute;
top:10px;
right:10px;
z-index:9999;
background:white;
padding:8px 12px;
border-radius:6px;
border:1px solid gray;
font-weight:bold;
cursor:pointer;
box-shadow:2px 2px 5px rgba(0,0,0,.3);
}}
</style>

<div class="zoom-button"
onclick="zoomMali()">
🌍 Full Zoom
</div>
"""

m.get_root().html.add_child(
    folium.Element(zoom_button)
)

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
