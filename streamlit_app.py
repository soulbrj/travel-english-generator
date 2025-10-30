import streamlit as st
import pandas as pd
import time
import io
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio
from io import BytesIO
import base64
import tempfile

# 设置页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 旅游英语视频生成器")
st.markdown("### 🌐 高级自定义视频生成 - 修复版")

# 初始化session state
if 'background_image' not in st.session_state:
    st.session_state.background_image = None
if 'preview_bg_image' not in st.session_state:
    st.session_state.preview_bg_image = None

# 特性介绍
col1, col2, col3 = st.columns(3)
with col1:
    st.info("🎨 完全自定义\n\n颜色、字体、背景随意调整")

with col2:
    st.info("🖼️ 背景图片\n\n支持自定义背景或纯色")

with col3:
    st.info("🔤 字体支持\n\n完美显示中文和音标")

# 文件上传
st.header("📤 第一步：上传Excel文件")
uploaded_file = st.file_uploader("选择Excel文件", type=['xlsx', 'xls'], 
                               help="Excel文件必须包含'英语','中文','音标'三列")

def wrap_text(text, max_chars):
    """将文本按最大字符数换行"""
    if not text or str(text) == 'nan':
        return [""]
    
    text = str(text)
    # 如果是中文，减少每行字符数
    if any('\u4e00' <= char <= '\u9fff' for char in text):
        max_chars = min(max_chars, 15)  # 中文每行最多15字
    
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        if len(test_line) <= max_chars:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            # 处理超长单词
            if len(word) > max_chars:
                for i in range(0, len(word), max_chars):
                    lines.append(word[i:i+max_chars])
                current_line = []
            else:
                current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines if lines else [text[:max_chars]]

def create_simple_frame(text_english, text_chinese, text_phonetic, width=600, height=400, 
                      bg_color=(0, 0, 0), bg_image=None,
                      english_color=(255, 255, 255), chinese_color=(0, 255, 255), phonetic_color=(255, 255, 0),
                      english_size=60, chinese_size=50, phonetic_size=40):
    """创建简单的预览帧"""
    
    # 创建图像
    if bg_image and hasattr(bg_image, 'resize'):
        try:
            img = bg_image.resize((width, height)).convert('RGB')
        except:
            img = Image.new('RGB', (width, height), color=bg_color)
    else:
        img = Image.new('RGB', (width, height), color=bg_color)
    
    draw = ImageDraw.Draw(img)
    
    # 尝试加载真实字体，失败则使用默认
    try:
        english_font = ImageFont.truetype("simhei.ttf", english_size)
        chinese_font = ImageFont.truetype("simhei.ttf", chinese_size)
        phonetic_font = ImageFont.truetype("simhei.ttf", phonetic_size)
    except:
        # 使用默认字体
        english_font = ImageFont.load_default()
        chinese_font = ImageFont.load_default()
        phonetic_font = ImageFont.load_default()
    
    # 计算文本区域
    english_lines = wrap_text(text_english, 25)
    chinese_lines = wrap_text(text_chinese, 12)
    phonetic_lines = wrap_text(text_phonetic, 30) if text_phonetic and str(text_phonetic).strip() and str(text_phonetic) != 'nan' else []
    
    # 计算总高度
    total_text_height = 0
    for line in english_lines:
        bbox = draw.textbbox((0, 0), line, font=english_font)
        total_text_height += bbox[3] - bbox[1]
    for line in chinese_lines:
        bbox = draw.textbbox((0, 0), line, font=chinese_font)
        total_text_height += bbox[3] - bbox[1]
    for line in phonetic_lines:
        bbox = draw.textbbox((0, 0), line, font=phonetic_font)
        total_text_height += bbox[3] - bbox[1]
    
    total_text_height += 60  # 间距
    
    # 计算起始Y位置（居中显示）
    y_position = (height - total_text_height) // 2
    
    # 绘制英语文本
    for line in english_lines:
        bbox = draw.textbbox((0, 0), line, font=english_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y_position), line, font=english_font, fill=english_color)
        y_position += bbox[3] - bbox[1] + 10  # 行间距
    
    # 绘制中文文本
    for line in chinese_lines:
        bbox = draw.textbbox((0, 0), line, font=chinese_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y_position), line, font=chinese_font, fill=chinese_color)
        y_position += bbox[3] - bbox[1] + 10  # 行间距
    
    # 绘制音标文本
    for line in phonetic_lines:
        bbox = draw.textbbox((0, 0), line, font=phonetic_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y_position), line, font=phonetic_font, fill=phonetic_color)
        y_position += bbox[3] - bbox[1] + 10  # 行间距
    
    return img

