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
    DataCollection,
    MimeType,
    CRS,
    BBox,
)

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="AgriSat - مراقب المحاصيل", page_icon="🛰️", layout="wide")

st.title("🛰️ AgriSat: نظام مراقبة صحة النبات عبر الأقمار الصناعية")
st.markdown("---")

# --- 2. التحقق من مفاتيح API ---
if "SH_CLIENT_ID" not in st.secrets or "SH_CLIENT_SECRET" not in st.secrets:
    st.error("⚠️ عذراً، لم يتم العثور على مفاتيح API. يرجى إضافتها في ملف secrets.toml")
    st.stop()

# إعداد الاتصال بـ Sentinel Hub
config = SHConfig()
config.sh_client_id = st.secrets["SH_CLIENT_ID"]
config.sh_client_secret = st.secrets["SH_CLIENT_SECRET"]

# --- 3. دالة جلب البيانات من القمر الصناعي (Backend Logic) ---
def get_sentinel_image(coords_list):
    """
    تقوم هذه الدالة بإرسال الإحداثيات إلى Sentinel Hub
    وتعيد صورة NDVI ومصفوفة البيانات
    """
    
    # تحويل إحداثيات الرسم إلى BBox
    lons = [c[0] for c in coords_list]
    lats = [c[1] for c in coords_list]
    bbox_coords = [min(lons), min(lats), max(lons), max(lats)]
    roi_bbox = BBox(bbox=bbox_coords, crs=CRS.WGS84)

    # Evalscript: كود جافاسكريبت لحساب NDVI
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

    # تحديد الفترة الزمنية (آخر 30 يوم)
    today = date.today()
    start_date = today - timedelta(days=30)

    # تجهيز الطلب
    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[
            SentinelHubRequest.input_data(
                # --- تم التصحيح: العودة إلى الخيار القياسي لضمان التوافق ---
                data_collection=DataCollection.SENTINEL_2,
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

    # تنفيذ الطلب
    data = request.get_data()[0]
    return data

# --- 4. واجهة المستخدم (Frontend) ---

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("1. خريطة الحقل")
    st.info("قم برسم مضلع (Polygon) حول الأرض التي تريد تحليلها.")

    m = folium.Map(location=[34.0, 9.0], zoom_start=7)

    draw = Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False,
            "circle": False,
            "marker": False,
            "circlemarker": False,
            "polygon": True,
            "rectangle": True,
        },
    )
    draw.add_to(m)

    output = st_folium(m, width=None, height=500)

with col2:
    st.subheader("2. لوحة النتائج والتحليل")

    if output["all_drawings"] is not None and len(output["all_drawings"]) > 0:
        last_drawing = output["all_drawings"][-1]
        geometry_type = last_drawing['geometry']['type']
        coords = last_drawing['geometry']['coordinates']

        if geometry_type == 'Polygon':
            final_coords = coords[0]
        else:
            st.warning("يرجى استخدام أداة المضلع (Polygon) للدقة.")
            final_coords = None

        if final_coords:
            st.success("تم تحديد الإحداثيات بنجاح ✅")
            
            if st.button("تحليل صحة الغطاء النباتي (NDVI)", type="primary"):
                with st.spinner('جاري الاتصال بالقمر الصناعي ومعالجة الصور...'):
                    try:
                        ndvi_image = get_sentinel_image(final_coords)
                        
                        st.markdown("### خريطة الصحة النباتية:")
                        
                        fig, ax = plt.subplots(figsize=(6, 6))
                        im = ax.imshow(ndvi_image, cmap='RdYlGn', vmin=0, vmax=0.8)
                        plt.colorbar(im, fraction=0.046, pad=0.04, label='مؤشر NDVI')
                        ax.axis('off')
                        ax.set_title("توزيع صحة النبات في الحقل", fontsize=10)
                        st.pyplot(fig)

                        avg_ndvi = np.mean(ndvi_image[ndvi_image > 0])
                        
                        st.markdown("### 📊 التقرير:")
                        if np.isnan(avg_ndvi):
                             st.warning("المنطقة المحددة لا تحتوي على بيانات صالحة.")
                        else:
                            st.metric(label="متوسط مؤشر الصحة (NDVI)", value=f"{avg_ndvi:.2f}")

                            if avg_ndvi > 0.5:
                                st.success("🟢 **الحالة ممتازة:** المحصول ينمو بشكل جيد.")
                            elif avg_ndvi > 0.25:
                                st.warning("🟡 **الحالة متوسطة:** قد توجد مناطق تعاني من إجهاد.")
                            else:
                                st.error("🔴 **الحالة حرجة:** الغطاء النباتي ضعيف جداً.")

                    except Exception as e:
                        st.error(f"حدث خطأ تقني: {e}")
                        st.error("تأكد من إعدادات الحساب أو أن المنطقة المحددة صحيحة.")

    else:
        st.info("في انتظار الرسم على الخريطة... ✏️")
