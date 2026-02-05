
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

# --- إعدادات الصفحة (وضع عريض) ---
st.set_page_config(page_title="AgriSight Pro", page_icon="🌾", layout="wide", initial_sidebar_state="collapsed")

# --- CSS: تصميم ملء الشاشة وإخفاء القوائم الزائدة ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    /* 1. إعدادات اللغة والخط */
    html, body, [class*="css"] {
        direction: rtl;
        text-align: right;
        font-family: 'Tajawal', sans-serif;
    }
    
    .main { background-color: #0e1117; }
    
    /* 2. إخفاء الشريط الجانبي والقائمة العلوية لزيادة المساحة */
    [data-testid="stSidebar"] { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    
    /* 3. تقليل الهوامش العلوية لرفع المحتوى لأعلى الشاشة */
    .block-container {
        padding-top: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* 4. تنسيق العنوان العلوي */
    .app-header {
        display: flex;
        align-items: center;
        gap: 15px;
        margin-bottom: 10px;
        background: #1e2130;
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #333;
    }
    
    /* 5. تحسين عرض الخريطة */
    iframe { width: 100% !important; min-height: 400px; border-radius: 10px; }
    
    /* 6. تنسيق الأزرار والنتائج */
    .stButton button { width: 100%; border-radius: 8px; font-weight: bold; }
    
    </style>
    """, unsafe_allow_html=True)

# --- دوال الاتصال (APIs) ---
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

# --- 1. رأس الصفحة (Header) بدلاً من الشريط الجانبي ---
c_logo, c_title = st.columns([0.2, 0.8])

with c_logo:
    st.image("https://img.icons8.com/fluency/96/drone-with-camera.png", width=60)

with c_title:
    # عنوان HTML مخصص يظهر بجانب الشعار
    st.markdown("""
    <div style="padding-top: 10px;">
        <h2 style="margin:0; padding:0; color:white; white-space:nowrap; font-size: 1.5rem;">AgriSight Pro</h2>
        <p style="margin:0; padding:0; color:#aaa; font-size: 0.8rem;">المنظومة الفلاحية الذكية</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# --- 2. الخريطة (تأخذ كامل العرض) ---
st.markdown("##### 📍 حدد الأرض على الخريطة:")
m = folium.Map(location=[36.8, 10.1], zoom_start=10)
folium.TileLayer(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='قمر صناعي').add_to(m)
folium.TileLayer('OpenStreetMap', name='طرقات').add_to(m)
folium.LayerControl().add_to(m)
Draw(export=False, position='topleft', draw_options={'polyline':False,'circle':False,'marker':False,'polygon':True,'rectangle':True}).add_to(m)

# عرض الخريطة بعرض كامل
map_output = st_folium(m, width="100%", height=400)

# --- 3. النتائج والتحليل (تظهر تحت الخريطة) ---
if map_output and map_output.get("all_drawings"):
    drawings = map_output["all_drawings"]
    polygon = drawings[-1]['geometry']['coordinates'][0]
    centroid_lat = np.mean([p[1] for p in polygon])
    centroid_lon = np.mean([p[0] for p in polygon])
    
    st.markdown("---")
    
    # أ) الطقس
    weather = get_agri_weather(centroid_lat, centroid_lon)
    if weather:
        curr = weather['current']
        wind = curr['wind_speed_10m']
        temp = curr['temperature_2m']
        can_spray = wind < 15 and curr['rain'] == 0
        spray_msg = "مناسب للرش" if can_spray else "رياح قوية"
        spray_bg = "#28a745" if can_spray else "#dc3545"

        st.markdown("#### 🌦️ الطقس")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🌡️ الحرارة", f"{temp}°")
        col2.metric("💨 الرياح", f"{wind}")
        col3.metric("💧 الرطوبة", f"{curr['relative_humidity_2m']}%")
        col4.markdown(f'<div style="background:{spray_bg};padding:10px;border-radius:5px;text-align:center;color:white;font-size:0.7rem;"><b>{spray_msg}</b></div>', unsafe_allow_html=True)

    # ب) زر التحليل
    st.write("") # مسافة
    if st.button("🚀 تحليل الأرض الآن", type="primary"):
        with st.spinner('جاري معالجة الصور الفضائية...'):
            try:
                raw_data = fetch_satellite_data(polygon)
                ndvi_img = raw_data[:, :, 0]
                ndwi_img = raw_data[:, :, 1]
                mask = ndvi_img > -0.5
                
                # التبويبات
                tab1, tab2, tab3, tab4 = st.tabs(["🌱 النمو", "💧 المياه", "🚜 التسميد", "📄 تقرير"])
                
                # 1. النمو
                with tab1:
                    avg_ndvi = np.mean(ndvi_img[mask])
                    st.metric("مؤشر الغطاء النباتي (NDVI)", f"{avg_ndvi:.2f}")
                    fig, ax = plt.subplots(figsize=(6,4))
                    im = ax.imshow(ndvi_img, cmap='RdYlGn', vmin=0, vmax=0.9)
                    plt.colorbar(im)
                    ax.axis('off')
                    fig.patch.set_facecolor('#1e2130')
                    ax.set_title(fix_text("خريطة الكثافة"), color='white')
                    st.pyplot(fig)
                    
                    st.caption("📈 تطور النمو (محاكاة):")
                    dates = pd.date_range(end=date.today(), periods=6, freq='M')
                    values = [avg_ndvi * (0.7 + 0.05*i) for i in range(6)]
                    st.line_chart(pd.DataFrame({"تاريخ": dates, "نمو": values}).set_index("تاريخ"), color="#28a745")

                # 2. المياه
                with tab2:
                    avg_ndwi = np.mean(ndwi_img[mask])
                    st.metric("مؤشر الرطوبة (NDWI)", f"{avg_ndwi:.2f}")
                    fig2, ax2 = plt.subplots(figsize=(6,4))
                    im2 = ax2.imshow(ndwi_img, cmap='Blues', vmin=-0.2, vmax=0.6)
                    plt.colorbar(im2)
                    ax2.axis('off')
                    fig2.patch.set_facecolor('#1e2130')
                    ax2.set_title(fix_text("خريطة المياه"), color='white')
                    st.pyplot(fig2)

                # 3. التسميد
                with tab3:
                    valid = ndvi_img[mask]
                    if len(valid) > 0:
                        q1, q2 = np.percentile(valid, [33, 66])
                        zones = np.zeros_like(ndvi_img)
                        zones[mask] = 1; zones[ndvi_img > q1] = 2; zones[ndvi_img > q2] = 3; zones[~mask]=0
                        
                        cmap = mcolors.ListedColormap(['black', '#ff4d4d', '#ffcc00', '#28a745'])
                        norm = mcolors.BoundaryNorm([0,1,2,3,4], cmap.N)
                        
                        fig3, ax3 = plt.subplots(figsize=(6,4))
                        im3 = ax3.imshow(zones, cmap=cmap, norm=norm)
                        ax3.axis('off')
                        fig3.patch.set_facecolor('#1e2130')
                        
                        import matplotlib.patches as mpatches
                        patches = [mpatches.Patch(color='#28a745', label=fix_text('قوي')),
                                  mpatches.Patch(color='#ffcc00', label=fix_text('متوسط')),
                                  mpatches.Patch(color='#ff4d4d', label=fix_text('ضعيف'))]
                        ax3.legend(handles=patches, loc='lower right', facecolor='white')
                        ax3.set_title(fix_text("خريطة التسميد"), color='white')
                        st.pyplot(fig3)

                # 4. التقرير
                with tab4:
                    report_html = f"""
                    <div dir="rtl" style="background:white; color:black; padding:15px; border-radius:10px;">
                        <h4 style="color:#0078d4; margin:0;">AgriSight Pro</h4>
                        <p style="color:gray; font-size:0.8rem;">{date.today()}</p>
                        <hr>
                        <b>النتائج:</b><br>
                        - الغطاء النباتي: {avg_ndvi:.2f}<br>
                        - الرطوبة: {avg_ndwi:.2f}<br>
                        <br>
                        <div style="background:#f0f2f6; padding:8px; font-size:0.9rem;">
                        <b>التوصية:</b> المنطقة الحمراء تحتاج تدخل عاجل.
                        </div>
                    </div>
                    """
                    st.components.v1.html(report_html, height=300, scrolling=True)

            except Exception as e:
                st.error(f"خطأ: {str(e)}")
else:
    st.info("👆 ارسم الأرض على الخريطة أعلاه لتبدأ.")
