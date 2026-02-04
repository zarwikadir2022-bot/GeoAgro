import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import matplotlib.pyplot as plt
import numpy as np
from datetime import date, timedelta
from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox

# --- 1. Page Configuration & Custom CSS (Windows Modern Style) ---
st.set_page_config(page_title="AgriSight Pro", page_icon="🛰️", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; background-color: #0078d4; color: white; border: none; }
    .stButton>button:hover { background-color: #005a9e; border: none; }
    .css-1r6slb0 { border-radius: 15px; border: 1px solid #30363d; padding: 20px; }
    h1, h2, h3 { color: #ffffff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Authentication Helper ---
def get_config():
    try:
        config = SHConfig()
        config.sh_client_id = st.secrets["SH_CLIENT_ID"].strip()
        config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"].strip()
        return config
    except:
        st.error("🔑 API Keys missing in Secrets!")
        st.stop()

# --- 3. Satellite Data Engine ---
def fetch_ndvi(coords_list):
    config = get_config()
    lons, lats = [c[0] for c in coords_list], [c[1] for c in coords_list]
    roi_bbox = BBox(bbox=[min(lons), min(lats), max(lons), max(lats)], crs=CRS.WGS84)

    evalscript = """
    //VERSION=3
    function setup() {
        return { input: ["B04", "B08", "dataMask"], output: { bands: 1 } };
    }
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
    # Correcting potential scaling issues directly
    raw_data = request.get_data()[0]
    return raw_data / 100 if np.max(raw_data) > 1 else raw_data

# --- 4. Main Interface ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite-sending-signal.png")
    st.title("AgriSight Pro")
    st.markdown("---")
    st.info("Version 2.0 (Feb 2026)")
    st.write("Professional Satellite Monitoring for Precision Agriculture.")

# Layout: 2 Columns
col_map, col_dash = st.columns([1.5, 1])

with col_map:
    st.subheader("📍 Field Mapping")
    m = folium.Map(location=[36.7, 10.2], zoom_start=11, tiles="CartoDB dark_matter")
    Draw(export=False, position='topleft', 
         draw_options={'polyline':False,'circle':False,'marker':False,'polygon':True,'rectangle':True}).add_to(m)
    
    output = st_folium(m, width="100%", height=550)

with col_dash:
    st.subheader("📊 Analysis Dashboard")
    
    if output["all_drawings"]:
        st.success("Target area selected!")
        analyze_btn = st.button("RUN SATELLITE ANALYSIS")
        
        if analyze_btn:
            with st.spinner('Accessing Sentinel-2 Satellite...'):
                try:
                    coords = output["all_drawings"][-1]['geometry']['coordinates'][0]
                    ndvi_img = fetch_ndvi(coords)
                    
                    # Visualization
                    fig, ax = plt.subplots(figsize=(5, 5), facecolor='#0e1117')
                    im = ax.imshow(ndvi_img, cmap='RdYlGn', vmin=0, vmax=0.9)
                    ax.axis('off')
                    fig.patch.set_alpha(0) # Transparent background
                    st.pyplot(fig)
                    
                    # Metrics
                    avg_v = np.mean(ndvi_img[ndvi_img > 0])
                    c1, c2 = st.columns(2)
                    c1.metric("Avg NDVI", f"{avg_v:.2f}")
                    
                    status = "Healthy" if avg_v > 0.5 else "Stressed" if avg_v > 0.2 else "Bare Soil"
                    c2.metric("Health Status", status)
                    
                    st.progress(min(float(avg_v), 1.0))
                    
                    st.markdown("### 💡 AI Recommendation")
                    if avg_v > 0.5:
                        st.write("✅ Crop is thriving. Continue current irrigation schedule.")
                    else:
                        st.write("⚠️ Low vigor detected. Check for water stress or nutrient deficiency in the red zones.")

                except Exception as e:
                    st.error(f"Execution Error: {str(e)}")
    else:
        st.warning("Please use the drawing tools to select a farm on the map.")

st.markdown("---")
st.caption("© 2026 AgriSight Technologies Tunisia | Precision Agriculture Portal")
