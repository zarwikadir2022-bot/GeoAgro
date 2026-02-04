import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import matplotlib.pyplot as plt
import numpy as np
from datetime import date, timedelta
from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox

# --- 1. Page Configuration & Professional UI Styling ---
st.set_page_config(page_title="AgriSight Pro | Satellite Monitoring", page_icon="🛰️", layout="wide")

# Custom CSS for Windows-like Modern UI (Dark Theme)
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { 
        background-color: #1e2130; 
        padding: 20px; 
        border-radius: 12px; 
        border: 1px solid #30363d;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .stButton>button { 
        width: 100%; 
        border-radius: 8px; 
        height: 3.5em; 
        background-color: #0078d4; 
        color: white; 
        font-weight: bold;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover { 
        background-color: #005a9e; 
        transform: translateY(-2px);
    }
    h1, h2, h3 { color: #ffffff; font-family: 'Segoe UI', sans-serif; }
    .report-box {
        background-color: #262730;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #0078d4;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Secure Configuration ---
def get_sh_config():
    try:
        config = SHConfig()
        config.sh_client_id = st.secrets["SH_CLIENT_ID"].strip()
        config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"].strip()
        return config
    except Exception:
        st.error("🔑 API Credentials missing! Please add SH_CLIENT_ID and SH_CLIENT_SECRET to Streamlit Secrets.")
        st.stop()

# --- 3. Satellite Data Processing Engine ---
def fetch_satellite_ndvi(coords_list):
    config = get_sh_config()
    
    # Calculate Bounding Box
    lons = [c[0] for c in coords_list]
    lats = [c[1] for c in coords_list]
    roi_bbox = BBox(bbox=[min(lons), min(lats), max(lons), max(lats)], crs=CRS.WGS84)

    # Professional Evalscript (NDVI Calculation)
    evalscript = """
    //VERSION=3
    function setup() {
        return {
            input: ["B04", "B08", "dataMask"],
            output: { bands: 1 }
        };
    }
    function evaluatePixel(sample) {
        let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
        return [sample.dataMask == 1 ? ndvi : 0];
    }
    """
    
    # Request definition using Dictionary for maximum compatibility
    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[{
            "dataFilter": {
                "timeRange": {
                    "from": (date.today() - timedelta(days=30)).isoformat() + "T00:00:00Z",
                    "to": date.today().isoformat() + "T23:59:59Z"
                },
                "maxCloudCoverage": 15
            },
            "type": "sentinel-2-l2a"
        }],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=roi_bbox,
        size=(512, 512),
        config=config
    )
    
    raw_img = request.get_data()[0]
    # Auto-scaling logic: Ensure NDVI is in 0.0 - 1.0 range
    return raw_img / 100 if np.max(raw_img) > 1.1 else raw_img

# --- 4. Application Layout ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite-sending-signal.png")
    st.title("AgriSight Pro")
    st.markdown("---")
    st.markdown("**Status:** Online 🟢")
    st.markdown("**Data Provider:** ESA Sentinel-2")
    st.markdown("---")
    st.caption("Developed by Consultant & Life Coach AI")

# Main Content Split
col_map, col_dash = st.columns([1.6, 1])

with col_map:
    st.subheader("🗺️ Field Selection (High-Res Satellite View)")
    
    # Clear Satellite Map (Esri World Imagery)
    m = folium.Map(
        location=[36.7, 10.2], 
        zoom_start=12, 
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri World Imagery'
    )
    
    # Add Drawing Tools
    draw_tools = Draw(
        export=False,
        position='topleft',
        draw_options={
            'polyline': False, 'circle': False, 'marker': False, 
            'circlemarker': False, 'polygon': True, 'rectangle': True
        }
    )
    draw_tools.add_to(m)
    
    # Render Map
    map_output = st_folium(m, width="100%", height=600)

with col_dash:
    st.subheader("📊 Analytics Dashboard")
    
    if map_output["all_drawings"]:
        st.success("Target area detected. Ready for analysis.")
        
        if st.button("RUN SATELLITE ANALYSIS"):
            with st.spinner('Synchronizing with Sentinel-2...'):
                try:
                    # Extract coordinates from the last drawing
                    raw_coords = map_output["all_drawings"][-1]['geometry']['coordinates'][0]
                    ndvi_data = fetch_satellite_ndvi(raw_coords)
                    
                    # Display NDVI Heatmap
                    st.markdown("#### Vegetation Health Map")
                    fig, ax = plt.subplots(figsize=(6, 6))
                    # RdYlGn: Red (Dry/Bare) -> Yellow -> Green (Healthy)
                    im = ax.imshow(ndvi_data, cmap='RdYlGn', vmin=0, vmax=0.9)
                    plt.colorbar(im, fraction=0.046, pad=0.04, label="NDVI Index")
                    ax.axis('off')
                    fig.patch.set_facecolor('#0e1117') # Match UI Background
                    st.pyplot(fig)
                    
                    # Core Metrics
                    avg_ndvi = np.mean(ndvi_data[ndvi_data > 0])
                    
                    m1, m2 = st.columns(2)
                    m1.metric("Average Health", f"{avg_ndvi:.2f}")
                    
                    health_status = "Excellent" if avg_ndvi > 0.5 else "Moderate" if avg_ndvi > 0.25 else "Poor/Bare"
                    m2.metric("Condition", health_status)
                    
                    # AI Insights Box
                    st.markdown("---")
                    st.markdown("#### 💡 Precision Insights")
                    with st.container():
                        st.markdown('<div class="report-box">', unsafe_allow_html=True)
                        if avg_ndvi > 0.5:
                            st.write("🟢 **Optimal Growth:** The crop shows high photosynthetic activity. Maintain current irrigation.")
                        elif avg_ndvi > 0.25:
                            st.write("🟡 **Mild Stress:** Potential water or nutrient deficiency detected in yellow/red zones.")
                        else:
                            st.write("🔴 **Critical Warning:** Bare soil or significant vegetation loss detected. Immediate field inspection required.")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                except Exception as e:
                    st.error(f"Analysis Failed: {str(e)}")
                    st.info("Check if your polygon is too large or if API keys are active.")
    else:
        st.warning("👈 Please use the polygon tool to select your farm on the map.")

st.markdown("---")
st.caption("© 2026 AgriSight Technologies Tunisia | Professional Edition")
