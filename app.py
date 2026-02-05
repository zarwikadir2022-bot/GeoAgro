import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import requests
from datetime import date, timedelta
from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox
import arabic_reshaper
from bidi.algorithm import get_display

# --- دالة تصحيح النص العربي ---
def fix_text(text):
    if not text: return ""
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except:
        return text

# --- إعدادات الصفحة ---
st.set_page_config(page_title="AgriSight Pro", page_icon="🌾", layout="wide", initial_sidebar_state="collapsed")

# --- CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        direction: rtl;
        text-align: right;
        font-family: 'Tajawal', sans-serif;
    }
    
    .main { background-color: #0e1117; }
    
    /* إخفاء الشريط الجانبي */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    header { visibility: hidden !important; }
    
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }
    
    /* تعديل ارتفاع الخريطة في CSS أيضاً لتتوافق */
    iframe { width: 100% !important; min-height: 250px !important; border-radius: 12px; }
    
    .stButton button { width: 100%; border-radius: 8px; font-weight: bold; font-family: 'Tajawal'; }
    
    .stTabs [data-baseweb="tab-list"] { 
        justify-content: center;
        flex-wrap: wrap;
    }
    .stTabs [data-baseweb="tab"] {
        flex-grow: 1;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- دوال الاتصال ---
def get_sh_config():
    try:
        config = SHConfig()
        config.sh_client_id = st.secrets["SH_CLIENT_ID"].strip()
        config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"].strip()
        return config
    except:
        st.error("🔑 مفاتيح SentinelHub مفقودة!")
        st.stop()

def get_agri_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,rain,wind_speed_10m&hourly=temperature_2m,wind_speed_10m,rain&timezone=auto"
    try:
        return requests.get(url).json()
    except:
        return None

def fetch_satellite_data(coords_list):
    config = get_sh_config()
    lons, lats = [c[0] for c in coords_list], [c[1] for c in coords_list]
    roi_bbox = BBox(bbox=[min(lons), min(lats), max(lons), max(lats)], crs=CRS.WGS84)

    evalscript = """
    //VERSION=3
    function setup() {
        return {
            input: ["B03", "B04", "B05", "B08", "B11", "dataMask"],
            output: { bands: 3 }
        };
    }
    function evaluatePixel(sample) {
        let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
        let ndwi = (sample.B08 - sample.B11) / (sample.B08 + sample.B11);
        let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
        if (sample.dataMask == 1) { return [ndvi, ndwi, ndre]; } 
        else { return [-1, -1, -1]; }
    }
    """
    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[{
            "dataFilter": {
                "timeRange": {"from": (date.today()-timedelta(days=30)).isoformat()+"T00:00:00Z", 
                             "to": date.today().isoformat()+"T23:59:59Z"},
                "maxCloudCoverage": 20
            },
            "type": "sentinel-2-l2a"
        }],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=roi_bbox, size=(512, 512), config=config
    )
    return request.get_data()[0]

