import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw, MarkerCluster, HeatMap
import pandas as pd
import requests

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
        if username in USERS and password == USERS[username]["password"]:
            st.session_state.auth_ok = True
            st.session_state.username = username
            st.session_state.user_role = USERS[username]["role"]
            st.session_state.accessible_regions = USERS[username]["regions"]
            st.rerun()
        else:
            st.sidebar.error("❌ Invalid login")
    st.stop()

# =========================================================
# LOAD GEOJSON POLYGONS
# =========================================================
@st.cache_data
def load_polygons():
    url = "https://filebrowser.instat.ml/files/geoagri_mali/AGeoAgri_Mali/data/emop2026.geojson"

    response = requests.get(url)

    # 🔍 DEBUG (important)
    if response.status_code != 200:
        st.error(f"❌ Error loading file: {response.status_code}")
        return []

    # 🔥 CHECK CONTENT TYPE
    if "application/json" not in response.headers.get("Content-Type", ""):
        st.error("❌ The URL does not return GeoJSON (probably HTML page)")
        st.stop()

    try:
        data = response.json()
    except Exception as e:
        st.error("❌ Invalid JSON format (server is not returning GeoJSON)")
        st.stop()

    return data.get("features", [])

# =========================================================
# LOAD GEOJSON POINTS
# =========================================================
@st.cache_data
def load_points():
    url = "https://filebrowser.instat.ml/files/geoagri_mali/AGeoAgri_Mali/data/agri_ml_exploitation.geojson"
    data = requests.get(url).json()

    records = []
    for f in data["features"]:
        coords = f["geometry"]["coordinates"]
        props = f["properties"]

        records.append({
            "lat": coords[1],
            "lon": coords[0],
            "id": props.get("id"),
            "region": props.get("LREG_NEW"),
            "cercle": props.get("LCER_NEW"),
            "commune": props.get("LCOM_NEW"),
            "num_se": props.get("num_se")
        })

    return pd.DataFrame(records)

# =========================================================
# LOAD DATA
# =========================================================
features = load_polygons()
points_df = load_points()

# =========================================================
# FILTER DATA (POLYGONS → TABLE)
# =========================================================
records = []
for f in features:
    p = f["properties"]
    records.append({
        "feature": f,
        "region": p.get("LREG_NEW"),
        "cercle": p.get("LCER_NEW"),
        "commune": p.get("LCOM_NEW"),
        "num_se": p.get("num_se"),
        "pop_se": p.get("pop_se")
    })

df = pd.DataFrame(records)

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown(f"**User:** {st.session_state.username}")

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# =========================================================
# FILTERS
# =========================================================
regions = df["region"].dropna().unique()
regions = regions if st.session_state.user_role=="Admin" else [r for r in regions if r in st.session_state.accessible_regions]

region = st.sidebar.selectbox("Region", regions)
df_r = df[df["region"] == region]

cercle = st.sidebar.selectbox("Cercle", df_r["cercle"].dropna().unique())
df_c = df_r[df_r["cercle"] == cercle]

commune = st.sidebar.selectbox("Commune", df_c["commune"].dropna().unique())
df_commune = df_c[df_c["commune"] == commune]

se_list = ["No filter"] + list(df_commune["num_se"].dropna().unique())
se_selected = st.sidebar.selectbox("SE", se_list)

df_final = df_commune if se_selected=="No filter" else df_commune[df_commune["num_se"]==se_selected]

# =========================================================
# FILTER POINTS (ATTRIBUTE FILTER)
# =========================================================
points_filtered = points_df[
    (points_df["region"] == region) &
    (points_df["cercle"] == cercle) &
    (points_df["commune"] == commune)
]

# =========================================================
# MAP
# =========================================================
if not df_final.empty:

    m = folium.Map(location=[14.5, -4], zoom_start=6)

    folium.TileLayer("OpenStreetMap").add_to(m)

    # POLYGONS
    geojson_data = {
        "type": "FeatureCollection",
        "features": list(df_final["feature"])
    }

    folium.GeoJson(
        geojson_data,
        tooltip=folium.GeoJsonTooltip(fields=["num_se","pop_se"])
    ).add_to(m)

    # POINTS
    if not points_filtered.empty:

        cluster = MarkerCluster().add_to(m)

        for _, r in points_filtered.iterrows():
            folium.CircleMarker(
                location=[r["lat"], r["lon"]],
                radius=5,
                color="red",
                fill=True
            ).add_to(cluster)

        HeatMap(points_filtered[["lat","lon"]].values.tolist()).add_to(m)

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
