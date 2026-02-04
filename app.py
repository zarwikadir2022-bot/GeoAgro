import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import matplotlib.pyplot as plt
import numpy as np
from datetime import date, timedelta

# استدعاء ServiceType لتعريف الخدمة يدوياً
from sentinelhub import (
    SHConfig,
    SentinelHubRequest,
    DataCollection,
    MimeType,
    CRS,
    BBox,
    ServiceType 
)

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="AgriSat - مراقب المحاصيل", page_icon="🛰️", layout="wide")
st.title("🛰️ AgriSat: نظام مراقبة صحة النبات عبر الأقمار الصناعية")

# --- 2. التحقق من المفاتيح ---
if "SH_CLIENT_ID" not in st.secrets or "SH_CLIENT_SECRET" not in st.secrets:
    st.error("⚠️ عذراً، لم يتم العثور على مفاتيح API في secrets.toml")
    st.stop()

config = SHConfig()
config.sh_client_id = st.secrets["SH_CLIENT_ID"]
config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"]

# --- 3. حل المشكلة: تعريف المجموعة يدوياً ---
# هذا الكود يتجاوز خطأ "AttributeError" عبر تعريف الاتصال مباشرة
def get_s2_collection():
    return DataCollection.define(
        "SENTINEL_2_L2A",  # اسم تعريفي
        api_id="sentinel-2-l2a",  # المعرف الرسمي في السيرفر
        service_type=ServiceType.PROCESS, 
        service_url="https://services.sentinel-hub.com"
    )

# --- 4. دالة جلب البيانات ---
def get_sentinel_image(coords_list):
    # تحويل الإحداثيات
    lons = [c[0] for c in coords_list]
    lats = [c[1] for c in coords_list]
    bbox_coords = [min(lons), min(lats), max(lons), max(lats)]
    roi_bbox = BBox(bbox=bbox_coords, crs=CRS.WGS84)

    # Evalscript لحساب NDVI
    evalscript = """
    setup = function() {
        return {
            input: ["B04", "B08", "dataMask"],
            output: { bands: 1 }
        };
    }
    evaluatePixel = function(sample) {
        let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
        if (sample.dataMask == 0) return [0];
        return [ndvi];
    }
    """

    today = date.today()
    start_date = today - timedelta(days=30)

    # استخدام المجموعة المعرفة يدوياً
    my_collection = get_s2_collection()

    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=my_collection, # استخدام المتغير الجديد هنا
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

# --- 5. واجهة المستخدم ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("1. خريطة الحقل")
    st.info("ارسم مضلعاً (Polygon) حول الأرض.")
    
    m = folium.Map(location=[34.0, 9.0], zoom_start=7)
    draw = Draw(
        export=False,
        draw_options={
            "polyline": False, "circle": False, "marker": False,
            "circlemarker": False, "polygon": True, "rectangle": True,
        },
    )
    draw.add_to(m)
    output = st_folium(m, width=None, height=500)

with col2:
    st.subheader("2. النتائج")
    
    if output["all_drawings"] and len(output["all_drawings"]) > 0:
        last_drawing = output["all_drawings"][-1]
        coords = last_drawing['geometry']['coordinates']
        geom_type = last_drawing['geometry']['type']
        
        # التعامل مع اختلاف هيكلية المضلع والمستطيل
        final_coords = coords[0] if geom_type == 'Polygon' else coords[0] 
        # ملاحظة: أحياناً المستطيل يحتاج معالجة مختلفة، لكن المضلع هو الأدق للزراعة
        
        if st.button("تحليل NDVI", type="primary"):
            with st.spinner('جاري الاتصال...'):
                try:
                    ndvi_img = get_sentinel_image(final_coords)
                    
                    fig, ax = plt.subplots(figsize=(6, 6))
                    im = ax.imshow(ndvi_img, cmap='RdYlGn', vmin=0, vmax=0.8)
                    plt.colorbar(im, fraction=0.046, pad=0.04, label='NDVI')
                    ax.axis('off')
                    st.pyplot(fig)
                    
                    avg = np.mean(ndvi_img[ndvi_img > 0])
                    st.metric("متوسط الصحة", f"{avg:.2f}")
                    
                    if avg > 0.4: st.success("الحالة جيدة 🟢")
                    elif avg > 0.2: st.warning("إجهاد متوسط 🟡")
                    else: st.error("إجهاد شديد أو أرض جرداء 🔴")
                    
                except Exception as e:
                    st.error(f"خطأ: {e}")