def create_video_frame(text_english, text_chinese, text_phonetic, width=1280, height=720, 
                     bg_color=(0, 0, 0), bg_image=None, 
                     english_color=(255, 255, 255), chinese_color=(0, 255, 255), phonetic_color=(255, 255, 0),
                     english_size=60, chinese_size=50, phonetic_size=40):
    """创建单个视频帧"""
    
    # 创建图像
    if bg_image and hasattr(bg_image, 'resize'):
        try:
            img = bg_image.resize((width, height)).convert('RGB')
        except:
            img = Image.new('RGB', (width, height), color=bg_color)
    else:
        img = Image.new('RGB', (width, height), color=bg_color)
    
    draw = ImageDraw.Draw(img)
    
    # 尝试加载真实字体，失败则使用默认
    try:
        english_font = ImageFont.truetype("simhei.ttf", english_size)
        chinese_font = ImageFont.truetype("simhei.ttf", chinese_size)
        phonetic_font = ImageFont.truetype("simhei.ttf", phonetic_size)
    except:
        # 使用默认字体
        english_font = ImageFont.load_default()
        chinese_font = ImageFont.load_default()
        phonetic_font = ImageFont.load_default()
    
    # 计算文本区域
    english_lines = wrap_text(text_english, 35)
    chinese_lines = wrap_text(text_chinese, 15)
    phonetic_lines = wrap_text(text_phonetic, 40) if text_phonetic and str(text_phonetic).strip() and str(text_phonetic) != 'nan' else []
    
    # 计算总高度
    total_text_height = 0
    line_spacing = 15
    for line in english_lines:
        bbox = draw.textbbox((0, 0), line, font=english_font)
        total_text_height += bbox[3] - bbox[1]
    total_text_height += line_spacing * (len(english_lines) - 1)
    
    for line in chinese_lines:
        bbox = draw.textbbox((0, 0), line, font=chinese_font)
        total_text_height += bbox[3] - bbox[1]
    total_text_height += line_spacing * (len(chinese_lines) - 1)
    
    for line in phonetic_lines:
        bbox = draw.textbbox((0, 0), line, font=phonetic_font)
        total_text_height += bbox[3] - bbox[1]
    total_text_height += line_spacing * (len(phonetic_lines) - 1)
    
    # 添加段落间距
    if chinese_lines:
        total_text_height += 20
    if phonetic_lines:
        total_text_height += 15
    
    # 计算起始Y位置（居中显示）
    y_position = (height - total_text_height) // 2
    
    # 绘制英语句子
    for line in english_lines:
        bbox = draw.textbbox((0, 0), line, font=english_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        
        # 绘制文本阴影（增强可读性）
        shadow_color = (0, 0, 0)
        draw.text((x + 2, y_position + 2), line, font=english_font, fill=shadow_color)
        
        # 绘制主文本
        draw.text((x, y_position), line, font=english_font, fill=english_color)
        
        y_position += (bbox[3] - bbox[1]) + line_spacing
    
    # 添加段落间距
    if chinese_lines:
        y_position += 10
    
    # 绘制中文翻译
    for line in chinese_lines:
        bbox = draw.textbbox((0, 0), line, font=chinese_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        
        # 绘制文本阴影
        draw.text((x + 2, y_position + 2), line, font=chinese_font, fill=shadow_color)
        
        # 绘制主文本
        draw.text((x, y_position), line, font=chinese_font, fill=chinese_color)
        
        y_position += (bbox[3] - bbox[1]) + line_spacing
    
    # 添加段落间距
    if phonetic_lines:
        y_position += 5
    
    # 绘制音标
    for line in phonetic_lines:
        bbox = draw.textbbox((0, 0), line, font=phonetic_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        
        # 绘制文本阴影
        draw.text((x + 2, y_position + 2), line, font=phonetic_font, fill=shadow_color)
        
        # 绘制主文本
        draw.text((x, y_position), line, font=phonetic_font, fill=phonetic_color)
        
        y_position += (bbox[3] - bbox[1]) + line_spacing
    
    return img

# 处理上传的文件
if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        
        # 检查必要的列
        required_columns = ['英语', '中文', '音标']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"Excel文件缺少必要的列: {', '.join(missing_columns)}")
        else:
            st.success("文件上传成功！")
            st.dataframe(df, height=300)
            
            # 第二步：自定义设置
            st.header("🎨 第二步：自定义设置")
            
            # 背景设置
            bg_option = st.radio("选择背景类型", ["纯色背景", "自定义图片"])
            
            bg_color = (0, 0, 0)  # 默认黑色
            if bg_option == "纯色背景":
                bg_color_hex = st.color_picker("选择背景颜色", "#000000")
                # 转换十六进制到RGB
                bg_color = tuple(int(bg_color_hex[i:i+2], 16) for i in (1, 3, 5))
                st.session_state.background_image = None
            else:
                uploaded_bg = st.file_uploader("上传背景图片", type=['jpg', 'jpeg', 'png'])
                if uploaded_bg is not None:
                    try:
                        img = Image.open(uploaded_bg)
                        st.session_state.background_image = img
                        st.success("背景图片上传成功！")
                        st.image(img, caption="预览背景图", width=300)
                    except Exception as e:
                        st.error(f"图片处理错误: {str(e)}")
                        st.session_state.background_image = None
            
            # 文字颜色设置
            col1, col2, col3 = st.columns(3)
            with col1:
                english_color_hex = st.color_picker("英语文字颜色", "#FFFFFF")
                english_color = tuple(int(english_color_hex[i:i+2], 16) for i in (1, 3, 5))
            with col2:
                chinese_color_hex = st.color_picker("中文文字颜色", "#00FFFF")
                chinese_color = tuple(int(chinese_color_hex[i:i+2], 16) for i in (1, 3, 5))
            with col3:
                phonetic_color_hex = st.color_picker("音标颜色", "#FFFF00")
                phonetic_color = tuple(int(phonetic_color_hex[i:i+2], 16) for i in (1, 3, 5))
            
            # 字号设置
            col4, col5, col6 = st.columns(3)
            with col4:
                english_size = st.slider("英语字号", min_value=20, max_value=100, value=60, step=2)
            with col5:
                chinese_size = st.slider("中文字号", min_value=20, max_value=100, value=50, step=2)
            with col6:
                phonetic_size = st.slider("音标字号", min_value=16, max_value=80, value=40, step=2)
            
            # 视频设置
            st.subheader("🎞️ 视频设置")
            col7, col8 = st.columns(2)
            with col7:
                duration_per_sentence = st.slider("每句显示时间(秒)", min_value=2, max_value=10, value=5)
            with col8:
                fps = st.slider("视频帧率", min_value=10, max_value=30, value=24)
            
            # 预览
            st.subheader("👀 预览")
            if not df.empty:
                selected_index = st.slider("选择预览行", 0, len(df)-1, 0)
                sample_row = df.iloc[selected_index]
                
                preview_img = create_simple_frame(
                    text_english=sample_row['英语'],
                    text_chinese=sample_row['中文'],
                    text_phonetic=sample_row['音标'],
                    bg_color=bg_color,
                    bg_image=st.session_state.background_image,
                    english_color=english_color,
                    chinese_color=chinese_color,
                    phonetic_color=phonetic_color,
                    english_size=english_size,
                    chinese_size=chinese_size,
                    phonetic_size=phonetic_size
                )
                
                st.image(preview_img, caption="预览效果")
            
            # 生成视频
            st.header("🚀 第三步：生成视频")
            if st.button("开始生成视频"):
                with st.spinner("正在生成视频，请稍候..."):
                    try:
                        # 创建临时文件
                        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                            video_path = temp_file.name
                        
                        # 计算每句需要的帧数
                        frames_per_sentence = duration_per_sentence * fps
                        
                        # 生成视频帧
                        writer = imageio.get_writer(video_path, fps=fps)
                        
                        # 进度条
                        progress_bar = st.progress(0)
                        total_frames = len(df) * frames_per_sentence
                        current_frame = 0
                        
                        for index, row in df.iterrows():
                            # 创建一帧并重复多次
                            frame = create_video_frame(
                                text_english=row['英语'],
                                text_chinese=row['中文'],
                                text_phonetic=row['音标'],
                                bg_color=bg_color,
                                bg_image=st.session_state.background_image,
                                english_color=english_color,
                                chinese_color=chinese_color,
                                phonetic_color=phonetic_color,
                                english_size=english_size,
                                chinese_size=chinese_size,
                                phonetic_size=phonetic_size
                            )
                            
                            # 转换为RGB模式并添加到视频
                            frame_rgb = frame.convert('RGB')
                            for _ in range(frames_per_sentence):
                                writer.append_data(np.array(frame_rgb))
                                current_frame += 1
                                progress_bar.progress(min(current_frame / total_frames, 1.0))
                        
                        writer.close()
                        progress_bar.progress(1.0)
                        
                        # 提供下载
                        st.success("视频生成成功！")
                        
                        # 读取视频文件
                        with open(video_path, 'rb') as f:
                            video_bytes = f.read()
                        
                        # 提供下载链接
                        st.download_button(
                            label="下载视频",
                            data=video_bytes,
                            file_name="travel_english_video.mp4",
                            mime="video/mp4"
                        )
                        
                        # 清理临时文件
                        os.unlink(video_path)
                        
                    except Exception as e:
                        st.error(f"视频生成失败: {str(e)}")
                        st.exception(e)
    except Exception as e:
        st.error(f"文件处理错误: {str(e)}")
else:
    st.info("请先上传包含'英语','中文','音标'三列的Excel文件")
