import os
import shutil
import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import imageio.v2 as imageio
import tempfile
import subprocess
import traceback
import asyncio
import base64
import time

# 检查 ffmpeg 是否可用
def check_ffmpeg():
    ffmpeg_path = shutil.which('ffmpeg')
    return ffmpeg_path

# 只使用 gTTS，简化依赖
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except Exception:
    GTTS_AVAILABLE = False

# 页面配置
st.set_page_config(
    page_title="旅行英语视频生成器",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #1f2937;
        margin: 1rem 0 0.5rem 0;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid #e5e7eb;
    }
    .warning-card {
        background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
    }
    .preview-section {
        background: #f8fafc;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

# 会话状态
if 'bg_image' not in st.session_state:
    st.session_state.bg_image = None

# -----------------------
# 工具函数
# -----------------------
def wrap_text(text, max_chars):
    if not text or str(text).strip().lower() == 'nan':
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
    return lines

def get_font(size, bold=False):
    """获取字体"""
    try:
        # 尝试加载系统字体
        fonts = [
            "Arial.ttf", "arial.ttf", 
            "DejaVuSans.ttf", "LiberationSans-Regular.ttf"
        ]
        
        for font in fonts:
            try:
                return ImageFont.truetype(font, size)
            except:
                continue
        
        # 使用默认字体
        return ImageFont.load_default()
    except Exception as e:
        return ImageFont.load_default()

def create_frame(english, chinese, phonetic, width=1280, height=720,
                 bg_color=(0,0,0), bg_image=None,
                 eng_color=(255,255,255), chn_color=(173,216,230), pho_color=(255,255,0),
                 eng_size=60, chn_size=45, pho_size=35,
                 text_bg_enabled=True, text_bg_color=(255,255,255,180), text_bg_padding=20,
                 text_bg_radius=20):
    """创建一帧图片 - 简化版本"""
    if bg_image:
        try:
            img = ImageOps.fit(bg_image.convert('RGB'), (width, height), Image.Resampling.LANCZOS)
        except Exception:
            img = Image.new('RGB', (width, height), bg_color)
    else:
        img = Image.new('RGB', (width, height), bg_color)

    draw = ImageDraw.Draw(img)
    
    eng_font = get_font(eng_size)
    chn_font = get_font(chn_size)
    pho_font = get_font(pho_size)

    eng_lines = wrap_text(english, 30)
    chn_lines = wrap_text(chinese, 15)
    pho_lines = wrap_text(phonetic, 35) if phonetic else []

    # 计算总高度
    total_height = 0
    for line in eng_lines:
        bbox = draw.textbbox((0,0), line, font=eng_font)
        total_height += bbox[3] - bbox[1]
    for line in pho_lines:
        bbox = draw.textbbox((0,0), line, font=pho_font)
        total_height += bbox[3] - bbox[1]
    for line in chn_lines:
        bbox = draw.textbbox((0,0), line, font=chn_font)
        total_height += bbox[3] - bbox[1]
    
    total_height += 20 * (len(eng_lines) + len(pho_lines) + len(chn_lines) - 1)  # 行间距

    # 文字背景
    if text_bg_enabled:
        max_width = 0
        for line in eng_lines:
            bbox = draw.textbbox((0,0), line, font=eng_font)
            max_width = max(max_width, bbox[2] - bbox[0])
        for line in pho_lines:
            bbox = draw.textbbox((0,0), line, font=pho_font)
            max_width = max(max_width, bbox[2] - bbox[0])
        for line in chn_lines:
            bbox = draw.textbbox((0,0), line, font=chn_font)
            max_width = max(max_width, bbox[2] - bbox[0])
        
        bg_width = max_width + text_bg_padding * 2
        bg_height = total_height + text_bg_padding * 2
        
        bg_x = (width - bg_width) // 2
        bg_y = (height - bg_height) // 2
        
        bg_layer = Image.new('RGBA', (bg_width, bg_height), (0,0,0,0))
        bg_draw = ImageDraw.Draw(bg_layer)
        
        bg_draw.rounded_rectangle(
            [(0, 0), (bg_width, bg_height)],
            radius=text_bg_radius,
            fill=text_bg_color
        )
        
        img.paste(bg_layer, (bg_x, bg_y), bg_layer)

    # 绘制文字
    y = (height - total_height) // 2

    for line in eng_lines:
        bbox = draw.textbbox((0,0), line, font=eng_font)
        w = bbox[2] - bbox[0]
        x = (width - w) // 2
        draw.text((x, y), line, font=eng_font, fill=eng_color)
        y += bbox[3] - bbox[1] + 20

    for line in pho_lines:
        bbox = draw.textbbox((0,0), line, font=pho_font)
        w = bbox[2] - bbox[0]
        x = (width - w) // 2
        draw.text((x, y), line, font=pho_font, fill=pho_color)
        y += bbox[3] - bbox[1] + 20

    for line in chn_lines:
        bbox = draw.textbbox((0,0), line, font=chn_font)
        w = bbox[2] - bbox[0]
        x = (width - w) // 2
        draw.text((x, y), line, font=chn_font, fill=chn_color)
        y += bbox[3] - bbox[1] + 20

    return img

# -----------------------
# 音频处理函数 - 简化版本
# -----------------------
def create_silent_audio(duration, output_path):
    """创建静音音频文件"""
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration), "-acodec", "libmp3lame", output_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        return False

