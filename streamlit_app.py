import streamlit as st
import pandas as pd
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio
import tempfile
import shutil
from gtts import gTTS
from pydub import AudioSegment
import subprocess
import traceback
import gc
import ffmpeg  # 注意：此处导入的是ffmpeg-python库

# 页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide"
)

# 初始化会话状态
if 'bg_image' not in st.session_state:
    st.session_state.bg_image = None
if 'audio_available' not in st.session_state:
    st.session_state.audio_available = True  # 标记音频功能是否可用

# --------------------------
# 核心功能函数
# --------------------------
def check_ffmpeg():
    """检查系统ffmpeg是否可用"""
    return shutil.which('ffmpeg') is not None

def wrap_text(text, max_chars):
    """文本自动换行处理"""
    if not text or str(text).strip().lower() == 'nan':
        return [""]
    
    text = str(text).strip()
    # 中文适配：减少每行字符数
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
            # 处理超长单词
            if len(word) > max_chars:
                for i in range(0, len(word), max_chars):
                    lines.append(word[i:i+max_chars])
                current = []
            else:
                current = [word]
    if current:
        lines.append(' '.join(current))
    return lines

def get_font(size):
    """优先加载项目内的中文字体，解决部署环境字体缺失问题"""
    try:
        # 尝试加载项目内的SimHei字体
        font_path = os.path.join(os.path.dirname(__file__), "fonts", "SimHei.ttf")
        return ImageFont.truetype(font_path, size)
    except:
        # 回退到系统字体
        font_candidates = ["WenQuanYi Micro Hei", "Heiti TC", "Arial Unicode MS"]
        for font_name in font_candidates:
            try:
                return ImageFont.truetype(font_name, size)
            except:
                continue
        st.warning("未找到合适的中文字体，中文可能显示异常")
        return ImageFont.load_default()

def create_frame(english, chinese, phonetic, width=1280, height=720, 
                bg_color=(0,0,0), bg_image=None,
                eng_color=(255,255,255), chn_color=(0,255,255), pho_color=(255,255,0),
                eng_size=60, chn_size=50, pho_size=40):
    """创建单帧图像（文字居中显示）"""
    # 创建背景
    if bg_image:
        try:
            img = bg_image.resize((width, height), Image.Resampling.LANCZOS).convert('RGB')
        except:
            img = Image.new('RGB', (width, height), bg_color)
    else:
        img = Image.new('RGB', (width, height), bg_color)
    
    draw = ImageDraw.Draw(img)
    # 获取字体（明确传递字号）
    eng_font = get_font(eng_size)
    chn_font = get_font(chn_size)
    pho_font = get_font(pho_size)
    
    # 文本换行处理
    eng_lines = wrap_text(english, 30)
    chn_lines = wrap_text(chinese, 15)
    pho_lines = wrap_text(phonetic, 35) if phonetic else []
    
    # 计算文本总高度（含间距）
    line_spacing = 10
    total_height = 0
    # 英语文本高度
    for line in eng_lines:
        _, _, _, h = draw.textbbox((0,0), line, font=eng_font)
        total_height += h
    total_height += line_spacing * (len(eng_lines) - 1)
    # 中文文本高度（加段落间距）
    if chn_lines:
        total_height += 20  # 段落间距
        for line in chn_lines:
            _, _, _, h = draw.textbbox((0,0), line, font=chn_font)
            total_height += h
        total_height += line_spacing * (len(chn_lines) - 1)
    # 音标文本高度（加段落间距）
    if pho_lines:
        total_height += 15  # 段落间距
        for line in pho_lines:
            _, _, _, h = draw.textbbox((0,0), line, font=pho_font)
            total_height += h
        total_height += line_spacing * (len(pho_lines) - 1)
    
    # 计算起始Y坐标（垂直居中）
    y = (height - total_height) // 2
    
    # 绘制英语
    for line in eng_lines:
        w, h = draw.textbbox((0,0), line, font=eng_font)[2:]
        x = (width - w) // 2
        # 文本阴影（增强可读性）
        draw.text((x+1, y+1), line, font=eng_font, fill=(0,0,0,128))
        draw.text((x, y), line, font=eng_font, fill=eng_color)
        y += h + line_spacing
    
    # 绘制中文
    if chn_lines:
        y += 10  # 段落间距
        for line in chn_lines:
            w, h = draw.textbbox((0,0), line, font=chn_font)[2:]
            x = (width - w) // 2
            draw.text((x+1, y+1), line, font=chn_font, fill=(0,0,0,128))
            draw.text((x, y), line, font=chn_font, fill=chn_color)
            y += h + line_spacing
    
    # 绘制音标
    if pho_lines:
        y += 5  # 段落间距
        for line in pho_lines:
            w, h = draw.textbbox((0,0), line, font=pho_font)[2:]
            x = (width - w) // 2
            draw.text((x+1, y+1), line, font=pho_font, fill=(0,0,0,128))
            draw.text((x, y), line, font=pho_font, fill=pho_color)
            y += h + line_spacing
    
    return img

