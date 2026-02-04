import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import matplotlib.pyplot as plt
import numpy as np
from datetime import date, timedelta

from sentinelhub import (
    SHConfig,
    SentinelHubRequest,
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

# --- 3. دالة جلب البيانات (الطريقة المباشرة والآمنة) ---
def get_sentinel_image(coords_list):
    # تحويل الإحداثيات إلى BBox
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

    # --- الحل النهائي: تمرير اسم المجموعة كنص مباشرة (String ID) ---
    # هذه الطريقة تتجاوز مشاكل الـ Attribute و الـ Metaclass
    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{start_date.isoformat()}T00:00:00Z",
                        "to": f"{today.isoformat()}T23:59:59Z"
                    },
                    "maxCloudCoverage": 20
                },
                "type": "sentinel-2-l2a" # نحدد النوع هنا مباشرة كنص
            }
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
                    # الحصول على الإحداثيات
                    last_draw = output["all_drawings"][-1]
                    # تأكد من أخذ الإحداثيات الصحيحة للمضلع
                    coords = last_draw['geometry']['coordinates'][0]
                    
                    img = get_sentinel_image(coords)
                    
                    # عرض الصورة
                    fig, ax = plt.subplots()
                    im = ax.imshow(img, cmap='RdYlGn', vmin=0, vmax=0.8)
                    plt.colorbar(im, label='NDVI Index')
                    ax.axis('off')
                    st.pyplot(fig)
                    
                    avg = np.mean(img[img > 0])
                    st.metric("متوسط NDVI", f"{avg:.2f}")
                    
                except Exception as e:
                    st.error(f"حدث خطأ: {e}")
    else:
        st.write("✏️ في انتظار رسم حدود المزرعة...")
