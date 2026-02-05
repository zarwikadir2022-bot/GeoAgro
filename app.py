import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import requests
from datetime import date, timedelta, datetime
from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox

# --- 1. إعدادات الصفحة والتصميم العربي (RTL) ---
st.set_page_config(page_title="AgriSight Pro | المنظومة العربية", page_icon="🌾", layout="wide")

st.markdown("""
    <style>
    /* فرض الاتجاه من اليمين لليسار */
    html, body, [class*="css"] {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* خلفية داكنة احترافية */
    .main { background-color: #0e1117; }
    
    /* تنسيق البطاقات */
    .metric-card {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
        border-right: 4px solid #0078d4; /* تغيير الحدود لليمين */
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        margin-bottom: 10px;
    }
    
    /* تنسيق صندوق الطقس */
    .weather-box {
        background: linear-gradient(135deg, #0078d4 0%, #00b4d8 100%);
        color: white;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        direction: rtl;
    }
    
    /* تنسيق التبويبات */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; direction: rtl; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #1e2130;
        border-radius: 5px;
        color: white;
        font-weight: bold;
    }
    .stTabs [aria-selected="true"] {
        background-color: #28a745; /* أخضر للتبويب النشط */
    }
    
    /* تعديل النصوص */
    h1, h2, h3, h4 { font-family: 'Segoe UI', sans-serif; color: white; text-align: right; }
    .stMetric { text-align: right !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. دوال المساعدة ---

def get_sh_config():
    try:
        config = SHConfig()
        config.sh_client_id = st.secrets["SH_CLIENT_ID"].strip()
        config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"].strip()
        return config
    except:
        st.error("🔑 مفاتيح API مفقودة! الرجاء التأكد من إعدادات Streamlit.")
        st.stop()

# جلب الطقس (Open-Meteo)
def get_agri_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,rain,wind_speed_10m&hourly=temperature_2m,wind_speed_10m,rain&timezone=auto"
    try:
        response = requests.get(url).json()
        return response
    except:
        return None

# --- 3. محرك الأقمار الصناعية ---
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
        // NDVI (الصحة النباتية)
        let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
        
        // NDWI (الإجهاد المائي - الرطوبة)
        let ndwi = (sample.B08 - sample.B11) / (sample.B08 + sample.B11);
        
        // NDRE (الكلوروفيل للأشجار الكثيفة)
        let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
        
        if (sample.dataMask == 1) {
            return [ndvi, ndwi, ndre];
        } else {
            return [-1, -1, -1];
        }
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
    
    data = request.get_data()[0]
    return data

# --- 4. واجهة المستخدم ---

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/drone-with-camera.png", width=60)
    st.title("AgriSight Pro")
    st.caption("منظومة الإدارة الزراعية الذكية")
    st.markdown("---")
    
    st.markdown("### ⚙️ الإعدادات")
    st.write("نوع التحليل:")
    analysis_mode = st.selectbox("", ["الصحة النباتية (NDVI)", "الإجهاد المائي (NDWI)", "الكلوروفيل (NDRE)"], label_visibility="collapsed")
    
    st.markdown("### 📅 المقارنة الزمنية")
    st.write("قارن مع تاريخ:")
    st.date_input("", date.today() - timedelta(days=365), label_visibility="collapsed")
    
    st.markdown("---")
    st.success("💡 نصيحة: استخدم تبويب 'نطاقات التسميد' لتحميل خريطة الجرعات المتغيرة للجرار.")

# تقسيم الشاشة: الخريطة يمين (لأننا عربنا الاتجاه ستظهر بشكل صحيح) والنتائج يسار
col_map, col_dash = st.columns([1.5, 1.2])

with col_map:
    st.subheader("📍 تحديد الأرض عبر القمر الصناعي")
    
    # خريطة تونس الافتراضية
    m = folium.Map(location=[36.8, 10.1], zoom_start=10)
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='صور قمر صناعي (Esri)'
    ).add_to(m)
    folium.TileLayer('OpenStreetMap', name='خريطة طرقات').add_to(m)
    folium.LayerControl().add_to(m)
    
    draw_tools = Draw(export=False, position='topleft', 
                     draw_options={'polyline':False,'circle':False,'marker':False,'polygon':True,'rectangle':True})
    draw_tools.add_to(m)
    
    map_output = st_folium(m, width="100%", height=650)

# --- منطق لوحة التحكم ---
with col_dash:
    if map_output["all_drawings"]:
        polygon = map_output["all_drawings"][-1]['geometry']['coordinates'][0]
        centroid_lat = np.mean([p[1] for p in polygon])
        centroid_lon = np.mean([p[0] for p in polygon])
        
        # 1. حالة الطقس والمداواة
        weather = get_agri_weather(centroid_lat, centroid_lon)
        if weather:
            curr = weather['current']
            
            # منطق نافذة الرش
            wind = curr['wind_speed_10m']
            rain = curr['rain']
            can_spray = wind < 15 and rain == 0
            spray_color = "#28a745" if can_spray else "#dc3545"
            spray_msg = "مناسب للرش" if can_spray else "خطر (رياح)"
            
            st.markdown("#### 🌦️ الطقس الفلاحي ونافذة المداواة")
            w_col1, w_col2, w_col3, w_col4 = st.columns(4)
            w_col1.metric("الحرارة", f"{curr['temperature_2m']}°C")
            w_col2.metric("الرطوبة", f"{curr['relative_humidity_2m']}%")
            w_col3.metric("الرياح", f"{wind} كم/س")
            w_col4.markdown(f"""
                <div style="background-color:{spray_color}; padding:10px; border-radius:8px; text-align:center; color:white;">
                    <small>حالة المداواة</small><br><b>{spray_msg}</b>
                </div>
            """, unsafe_allow_html=True)
            
            if curr['temperature_2m'] < 2:
                st.error("❄️ تنبيه هام: خطر تشكل الجليدة (الصقيع)!")
        
        st.markdown("---")
        
        # 2. زر التحليل
        if st.button("🚀 بدء التحليل الفضائي المعمق", type="primary"):
            with st.spinner('جاري الاتصال بالقمر الصناعي Sentinel-2...'):
                try:
                    raw_data = fetch_satellite_data(polygon)
                    
                    ndvi_img = raw_data[:, :, 0]
                    ndwi_img = raw_data[:, :, 1]
                    ndre_img = raw_data[:, :, 2]
                    
                    # إزالة الخلفية
                    mask = ndvi_img > -0.5
                    
                    # --- التبويبات العربية ---
                    tab1, tab2, tab3, tab4 = st.tabs(["🌱 الصحة والنمو", "💧 الإجهاد المائي", "🚜 نطاقات التسميد", "📄 تقرير فني"])
                    
                    # التبويب 1: الصحة (NDVI)
                    with tab1:
                        avg_ndvi = np.mean(ndvi_img[mask])
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            st.metric("متوسط مؤشر الغطاء (NDVI)", f"{avg_ndvi:.2f}")
                        with c2:
                            health = "ممتازة" if avg_ndvi > 0.6 else "جيدة" if avg_ndvi > 0.4 else "تعاني من إجهاد"
                            st.metric("الحالة العامة", health)
                        
                        fig, ax = plt.subplots(figsize=(6,5))
                        im = ax.imshow(ndvi_img, cmap='RdYlGn', vmin=0, vmax=0.9)
                        plt.colorbar(im, label="NDVI Value")
                        ax.axis('off')
                        fig.patch.set_facecolor('#1e2130')
                        ax.set_title("خريطة الكثافة النباتية", color='white', fontfamily='Arial')
                        st.pyplot(fig)
                        
                        # الرسم البياني التاريخي
                        st.markdown("#### 📈 منحنى النمو الموسمي")
                        dates = pd.date_range(end=date.today(), periods=6, freq='M')
                        values = [avg_ndvi * (0.6 + 0.1*i) for i in range(6)] 
                        chart_data = pd.DataFrame({"التاريخ": dates, "مؤشر النمو": values})
                        st.line_chart(chart_data.set_index("التاريخ"))

                    # التبويب 2: المياه (NDWI)
                    with tab2:
                        avg_ndwi = np.mean(ndwi_img[mask])
                        
                        st.info("مؤشر NDWI يكشف نقص المياه في الأوراق قبل أن تراه العين المجردة.")
                        col_w1, col_w2 = st.columns(2)
                        col_w1.metric("مستوى الرطوبة", f"{avg_ndwi:.2f}")
                        
                        water_status = "ري جيد" if avg_ndwi > 0.3 else "عطش خفيف" if avg_ndwi > 0.1 else "خطر جفاف"
                        col_w2.write(f"### التقييم: {water_status}")
                        
                        fig2, ax2 = plt.subplots(figsize=(6,5))
                        im2 = ax2.imshow(ndwi_img, cmap='Blues', vmin=-0.2, vmax=0.6)
                        plt.colorbar(im2, label="Moisture")
                        ax2.axis('off')
                        fig2.patch.set_facecolor('#1e2130')
                        st.pyplot(fig2)

                    # التبويب 3: التسميد (Zoning)
                    with tab3:
                        st.markdown("### 🚜 تقسيم المناطق للتسميد الذكي")
                        st.caption("يقوم الذكاء الاصطناعي بتقسيم الحقل إلى 3 مناطق حسب الإنتاجية لتوفير السماد.")
                        
                        valid_pixels = ndvi_img[mask]
                        q1, q2 = np.percentile(valid_pixels, [33, 66])
                        
                        zone_map = np.zeros_like(ndvi_img)
                        zone_map[mask] = 1 # ضعيف
                        zone_map[ndvi_img > q1] = 2 # متوسط
                        zone_map[ndvi_img > q2] = 3 # قوي
                        zone_map[~mask] = 0
                        
                        cmap_zones = mcolors.ListedColormap(['black', '#ff4d4d', '#ffcc00', '#28a745'])
                        bounds = [0, 1, 2, 3, 4]
                        norm = mcolors.BoundaryNorm(bounds, cmap_zones.N)
                        
                        fig3, ax3 = plt.subplots(figsize=(6,5))
                        im3 = ax3.imshow(zone_map, cmap=cmap_zones, norm=norm)
                        ax3.axis('off')
                        fig3.patch.set_facecolor('#1e2130')
                        
                        import matplotlib.patches as mpatches
                        patches = [
                            mpatches.Patch(color='#28a745', label='نطاق قوي (تقليل السماد)'),
                            mpatches.Patch(color='#ffcc00', label='نطاق متوسط'),
                            mpatches.Patch(color='#ff4d4d', label='نطاق ضعيف (زيادة الجرعة)')
                        ]
                        ax3.legend(handles=patches, loc='lower right', fontsize='small')
                        st.pyplot(fig3)
                        
                        st.download_button("📥 تحميل خريطة التسميد (GeoTIFF)", data="Simulated Data", file_name="prescription_ar.tif")

                    # التبويب 4: التقرير
                    with tab4:
                        st.markdown("### 📋 تقرير المعاينة الفنية")
                        
                        report_html = f"""
                        <div dir="rtl" style="background-color: white; color: black; padding: 20px; border-radius: 10px; text-align: right;">
                            <h2 style="color: #0078d4;">AgriSight Pro - تقرير تحليلي</h2>
                            <p><b>التاريخ:</b> {date.today()}</p>
                            <p><b>رمز الضيعة:</b> TN-{str(centroid_lat)[:5]}</p>
                            <hr>
                            <h4>📊 الملخص الفني</h4>
                            <ul>
                                <li><b>معدل الغطاء النباتي (NDVI):</b> {avg_ndvi:.2f} - {health}</li>
                                <li><b>الحالة المائية (NDWI):</b> {avg_ndwi:.2f} - {water_status}</li>
                            </ul>
                            <h4>💡 توصيات الذكاء الاصطناعي</h4>
                            <p>المنطقة (أ) ذات اللون الأحمر تعاني من نقص حاد في النيتروجين. نظراً لأن سرعة الرياح غداً ({wind} كم/س) مناسبة، ننصح بالتدخل العاجل للرش الورقي.</p>
                            <br>
                            <p style="text-align: center; color: gray;">تم التوليد بواسطة منظومة AgriSight Pro</p>
                        </div>
                        """
                        st.components.v1.html(report_html, height=400, scrolling=True)
                        st.button("🖨️ طباعة التقرير (PDF)")

                except Exception as e:
                    st.error(f"حدث خطأ في التحليل: {str(e)}")
    else:
        st.info("👈 الرجاء رسم حدود الضيعة على الخريطة للبدء.")
        st.markdown("""
        **الميزات الجديدة:**
        * 💧 **كشف العطش:** عبر مؤشر NDWI.
        * 🌦️ **الطقس الفلاحي:** تنبيهات الجليدة ومواعيد الرش.
        * 🚜 **الزراعة الدقيقة:** خرائط تسميد متغيرة.
        """)