def generate_audio(text, lang='en', speed=1.0):
    """生成TTS音频"""
    try:
        tts = gTTS(text=text, lang=lang, slow=speed < 0.9)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tts.save(f.name)
            return f.name
    except Exception as e:
        st.error(f"音频生成失败: {str(e)}")
        st.session_state.audio_available = False
        return None

def merge_audio_files(audio_paths, target_duration):
    """合并音频并匹配视频时长"""
    combined = AudioSegment.empty()
    for path in audio_paths:
        if not path:
            continue
        try:
            audio = AudioSegment.from_mp3(path)
            # 确保音频时长与视频帧时长一致
            if len(audio) > target_duration * 1000:  # 转换为毫秒
                audio = audio[:int(target_duration * 1000)]
            else:
                # 不足时补静音
                silence = AudioSegment.silent(duration=int(target_duration * 1000) - len(audio))
                audio += silence
            combined += audio
            os.remove(path)  # 清理临时文件
        except Exception as e:
            st.warning(f"音频片段处理失败: {str(e)}")
    return combined

def merge_video_audio(video_path, audio_path, output_path):
    """用ffmpeg合并音视频（适配旧版ffmpeg-python API）"""
    try:
        # 分别创建输入流后合并
        video = ffmpeg.input(video_path)
        audio = ffmpeg.input(audio_path)
        ffmpeg.output(video, audio, output_path, vcodec='copy', acodec='aac', strict='experimental').run(overwrite_output=True)
        return output_path
    except ffmpeg.Error as e:
        st.error(f"音视频合并失败: {e.stderr.decode()}")
        return None

# --------------------------
# 页面UI与逻辑
# --------------------------
st.title("🎬 旅游英语视频生成器")
st.markdown("生成包含英语句子、中文翻译和音标的带音频视频")

# 检查ffmpeg状态
if not check_ffmpeg():
    st.warning("⚠️ 未检测到系统ffmpeg，音频功能可能无法使用（需安装ffmpeg支持）")

