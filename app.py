import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import matplotlib.pyplot as plt
import numpy as np
from datetime import date, timedelta

# استدعاء المكونات الأساسية
from sentinelhub import (
    SHConfig,
    SentinelHubRequest,
    DataCollection,
    MimeType,
    CRS,
    BBox
)

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="AgriSat", page_icon="🌱", layout="wide")
st.title("🛰️ AgriSat: مراقبة صحة النبات")

# --- 2. المفاتيح ---
if "SH_CLIENT_ID" not in st.secrets:
    st.error("⚠️ يرجى إضافة المفاتيح في Secrets")
    st.stop()

config = SHConfig()
config.sh_client_id = st.secrets["SH_CLIENT_ID"]
config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"]

# --- 3. دالة جلب البيانات (الحل النهائي المضمون) ---
def get_sentinel_image(coords_list):
    # تحويل الإحداثيات
    lons = [c[0] for c in coords_list]
    lats = [c[1] for c in coords_list]
    bbox_coords = [min(lons), min(lats), max(lons), max(lats)]
    roi_bbox = BBox(bbox=bbox_coords, crs=CRS.WGS84)

    # Evalscript لحساب NDVI
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
        if (sample.dataMask == 0) return [0];
        return [ndvi];
    }
    """

    today = date.today()
    start_date = today - timedelta(days=30)

    # --- الحل الجذري: تعريف المجموعة يدوياً بالكامل لتجنب أخطاء النسخ ---
    # نقوم بإنشاء الكائن يدوياً وتحديد الخدمة sentinel-2-l2a مباشرة
    try:
        data_collection = DataCollection.SENTINEL_2_L2A
    except AttributeError:
        # إذا فشلت الطريقة التلقائية، نستخدم التعريف المباشر
        data_collection = DataCollection(
            service_url="https://services.sentinel-hub.com",
            api_id="sentinel-2-l2a"
        )

    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=data_collection,
                time_interval=(start_date.isoformat(), today.isoformat()),
                maxcc=20.0,
                mosaicking_order="leastCC"
            )
        ],
        responses=[
            SentinelHubRequest.output_response('default', MimeType.TIFF)
        ],
        bbox=roi_bbox,
        size=(512, 512),
        config=config
    )

    return request.get_data()[0]

# --- 4. الواجهة ---
col1, col2 = st.columns([2, 1])

with col1:
    st.info("قم برسم مضلع حول الأرض على الخريطة:")
    m = folium.Map(location=[34.0, 9.0], zoom_start=7)
    draw = Draw(
        export=False,
        draw_options={"polyline": False, "circle": False, "marker": False, "polygon": True, "rectangle": True}
    )
    draw.add_to(m)
    output = st_folium(m, width=None, height=500)

with col2:
    st.subheader("تحليل الصحة النباتية")
    if output["all_drawings"]:
        if st.button("تحليل NDVI الآن"):
            with st.spinner('جاري التحليل...'):
                try:
                    last_draw = output["all_drawings"][-1]
                    coords = last_draw['geometry']['coordinates'][0]
                    
                    img = get_sentinel_image(coords)
                    
                    fig, ax = plt.subplots()
                    im = ax.imshow(img, cmap='RdYlGn', vmin=0, vmax=0.8)
                    plt.colorbar(im, label='مؤشر NDVI')
                    ax.axis('off')
                    st.pyplot(fig)
                    
                    valid_pixels = img[img > 0]
                    if len(valid_pixels) > 0:
                        avg = np.mean(valid_pixels)
                        st.metric("متوسط NDVI", f"{avg:.2f}")
                    
                except Exception as e:
                    st.error(f"حدث خطأ أثناء المعالجة: {e}")
