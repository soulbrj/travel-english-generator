import streamlit as st
import pandas as pd
import os
import numpy as np
from PIL import Image, ImageDraw
import imageio.v2 as imageio
import tempfile
import base64
import subprocess
import platform

# 页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide"
)

# 初始化会话状态
if 'bg_image' not in st.session_state:
    st.session_state.bg_image = None

def check_system_tts():
    """检查系统TTS支持"""
    system = platform.system()
    if system == "Windows":
        return "Windows TTS可用"
    elif system == "Darwin":  # macOS
        return "macOS TTS可用"
    elif system == "Linux":
        # 检查espeak是否安装
        result = subprocess.run(["which", "espeak"], capture_output=True, text=True)
        if result.returncode == 0:
            return "espeak TTS可用"
    return "无本地TTS支持"

def generate_audio_system(text, lang='en', output_file=None):
    """使用系统TTS生成音频"""
    system = platform.system()
    
    try:
        if system == "Windows":
            # 使用Windows SAPI
            try:
                import win32com.client
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                speaker.Speak(text)
                # Windows SAPI不能直接保存文件，这里简化处理
                return None
            except ImportError:
                st.warning("Windows TTS不可用，需要安装pywin32")
                return None
        elif system == "Darwin":  # macOS
            # 使用say命令
            cmd = ['say', '-v', 'Alex' if lang == 'en' else 'Ting-Ting', '-o', output_file, text]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return output_file
        elif system == "Linux":
            # 使用espeak
            voice = 'en' if lang == 'en' else 'zh'
            cmd = ['espeak', '-v', voice, '-w', output_file, text]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return output_file
    except Exception as e:
        st.warning(f"系统TTS失败: {str(e)}")
    
    return None

def generate_audio_fallback(text, lang='en'):
    """备选音频生成方案"""
    # 方案1: 尝试gTTS（在线）
    try:
        from gtts import gTTS
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tts = gTTS(text=text, lang=lang)
            tts.save(f.name)
            return f.name
    except Exception as e:
        st.warning(f"gTTS失败: {str(e)}")
    
    # 方案2: 创建静音音频（完全离线方案）
    try:
        # 生成静音WAV文件
        import wave
        import struct
        
        sample_rate = 22050
        duration = 3  # 3秒静音
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            with wave.open(f.name, 'w') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 2字节样本
                wav_file.setframerate(sample_rate)
                
                # 生成静音数据
                frames = b''
                for i in range(int(sample_rate * duration)):
                    frames += struct.pack('<h', 0)  # 16位静音
                
                wav_file.writeframes(frames)
            return f.name
    except Exception as e:
        st.warning(f"静音音频生成失败: {str(e)}")
        return None

def wrap_text(text, max_chars):
    """文本自动换行处理"""
    if not text or str(text).strip().lower() in ['nan', 'none', '']:
        return [""]
    
    text = str(text).strip()
    if any('\u4e00' <= c <= '\u9fff' for c in text):
        max_chars = min(max_chars, 15)
    
    words = text.split()
    lines, current = [], []
    
    for word in words:
        test_line = ' '.join(current + [word])
        if len(test_line) <= max_chars:
            current.append(word)
        else:
            if current:
                lines.append(' '.join(current))
            if len(word) > max_chars:
                for i in range(0, len(word), max_chars):
                    lines.append(word[i:i+max_chars])
                current = []
            else:
                current = [word]
    
    if current:
        lines.append(' '.join(current))
    
    return lines if lines else [""]

