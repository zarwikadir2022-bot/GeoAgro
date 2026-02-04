import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import matplotlib.pyplot as plt
import numpy as np

# إعدادات الصفحة
st.set_page_config(page_title="AgriSat - مراقب المحاصيل الذكي", layout="wide")

# --- 1. الدوال المساعدة (Backend Logic) ---

def get_ndvi_data(bbox_coords):
    """
    هنا نضع كود Sentinel Hub الذي كتبناه سابقاً.
    هذه دالة محاكاة (Simulation) لغرض العرض، 
    عليك استبدالها بالكود الحقيقي ووضع مفاتيح API الخاصة بك.
    """
    # محاكاة: إرجاع صورة عشوائية لتمثيل NDVI
    # في الواقع، هنا تستدعي request.get_data()
    fake_data = np.random.rand(512, 512) 
    return fake_data

# --- 2. واجهة المستخدم (Frontend) ---

st.title("🛰️ AgriSat: نظام مراقب النباتات عبر الأقمار الصناعية")
st.markdown("---")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("1. حدد موقع المزرعة")
    st.info("استخدم أدوات الرسم (المربع أو المضلع) على الخريطة لتحديد حدود أرضك.")

    # إنشاء خريطة أساسية (مُركزة على تونس)
    m = folium.Map(location=[34.0, 9.0], zoom_start=7)

    # إضافة أداة الرسم (Draw Control)
    draw = Draw(
        export=True,
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

    # عرض الخريطة وتخزين المخرجات
    output = st_folium(m, width=800, height=500)

with col2:
    st.subheader("2. لوحة التحليل")
    
    analyze_btn = st.button("تحليل صحة النبات (NDVI)", type="primary")

    if output["all_drawings"] is not None and len(output["all_drawings"]) > 0:
        # استخراج الإحداثيات من الرسم الأخير
        last_drawing = output["all_drawings"][-1]
        geometry = last_drawing['geometry']
        coordinates = geometry['coordinates']
        
        st.success("تم تحديد المنطقة بنجاح! ✅")
        st.json(geometry) # عرض الإحداثيات للتأكد (للمطور)

        if analyze_btn:
            with st.spinner('جاري الاتصال بالقمر الصناعي Sentinel-2...'):
                # هنا يتم استدعاء دالة المعالجة
                ndvi_img = get_ndvi_data(coordinates)
                
                st.subheader("نتائج التحليل:")
                
                # عرض الصورة باستخدام Matplotlib داخل Streamlit
                fig, ax = plt.subplots()
                im = ax.imshow(ndvi_img, cmap='RdYlGn', vmin=0, vmax=1)
                plt.colorbar(im, label='NDVI')
                ax.axis('off')
                ax.set_title(f"صحة النبات بتاريخ: {np.datetime64('today')}")
                
                st.pyplot(fig)
                
                # تفسير النتائج للفلاح
                avg_health = np.mean(ndvi_img)
                if avg_health > 0.6:
                    st.success("الوضع ممتاز: الغطاء النباتي كثيف وصحي.")
                elif avg_health > 0.3:
                    st.warning("تحذير: هناك علامات إجهاد متوسطة.")
                else:
                    st.error("خطر: المنطقة تعاني من جفاف شديد أو غياب للغطاء النباتي.")

    else:
        st.warning("يرجى رسم حدود المزرعة على الخريطة أولاً.")