def generate_gtts_audio_safe(text, lang='en', out_path=None):
    """安全的gTTS生成函数，带重试机制"""
    if not GTTS_AVAILABLE:
        return None
    
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix='.mp3')
        os.close(fd)
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(out_path)
            
            # 检查文件
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:  # 确保文件不是空的
                return out_path
            else:
                time.sleep(1)  # 等待后重试
        except Exception as e:
            if attempt == max_retries - 1:
                break
            time.sleep(1)
    
    # 所有尝试都失败，创建静音
    silent_path = tempfile.mktemp(suffix='.mp3')
    if create_silent_audio(3.0, silent_path):
        return silent_path
    
    return None

def merge_audio_files_simple(audio_paths, output_path):
    """简化音频合并"""
    if not check_ffmpeg():
        return None
    
    with tempfile.TemporaryDirectory() as tmpdir:
        list_file = os.path.join(tmpdir, "audio_list.txt")
        
        with open(list_file, 'w') as f:
            for audio_path in audio_paths:
                if audio_path and os.path.exists(audio_path):
                    f.write(f"file '{audio_path}'\n")
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", output_path
        ]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return output_path if os.path.exists(output_path) else None
        except Exception:
            return None

def merge_video_audio_simple(video_path, audio_path, output_path):
    """简化视频音频合并"""
    if not check_ffmpeg():
        return None
        
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path if os.path.exists(output_path) else None
    except Exception:
        return None

# -----------------------
# 视频生成函数 - 优化版本
# -----------------------
def generate_video_optimized(df, settings, progress_bar, status_placeholder):
    """优化的视频生成函数，减少内存使用"""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 使用较低的分辨率以减少内存使用
            width = min(settings.get('width', 1280), 1280)
            height = min(settings.get('height', 720), 720)
            fps = settings.get('fps', 15)  # 降低帧率
            per_duration = settings.get('per_duration', 3)
            
            video_no_audio = os.path.join(tmpdir, "video_no_audio.mp4")
            final_video = os.path.join(tmpdir, "final_video.mp4")
            
            # 限制处理的数据量
            max_rows = min(len(df), 20)  # 最多处理20行
            df_limited = df.head(max_rows)
            
            if len(df) > max_rows:
                st.warning(f"为了稳定性，只处理前 {max_rows} 行数据（共 {len(df)} 行）")
            
            total_segments = len(df_limited) * 4  # 每行4段
            progress_steps = total_segments + 10  # 进度步骤总数
            
            # 生成音频 - 分批处理
            status_placeholder.info("🎵 正在生成音频（分批处理）...")
            audio_paths = []
            current_step = 0
            
            for i, row in df_limited.iterrows():
                eng = str(row['英语'])
                chn = str(row['中文'])
                
                # 为每行生成4段音频
                for segment_type in ['英文', '中文', '英文', '中文']:
                    text_to_speak = eng if segment_type == '英文' else chn
                    lang = 'en' if segment_type == '英文' else 'zh-CN'
                    
                    audio_file = generate_gtts_audio_safe(text_to_speak, lang)
                    audio_paths.append(audio_file)
                    
                    current_step += 1
                    progress_bar.progress(current_step / progress_steps)
                    
                    # 每生成几个音频就稍微暂停，避免服务器过载
                    if current_step % 4 == 0:
                        time.sleep(0.5)
            
            # 生成视频帧
            status_placeholder.info("🎬 正在生成视频帧...")
            writer = imageio.get_writer(video_no_audio, fps=fps, macro_block_size=1, format='FFMPEG', codec='libx264')
            
            per_duration_frames = int(per_duration * fps)
            
            for i, row in df_limited.iterrows():
                eng = str(row['英语'])
                chn = str(row['中文'])
                pho = str(row['音标']) if pd.notna(row['音标']) else ""
                
                frame_img = create_frame(
                    english=eng, chinese=chn, phonetic=pho,
                    width=width, height=height,
                    bg_color=settings.get('bg_color', (0,0,0)),
                    bg_image=settings.get('bg_image'),
                    eng_color=settings.get('eng_color', (255,255,255)),
                    chn_color=settings.get('chn_color', (173,216,230)),
                    pho_color=settings.get('pho_color', (255,255,0)),
                    eng_size=settings.get('eng_size', 60),
                    chn_size=settings.get('chn_size', 45),
                    pho_size=settings.get('pho_size', 35)
                )
                
                frame_array = np.array(frame_img.convert('RGB'))
                
                # 为每行重复帧（4段）
                for _ in range(4):
                    for frame_idx in range(per_duration_frames):
                        writer.append_data(frame_array)
                        current_step += 1/progress_steps
                        if frame_idx % 5 == 0:  # 每5帧更新一次进度
                            progress_bar.progress(min(current_step / progress_steps, 0.9))
            
            writer.close()
            
            # 合并音频
            status_placeholder.info("🔊 正在合并音频...")
            valid_audio_paths = [p for p in audio_paths if p and os.path.exists(p)]
            
            if valid_audio_paths:
                combined_audio = os.path.join(tmpdir, "combined.mp3")
                if merge_audio_files_simple(valid_audio_paths, combined_audio):
                    # 合并视频和音频
                    status_placeholder.info("🎵 正在合并视频和音频...")
                    if merge_video_audio_simple(video_no_audio, combined_audio, final_video):
                        progress_bar.progress(1.0)
                        with open(final_video, "rb") as f:
                            return f.read()
            
            # 如果音频合并失败，返回无声视频
            progress_bar.progress(1.0)
            with open(video_no_audio, "rb") as f:
                return f.read()
                
    except Exception as e:
        st.error(f"生成过程中出错: {str(e)}")
        return None

