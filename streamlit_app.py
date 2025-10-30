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
from gtts import gTTS  # 新增TTS库
from pydub import AudioSegment  # 新增音频处理库
import subprocess  # 用于调用ffmpeg合并音视频
import shutil  # 用于操作临时文件

# 设置页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 旅游英语视频生成器")
st.markdown("### 🌐 高级自定义视频生成 - 带音频版")

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

# 音频设置
st.header("🔊 音频设置")
language = st.selectbox("选择语音语言", ["英语", "中文"])
voice_speed = st.slider("语音速度", 0.5, 2.0, 1.0, 0.1)

# ... (省略中间相同的函数：create_custom_font, wrap_text, create_simple_frame, create_video_frame)

def generate_audio(text, lang='en', slow=False):
    """使用gTTS生成音频文件"""
    tts = gTTS(text=text, lang=lang, slow=slow)
    audio_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
    tts.save(audio_path)
    return audio_path

def create_video_with_audio(video_path, audio_path, output_path):
    """使用ffmpeg合并视频和音频"""
    try:
        # 确保ffmpeg可用
        if not shutil.which('ffmpeg'):
            st.error("未找到ffmpeg，请安装ffmpeg以支持音频功能")
            return None
            
        # 使用ffmpeg合并
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-strict', 'experimental',
            output_path
        ]
        
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return output_path
    except Exception as e:
        st.error(f"合并音视频时出错: {str(e)}")
        return None

def process_data(df):
    """处理数据并生成带音频的视频"""
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        frames = []
        audio_paths = []
        duration_per_sentence = 5  # 每个句子的时长（秒）
        
        # 为每一行生成帧和音频
        for index, row in df.iterrows():
            st.write(f"正在处理: {row['英语']}")
            
            # 生成视频帧
            frame = create_video_frame(
                text_english=str(row['英语']),
                text_chinese=str(row['中文']),
                text_phonetic=str(row['音标']) if pd.notna(row['音标']) else ""
            )
            
            # 每个句子重复多帧以达到指定时长
            for _ in range(int(duration_per_sentence * 10)):  # 10fps
                frames.append(np.array(frame))
            
            # 生成音频
            lang_code = 'en' if language == "英语" else 'zh-CN'
            audio_path = generate_audio(str(row['英语']), lang=lang_code, slow=voice_speed < 1.0)
            audio_paths.append(audio_path)
        
        # 保存视频（无音频）
        video_path = os.path.join(temp_dir, "temp_video.mp4")
        imageio.mimsave(video_path, frames, fps=10)
        
        # 合并所有音频
        combined_audio = AudioSegment.empty()
        for audio_path in audio_paths:
            audio = AudioSegment.from_mp3(audio_path)
            # 调整音频时长与视频帧时长匹配
            audio = audio[:duration_per_sentence * 1000]  # 转换为毫秒
            combined_audio += audio
            os.remove(audio_path)  # 清理临时音频
        
        # 保存合并后的音频
        combined_audio_path = os.path.join(temp_dir, "combined_audio.mp3")
        combined_audio.export(combined_audio_path, format="mp3")
        
        # 合并视频和音频
        final_video_path = os.path.join(temp_dir, "final_video.mp4")
        result = create_video_with_audio(video_path, combined_audio_path, final_video_path)
        
        if result:
            # 读取最终视频
            with open(final_video_path, "rb") as f:
                video_bytes = f.read()
            return video_bytes
        return None

# 处理逻辑
if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        
        # 检查必要的列
        required_columns = ['英语', '中文', '音标']
        if not all(col in df.columns for col in required_columns):
            st.error("Excel文件必须包含'英语'、'中文'和'音标'三列")
        else:
            st.success("文件上传成功！")
            st.dataframe(df.head())
            
            if st.button("生成视频"):
                with st.spinner("正在生成视频和音频..."):
                    video_bytes = process_data(df)
                    if video_bytes:
                        st.success("视频生成成功！")
                        st.video(video_bytes)
                        
                        # 提供下载链接
                        b64 = base64.b64encode(video_bytes).decode()
                        href = f'<a href="data:video/mp4;base64,{b64}" download="travel_english.mp4">下载视频</a>'
                        st.markdown(href, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"处理文件时出错: {str(e)}")
