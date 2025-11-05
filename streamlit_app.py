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

# 尝试导入各种TTS库
EDGE_TTS_AVAILABLE = False
PYTTSX3_AVAILABLE = False
GTTS_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except Exception:
    PYTTSX3_AVAILABLE = False

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
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1f2937;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e5e7eb;
    }
    .info-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
    .success-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
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
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    .upload-section {
        border: 2px dashed #667eea;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        background: rgba(102, 126, 234, 0.05);
        margin: 1rem 0;
    }
    .preview-section {
        background: #f8fafc;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
    }
    .setting-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid #e5e7eb;
        margin: 0.5rem 0;
    }
    .voice-preview-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.5rem 1rem !important;
        font-size: 0.9rem !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        border-radius: 4px 4px 0px 0px;
        gap: 0px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 会话状态
if 'bg_image' not in st.session_state:
    st.session_state.bg_image = None
if 'tts_method' not in st.session_state:
    st.session_state.tts_method = "edge_tts"

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

def get_phonetic_font(size, bold=False):
    """专门用于音标显示的字体加载函数"""
    try:
        font_files = [
            "DoulosSIL-R.ttf", "CharisSIL-R.ttf", "NotoSansIPA-Regular.ttf",
            "ArialUni.ttf", "l_10646.ttf", "DejaVuSans.ttf",
        ]
        
        system_font_paths = [
            "/usr/share/fonts/", "C:/Windows/Fonts/", 
            "~/Library/Fonts/", "/Library/Fonts/",
        ]
        
        if bold:
            bold_fonts = [
                "DoulosSIL-B.ttf", "CharisSIL-B.ttf", "NotoSansIPA-Bold.ttf",
                "ArialUniBold.ttf", "DejaVuSans-Bold.ttf",
            ]
            for font in bold_fonts:
                try:
                    return ImageFont.truetype(font, size)
                except:
                    pass
        
        for font in font_files:
            try:
                return ImageFont.truetype(font, size)
            except:
                pass
        
        return ImageFont.load_default()
    except Exception as e:
        return ImageFont.load_default()

def get_font(size, font_type="default", bold=False):
    """获取字体，支持音标符号和中文"""
    if font_type == "phonetic":
        return get_phonetic_font(size, bold)
    
    try:
        chinese_fonts = [
            "simhei.ttf", "msyh.ttc", "simsun.ttc", "STHeiti Light.ttc",
            "PingFang.ttc", "Arial Unicode MS", "SimHei", "Microsoft YaHei",
            "WenQuanYi Micro Hei", "NotoSansCJK-Regular.ttc",
        ]
        
        if bold:
            bold_fonts = [
                "simhei.ttf", "msyhbd.ttc", "STHeiti Medium.ttc",
                "PingFang SC Semibold.ttc", "Arial Unicode MS", "SimHei",
            ]
            for f in bold_fonts:
                try:
                    return ImageFont.truetype(f, size)
                except Exception:
                    continue
        
        for f in chinese_fonts:
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
        
        return ImageFont.load_default()
    except Exception as e:
        return ImageFont.load_default()