# --- رأس الصفحة ---
st.markdown("""
<div style="
    background: #1e2130; 
    padding: 10px; 
    border-radius: 12px; 
    margin-bottom: 10px; 
    display: flex; 
    align-items: center; 
    justify-content: flex-start; 
    gap: 15px; 
    border: 1px solid #333;
    direction: rtl;
">
    <img src="https://img.icons8.com/fluency/96/drone-with-camera.png" width="50" style="background: white; border-radius: 50%; padding: 4px; box-shadow: 0 0 10px rgba(0,0,0,0.3);">
    <div style="text-align: right;">
        <h2 style="margin: 0; color: white; font-size: 1.4rem; font-weight: 700; white-space: nowrap; font-family: 'Tajawal', sans-serif;">AgriSight Pro</h2>
        <div style="display: flex; align-items: center; gap: 5px;">
            <span style="height: 8px; width: 8px; background-color: #28a745; border-radius: 50%; display: inline-block; box-shadow: 0 0 5px #28a745;"></span>
            <span style="color: #a0a0a0; font-size: 0.8rem;">متصل بالأقمار الصناعية</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- الخريطة (تم تصغير الارتفاع) ---
m = folium.Map(location=[36.8, 10.1], zoom_start=10)
folium.TileLayer(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='قمر صناعي').add_to(m)
folium.TileLayer('OpenStreetMap', name='طرقات').add_to(m)
folium.LayerControl().add_to(m)
Draw(export=False, position='topleft', draw_options={'polyline':False,'circle':False,'marker':False,'polygon':True,'rectangle':True}).add_to(m)

st.caption("📍 حدد الأرض:")
# تم تقليل الارتفاع هنا إلى 250 بكسل
map_output = st_folium(m, width="100%", height=250)

# --- النتائج ---
if map_output and map_output.get("all_drawings"):
    drawings = map_output["all_drawings"]
    polygon = drawings[-1]['geometry']['coordinates'][0]
    centroid_lat = np.mean([p[1] for p in polygon])
    centroid_lon = np.mean([p[0] for p in polygon])
    
    st.markdown("---")
    
    weather = get_agri_weather(centroid_lat, centroid_lon)
    if weather:
        curr = weather['current']
        wind = curr['wind_speed_10m']
        temp = curr['temperature_2m']
        can_spray = wind < 15 and curr['rain'] == 0
        spray_msg = "ملائم" if can_spray else "خطر"
        spray_bg = "#28a745" if can_spray else "#dc3545"

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🌡️", f"{temp}°")
        c2.metric("💨", f"{wind}")
        c3.metric("💧", f"{curr['relative_humidity_2m']}%")
        c4.markdown(f'<div style="background:{spray_bg}; border-radius:8px; text-align:center; color:white; padding:5px; font-size:0.7rem;"><b>رش:<br>{spray_msg}</b></div>', unsafe_allow_html=True)

    st.write("")
    if st.button("🚀 تحليل الأرض الآن", type="primary"):
        with st.spinner('جاري المسح...'):
            try:
                raw_data = fetch_satellite_data(polygon)
                ndvi_img = raw_data[:, :, 0]
                ndwi_img = raw_data[:, :, 1]
                mask = ndvi_img > -0.5
                
                tab1, tab2, tab3 = st.tabs(["🌱 النمو", "💧 المياه", "🚜 التسميد"])
                
                with tab1:
                    avg_ndvi = np.mean(ndvi_img[mask])
                    st.metric("الغطاء النباتي (NDVI)", f"{avg_ndvi:.2f}")
                    fig, ax = plt.subplots(figsize=(6,3.5)) # تصغير الرسم البياني قليلاً أيضاً
                    im = ax.imshow(ndvi_img, cmap='RdYlGn', vmin=0, vmax=0.9)
                    plt.colorbar(im)
                    ax.axis('off')
                    fig.patch.set_facecolor('#1e2130')
                    ax.set_title(fix_text("خريطة الكثافة"), color='white')
                    st.pyplot(fig)

                with tab2:
                    avg_ndwi = np.mean(ndwi_img[mask])
                    st.metric("الرطوبة (NDWI)", f"{avg_ndwi:.2f}")
                    fig2, ax2 = plt.subplots(figsize=(6,3.5))
                    im2 = ax2.imshow(ndwi_img, cmap='Blues', vmin=-0.2, vmax=0.6)
                    plt.colorbar(im2)
                    ax2.axis('off')
                    fig2.patch.set_facecolor('#1e2130')
                    ax2.set_title(fix_text("خريطة المياه"), color='white')
                    st.pyplot(fig2)

                with tab3:
                    valid = ndvi_img[mask]
                    if len(valid) > 0:
                        q1, q2 = np.percentile(valid, [33, 66])
                        zones = np.zeros_like(ndvi_img)
                        zones[mask] = 1; zones[ndvi_img > q1] = 2; zones[ndvi_img > q2] = 3; zones[~mask]=0
                        cmap = mcolors.ListedColormap(['black', '#ff4d4d', '#ffcc00', '#28a745'])
                        norm = mcolors.BoundaryNorm([0,1,2,3,4], cmap.N)
                        fig3, ax3 = plt.subplots(figsize=(6,3.5))
                        im3 = ax3.imshow(zones, cmap=cmap, norm=norm)
                        ax3.axis('off')
                        fig3.patch.set_facecolor('#1e2130')
                        st.pyplot(fig3)
                        st.info("الأحمر: يحتاج تسميد.")

            except Exception as e:
                st.error(f"خطأ: {str(e)}")
else:
    st.info("👆 ارسم المضلع.")
