import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import matplotlib.pyplot as plt
import numpy as np
from datetime import date, timedelta
from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox

# --- 1. Page Configuration & Modern UI ---
st.set_page_config(page_title="AgriSight Pro", page_icon="🛰️", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 20px; border-radius: 12px; border: 1px solid #30363d; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #0078d4; color: white; font-weight: bold; border: none; }
    .stButton>button:hover { background-color: #005a9e; }
    h1, h2, h3 { color: #ffffff; font-family: 'Segoe UI', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Authentication ---
def get_sh_config():
    try:
        config = SHConfig()
        config.sh_client_id = st.secrets["SH_CLIENT_ID"].strip()
        config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"].strip()
        return config
    except:
        st.error("🔑 API Credentials missing in Secrets!")
        st.stop()

# --- 3. Analysis Engine ---
def fetch_satellite_ndvi(coords_list):
    config = get_sh_config()
    lons, lats = [c[0] for c in coords_list], [c[1] for c in coords_list]
    roi_bbox = BBox(bbox=[min(lons), min(lats), max(lons), max(lats)], crs=CRS.WGS84)

    evalscript = """
    //VERSION=3
    function setup() { return { input: ["B04", "B08", "dataMask"], output: { bands: 1 } }; }
    function evaluatePixel(sample) {
        let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
        return [sample.dataMask == 1 ? ndvi : 0];
    }
    """
    
    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[{
            "dataFilter": {
                "timeRange": {"from": (date.today()-timedelta(days=30)).isoformat()+"T00:00:00Z", 
                             "to": date.today().isoformat()+"T23:59:59Z"},
                "maxCloudCoverage": 15
            },
            "type": "sentinel-2-l2a"
        }],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=roi_bbox, size=(512, 512), config=config
    )
    
    raw_img = request.get_data()[0]
    return raw_img / 100 if np.max(raw_img) > 1.1 else raw_img

# --- 4. Layout ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite-sending-signal.png")
    st.title("AgriSight Pro")
    st.markdown("---")
    st.write("**Language:** English 🇺🇸")
    st.write("**Mode:** Standard + Satellite")

col_map, col_dash = st.columns([1.6, 1])

with col_map:
    st.subheader("🗺️ Interactive Field Selection")
    
    # 1. Create Base Map (Standard View)
    m = folium.Map(location=[36.7, 10.2], zoom_start=12)

    # 2. Add Satellite Layer (Hybrid/Clear View)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri World Imagery',
        name='Satellite View',
        control=True
    ).add_to(m)

    # 3. Add Layer Control (This creates the button to switch maps)
    folium.LayerControl(position='topright').add_to(m)
    
    # 4. Add Drawing Tools
    Draw(export=False, position='topleft', 
         draw_options={'polyline':False,'circle':False,'marker':False,'polygon':True,'rectangle':True}).add_to(m)
    
    map_output = st_folium(m, width="100%", height=600)

with col_dash:
    st.subheader("📊 Analytics Dashboard")
    
    if map_output["all_drawings"]:
        st.success("Area Selected! Ready to analyze.")
        if st.button("RUN ANALYSIS"):
            with st.spinner('Syncing with Sentinel-2...'):
                try:
                    raw_coords = map_output["all_drawings"][-1]['geometry']['coordinates'][0]
                    ndvi_data = fetch_satellite_ndvi(raw_coords)
                    
                    st.markdown("#### Crop Health Index")
                    fig, ax = plt.subplots(figsize=(6, 6))
                    im = ax.imshow(ndvi_data, cmap='RdYlGn', vmin=0, vmax=0.9)
                    plt.colorbar(im, label="NDVI Index")
                    ax.axis('off')
                    fig.patch.set_facecolor('#0e1117')
                    st.pyplot(fig)
                    
                    avg_ndvi = np.mean(ndvi_data[ndvi_data > 0])
                    st.metric("Average Health Score", f"{avg_ndvi:.2f}")
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    else:
        st.info("👈 Use the polygon tool on the map to select a farm. You can switch to Satellite view using the button in the top-right corner of the map.")

st.markdown("---")
st.caption("© 2026 AgriSight Technologies Tunisia")