# -----------------------
# UI 与主流程 - 简化版本
# -----------------------
st.markdown('<h1 class="main-header">🎬 旅行英语视频生成器</h1>', unsafe_allow_html=True)
st.markdown("### 简化稳定版本 • 适合在线使用")

# 系统检查
with st.sidebar:
    st.markdown("## 🔧 系统状态")
    if check_ffmpeg():
        st.success("✅ FFmpeg 可用")
    else:
        st.error("❌ FFmpeg 不可用")
    
    if GTTS_AVAILABLE:
        st.success("✅ gTTS 可用")
    else:
        st.error("❌ gTTS 不可用")

# 上传 Excel
st.markdown('<div class="section-header">📁 1. 上传数据文件</div>', unsafe_allow_html=True)

uploaded = st.file_uploader(
    "选择 Excel 文件",
    type=["xlsx", "xls"],
    help="必须包含列：英语、中文、音标",
    key="excel_uploader"
)

if uploaded:
    try:
        df = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"读取 Excel 失败：{e}")
        df = None
else:
    df = None

if df is not None:
    required = ['英语','中文','音标']
    miss = [c for c in required if c not in df.columns]
    if miss:
        st.error(f"Excel 缺少列：{', '.join(miss)}")
        st.stop()
    
    # 数据预览
    st.markdown('<div class="preview-section">', unsafe_allow_html=True)
    st.subheader("📊 数据预览")
    st.dataframe(df.head(5), height=150, use_container_width=True)
    st.info(f"📈 共 {len(df)} 行数据")
    st.markdown('</div>', unsafe_allow_html=True)

    # 简单设置
    st.markdown('<div class="section-header">🎨 2. 视频设置</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        bg_type = st.radio("背景类型", ["纯色", "图片"], horizontal=True)
        if bg_type == "纯色":
            bg_color_hex = st.color_picker("背景颜色", "#000000")
            bg_color = tuple(int(bg_color_hex[i:i+2],16) for i in (1,3,5))
            bg_image = None
        else:
            bg_file = st.file_uploader("上传背景图片", type=["jpg","jpeg","png"])
            if bg_file:
                try:
                    bg_image = Image.open(bg_file)
                    st.image(bg_image, caption="背景预览", use_container_width=True)
                except Exception as e:
                    st.error(f"打开背景图片失败：{e}")
                    bg_image = None
            bg_color = (0,0,0)
    
    with col2:
        per_duration = st.slider("每段时长（秒）", 2, 5, 3)
        resolution = st.selectbox("分辨率", ["640x360", "854x480", "1280x720"], index=1)
        width, height = map(int, resolution.split('x'))

    # 生成按钮
    st.markdown('<div class="section-header">🚀 3. 生成视频</div>', unsafe_allow_html=True)
    
    if len(df) > 20:
        st.markdown(f'<div class="warning-card">⚠️ 数据量较大，为了稳定性将只处理前20行数据</div>', unsafe_allow_html=True)
    
    if st.button("🎬 开始生成视频", use_container_width=True, type="primary"):
        if not GTTS_AVAILABLE:
            st.error("gTTS 不可用，无法生成音频")
            st.stop()
        
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        
        with st.spinner("正在生成视频，请耐心等待..."):
            settings = {
                'width': width,
                'height': height,
                'fps': 15,
                'per_duration': per_duration,
                'bg_color': bg_color,
                'bg_image': bg_image,
                'eng_color': (255,255,255),
                'chn_color': (173,216,230),
                'pho_color': (255,255,0),
                'eng_size': 60,
                'chn_size': 45,
                'pho_size': 35
            }
            
            video_bytes = generate_video_optimized(df, settings, progress_bar, status_placeholder)
            
            if video_bytes:
                status_placeholder.success("✅ 视频生成完成！")
                
                # 显示视频
                st.video(video_bytes)
                
                # 下载按钮
                st.download_button(
                    label="📥 下载视频",
                    data=video_bytes,
                    file_name="english_video.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )
            else:
                status_placeholder.error("视频生成失败")

# 页脚
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "🎬 旅行英语视频生成器 | 优化稳定版本"
    "</div>", 
    unsafe_allow_html=True
)

# 隐藏 Streamlit 默认菜单和页脚
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display:none;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