def create_frame(english, chinese, phonetic, width=1920, height=1080,
                 bg_color=(0,0,0), bg_image=None,
                 eng_color=(255,255,255), chn_color=(173,216,230), pho_color=(255,255,0),
                 eng_size=80, chn_size=60, pho_size=50,
                 text_bg_enabled=False, text_bg_color=(255,255,255,180), text_bg_padding=20,
                 text_bg_radius=30, text_bg_width=None, text_bg_height=None,
                 bold_text=True, eng_pho_spacing=30, pho_chn_spacing=30, line_spacing=15):
    """创建一帧图片"""
    if bg_image:
        try:
            img = ImageOps.fit(bg_image.convert('RGB'), (width, height), Image.Resampling.LANCZOS)
        except Exception:
            img = Image.new('RGB', (width, height), bg_color)
    else:
        img = Image.new('RGB', (width, height), bg_color)

    draw = ImageDraw.Draw(img)
    
    eng_font = get_font(eng_size, "phonetic", bold=bold_text)
    chn_font = get_font(chn_size, "chinese", bold=bold_text)
    pho_font = get_font(pho_size, "phonetic", bold=bold_text)

    eng_lines = wrap_text(english, 40)
    chn_lines = wrap_text(chinese, 20)
    pho_lines = wrap_text(phonetic, 45) if phonetic else []

    total_height = 0

    for line in eng_lines:
        bbox = draw.textbbox((0,0), line, font=eng_font)
        h = bbox[3] - bbox[1]
        total_height += h
    total_height += line_spacing * (len(eng_lines)-1)

    if pho_lines:
        total_height += eng_pho_spacing
        for line in pho_lines:
            bbox = draw.textbbox((0,0), line, font=pho_font)
            h = bbox[3] - bbox[1]
            total_height += h
        total_height += line_spacing * (len(pho_lines)-1)

    if chn_lines:
        total_height += pho_chn_spacing
        for line in chn_lines:
            bbox = draw.textbbox((0,0), line, font=chn_font)
            h = bbox[3] - bbox[1]
            total_height += h
        total_height += line_spacing * (len(chn_lines)-1)

    if text_bg_enabled:
        max_width = 0
        for line in eng_lines:
            bbox = draw.textbbox((0,0), line, font=eng_font)
            w = bbox[2] - bbox[0]
            max_width = max(max_width, w)
        for line in pho_lines:
            bbox = draw.textbbox((0,0), line, font=pho_font)
            w = bbox[2] - bbox[0]
            max_width = max(max_width, w)
        for line in chn_lines:
            bbox = draw.textbbox((0,0), line, font=chn_font)
            w = bbox[2] - bbox[0]
            max_width = max(max_width, w)
        
        if text_bg_width is None:
            bg_width = max_width + text_bg_padding * 2
        else:
            bg_width = text_bg_width
            
        if text_bg_height is None:
            bg_height = total_height + text_bg_padding * 2
        else:
            bg_height = text_bg_height
        
        bg_x = (width - bg_width) // 2
        bg_y = (height - bg_height) // 2
        
        bg_layer = Image.new('RGBA', (bg_width, bg_height), (0,0,0,0))
        bg_draw = ImageDraw.Draw(bg_layer)
        
        if text_bg_radius > 0:
            bg_draw.rounded_rectangle(
                [(0, 0), (bg_width, bg_height)],
                radius=text_bg_radius,
                fill=text_bg_color
            )
        else:
            bg_draw.rectangle(
                [(0, 0), (bg_width, bg_height)],
                fill=text_bg_color
            )
        
        img.paste(bg_layer, (bg_x, bg_y), bg_layer)

    y = (height - total_height)//2

    for line in eng_lines:
        bbox = draw.textbbox((0,0), line, font=eng_font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (width - w)//2
        shadow_offset = 3
        draw.text((x+shadow_offset, y+shadow_offset), line, font=eng_font, fill=(0,0,0,128))
        draw.text((x, y), line, font=eng_font, fill=eng_color)
        y += h + line_spacing

    if pho_lines:
        y += eng_pho_spacing
        for line in pho_lines:
            bbox = draw.textbbox((0,0), line, font=pho_font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            x = (width - w)//2
            shadow_offset = 3
            draw.text((x+shadow_offset, y+shadow_offset), line, font=pho_font, fill=(0,0,0,128))
            draw.text((x, y), line, font=pho_font, fill=pho_color)
            y += h + line_spacing

    if chn_lines:
        y += pho_chn_spacing
        for line in chn_lines:
            bbox = draw.textbbox((0,0), line, font=chn_font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            x = (width - w)//2
            shadow_offset = 3
            draw.text((x+shadow_offset, y+shadow_offset), line, font=chn_font, fill=(0,0,0,128))
            draw.text((x, y), line, font=chn_font, fill=chn_color)
            y += h + line_spacing

    return img

# -----------------------
# TTS 服务 - 多方案支持
# -----------------------
VOICE_OPTIONS = {
    "English - Female (US) - Aria": "en-US-AriaNeural",
    "English - Female (US) - Jenny": "en-US-JennyNeural",
    "English - Male (US) - Guy": "en-US-GuyNeural",
    "English - Male (US) - Davis": "en-US-DavisNeural",
    "Chinese - Female (CN) - Xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "Chinese - Female (CN) - Xiaoyi": "zh-CN-XiaoyiNeural",
    "Chinese - Male (CN) - Yunxi": "zh-CN-YunxiNeural",
}

# Edge TTS
async def _edge_tts_save(text: str, voice_name: str, out_path: str, rate: str = "+0%"):
    try:
        communicate = edge_tts.Communicate(text, voice_name, rate=rate)
        await communicate.save(out_path)
        return True
    except Exception as e:
        st.error(f"Edge TTS生成失败: {e}")
        return False

def generate_edge_audio(text, voice, speed=1.0, out_path=None):
    if not EDGE_TTS_AVAILABLE:
        return None
    
    pct = int((speed - 1.0) * 100)
    rate_str = f"{pct:+d}%"
    
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix='.mp3')
        os.close(fd)
    
    try:
        success = asyncio.run(_edge_tts_save(text, voice, out_path, rate_str))
        if success and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
        else:
            if os.path.exists(out_path):
                os.unlink(out_path)
            return None
    except Exception as e:
        if os.path.exists(out_path):
            os.unlink(out_path)
        return None

# pyttsx3 TTS (离线)
def generate_pyttsx3_audio(text, out_path=None):
    if not PYTTSX3_AVAILABLE:
        return None
    
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix='.mp3')
        os.close(fd)
    
    try:
        engine = pyttsx3.init()
        
        # 设置属性
        engine.setProperty('rate', 150)  # 语速
        engine.setProperty('volume', 0.9)  # 音量
        
        # 保存到文件
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        
        # 等待文件生成
        time.sleep(1)
        
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
        else:
            if os.path.exists(out_path):
                os.unlink(out_path)
            return None
    except Exception as e:
        st.error(f"pyttsx3 TTS生成失败: {e}")
        if os.path.exists(out_path):
            os.unlink(out_path)
        return None

# gTTS (Google TTS)
def generate_gtts_audio(text, lang='en', out_path=None):
    if not GTTS_AVAILABLE:
        return None
    
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix='.mp3')
        os.close(fd)
    
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(out_path)
        
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
        else:
            if os.path.exists(out_path):
                os.unlink(out_path)
            return None
    except Exception as e:
        st.error(f"gTTS生成失败: {e}")
        if os.path.exists(out_path):
            os.unlink(out_path)
        return None

