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

# 检查 ffmpeg 是否可用（静默模式）
def check_ffmpeg():
    ffmpeg_path = shutil.which('ffmpeg')
    return ffmpeg_path

# edge-tts 用于多音色 TTS
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

# 页面配置
st.set_page_config(
    page_title="旅行英语视频生成器",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式 - 移除不必要的空白
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
    /* 移除不必要的空白 */
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
if 'audio_available' not in st.session_state:
    st.session_state.audio_available = EDGE_TTS_AVAILABLE
if 'generation_status' not in st.session_state:
    st.session_state.generation_status = None

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
        # 优先尝试直接加载已知的音标字体文件
        font_files = [
            "DoulosSIL-R.ttf",
            "CharisSIL-R.ttf",
            "NotoSansIPA-Regular.ttf",
            "ArialUni.ttf",
            "l_10646.ttf",
            "DejaVuSans.ttf",
        ]
        
        # 尝试从系统字体目录加载
        system_font_paths = [
            "/usr/share/fonts/",
            "C:/Windows/Fonts/",
            "~/Library/Fonts/",
            "/Library/Fonts/",
        ]
        
        # 尝试加载粗体
        if bold:
            bold_fonts = [
                "DoulosSIL-B.ttf",
                "CharisSIL-B.ttf",
                "NotoSansIPA-Bold.ttf",
                "ArialUniBold.ttf",
                "DejaVuSans-Bold.ttf",
            ]
            for font in bold_fonts:
                try:
                    return ImageFont.truetype(font, size)
                except:
                    pass
                for path in system_font_paths:
                    font_path = os.path.join(path, font)
                    if os.path.exists(font_path):
                        try:
                            return ImageFont.truetype(font_path, size)
                        except:
                            continue
        
        # 尝试加载常规字体
        for font in font_files:
            try:
                return ImageFont.truetype(font, size)
            except:
                pass
            for path in system_font_paths:
                font_path = os.path.join(path, font)
                if os.path.exists(font_path):
                    try:
                        return ImageFont.truetype(font_path, size)
                    except:
                        continue
        
        # 最后使用默认字体
        return ImageFont.load_default()
    except Exception as e:
        return ImageFont.load_default()

def get_font(size, font_type="default", bold=False):
    """获取字体，支持音标符号和中文"""
    if font_type == "phonetic":
        return get_phonetic_font(size, bold)
    
    try:
        chinese_fonts = [
            "simhei.ttf",
            "msyh.ttc",
            "simsun.ttc",
            "STHeiti Light.ttc",
            "PingFang.ttc",
            "Arial Unicode MS",
            "SimHei", 
            "Microsoft YaHei",
            "WenQuanYi Micro Hei",
            "NotoSansCJK-Regular.ttc",
            "FZSTK.TTF",
            "SourceHanSansCN-Regular.otf",
        ]
        
        if bold:
            bold_fonts = [
                "simhei.ttf",
                "msyhbd.ttc",
                "STHeiti Medium.ttc",
                "PingFang SC Semibold.ttc",
                "Arial Unicode MS",
                "SimHei",
                "Arial Bold",
                "Arial-Bold",
                "arialbd.ttf"
            ]
            for f in chinese_fonts:
                try:
                    if f in bold_fonts or any(bold_font in f.lower() for bold_font in ['bold', 'bd', 'black', 'heavy']):
                        return ImageFont.truetype(f, size)
                except Exception:
                    continue
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
        total_height += eng_pho_spacing  # 使用可调节的英语-音标间距
        for line in pho_lines:
            bbox = draw.textbbox((0,0), line, font=pho_font)
            h = bbox[3] - bbox[1]
            total_height += h
        total_height += line_spacing * (len(pho_lines)-1)

    if chn_lines:
        total_height += pho_chn_spacing  # 使用可调节的音标-中文间距
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
        y += eng_pho_spacing  # 使用可调节的英语-音标间距
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
        y += pho_chn_spacing  # 使用可调节的音标-中文间距
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
# Edge TTS helpers
# -----------------------
VOICE_OPTIONS = {
    "English - Female (US) - Aria": "en-US-AriaNeural",
    "English - Female (US) - Jenny": "en-US-JennyNeural",
    "English - Female (US) - Sara": "en-US-SaraNeural",
    "English - Male (US) - Davis": "en-US-DavisNeural",
    "English - Male (US) - Guy": "en-US-GuyNeural",
    "English - Male (US) - Tony": "en-US-TonyNeural",
    "English - Male (US) - Brian": "en-US-BrianNeural",
    "English - Male (US) - Eric": "en-US-EricNeural",
    "English - Female (UK) - Libby": "en-GB-LibbyNeural",
    "English - Female (UK) - Sonia": "en-GB-SoniaNeural",
    "English - Male (UK) - Ryan": "en-GB-RyanNeural",
    "English - Male (UK) - Alfie": "en-GB-AlfieNeural",
    "English - Male (UK) - George": "en-GB-GeorgeNeural",
    "English - Female (AU) - Natasha": "en-AU-NatashaNeural",
    "English - Male (AU) - William": "en-AU-WilliamNeural",
    "Chinese - Female (CN) - Xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "Chinese - Female (CN) - Xiaoyi": "zh-CN-XiaoyiNeural",
    "Chinese - Female (CN) - Xiaochen": "zh-CN-XiaochenNeural",
    "Chinese - Female (CN) - Xiaohan": "zh-CN-XiaohanNeural",
    "Chinese - Male (CN) - Yunfeng": "zh-CN-YunfengNeural",
    "Chinese - Male (CN) - Yunyang": "zh-CN-YunyangNeural",
    "Chinese - Male (CN) - Yunjian": "zh-CN-YunjianNeural",
    "Chinese - Male (CN) - Yunze": "zh-CN-YunzeNeural",
    "Chinese - Male (CN) - Yunkai": "zh-CN-YunkaiNeural",
    "Chinese - Male (CN) - Yunxi": "zh-CN-YunxiNeural",
    "Chinese - Male (CN) - Yunhao": "zh-CN-YunhaoNeural",
    "Chinese - Male (CN) - Yunlong": "zh-CN-YunlongNeural",
    "Chinese - Female (TW) - HsiaoChen": "zh-TW-HsiaoChenNeural",
    "Chinese - Female (TW) - HsiaoYu": "zh-TW-HsiaoYuNeural",
    "Chinese - Male (TW) - YunJhe": "zh-TW-YunJheNeural",
    "Chinese - Male (TW) - YunSong": "zh-TW-YunSongNeural"
}

async def _edge_tts_save(text: str, voice_name: str, out_path: str, rate: str = "+0%"):
    try:
        communicate = edge_tts.Communicate(text, voice_name, rate=rate)
        await communicate.save(out_path)
        return True
    except Exception as e:
        st.error(f"TTS生成失败: {e}")
        return False

def generate_edge_audio(text, voice, speed=1.0, out_path=None):
    if not EDGE_TTS_AVAILABLE:
        st.warning("Edge TTS 不可用")
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
        st.error(f"生成音频异常: {e}")
        if os.path.exists(out_path):
            os.unlink(out_path)
        return None

def preview_voice(voice_name, text, speed=1.0):
    if not EDGE_TTS_AVAILABLE:
        return None
    
    pct = int((speed - 1.0) * 100)
    rate_str = f"{pct:+d}%"
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
            temp_path = f.name
        
        success = asyncio.run(_edge_tts_save(text, voice_name, temp_path, rate_str))
        if success and os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            with open(temp_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()
            os.unlink(temp_path)
            return audio_bytes
        else:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return None
    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return None

# -----------------------
# 音频合并 / 视频合并 (使用 FFmpeg 替代 pydub)
# -----------------------
def create_silent_audio(duration, output_path):
    """创建静音音频文件"""
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", str(duration), "-q:a", "9", "-acodec", "libmp3lame", output_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        st.warning(f"创建静音音频失败: {e}")
        return False

def adjust_audio_duration(input_path, target_duration, output_path):
    """调整音频到指定时长"""
    if not input_path or not os.path.exists(input_path):
        return create_silent_audio(target_duration, output_path)
    
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-t", str(target_duration),
        "-af", "apad", "-acodec", "libmp3lame", output_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        st.warning(f"调整音频时长失败: {e}")
        return create_silent_audio(target_duration, output_path)

def merge_audio_files(audio_paths, target_duration, pause_duration):
    """使用 FFmpeg 合并音频文件"""
    if not check_ffmpeg():
        st.error("未检测到 ffmpeg，无法合并音频。")
        return None
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建文件列表
        list_file = os.path.join(tmpdir, "audio_list.txt")
        output_path = os.path.join(tmpdir, "combined.mp3")
        
        valid_files = []
        
        for i, audio_path in enumerate(audio_paths):
            if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                # 调整音频时长
                adjusted_audio = os.path.join(tmpdir, f"adjusted_{i}.mp3")
                if adjust_audio_duration(audio_path, target_duration, adjusted_audio):
                    valid_files.append(adjusted_audio)
                    
                    # 如果不是最后一个音频，添加停顿
                    if i < len(audio_paths) - 1:
                        pause_audio = os.path.join(tmpdir, f"pause_{i}.mp3")
                        if create_silent_audio(pause_duration, pause_audio):
                            valid_files.append(pause_audio)
                else:
                    # 如果调整失败，使用静音替代
                    silent_audio = os.path.join(tmpdir, f"silent_{i}.mp3")
                    if create_silent_audio(target_duration, silent_audio):
                        valid_files.append(silent_audio)
                        
                        if i < len(audio_paths) - 1:
                            pause_audio = os.path.join(tmpdir, f"pause_{i}.mp3")
                            if create_silent_audio(pause_duration, pause_audio):
                                valid_files.append(pause_audio)
            else:
                # 如果音频不存在，使用静音替代
                silent_audio = os.path.join(tmpdir, f"silent_{i}.mp3")
                if create_silent_audio(target_duration, silent_audio):
                    valid_files.append(silent_audio)
                    
                    if i < len(audio_paths) - 1:
                        pause_audio = os.path.join(tmpdir, f"pause_{i}.mp3")
                        if create_silent_audio(pause_duration, pause_audio):
                            valid_files.append(pause_audio)
        
        if not valid_files:
            st.error("没有有效的音频文件可合并")
            return None
            
        # 写入文件列表
        with open(list_file, 'w') as f:
            for file_path in valid_files:
                f.write(f"file '{file_path}'\n")
        
        # 使用 concat 协议合并音频
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", output_path
        ]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            else:
                st.error("合并后的音频文件无效")
                return None
        except subprocess.CalledProcessError as e:
            st.error(f"音频合并失败: {e.stderr.decode() if e.stderr else str(e)}")
            return None
        except Exception as e:
            st.error(f"音频合并异常: {e}")
            return None

def merge_video_audio(video_path, audio_path, output_path):
    """合并视频和音频"""
    if not check_ffmpeg():
        st.error("未检测到 ffmpeg，无法合并音频。")
        return None
        
    if not os.path.exists(video_path) or not os.path.exists(audio_path):
        st.error("视频或音频文件不存在")
        return None
        
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-strict", "experimental",
        "-shortest",  # 确保视频长度与音频一致
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
        else:
            st.error(f"ffmpeg 合并失败: {result.stderr}")
            return None
    except Exception as e:
        st.error(f"调用 ffmpeg 失败: {e}")
        return None

# -----------------------
# 优化的视频生成函数 - 修复重复进度条问题
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
                # 先预生成所有音频
                status_placeholder.info("🎵 正在生成音频...")
                for i, row in df.iterrows():
                    eng = str(row['英语'])
                    chn = str(row['中文'])
                    
                    for j, segment_type in enumerate(segment_order):
                        voice, text_type = voice_mapping[segment_type]
                        text_to_speak = eng if text_type == "english" else chn
                        
                        audio_file = generate_edge_audio(text_to_speak, voice, speed=tts_speed)
                        audio_paths.append(audio_file)
                        
                        # 更新音频生成进度
                        audio_progress = (i * len(segment_order) + j + 1) / (len(df) * len(segment_order)) * 0.3
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
                    
                    # 为每个片段重复帧
                    for segment_idx in range(len(segment_order)):
                        for _ in range(per_duration_frames):
                            writer.append_data(frame_array)
                            current_frame += 1
                            if current_frame % 10 == 0:
                                video_progress = 0.3 + 0.5 * (current_frame / total_frames)
                                progress_bar.progress(min(video_progress, 0.8))
                        
                        # 如果不是最后一个片段，添加停顿
                        if not (i == len(df) - 1 and segment_idx == len(segment_order) - 1):
                            for _ in range(pause_duration_frames):
                                writer.append_data(frame_array)
                                current_frame += 1
                                if current_frame % 10 == 0:
                                    video_progress = 0.3 + 0.5 * (current_frame / total_frames)
                                    progress_bar.progress(min(video_progress, 0.8))
            
            except Exception as e:
                st.error(f"生成视频过程中出错: {e}")
                return None
            finally:
                if writer is not None:
                    writer.close()
            
            # 检查无声视频是否生成成功
            if not os.path.exists(video_no_audio) or os.path.getsize(video_no_audio) == 0:
                st.error("无声视频生成失败")
                return None
            
            # 合并音频
            status_placeholder.info("🔊 正在合并音频...")
            progress_bar.progress(0.85)
            
            if any(p for p in audio_paths if p is not None) and check_ffmpeg():
                combined_audio_path = merge_audio_files(audio_paths, per_duration, pause_duration)
                if combined_audio_path and os.path.exists(combined_audio_path) and os.path.getsize(combined_audio_path) > 0:
                    # 合并视频和音频
                    status_placeholder.info("🎵 正在合并视频和音频...")
                    progress_bar.progress(0.9)
                    
                    merged = merge_video_audio(video_no_audio, combined_audio_path, final_video)
                    if merged:
                        final_video = merged
                        progress_bar.progress(1.0)
                    else:
                        st.warning("音频合并失败，将使用无声视频")
                        final_video = video_no_audio
                else:
                    st.warning("音频生成失败，将使用无声视频")
                    final_video = video_no_audio
            else:
                st.warning("无法生成音频，将使用无声视频")
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
        st.text(traceback.format_exc())
        return None

# -----------------------
# UI 与主流程
# -----------------------
st.markdown('<h1 class="main-header">🎬 旅行英语视频生成器</h1>', unsafe_allow_html=True)
st.markdown("### 多音色循环播放 • 专业级视频制作")

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

    # 设置面板 - 修复空白框问题
    st.markdown('<div class="section-header">🎨 2. 自定义设置</div>', unsafe_allow_html=True)
    
    # 使用标签页组织设置 - 移除不必要的空白
    tab1, tab2, tab3, tab4 = st.tabs(["🎨 样式设置", "🔊 音频设置", "📝 文字背景", "⚙️ 视频参数"])
    
    with tab1:
        # 使用紧凑布局
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
            
            # 文字间距设置 - 紧凑布局
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
        st.subheader("🔊 播放顺序设置")
        
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

        st.subheader("🎙️ 音色选择与试听")
        
        col_voice1, col_voice2, col_voice3 = st.columns(3)
        
        with col_voice1:
            st.markdown("**英文男声**")
            male_english_voices = {k:v for k,v in VOICE_OPTIONS.items() if "Male" in k and "English" in k}
            male_english_label = st.selectbox("选择男声音色", list(male_english_voices.keys()), index=2, key="male_voice")
            male_english_voice = male_english_voices[male_english_label]
            
            if st.button("🎧 试听男声", key="preview_male_english"):
                preview_text = "Hello, this is a preview of the male English voice."
                audio_bytes = preview_voice(male_english_voice, preview_text, tts_speed)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")
                else:
                    st.warning("试听生成失败")

        with col_voice2:
            st.markdown("**英文女声**")
            female_english_voices = {k:v for k,v in VOICE_OPTIONS.items() if "Female" in k and "English" in k}
            female_english_label = st.selectbox("选择女声音色", list(female_english_voices.keys()), index=2, key="female_voice")
            female_english_voice = female_english_voices[female_english_label]
            
            if st.button("🎧 试听女声", key="preview_female_english"):
                preview_text = "Hello, this is a preview of the female English voice."
                audio_bytes = preview_voice(female_english_voice, preview_text, tts_speed)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")
                else:
                    st.warning("试听生成失败")

        with col_voice3:
            st.markdown("**中文音色**")
            chinese_voices = {k:v for k,v in VOICE_OPTIONS.items() if "Chinese" in k}
            chinese_label = st.selectbox("选择中文音色", list(chinese_voices.keys()), index=0, key="chinese_voice")
            chinese_voice = chinese_voices[chinese_label]
            
            if st.button("🎧 试听中文", key="preview_chinese"):
                preview_text = "你好，这是中文音色的预览。"
                audio_bytes = preview_voice(chinese_voice, preview_text, tts_speed)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")
                else:
                    st.warning("试听生成失败")

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

    # 生成按钮 - 修复重复进度条问题
    st.markdown('<div class="section-header">🚀 4. 生成视频</div>', unsafe_allow_html=True)
    
    if len(df) > 20:
        st.markdown(f'<div class="warning-card">⚠️ 数据量较大（{len(df)} 行），生成可能需要一些时间。建议分批处理或减少每段音频时长。</div>', unsafe_allow_html=True)
    
    col_gen1, col_gen2, col_gen3 = st.columns([1, 2, 1])
    with col_gen2:
        if st.button("🎬 开始生成视频", use_container_width=True, key="generate_button"):
            # 创建状态占位符和单一进度条
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            with st.spinner("🎥 正在生成视频 - 会为每行生成4段音频，请耐心等待..."):
                # 创建语音类型到实际语音的映射
                voice_mapping = {
                    "英文男声": (male_english_voice, "english"),
                    "英文女声": (female_english_voice, "english"), 
                    "中文音色": (chinese_voice, "chinese")
                }
                
                # 获取播放顺序
                segment_order = [segment1_type, segment2_type, segment3_type, segment4_type]
                
                # 收集所有设置
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
                    'eng_pho_spacing': eng_pho_spacing,
                    'pho_chn_spacing': pho_chn_spacing,
                    'line_spacing': line_spacing
                }
                
                # 使用优化的生成函数
                video_bytes = generate_video_with_optimization(df, settings, progress_bar, status_placeholder)
                
                if video_bytes:
                    status_placeholder.success("✅ 视频生成完成！")
                    
                    # 显示视频和下载按钮
                    col_vid1, col_vid2, col_vid3 = st.columns([1, 2, 1])
                    with col_vid2:
                        st.video(video_bytes)
                        
                        # 下载按钮
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
    
    with st.expander("🎵 音频设置说明"):
        st.markdown("""
        - **播放顺序**: 设置4段音频的播放顺序
        - **音色选择**: 为不同语言选择合适音色
        - **语速调节**: 0.5x-2.0x 可调
        - **停顿时间**: 每组之间的间隔
        """)
    
    with st.expander("🎨 样式设置提示"):
        st.markdown("""
        - **背景**: 纯色或自定义图片
        - **文字**: 支持中英文和音标
        - **背景区域**: 增强文字可读性
        - **字体**: 自动适配最佳字体
        - **间距**: 可调节文字间距离
        """)
    
    with st.expander("⚙️ 系统要求"):
        st.markdown("""
        - **网络**: 需要联网
        - **浏览器**: 建议使用 Chrome/Firefox
        - **数据量**: 建议每次不超过50行
        - **处理时间**: 根据数据量可能需要几分钟
        """)

# 页脚
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "🎬 旅行英语视频生成器 | 专业级多音色视频制作工具"
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
