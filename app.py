import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import matplotlib.pyplot as plt
import numpy as np
from datetime import date, timedelta
from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox

# --- 1. Page Configuration & Ultra-Modern UI ---
st.set_page_config(page_title="AgriSight Pro", page_icon="🛰️", layout="wide")

# Custom CSS for Professional Dashboard Look
st.markdown("""
    <style>
    /* Main Background */
    .main { background-color: #0e1117; }
    
    /* Highlighted Metric Card - Light/Modern version */
    [data-testid="stMetric"] {
        background-color: #f0f2f6; /* Lighter background for better contrast */
        padding: 20px;
        border-radius: 15px;
        border: 2px solid #0078d4;
        box-shadow: 0 4px 15px rgba(0, 120, 212, 0.2);
    }
    
    /* Make the metric labels/values dark for contrast against light BG */
    [data-testid="stMetricValue"] { color: #0e1117 !important; font-weight: bold; }
    [data-testid="stMetricLabel"] { color: #31333F !important; }

    .stButton>button { 
        width: 100%; border-radius: 10px; height: 3.5em; 
        background-color: #0078d4; color: white; font-weight: bold; border: none; 
    }
    .stButton>button:hover { background-color: #005a9e; box-shadow: 0 4px 8px rgba(0,0,0,0.5); }
    
    h1, h2, h3 { color: #ffffff; font-family: 'Segoe UI', sans-serif; }
    
    /* Result Box Styling */
    .insight-card {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 12px;
        border-left: 6px solid #28a745;
        margin-top: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Configuration & Engine ---
def get_sh_config():
    try:
        config = SHConfig()
        config.sh_client_id = st.secrets["SH_CLIENT_ID"].strip()
        config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"].strip()
        return config
    except:
        st.error("🔑 API Credentials missing in Secrets!")
        st.stop()

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

# --- 3. Sidebar ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite-sending-signal.png")
    st.title("AgriSight Pro")
    st.markdown("---")
    st.write("Professional Vegetation Analysis")
    st.caption("Version 2.5 - Stable")

# --- 4. Main Layout ---
col_map, col_dash = st.columns([1.6, 1])

with col_map:
    st.subheader("🗺️ Select Your Farm")
    m = folium.Map(location=[36.7, 10.2], zoom_start=12)

    # Base Maps
    folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri World Imagery',
        name='Satellite Imagery',
    ).add_to(m)

    folium.LayerControl(position='topright').add_to(m)
    
    Draw(export=False, position='topleft', 
         draw_options={'polyline':False,'circle':False,'marker':False,'polygon':True,'rectangle':True}).add_to(m)
    
    map_output = st_folium(m, width="100%", height=600)

with col_dash:
    st.subheader("📊 Performance Metrics")
    
    if map_output["all_drawings"]:
        if st.button("EXECUTE ANALYSIS"):
            with st.spinner('Calculating Biomass Index...'):
                try:
                    raw_coords = map_output["all_drawings"][-1]['geometry']['coordinates'][0]
                    ndvi_data = fetch_satellite_ndvi(raw_coords)
                    
                    # 1. Visualization
                    st.markdown("#### Crop Vitality Heatmap")
                    fig, ax = plt.subplots(figsize=(6, 5))
                    im = ax.imshow(ndvi_data, cmap='RdYlGn', vmin=0, vmax=0.9)
                    plt.colorbar(im, label="NDVI Level")
                    ax.axis('off')
                    fig.patch.set_facecolor('#0e1117')
                    st.pyplot(fig)
                    
                    # 2. Key Metrics with Light Background Card
                    avg_ndvi = np.mean(ndvi_data[ndvi_data > 0])
                    st.markdown("---")
                    
                    # This section uses the CSS styled st.metric
                    st.metric(label="AVERAGE HEALTH SCORE", value=f"{avg_ndvi:.2f}")
                    
                    # 3. Insights Card
                    st.markdown(f"""
                        <div class="insight-card">
                            <h4 style="color:white; margin:0;">AI Insight</h4>
                            <p style="color:#d1d1d1;">
                                Score <b>{avg_ndvi:.2f}</b> indicates 
                                {"Excellent vegetation density." if avg_ndvi > 0.5 else "Moderate stress detected."}
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    else:
        st.info("👈 Please draw the farm boundaries on the map to begin analysis.")

st.markdown("---")
st.caption("© 2026 AgriSight Technologies | Precision Agriculture Solutions")