def create_frame(english, chinese, phonetic, width=1280, height=720, 
                bg_color=(0,0,0), bg_image=None,
                eng_color=(255,255,255), chn_color=(0,255,255), pho_color=(255,255,0),
                eng_size=60, chn_size=50, pho_size=40):
    """创建单帧图像"""
    if bg_image and hasattr(bg_image, 'resize'):
        try:
            img = bg_image.resize((width, height), Image.Resampling.LANCZOS).convert('RGB')
        except:
            img = Image.new('RGB', (width, height), bg_color)
    else:
        img = Image.new('RGB', (width, height), bg_color)
    
    draw = ImageDraw.Draw(img)
    
    eng_lines = wrap_text(english, 30)
    chn_lines = wrap_text(chinese, 15)
    pho_lines = wrap_text(phonetic, 35) if phonetic and str(phonetic).strip().lower() not in ['nan', 'none', ''] else []
    
    line_spacing = 10
    total_height = 0
    
    total_height += len(eng_lines) * eng_size + line_spacing * max(0, len(eng_lines) - 1)
    
    if chn_lines:
        total_height += 20 + len(chn_lines) * chn_size + line_spacing * max(0, len(chn_lines) - 1)
    
    if pho_lines:
        total_height += 15 + len(pho_lines) * pho_size + line_spacing * max(0, len(pho_lines) - 1)
    
    y = (height - total_height) // 2
    
    for line in eng_lines:
        w = len(line) * eng_size // 2
        h = eng_size
        x = (width - w) // 2
        shadow_color = (0, 0, 0)
        draw.text((x+2, y+2), line, fill=shadow_color)
        draw.text((x, y), line, fill=eng_color)
        y += h + line_spacing
    
    if chn_lines:
        y += 10
        for line in chn_lines:
            w = len(line) * chn_size // 2
            h = chn_size
            x = (width - w) // 2
            draw.text((x+2, y+2), line, fill=shadow_color)
            draw.text((x, y), line, fill=chn_color)
            y += h + line_spacing
    
    if pho_lines:
        y += 5
        for line in pho_lines:
            w = len(line) * pho_size // 2
            h = pho_size
            x = (width - w) // 2
            draw.text((x+2, y+2), line, fill=shadow_color)
            draw.text((x, y), line, fill=pho_color)
            y += h + line_spacing
    
    return img

def create_sample_excel():
    """创建示例Excel文件"""
    sample_data = {
        '英语': [
            "Hello, how are you?",
            "Where is the nearest restaurant?",
            "How much does this cost?",
            "Thank you very much",
            "Good morning"
        ],
        '中文': [
            "你好，最近怎么样？",
            "最近的餐厅在哪里？",
            "这个多少钱？",
            "非常感谢",
            "早上好"
        ],
        '音标': [
            "/həˈloʊ, haʊ ɑːr juː/",
            "/wer ɪz ðə ˈnɪrɪst ˈrɛstərənt/",
            "/haʊ mʌtʃ dʌz ðɪs kɒst/",
            "/θæŋk juː ˈvɛri mʌtʃ/",
            "/ɡʊd ˈmɔːrnɪŋ/"
        ]
    }
    return pd.DataFrame(sample_data)

# 页面UI
st.title("🎬 旅游英语视频生成器 - 离线版")
st.markdown("生成包含英语句子、中文翻译和音标的学习视频（支持离线音频）")

# 检查TTS支持
tts_status = check_system_tts()
st.info(f"TTS状态: {tts_status}")

# 提供示例文件下载
st.header("📋 示例文件")
sample_df = create_sample_excel()
st.dataframe(sample_df, height=200)

sample_csv = sample_df.to_csv(index=False).encode('utf-8')
st.download_button(
    "下载示例CSV文件",
    data=sample_csv,
    file_name="travel_english_sample.csv",
    mime="text/csv"
)

# 文件上传
st.header("1. 上传数据文件")
uploaded_file = st.file_uploader("选择Excel或CSV文件", type=['xlsx', 'xls', 'csv'])

df = None
if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        required_cols = ['英语', '中文', '音标']
        missing = [c for c in required_cols if c not in df.columns]
        
        if missing:
            st.error(f"文件缺少必要列: {', '.join(missing)}")
        else:
            st.success(f"文件上传成功！共 {len(df)} 条数据")
            st.dataframe(df.head(10), height=300)
            
    except Exception as e:
        st.error(f"文件处理错误: {str(e)}")

