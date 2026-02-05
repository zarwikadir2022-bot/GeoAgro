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

# --- دالة لتصحيح الكتابة العربية في الرسوم البيانية ---
def fix_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

# --- 1. إعدادات الصفحة والتصميم ---
st.set_page_config(page_title="AgriSight Pro | المنظومة العربية", page_icon="🌾", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        direction: rtl;
        text-align: right;
        font-family: 'Tajawal', sans-serif;
    }
    
    .main { background-color: #0e1117; }
    
    /* تنسيق العناوين */
    h1, h2, h3, h4 { color: white; text-align: right; font-family: 'Tajawal', sans-serif; }
    
    /* تنسيق التبويبات */
    .stTabs [data-baseweb="tab-list"] { justify-content: flex-end; }
    
    /* تنسيق صندوق الطقس */
    .weather-card {
        background: linear-gradient(135deg, #0078d4 0%, #00b4d8 100%);
        border-radius: 10px;
        padding: 10px;
        color: white;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. دوال الاتصال (APIs) ---

def get_sh_config():
    try:
        config = SHConfig()
        # تأكد من وجود secrets.toml
        config.sh_client_id = st.secrets["SH_CLIENT_ID"].strip()
        config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"].strip()
        return config
    except:
        st.error("🔑 مفاتيح SentinelHub مفقودة! تأكد من ملف .streamlit/secrets.toml")
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

    # سكربت لجلب 3 مؤشرات: NDVI, NDWI, NDRE
    evalscript = """
    //VERSION=3
    function setup() {
        return {
            input: ["B03", "B04", "B05", "B08", "B11", "dataMask"],
            output: { bands: 3 }
        };
    }
    function evaluatePixel(sample) {
        let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04); // صحة
        let ndwi = (sample.B08 - sample.B11) / (sample.B08 + sample.B11); // مياه
        let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05); // كلوروفيل
        
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

# --- 3. واجهة المستخدم ---

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/drone-with-camera.png", width=60)
    st.title("AgriSight Pro")
    st.caption("المنظومة الذكية للفلاحة الدقيقة")
    st.markdown("---")
    st.info("👈 ارسم حدود الأرض على الخريطة للبدء")
    st.markdown("---")
    st.write("© 2026 Integrity Business Hub")

# تقسيم الشاشة
col_map, col_dash = st.columns([1.5, 1.2])

with col_map:
    st.subheader("📍 تحديد الضيعة")
    # الخريطة
    m = folium.Map(location=[36.8, 10.1], zoom_start=10)
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='قمر صناعي'
    ).add_to(m)
    
    folium.TileLayer('OpenStreetMap', name='خريطة طرقات').add_to(m)
    folium.LayerControl().add_to(m)
    
    # أدوات الرسم
    Draw(export=False, position='topleft', 
         draw_options={'polyline':False,'circle':False,'marker':False,'polygon':True,'rectangle':True}).add_to(m)
    
    map_output = st_folium(m, width="100%", height=600)

with col_dash:
    # التحقق من وجود رسم
    if map_output["all_drawings"]:
        polygon = map_output["all_drawings"][-1]['geometry']['coordinates'][0]
        centroid_lat = np.mean([p[1] for p in polygon])
        centroid_lon = np.mean([p[0] for p in polygon])
        
        # --- 1. الطقس ---
        weather = get_agri_weather(centroid_lat, centroid_lon)
        if weather:
            curr = weather['current']
            wind = curr['wind_speed_10m']
            temp = curr['temperature_2m']
            
            # منطق المداواة
            can_spray = wind < 15 and curr['rain'] == 0
            spray_msg = "✅ مناسب للرش" if can_spray else "❌ رياح قوية"
            spray_color = "#28a745" if can_spray else "#dc3545"

            st.markdown("#### 🌦️ الطقس الفلاحي")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("الحرارة", f"{temp}°C")
            c2.metric("الرياح", f"{wind} km/h")
            c3.metric("الرطوبة", f"{curr['relative_humidity_2m']}%")
            
            with c4:
                st.markdown(f"""
                <div style="background-color:{spray_color}; padding:5px; border-radius:5px; text-align:center; color:white;">
                    <small>المداواة</small><br><b>{spray_msg}</b>
                </div>
                """, unsafe_allow_html=True)
            
            if temp < 3:
                st.error("❄️ تحذير: خطر الجليدة (الصقيع)!")

        st.markdown("---")

        # --- 2. التحليل الفضائي ---
        if st.button("🚀 تحليل الأرض الآن", type="primary"):
            with st.spinner('جاري الاتصال بالقمر الصناعي Sentinel-2...'):
                try:
                    # جلب البيانات
                    raw_data = fetch_satellite_data(polygon)
                    ndvi_img = raw_data[:, :, 0]
                    ndwi_img = raw_data[:, :, 1]
                    
                    # إزالة الخلفية
                    mask = ndvi_img > -0.5
                    
                    # التبويبات
                    tab1, tab2, tab3 = st.tabs(["🌱 الصحة", "💧 المياه", "🚜 التسميد"])
                    
                    # تبويب الصحة (NDVI)
                    with tab1:
                        avg_ndvi = np.mean(ndvi_img[mask])
                        status = "ممتاز" if avg_ndvi > 0.6 else "متوسط"
                        st.metric("مؤشر الغطاء (NDVI)", f"{avg_ndvi:.2f}", delta=status)
                        
                        fig, ax = plt.subplots(figsize=(6,5))
                        im = ax.imshow(ndvi_img, cmap='RdYlGn', vmin=0, vmax=0.9)
                        plt.colorbar(im, label="NDVI")
                        ax.axis('off')
                        fig.patch.set_facecolor('#1e2130')
                        ax.set_title(fix_text("خريطة الكثافة النباتية"), color='white', fontsize=15)
                        st.pyplot(fig)

                    # تبويب المياه (NDWI)
                    with tab2:
                        avg_ndwi = np.mean(ndwi_img[mask])
                        w_status = "ري جيد" if avg_ndwi > 0.3 else "إجهاد مائي"
                        st.metric("مؤشر الرطوبة (NDWI)", f"{avg_ndwi:.2f}", delta=w_status)
                        
                        fig2, ax2 = plt.subplots(figsize=(6,5))
                        im2 = ax2.imshow(ndwi_img, cmap='Blues', vmin=-0.2, vmax=0.6)
                        plt.colorbar(im2, label="Moisture")
                        ax2.axis('off')
                        fig2.patch.set_facecolor('#1e2130')
                        ax2.set_title(fix_text("خريطة الرطوبة"), color='white', fontsize=15)
                        st.pyplot(fig2)

                    # تبويب التسميد (Zoning)
                    with tab3:
                        st.write("خرائط الجرعات المتغيرة (VRA)")
                        valid_pixels = ndvi_img[mask]
                        q1, q2 = np.percentile(valid_pixels, [33, 66])
                        
                        # إنشاء المناطق
                        zone_map = np.zeros_like(ndvi_img)
                        zone_map[mask] = 1 # ضعيف
                        zone_map[ndvi_img > q1] = 2 # متوسط
                        zone_map[ndvi_img > q2] = 3 # قوي
                        zone_map[~mask] = 0
                        
                        cmap_zones = mcolors.ListedColormap(['black', '#ff4d4d', '#ffcc00', '#28a745'])
                        norm = mcolors.BoundaryNorm([0, 1, 2, 3, 4], cmap_zones.N)
                        
                        fig3, ax3 = plt.subplots(figsize=(6,5))
                        im3 = ax3.imshow(zone_map, cmap=cmap_zones, norm=norm)
                        ax3.axis('off')
                        fig3.patch.set_facecolor('#1e2130')
                        
                        # مفتاح الخريطة بالعربي
                        import matplotlib.patches as mpatches
                        patches = [
                            mpatches.Patch(color='#28a745', label=fix_text('نطاق قوي (سماد أقل)')),
                            mpatches.Patch(color='#ffcc00', label=fix_text('نطاق متوسط')),
                            mpatches.Patch(color='#ff4d4d', label=fix_text('نطاق ضعيف (سماد أكثر)'))
                        ]
                        ax3.legend(handles=patches, loc='lower right', facecolor='white')
                        ax3.set_title(fix_text("خريطة توجيه التسميد"), color='white', fontsize=15)
                        st.pyplot(fig3)

                except Exception as e:
                    st.error(f"خطأ في التحليل: {e}")
    else:
        st.warning("⚠️ الرجاء رسم قطعة الأرض على الخريطة أولاً.")