# 统一的TTS生成函数
def generate_audio_with_fallback(text, voice_info, tts_method, speed=1.0):
    """使用多种TTS方法生成音频，有备用方案"""
    
    # 根据语音类型判断语言
    if "Chinese" in voice_info or "zh-" in voice_info:
        lang = 'zh'
    else:
        lang = 'en'
    
    out_path = tempfile.mktemp(suffix='.mp3')
    
    # 根据选择的TTS方法生成音频
    if tts_method == "edge_tts" and EDGE_TTS_AVAILABLE:
        result = generate_edge_audio(text, voice_info, speed, out_path)
        if result:
            return result
    
    if tts_method == "pyttsx3" and PYTTSX3_AVAILABLE:
        result = generate_pyttsx3_audio(text, out_path)
        if result:
            return result
    
    if tts_method == "gtts" and GTTS_AVAILABLE:
        result = generate_gtts_audio(text, lang, out_path)
        if result:
            return result
    
    # 如果所有方法都失败，尝试其他可用方法
    if EDGE_TTS_AVAILABLE and tts_method != "edge_tts":
        result = generate_edge_audio(text, voice_info, speed, out_path)
        if result:
            return result
    
    if PYTTSX3_AVAILABLE and tts_method != "pyttsx3":
        result = generate_pyttsx3_audio(text, out_path)
        if result:
            return result
    
    if GTTS_AVAILABLE and tts_method != "gtts":
        result = generate_gtts_audio(text, lang, out_path)
        if result:
            return result
    
    # 所有方法都失败
    return None

# -----------------------
# 音频处理函数
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

def merge_audio_files(audio_paths, per_duration, pause_duration, output_path):
    """合并音频文件"""
    if not check_ffmpeg():
        return None
    
    with tempfile.TemporaryDirectory() as tmpdir:
        list_file = os.path.join(tmpdir, "audio_list.txt")
        
        valid_files = []
        
        with open(list_file, 'w') as f:
            for i, audio_path in enumerate(audio_paths):
                if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                    f.write(f"file '{audio_path}'\n")
                    valid_files.append(audio_path)
                    
                    if i < len(audio_paths) - 1 and pause_duration > 0:
                        pause_audio = os.path.join(tmpdir, f"pause_{i}.mp3")
                        if create_silent_audio(pause_duration, pause_audio):
                            f.write(f"file '{pause_audio}'\n")
                            valid_files.append(pause_audio)
                else:
                    silent_audio = os.path.join(tmpdir, f"silent_{i}.mp3")
                    if create_silent_audio(per_duration, silent_audio):
                        f.write(f"file '{silent_audio}'\n")
                        valid_files.append(silent_audio)
        
        if not valid_files:
            return None
            
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", output_path
        ]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            else:
                return None
        except Exception:
            return None

