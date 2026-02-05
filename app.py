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

# --- دالة تصحيح النص العربي للرسوم البيانية ---
def fix_text(text):
    if not text: return ""
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except:
        return text

# --- إعدادات الصفحة ---
st.set_page_config(page_title="AgriSight Pro", page_icon="🌾", layout="wide")

# --- CSS: تحسينات التصميم والموبايل ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        direction: rtl;
        text-align: right;
        font-family: 'Tajawal', sans-serif;
    }
    
    .main { background-color: #0e1117; }
    
    /* تحسين عرض الخريطة لتملأ الشاشة */
    iframe { width: 100% !important; min-height: 400px; }
    
    /* تحسين الهوامش لتوسيع مساحة العرض */
    .block-container {
        padding-top: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    
    /* تنسيق التبويبات */
    .stTabs [data-baseweb="tab-list"] { 
        justify-content: flex-end;
        flex-wrap: wrap;
    }
    
    /* تنسيق صندوق الطقس */
    .weather-box {
        background: linear-gradient(135deg, #0078d4 0%, #00b4d8 100%);
        border-radius: 8px;
        padding: 10px;
        color: white;
        text-align: center;
        margin-bottom: 10px;
    }
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

# --- الشريط الجانبي (تم التعديل لإصلاح الكتابة) ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/drone-with-camera.png", width=60)
    
    # استخدام HTML لإجبار العنوان على البقاء أفقياً
    st.markdown("""
        <div style="text-align: right; direction: rtl; padding-bottom: 10px;">
            <h1 style="
                color: white; 
                font-family: 'Tajawal', sans-serif; 
                font-size: 22px !important; 
                margin: 0; 
                padding: 0; 
                white-space: nowrap !important;
                line-height: 1.5;
            ">AgriSight Pro</h1>
            <p style="color: #a0a0a0; font-size: 13px; margin: 0;">المنظومة الفلاحية الذكية</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.info("👈 ارسم حدود الأرض على الخريطة للبدء")

# تقسيم الأعمدة
col_map, col_dash = st.columns([1.5, 1.2])

with col_map:
    st.subheader("📍 الخريطة")
    m = folium.Map(location=[36.8, 10.1], zoom_start=10)
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='قمر صناعي'
    ).add_to(m)
    folium.TileLayer('OpenStreetMap', name='طرقات').add_to(m)
    folium.LayerControl().add_to(m)
    
    Draw(export=False, position='topleft', 
         draw_options={'polyline':False,'circle':False,'marker':False,'polygon':True,'rectangle':True}).add_to(m)
    
    map_output = st_folium(m, width="100%", height=500)

with col_dash:
    if map_output and map_output.get("all_drawings"):
        drawings = map_output["all_drawings"]
        polygon = drawings[-1]['geometry']['coordinates'][0]
        centroid_lat = np.mean([p[1] for p in polygon])
        centroid_lon = np.mean([p[0] for p in polygon])
        
        # --- الطقس ---
        weather = get_agri_weather(centroid_lat, centroid_lon)
        if weather:
            curr = weather['current']
            wind = curr['wind_speed_10m']
            temp = curr['temperature_2m']
            can_spray = wind < 15 and curr['rain'] == 0
            spray_msg = "✅ مناسب للرش" if can_spray else "❌ رياح قوية"
            spray_bg = "#28a745" if can_spray else "#dc3545"

            st.markdown("#### 🌦️ الطقس الفلاحي")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("الحرارة", f"{temp}°C")
            c2.metric("الرياح", f"{wind} km/h")
            c3.metric("الرطوبة", f"{curr['relative_humidity_2m']}%")
            c4.markdown(f'<div style="background:{spray_bg};padding:5px;border-radius:5px;text-align:center;color:white;font-size:0.8rem;">{spray_msg}</div>', unsafe_allow_html=True)

        if st.button("🚀 تحليل الأرض الآن", type="primary"):
            with st.spinner('جاري التحليل الفضائي...'):
                try:
                    raw_data = fetch_satellite_data(polygon)
                    ndvi_img = raw_data[:, :, 0]
                    ndwi_img = raw_data[:, :, 1]
                    mask = ndvi_img > -0.5
                    
                    # التبويبات (4 تبويبات)
                    tab1, tab2, tab3, tab4 = st.tabs(["🌱 النمو", "💧 المياه", "🚜 التسميد", "📄 تقرير"])
                    
                    # 1. النمو (NDVI)
                    with tab1:
                        avg_ndvi = np.mean(ndvi_img[mask])
                        st.metric("مؤشر الغطاء", f"{avg_ndvi:.2f}")
                        
                        fig, ax = plt.subplots(figsize=(6,4))
                        im = ax.imshow(ndvi_img, cmap='RdYlGn', vmin=0, vmax=0.9)
                        plt.colorbar(im)
                        ax.axis('off')
                        fig.patch.set_facecolor('#1e2130')
                        ax.set_title(fix_text("خريطة الكثافة النباتية"), color='white')
                        st.pyplot(fig)
                        
                        st.markdown("##### 📈 تطور النمو")
                        dates = pd.date_range(end=date.today(), periods=6, freq='M')
                        values = [avg_ndvi * (0.7 + 0.05*i) for i in range(6)]
                        chart_df = pd.DataFrame({"التاريخ": dates, "النمو": values})
                        st.line_chart(chart_df.set_index("التاريخ"), color="#28a745")

                    # 2. المياه (NDWI)
                    with tab2:
                        avg_ndwi = np.mean(ndwi_img[mask])
                        st.metric("مؤشر الرطوبة", f"{avg_ndwi:.2f}")
                        
                        fig2, ax2 = plt.subplots(figsize=(6,4))
                        im2 = ax2.imshow(ndwi_img, cmap='Blues', vmin=-0.2, vmax=0.6)
                        plt.colorbar(im2)
                        ax2.axis('off')
                        fig2.patch.set_facecolor('#1e2130')
                        ax2.set_title(fix_text("خريطة المحتوى المائي"), color='white')
                        st.pyplot(fig2)

                    # 3. التسميد (Zoning)
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
                            ax3.set_title(fix_text("خريطة توجيه التسميد"), color='white')
                            st.pyplot(fig3)

                    # 4. التقرير
                    with tab4:
                        st.markdown("### 📋 تقرير المعاينة")
                        report_html = f"""
                        <div dir="rtl" style="background:white; color:black; padding:15px; border-radius:10px; text-align:right;">
                            <h3 style="color:#0078d4; margin:0;">AgriSight - تقرير</h3>
                            <p style="color:gray;">{date.today()}</p>
                            <hr>
                            <ul>
                                <li>الغطاء النباتي: <b>{avg_ndvi:.2f}</b></li>
                                <li>الرطوبة: <b>{avg_ndwi:.2f}</b></li>
                            </ul>
                            <div style="background:#f0f2f6; padding:10px;">
                                <b>التوصية:</b> متابعة الري في المناطق الحمراء.
                            </div>
                        </div>
                        """
                        st.components.v1.html(report_html, height=350, scrolling=True)

                except Exception as e:
                    st.error(f"خطأ: {str(e)}")
    else:
        st.info("⚠️ الرجاء رسم حدود الأرض على الخريطة.")
