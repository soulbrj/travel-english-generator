import streamlit as st
import pandas as pd
from PIL import Image
import tempfile

# 页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 旅游英语视频生成器")
st.success("应用启动成功！")

# 简单的文件上传演示
uploaded_file = st.file_uploader("上传Excel文件", type=['xlsx', 'xls', 'csv'])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.write(f"成功读取文件，共 {len(df)} 行数据")
        st.dataframe(df.head())
        
    except Exception as e:
        st.error(f"文件读取失败: {str(e)}")
else:
    st.info("请上传Excel或CSV文件")