def merge_video_audio(video_path, audio_path, output_path):
    """合并视频和音频"""
    if not check_ffmpeg():
        return None
        
    if not os.path.exists(video_path) or not os.path.exists(audio_path):
        return None
        
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-strict", "experimental",
        "-shortest",
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
        else:
            return None
    except Exception:
        return None

# -----------------------
# 视频生成函数
# -----------------------
def generate_video_with_optimization(df, settings, progress_bar, status_placeholder):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            video_no_audio = os.path.join(tmpdir, "video_no_audio.mp4")
            final_video = os.path.join(tmpdir, "final_video.mp4")
            
            width = settings['width']
            height = settings['height']
            fps = settings['fps']
            per_duration = settings['per_duration']
            pause_duration = settings['pause_duration']
            bg_color = settings['bg_color']
            bg_image = settings['bg_image']
            eng_color = settings['eng_color']
            chn_color = settings['chn_color']
            pho_color = settings['pho_color']
            eng_size = settings['eng_size']
            chn_size = settings['chn_size']
            pho_size = settings['pho_size']
            text_bg_enabled = settings['text_bg_enabled']
            text_bg_color = settings['text_bg_color']
            text_bg_padding = settings['text_bg_padding']
            text_bg_radius = settings['text_bg_radius']
            text_bg_width = settings['text_bg_width']
            text_bg_height = settings['text_bg_height']
            bold_text = settings['bold_text']
            segment_order = settings['segment_order']
            voice_mapping = settings['voice_mapping']
            tts_speed = settings['tts_speed']
            tts_method = settings['tts_method']
            eng_pho_spacing = settings['eng_pho_spacing']
            pho_chn_spacing = settings['pho_chn_spacing']
            line_spacing = settings['line_spacing']
            
            per_duration_frames = int(round(per_duration * fps))
            pause_duration_frames = int(round(pause_duration * fps))
            
            total_segments = len(df) * len(segment_order)
            total_frames = total_segments * per_duration_frames + (total_segments - 1) * pause_duration_frames
            current_frame = 0
            
            writer = None
            audio_paths = []
            
            try:
                # 生成音频
                status_placeholder.info("🎵 正在生成音频...")
                audio_count = 0
                total_audio_count = len(df) * len(segment_order)
                
                for i, row in df.iterrows():
                    eng = str(row['英语'])
                    chn = str(row['中文'])
                    
                    for j, segment_type in enumerate(segment_order):
                        voice_info, text_type = voice_mapping[segment_type]
                        text_to_speak = eng if text_type == "english" else chn
                        
                        # 使用统一的TTS生成函数
                        audio_file = generate_audio_with_fallback(text_to_speak, voice_info, tts_method, tts_speed)
                        
                        if audio_file and os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
                            audio_paths.append(audio_file)
                            st.success(f"✅ 音频 {audio_count+1}/{total_audio_count} 生成成功")
                        else:
                            # 生成失败时使用静音
                            silent_audio = os.path.join(tmpdir, f"silent_{i}_{j}.mp3")
                            if create_silent_audio(per_duration, silent_audio):
                                audio_paths.append(silent_audio)
                                st.warning(f"⚠️ 音频 {audio_count+1}/{total_audio_count} 生成失败，使用静音替代")
                            else:
                                audio_paths.append(None)
                        
                        audio_count += 1
                        audio_progress = audio_count / total_audio_count * 0.4
                        progress_bar.progress(audio_progress)
                
                # 生成视频帧
                status_placeholder.info("🎬 正在生成视频...")
                writer = imageio.get_writer(video_no_audio, fps=fps, macro_block_size=1, format='FFMPEG', codec='libx264')
                
                for i, row in df.iterrows():
                    eng = str(row['英语'])
                    chn = str(row['中文'])
                    pho = str(row['音标']) if pd.notna(row['音标']) else ""
                    
                    frame_img = create_frame(
                        english=eng, chinese=chn, phonetic=pho,
                        width=width, height=height,
                        bg_color=bg_color, bg_image=bg_image,
                        eng_color=eng_color, chn_color=chn_color, pho_color=pho_color,
                        eng_size=eng_size, chn_size=chn_size, pho_size=pho_size,
                        text_bg_enabled=text_bg_enabled,
                        text_bg_color=text_bg_color,
                        text_bg_padding=text_bg_padding,
                        text_bg_radius=text_bg_radius,
                        text_bg_width=text_bg_width,
                        text_bg_height=text_bg_height,
                        bold_text=bold_text,
                        eng_pho_spacing=eng_pho_spacing,
                        pho_chn_spacing=pho_chn_spacing,
                        line_spacing=line_spacing
                    )
                    
                    frame_array = np.array(frame_img.convert('RGB'))
                    
                    for segment_idx in range(len(segment_order)):
                        for _ in range(per_duration_frames):
                            writer.append_data(frame_array)
                            current_frame += 1
                            if current_frame % 10 == 0:
                                video_progress = 0.4 + 0.4 * (current_frame / total_frames)
                                progress_bar.progress(min(video_progress, 0.8))
                        
                        if not (i == len(df) - 1 and segment_idx == len(segment_order) - 1):
                            for _ in range(pause_duration_frames):
                                writer.append_data(frame_array)
                                current_frame += 1
                                if current_frame % 10 == 0:
                                    video_progress = 0.4 + 0.4 * (current_frame / total_frames)
                                    progress_bar.progress(min(video_progress, 0.8))
            
            except Exception as e:
                st.error(f"生成视频过程中出错: {e}")
                return None
            finally:
                if writer is not None:
                    writer.close()
            
            if not os.path.exists(video_no_audio) or os.path.getsize(video_no_audio) == 0:
                st.error("无声视频生成失败")
                return None
            
            # 合并音频
            status_placeholder.info("🔊 正在合并音频...")
            progress_bar.progress(0.85)
            
            valid_audio_paths = [p for p in audio_paths if p is not None and os.path.exists(p) and os.path.getsize(p) > 0]
            
            if valid_audio_paths and check_ffmpeg():
                st.info(f"找到 {len(valid_audio_paths)}/{len(audio_paths)} 个有效音频文件")
                
                combined_audio_path = os.path.join(tmpdir, "combined_audio.mp3")
                merged_audio = merge_audio_files(valid_audio_paths, per_duration, pause_duration, combined_audio_path)
                
                if merged_audio and os.path.exists(merged_audio) and os.path.getsize(merged_audio) > 0:
                    status_placeholder.info("🎵 正在合并视频和音频...")
                    progress_bar.progress(0.95)
                    
                    merged_video = merge_video_audio(video_no_audio, merged_audio, final_video)
                    if merged_video:
                        final_video = merged_video
                        progress_bar.progress(1.0)
                        st.success("✅ 视频和音频合并成功！")
                    else:
                        st.warning("视频音频合并失败，将使用无声视频")
                        final_video = video_no_audio
                else:
                    st.warning("音频合并失败，将使用无声视频")
                    final_video = video_no_audio
            else:
                st.warning("没有有效的音频文件，将使用无声视频")
                final_video = video_no_audio
            
            if os.path.exists(final_video) and os.path.getsize(final_video) > 0:
                with open(final_video, "rb") as f:
                    video_bytes = f.read()
                return video_bytes
            else:
                st.error("生成的视频文件不存在或为空")
                return None
                
    except Exception as e:
        st.error(f"生成失败: {e}")
        return None