if df is not None and not df.empty:
    # 自定义设置
    st.header("2. 自定义设置")
    
    bg_type = st.radio("背景类型", ["纯色", "图片"])
    bg_color = (0, 0, 0)
    
    if bg_type == "纯色":
        bg_hex = st.color_picker("背景颜色", "#000000")
        bg_color = tuple(int(bg_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        st.session_state.bg_image = None
    else:
        bg_file = st.file_uploader("上传背景图片", type=['jpg', 'jpeg', 'png'])
        if bg_file:
            try:
                st.session_state.bg_image = Image.open(bg_file)
                st.image(st.session_state.bg_image, caption="背景预览", width=300)
            except Exception as e:
                st.error(f"图片处理失败: {str(e)}")
                st.session_state.bg_image = None
    
    st.subheader("文字样式")
    col1, col2, col3 = st.columns(3)
    with col1:
        eng_color_hex = st.color_picker("英语颜色", "#FFFFFF")
        eng_color = tuple(int(eng_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        eng_size = st.slider("英语字号", 20, 100, 60)
    with col2:
        chn_color_hex = st.color_picker("中文颜色", "#00FFFF")
        chn_color = tuple(int(chn_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        chn_size = st.slider("中文字号", 20, 100, 50)
    with col3:
        pho_color_hex = st.color_picker("音标颜色", "#FFFF00")
        pho_color = tuple(int(pho_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        pho_size = st.slider("音标字号", 16, 80, 40)
    
    st.subheader("视频设置")
    col4, col5 = st.columns(2)
    with col4:
        duration = st.slider("每句显示时间(秒)", 2, 10, 5)
        fps = st.slider("帧率", 10, 30, 24)
    with col5:
        tts_option = st.selectbox("TTS选项", ["系统TTS", "在线TTS", "无音频"])
        tts_lang = st.selectbox("语音语言", ["英语", "中文"])
        tts_lang_code = "en" if tts_lang == "英语" else "zh"
    
    # 预览
    st.header("3. 预览效果")
    preview_idx = st.slider("选择预览行", 0, len(df)-1, 0)
    row = df.iloc[preview_idx]
    
    try:
        preview_img = create_frame(
            english=str(row['英语']),
            chinese=str(row['中文']),
            phonetic=str(row['音标']) if pd.notna(row['音标']) else "",
            bg_color=bg_color,
            bg_image=st.session_state.bg_image,
            eng_color=eng_color,
            chn_color=chn_color,
            pho_color=pho_color,
            eng_size=eng_size,
            chn_size=chn_size,
            pho_size=pho_size
        )
        st.image(preview_img, caption=f"预览: {row['英语'][:50]}...", use_column_width=True)
    except Exception as e:
        st.error(f"预览生成失败: {str(e)}")
    
    # 生成视频
    st.header("4. 生成视频")
    
    if st.button("🎬 开始生成视频", type="primary", use_container_width=True):
        with st.spinner("正在生成视频，这可能需要一些时间..."):
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    frames = []
                    audio_paths = []
                    total_frames = len(df) * duration * fps
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, row in df.iterrows():
                        status_text.text(f"处理第 {idx + 1}/{len(df)} 句: {row['英语'][:30]}...")
                        
                        frame = create_frame(
                            english=str(row['英语']),
                            chinese=str(row['中文']),
                            phonetic=str(row['音标']) if pd.notna(row['音标']) else "",
                            bg_color=bg_color,
                            bg_image=st.session_state.bg_image,
                            eng_color=eng_color,
                            chn_color=chn_color,
                            pho_color=pho_color,
                            eng_size=eng_size,
                            chn_size=chn_size,
                            pho_size=pho_size
                        )
                        
                        for _ in range(duration * fps):
                            frames.append(np.array(frame.convert('RGB')))
                        
                        # 音频生成逻辑
                        if tts_option != "无音频":
                            audio_file = os.path.join(temp_dir, f"audio_{idx}.wav")
                            
                            if tts_option == "系统TTS":
                                audio_path = generate_audio_system(
                                    text=str(row['英语']),
                                    lang=tts_lang_code,
                                    output_file=audio_file
                                )
                            else:  # 在线TTS
                                audio_path = generate_audio_fallback(
                                    text=str(row['英语']),
                                    lang=tts_lang_code
                                )
                            
                            audio_paths.append(audio_path)
                        
                        current_progress = min((idx + 1) / len(df), 1.0)
                        progress_bar.progress(current_progress)
                    
                    status_text.text("正在保存视频...")
                    
                    video_path = os.path.join(temp_dir, "video_no_audio.mp4")
                    try:
                        imageio.mimsave(video_path, frames, fps=fps, quality=8)
                    except Exception as e:
                        st.error(f"视频保存失败: {str(e)}")
                        return
                    
                    final_video_path = video_path
                    has_audio = False
                    
                    if tts_option != "无音频" and audio_paths and any(audio_paths):
                        status_text.text("正在处理音频...")
                        try:
                            # 合并音频
                            audio_list_path = os.path.join(temp_dir, "audio_list.txt")
                            with open(audio_list_path, 'w') as f:
                                for audio_path in audio_paths:
                                    if audio_path and os.path.exists(audio_path):
                                        f.write(f"file '{audio_path}'\n")
                            
                            combined_audio_path = os.path.join(temp_dir, "combined_audio.wav")
                            cmd = [
                                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                                '-i', audio_list_path, '-c', 'copy', combined_audio_path
                            ]
                            
                            result = subprocess.run(cmd, capture_output=True, text=True)
                            
                            if result.returncode == 0 and os.path.exists(combined_audio_path):
                                final_video_path = os.path.join(temp_dir, "video_with_audio.mp4")
                                merge_cmd = [
                                    'ffmpeg', '-y',
                                    '-i', video_path,
                                    '-i', combined_audio_path,
                                    '-c:v', 'copy',
                                    '-c:a', 'aac',
                                    '-shortest',
                                    final_video_path
                                ]
                                
                                merge_result = subprocess.run(merge_cmd, capture_output=True, text=True)
                                if merge_result.returncode == 0:
                                    has_audio = True
                                    st.success("✅ 已生成带音频的视频")
                        except Exception as e:
                            st.warning(f"音频处理失败: {str(e)}")
                    
                    try:
                        with open(final_video_path, "rb") as f:
                            video_bytes = f.read()
                        
                        progress_bar.progress(1.0)
                        status_text.text("视频生成完成！")
                        
                        st.success("🎉 视频生成完成！")
                        st.video(video_bytes)
                        
                        file_suffix = "_with_audio" if has_audio else "_no_audio"
                        st.download_button(
                            f"📥 下载视频{'（含音频）' if has_audio else '（无音频）'}",
                            data=video_bytes,
                            file_name=f"travel_english_video{file_suffix}.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )
                        
                    except Exception as e:
                        st.error(f"视频文件读取失败: {str(e)}")
                        
            except Exception as e:
                st.error(f"生成失败: {str(e)}")
else:
    st.info("👆 请先上传数据文件或使用示例数据")

st.markdown("---")
st.markdown("### 💡 使用说明")
st.markdown("""
**TTS选项说明**:
- **系统TTS**: 使用操作系统自带的TTS引擎（需要系统支持）
- **在线TTS**: 使用gTTS在线服务（需要网络）
- **无音频**: 生成无音频视频

**系统TTS支持**:
- Windows: 使用SAPI
- macOS: 使用say命令
- Linux: 使用espeak（需要安装）
""")