# 1. 文件上传
st.header("1. 上传Excel文件")
uploaded_file = st.file_uploader("选择Excel文件", type=['xlsx', 'xls'])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        required_cols = ['英语', '中文', '音标']
        missing = [c for c in required_cols if c not in df.columns]
        
        if missing:
            st.error(f"Excel缺少必要列: {', '.join(missing)}")
        else:
            # 限制数据量，避免内存溢出
            if len(df) > 30:
                st.warning("Excel行数超过30行，可能导致内存溢出，请拆分文件后重试")
                uploaded_file = None
            else:
                st.success("文件上传成功！")
                st.dataframe(df, height=200)
                
                # 2. 自定义设置
                st.header("2. 自定义设置")
                
                # 背景设置
                bg_type = st.radio("背景类型", ["纯色", "图片"])
                bg_color = (0,0,0)
                if bg_type == "纯色":
                    bg_hex = st.color_picker("背景颜色", "#000000")
                    bg_color = tuple(int(bg_hex[i:i+2], 16) for i in (1,3,5))
                    st.session_state.bg_image = None
                else:
                    bg_file = st.file_uploader("上传背景图片", type=['jpg','jpeg','png'])
                    if bg_file:
                        try:
                            st.session_state.bg_image = Image.open(bg_file)
                            st.image(st.session_state.bg_image, caption="背景预览", width=300)
                        except Exception as e:
                            st.error(f"图片处理失败: {str(e)}")
                            st.session_state.bg_image = None
                
                # 文字设置
                st.subheader("文字样式")
                col1, col2, col3 = st.columns(3)
                with col1:
                    eng_color = st.color_picker("英语颜色", "#FFFFFF")
                    eng_color = tuple(int(eng_color[i:i+2], 16) for i in (1,3,5))
                    eng_size = st.slider("英语字号", 20, 100, 60)
                with col2:
                    chn_color = st.color_picker("中文颜色", "#00FFFF")
                    chn_color = tuple(int(chn_color[i:i+2], 16) for i in (1,3,5))
                    chn_size = st.slider("中文字号", 20, 100, 50)
                with col3:
                    pho_color = st.color_picker("音标颜色", "#FFFF00")
                    pho_color = tuple(int(pho_color[i:i+2], 16) for i in (1,3,5))
                    pho_size = st.slider("音标字号", 16, 80, 40)
                
                # 视频与音频设置
                st.subheader("视频与音频")
                col4, col5 = st.columns(2)
                with col4:
                    duration = st.slider("每句显示时间(秒)", 2, 10, 5)
                    fps = st.slider("帧率", 10, 30, 24)
                    resolution = st.selectbox("视频分辨率", ["1280x720 (HD)", "1920x1080 (FHD)"])
                    res_num = resolution.split(' ')[0]
                    width, height = map(int, res_num.split('x'))
                with col5:
                    tts_lang = st.selectbox("语音语言", ["英语", "中文"])
                    tts_speed = st.slider("语音速度", 0.5, 2.0, 1.0)
                    tts_lang_code = "en" if tts_lang == "英语" else "zh-CN"
                
                # 3. 预览
                st.header("3. 预览效果")
                if not df.empty:
                    preview_idx = st.slider("选择预览行", 0, len(df)-1, 0)
                    row = df.iloc[preview_idx]
                    preview_img = create_frame(
                        english=str(row['英语']),
                        chinese=str(row['中文']),
                        phonetic=str(row['音标']) if pd.notna(row['音标']) else "",
                        width=width,
                        height=height,
                        bg_color=bg_color,
                        bg_image=st.session_state.bg_image,
                        eng_color=eng_color,
                        chn_color=chn_color,
                        pho_color=pho_color,
                        eng_size=eng_size,
                        chn_size=chn_size,
                        pho_size=pho_size
                    )
                    st.image(preview_img, caption="帧预览")
                
                # 4. 生成视频
                st.header("4. 生成视频")
                if st.button("开始生成", type="primary"):
                    with st.spinner("正在生成视频..."):
                        try:
                            with tempfile.TemporaryDirectory() as temp_dir:
                                # 生成视频帧（流式写入，避免内存溢出）
                                audio_paths = []
                                total_frames = len(df) * duration * fps
                                progress = st.progress(0)
                                current = 0
                                
                                video_path = os.path.join(temp_dir, "video_no_audio.mp4")
                                with imageio.get_writer(video_path, fps=fps) as writer:
                                    for idx, row in df.iterrows():
                                        # 生成单帧
                                        frame = create_frame(
                                            english=str(row['英语']),
                                            chinese=str(row['中文']),
                                            phonetic=str(row['音标']) if pd.notna(row['音标']) else "",
                                            width=width,
                                            height=height,
                                            bg_color=bg_color,
                                            bg_image=st.session_state.bg_image,
                                            eng_color=eng_color,
                                            chn_color=chn_color,
                                            pho_color=pho_color,
                                            eng_size=eng_size,
                                            chn_size=chn_size,
                                            pho_size=pho_size
                                        )
                                        # 直接写入帧，不缓存到列表
                                        writer.append_data(np.array(frame.convert('RGB')))
                                        # 更新进度
                                        current += 1
                                        progress.progress(min(current / total_frames, 1.0))
                                        
                                        # 生成对应音频
                                        if st.session_state.audio_available:
                                            audio_path = generate_audio(
                                                text=str(row['英语']),
                                                lang=tts_lang_code,
                                                speed=tts_speed
                                            )
                                            audio_paths.append(audio_path)
                                
                                # 处理音频
                                final_video_path = video_path  # 默认无音频
                                if st.session_state.audio_available and audio_paths:
                                    # 合并音频
                                    combined_audio = merge_audio_files(audio_paths, duration)
                                    audio_path = os.path.join(temp_dir, "combined_audio.mp3")
                                    combined_audio.export(audio_path, format="mp3")
                                    
                                    # 合并音视频
                                    final_video_path = os.path.join(temp_dir, "video_with_audio.mp4")
                                    if not merge_video_audio(video_path, audio_path, final_video_path):
                                        final_video_path = video_path  # 合并失败则使用无音频版本
                                
                                # 提供下载
                                with open(final_video_path, "rb") as f:
                                    video_bytes = f.read()
                                
                                st.success("视频生成完成！")
                                st.video(video_bytes)
                                st.download_button(
                                    "下载视频",
                                    data=video_bytes,
                                    file_name="travel_english_video.mp4",
                                    mime="video/mp4"
                                )
                                progress.progress(1.0)
                                
                        except Exception as e:
                            st.error(f"生成失败: {str(e)}")
                            st.text(traceback.format_exc())  # 显示详细错误信息
                        finally:
                            gc.collect()  # 强制垃圾回收
                            # 清理临时资源（防止内存泄漏）
                            if 'temp_dir' in locals():
                                shutil.rmtree(temp_dir, ignore_errors=True)
    
    except Exception as e:
        st.error(f"文件处理错误: {str(e)}")
else:
    st.info("请先上传包含'英语'、'中文'、'音标'三列的Excel文件")