# -----------------------
# UI 与主流程
# -----------------------
st.markdown('<h1 class="main-header">🎬 旅行英语视频生成器</h1>', unsafe_allow_html=True)
st.markdown("### 多音色循环播放 • 专业级视频制作")

# 系统检查
with st.sidebar:
    st.markdown("## 🔧 系统检查")
    ffmpeg_available = check_ffmpeg()
    
    st.markdown("## 🎵 TTS 服务状态")
    if EDGE_TTS_AVAILABLE:
        st.success("✅ Edge TTS 可用")
    else:
        st.error("❌ Edge TTS 不可用")
    
    if PYTTSX3_AVAILABLE:
        st.success("✅ pyttsx3 (离线) 可用")
    else:
        st.warning("⚠️ pyttsx3 不可用")
    
    if GTTS_AVAILABLE:
        st.success("✅ gTTS (Google) 可用")
    else:
        st.warning("⚠️ gTTS 不可用")

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
    st.dataframe(df.head(10), height=220, use_container_width=True)
    st.info(f"📈 共 {len(df)} 行数据，预计生成 {len(df) * 4} 段音频")
    st.markdown('</div>', unsafe_allow_html=True)

    # 设置面板
    st.markdown('<div class="section-header">🎨 2. 自定义设置</div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["🎨 样式设置", "🔊 音频设置", "📝 文字背景", "⚙️ 视频参数"])
    
    with tab1:
        col_bg, col_txt = st.columns([1, 2])
        
        with col_bg:
            st.subheader("🎨 背景设置")
            bg_type = st.radio("背景类型", ["纯色", "图片"], horizontal=True, key="bg_type")
            if bg_type == "纯色":
                bg_hex = st.color_picker("背景颜色", "#000000", key="bg_color_picker")
                bg_color = tuple(int(bg_hex[i:i+2],16) for i in (1,3,5))
                st.session_state.bg_image = None
            else:
                bg_file = st.file_uploader("上传背景图片", type=["jpg","jpeg","png"], key="bg_image_uploader")
                if bg_file:
                    try:
                        st.session_state.bg_image = Image.open(bg_file)
                        st.image(st.session_state.bg_image, caption="背景预览", use_container_width=True)
                    except Exception as e:
                        st.error(f"打开背景图片失败：{e}")
                        st.session_state.bg_image = None
                bg_color = (0,0,0)

        with col_txt:
            st.subheader("📝 文字样式")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**英语设置**")
                eng_color = st.color_picker("颜色", "#FFFFFF", key="eng_color")
                eng_color = tuple(int(eng_color[i:i+2],16) for i in (1,3,5))
                eng_size = st.slider("字号", 20, 120, 80, key="eng_size")
            with c2:
                st.markdown("**音标设置**")
                pho_color = st.color_picker("颜色", "#FFFF00", key="pho_color")
                pho_color = tuple(int(pho_color[i:i+2],16) for i in (1,3,5))
                pho_size = st.slider("字号", 16, 100, 50, key="pho_size")
            with c3:
                st.markdown("**中文设置**")
                chn_color = st.color_picker("颜色", "#ADD8E6", key="chn_color")
                chn_color = tuple(int(chn_color[i:i+2],16) for i in (1,3,5))
                chn_size = st.slider("字号", 20, 120, 60, key="chn_size")
            
            bold_text = st.checkbox("文字加粗", value=True, key="bold_text")
            
            st.markdown("---")
            st.subheader("📏 文字间距设置")
            col_spacing1, col_spacing2, col_spacing3 = st.columns(3)
            with col_spacing1:
                eng_pho_spacing = st.slider("英语-音标间距", 10, 100, 30, key="eng_pho_spacing")
            with col_spacing2:
                pho_chn_spacing = st.slider("音标-中文间距", 10, 100, 50, key="pho_chn_spacing")
            with col_spacing3:
                line_spacing = st.slider("行内间距", 5, 50, 15, key="line_spacing")

    with tab2:
        st.subheader("🔊 TTS 服务选择")
        
        # TTS方法选择
        tts_options = []
        if EDGE_TTS_AVAILABLE:
            tts_options.append("Edge TTS (推荐)")
        if PYTTSX3_AVAILABLE:
            tts_options.append("pyttsx3 (离线)")
        if GTTS_AVAILABLE:
            tts_options.append("gTTS (Google)")
        
        if not tts_options:
            st.error("❌ 没有可用的TTS服务，请安装至少一个TTS库")
            st.stop()
        
        tts_method_display = st.selectbox(
            "选择TTS服务",
            tts_options,
            key="tts_method_display"
        )
        
        # 映射显示名称到内部名称
        tts_method_mapping = {
            "Edge TTS (推荐)": "edge_tts",
            "pyttsx3 (离线)": "pyttsx3", 
            "gTTS (Google)": "gtts"
        }
        tts_method = tts_method_mapping[tts_method_display]
        st.session_state.tts_method = tts_method
        
        st.subheader("🎵 播放顺序设置")
        
        col_order1, col_order2, col_order3, col_order4 = st.columns(4)
        with col_order1:
            segment1_type = st.selectbox("第1段", ["英文男声", "英文女声", "中文音色"], index=0, key="segment1")
        with col_order2:
            segment2_type = st.selectbox("第2段", ["英文男声", "英文女声", "中文音色"], index=1, key="segment2")
        with col_order3:
            segment3_type = st.selectbox("第3段", ["英文男声", "英文女声", "中文音色"], index=2, key="segment3")
        with col_order4:
            segment4_type = st.selectbox("第4段", ["英文男声", "英文女声", "中文音色"], index=0, key="segment4")
        
        st.markdown(f'<div class="success-card">🎵 播放顺序：{segment1_type} → {segment2_type} → {segment3_type} → {segment4_type}</div>', unsafe_allow_html=True)

        st.subheader("🎙️ 音色选择")
        
        col_voice1, col_voice2, col_voice3 = st.columns(3)
        
        with col_voice1:
            st.markdown("**英文男声**")
            male_english_voices = {k:v for k,v in VOICE_OPTIONS.items() if "Male" in k and "English" in k}
            male_english_label = st.selectbox("选择男声音色", list(male_english_voices.keys()), index=0, key="male_voice")
            male_english_voice = male_english_voices[male_english_label]

        with col_voice2:
            st.markdown("**英文女声**")
            female_english_voices = {k:v for k,v in VOICE_OPTIONS.items() if "Female" in k and "English" in k}
            female_english_label = st.selectbox("选择女声音色", list(female_english_voices.keys()), index=0, key="female_voice")
            female_english_voice = female_english_voices[female_english_label]

        with col_voice3:
            st.markdown("**中文音色**")
            chinese_voices = {k:v for k,v in VOICE_OPTIONS.items() if "Chinese" in k}
            chinese_label = st.selectbox("选择中文音色", list(chinese_voices.keys()), index=0, key="chinese_voice")
            chinese_voice = chinese_voices[chinese_label]

        col_speed, col_pause = st.columns(2)
        with col_speed:
            tts_speed = st.slider("语速调节", 0.5, 2.0, 1.0, 0.1, key="tts_speed")
            st.info(f"当前语速: {tts_speed}x")
        with col_pause:
            pause_duration = st.slider("每组停顿时间（秒）", 0.0, 3.0, 0.5, 0.1, key="pause_duration")

    with tab3:
        st.subheader("🖼️ 文字背景区域")
        text_bg_enabled = st.checkbox("启用文字背景区域", value=True, key="text_bg_enabled")
        if text_bg_enabled:
            col_bg_size1, col_bg_size2 = st.columns(2)
            with col_bg_size1:
                text_bg_width = st.slider("文字背景宽度", 520, 1600, 1000, key="text_bg_width")
            with col_bg_size2:
                text_bg_height = st.slider("文字背景高度", 200, 800, 400, key="text_bg_height")
                
            text_bg_hex = st.color_picker("文字背景颜色", "#FFFFFF", key="text_bg_color")
            text_bg_rgb = tuple(int(text_bg_hex[i:i+2],16) for i in (1,3,5))
            text_bg_alpha = st.slider("文字背景透明度", 0, 255, 180, key="text_bg_alpha")
            text_bg_color = text_bg_rgb + (text_bg_alpha,)
            text_bg_padding = st.slider("文字背景内边距", 10, 50, 20, key="text_bg_padding")
            text_bg_radius = st.slider("文字背景圆角", 0, 50, 30, key="text_bg_radius")
        else:
            text_bg_color = (255,255,255,180)
            text_bg_padding = 20
            text_bg_radius = 30
            text_bg_width = None
            text_bg_height = None

    with tab4:
        st.subheader("⚙️ 视频参数")
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            per_duration = st.slider("每段音频时长（秒）", 2, 8, 4, key="per_duration")
            fps = st.slider("帧率", 8, 30, 20, key="fps")
        with col_v2:
            width = st.selectbox("分辨率宽度", [640, 960, 1280, 1920], index=3, key="width")
            height = int(width * 9 / 16)
            st.info(f"分辨率: {width} × {height}")

    # 预览单行
    st.markdown('<div class="section-header">👁️ 3. 预览效果</div>', unsafe_allow_html=True)
    
    if not df.empty:
        st.markdown('<div class="preview-section">', unsafe_allow_html=True)
        col_preview1, col_preview2 = st.columns([1, 2])
        
        with col_preview1:
            idx = st.slider("选择预览行", 0, min(len(df)-1, 9), 0, key="preview_row")
            row = df.iloc[idx]
            st.write(f"**英语:** {row['英语']}")
            st.write(f"**音标:** {row['音标'] if pd.notna(row['音标']) else '无'}")
            st.write(f"**中文:** {row['中文']}")
        
        with col_preview2:
            preview_img = create_frame(
                english=str(row['英语']),
                chinese=str(row['中文']),
                phonetic=str(row['音标']) if pd.notna(row['音标']) else "",
                width=width, height=height,
                bg_color=bg_color, bg_image=st.session_state.bg_image,
                eng_color=eng_color, chn_color=chn_color, pho_color=pho_color,
                eng_size=eng_size, chn_size=chn_size, pho_size=pho_size,
                text_bg_enabled=text_bg_enabled,
                text_bg_color=text_bg_color,
                text_bg_padding=text_bg_padding,
                text_bg_radius=text_bg_radius,
                text_bg_width=text_bg_width,
                text_bg_height=text_bg_height,
                bold_text=bold_text,
                eng_pho_spacing=eng_pho_spacing,
                pho_chn_spacing=pho_chn_spacing,
                line_spacing=line_spacing
            )
            st.image(preview_img, caption="帧预览", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 生成按钮
    st.markdown('<div class="section-header">🚀 4. 生成视频</div>', unsafe_allow_html=True)
    
    if len(df) > 20:
        st.markdown(f'<div class="warning-card">⚠️ 数据量较大（{len(df)} 行），生成可能需要一些时间。建议分批处理或减少每段音频时长。</div>', unsafe_allow_html=True)
    
    col_gen1, col_gen2, col_gen3 = st.columns([1, 2, 1])
    with col_gen2:
        if st.button("🎬 开始生成视频", use_container_width=True, key="generate_button"):
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            with st.spinner("🎥 正在生成视频..."):
                voice_mapping = {
                    "英文男声": (male_english_voice, "english"),
                    "英文女声": (female_english_voice, "english"), 
                    "中文音色": (chinese_voice, "chinese")
                }
                
                segment_order = [segment1_type, segment2_type, segment3_type, segment4_type]
                
                settings = {
                    'width': width,
                    'height': height,
                    'fps': fps,
                    'per_duration': per_duration,
                    'pause_duration': pause_duration,
                    'bg_color': bg_color,
                    'bg_image': st.session_state.bg_image,
                    'eng_color': eng_color,
                    'chn_color': chn_color,
                    'pho_color': pho_color,
                    'eng_size': eng_size,
                    'chn_size': chn_size,
                    'pho_size': pho_size,
                    'text_bg_enabled': text_bg_enabled,
                    'text_bg_color': text_bg_color,
                    'text_bg_padding': text_bg_padding,
                    'text_bg_radius': text_bg_radius,
                    'text_bg_width': text_bg_width,
                    'text_bg_height': text_bg_height,
                    'bold_text': bold_text,
                    'segment_order': segment_order,
                    'voice_mapping': voice_mapping,
                    'tts_speed': tts_speed,
                    'tts_method': st.session_state.tts_method,
                    'eng_pho_spacing': eng_pho_spacing,
                    'pho_chn_spacing': pho_chn_spacing,
                    'line_spacing': line_spacing
                }
                
                video_bytes = generate_video_with_optimization(df, settings, progress_bar, status_placeholder)
                
                if video_bytes:
                    status_placeholder.success("✅ 视频生成完成！")
                    
                    col_vid1, col_vid2, col_vid3 = st.columns([1, 2, 1])
                    with col_vid2:
                        st.video(video_bytes)
                        
                        st.download_button(
                            label="📥 下载视频",
                            data=video_bytes,
                            file_name="travel_english_video.mp4",
                            mime="video/mp4",
                            use_container_width=True,
                            key="download_button"
                        )
                else:
                    status_placeholder.error("视频生成失败，请检查系统配置或重试")

# 侧边栏信息
with st.sidebar:
    st.markdown("## ℹ️ 使用指南")
    
    with st.expander("📝 数据格式要求", expanded=True):
        st.markdown("""
        Excel 文件必须包含以下列：
        - **英语**: 英文句子
        - **中文**: 中文翻译  
        - **音标**: 音标标注（可选）
        """)
    
    with st.expander("🎵 TTS 服务说明"):
        st.markdown("""
        - **Edge TTS**: 微软在线服务，音质好但需要网络
        - **pyttsx3**: 离线服务，稳定但音质一般
        - **gTTS**: Google在线服务，需要网络
        """)
    
    with st.expander("⚙️ 系统要求"):
        st.markdown("""
        - **FFmpeg**: 必须安装
        - **网络**: 在线TTS服务需要联网
        - **浏览器**: 建议使用 Chrome/Firefox
        - **数据量**: 建议每次不超过50行
        """)

# 页脚
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "🎬 旅行英语视频生成器 | 多TTS服务支持"
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
