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

# --- مكتبات تصحيح اللغة العربية في الرسوم البيانية ---
import arabic_reshaper
from bidi.algorithm import get_display

def fix_text(text):
    """دالة لربط الحروف العربية وعكس اتجاهها لتظهر بشكل صحيح في Matplotlib"""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

# --- 1. إعدادات الصفحة والتصميم العربي ---
st.set_page_config(page_title="AgriSight Pro | المنظومة العربية", page_icon="🌾", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        direction: rtl;
        text-align: right;
        font-family: 'Tajawal', 'Segoe UI', sans-serif;
    }
    
    .main { background-color: #0e1117; }
    
    .metric-card {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
        border-right: 4px solid #0078d4;
        margin-bottom: 10px;
    }
    
    h1, h2, h3, h4 { font-family: 'Tajawal', sans-serif; color: white; text-align: right; }
    
    /* إصلاح محاذاة التبويبات */
    .stTabs [data-baseweb="tab-list"] { 
        justify-content: flex-end;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. الإعدادات ---
def get_sh_config():
    try:
        config = SHConfig()
        config.sh_client_id = st.secrets["SH_CLIENT_ID"].strip()
        config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"].strip()
        return config
    except:
        st.error("🔑 مفاتيح API مفقودة! الرجاء التأكد من إعدادات Streamlit.")
        st.stop()

def get_agri_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,rain,wind_speed_10m&hourly=temperature_2m,wind_speed_10m,rain&timezone=auto"
    try:
        response = requests.get(url).json()
        return response
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
                "timeRange": {"from": (date.today()-timedelta(days=20)).isoformat()+"T00:00:00Z", 
                             "to": date.today().isoformat()+"T23:59:59Z"},
                "maxCloudCoverage": 20
            },
            "type": "sentinel-2-l2a"
        }],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=roi_bbox, size=(512, 512), config=config
    )
    return request.get_data()[0]

# --- 3. الواجهة ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/drone-with-camera.png", width=60)
    st.title("AgriSight Pro")
    st.caption("المنظومة الذكية")
    st.markdown("---")
    st.write("إعدادات العرض:")
    st.info("قم برسم الأرض على الخريطة للبدء")

col_map, col_dash = st.columns([1.5, 1.2])

with col_map:
    st.subheader("📍 الخريطة التفاعلية")
    m = folium.Map(location=
