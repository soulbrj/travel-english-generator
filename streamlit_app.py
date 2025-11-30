# ---------- 基本导入 ----------
import os
import sys
import io
import json
import time
import math
import shutil
import hashlib
import tempfile
import asyncio
import traceback
import subprocess
import glob
import base64
from queue import Queue
from threading import Thread
from typing import List, Dict, Tuple, Optional

import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageColor

# imageio import (video writing later)
import imageio.v2 as imageio

# ---------- 配置 & 常量 ----------
LIGHTWEIGHT_MODE = False  # True -> 更轻量, 禁用队列/模板/进度

# 兼容 Streamlit Cloud 的临时目录处理
if 'STREAMLIT_SHARING_MODE' in os.environ or 'STREAMLIT_SERVER_HEADLESS' in os.environ:
    APP_TMP = os.path.join(tempfile.gettempdir(), "travel_english_tts_app")
else:
    APP_TMP = os.path.join(tempfile.gettempdir(), "travel_english_tts_app")

CACHE_DIR = os.path.join(APP_TMP, "cache")
SAMPLES_DIR = os.path.join(APP_TMP, "samples")
TEMPLATE_DIR = os.path.join(APP_TMP, "templates")
PROGRESS_FILE = os.path.join(APP_TMP, "learning_progress.json")

for p in (APP_TMP, CACHE_DIR, SAMPLES_DIR, TEMPLATE_DIR):
    os.makedirs(p, exist_ok=True)

# ---------- 可选依赖检测 ----------
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except Exception:
    PYTTSX3_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except Exception:
    PYDUB_AVAILABLE = False

# ---------- 跨平台 FFmpeg 检测函数 ----------
def find_ffmpeg_path():
    """跨平台查找 ffmpeg 路径"""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    
    possible_paths = []
    if sys.platform.startswith("win"):
        possible_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        ]
    elif sys.platform.startswith("darwin"):
        possible_paths = [
            "/usr/local/bin/ffmpeg",
            "/opt/homebrew/bin/ffmpeg",
        ]
    else:
        possible_paths = [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
        ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    try:
        import imageio_ffmpeg as iioff
        ffexe = iioff.get_ffmpeg_exe()
        if ffexe and os.path.exists(ffexe):
            return ffexe
    except Exception:
        pass
    
    return None

def ffmpeg_available() -> bool:
    return find_ffmpeg_path() is not None

def run_ffmpeg_command(cmd):
    """跨平台运行 ffmpeg 命令"""
    ffmpeg_path = find_ffmpeg_path()
    if not ffmpeg_path:
        raise RuntimeError("FFmpeg not found")
    
    if cmd[0] == "ffmpeg":
        cmd[0] = ffmpeg_path
    
    env = os.environ.copy()
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                              timeout=300, check=True, env=env)
        return True
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg command timed out")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg command failed: {error_msg}")
    except Exception as e:
        raise RuntimeError(f"FFmpeg execution error: {str(e)}")

# ---------- 高级UI theme & CSS ----------
PRIMARY_LIGHT = "#f8faff"
SECONDARY_LIGHT = "#f0f4ff"
ACCENT_PRIMARY = "#7c3aed"
ACCENT_SECONDARY = "#4f46e5"
ACCENT_GRADIENT_START = "#8b5cf6"
ACCENT_GRADIENT_END = "#6366f1"
SUCCESS_COLOR = "#10b981"
WARNING_COLOR = "#f59e0b"
ERROR_COLOR = "#ef4444"
CARD_BG = "rgba(255, 255, 255, 0.85)"
TEXT_DARK = "#1e293b"
TEXT_MUTED = "#64748b"
BORDER_COLOR = "rgba(99, 102, 241, 0.2)"

st.set_page_config(
    page_title="🎬 英语视频生成器 - 专业级多音色教学视频制作平台",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Charis+SIL:wght@400;700&display=swap');

:root {{
  --primary-light: {PRIMARY_LIGHT};
  --secondary-light: {SECONDARY_LIGHT};
  --accent-primary: {ACCENT_PRIMARY};
  --accent-secondary: {ACCENT_SECONDARY};
  --gradient-start: {ACCENT_GRADIENT_START};
  --gradient-end: {ACCENT_GRADIENT_END};
  --text-dark: {TEXT_DARK};
  --text-muted: {TEXT_MUTED};
  --card-bg: {CARD_BG};
  --border-color: {BORDER_COLOR};
}}

/* 使用组合字体 */
.english-text {{
    font-family: 'Charis SIL', 'Noto Sans SC', sans-serif;
}}

.phonetic-text {{
    font-family: 'Charis SIL', 'Arial Unicode MS', sans-serif;
}}

.chinese-text {{
    font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
}}

.stApp {{
  background: linear-gradient(135deg, {PRIMARY_LIGHT} 0%, {SECONDARY_LIGHT} 100%) !important;
  color: {TEXT_DARK} !important;
}}

.main-title {{
  background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
  color: white;
  padding: 24px 32px;
  border-radius: 20px;
  font-size: 28px;
  font-weight: 800;
  text-align: center;
  margin-bottom: 24px;
  box-shadow: 0 12px 40px rgba(99, 102, 241, 0.25);
}}

.navbar {{
  display: flex;
  gap: 12px;
  justify-content: center;
  padding: 16px 0;
  margin-bottom: 32px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 16px;
  border: 1px solid var(--border-color);
}}

.nav-btn {{
  padding: 12px 24px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  color: {TEXT_DARK};
  cursor: pointer;
  font-weight: 600;
  font-size: 14px;
  transition: all 0.3s ease;
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.1);
  display: flex;
  align-items: center;
  gap: 8px;
}}

.nav-btn:hover {{
  background: white;
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.2);
  border-color: var(--accent-primary);
}}

.card {{
  background: var(--card-bg);
  border-radius: 20px;
  padding: 24px;
  margin-bottom: 20px;
  border: 1px solid var(--border-color);
  box-shadow: 0 8px 32px rgba(99, 102, 241, 0.1);
  transition: all 0.3s ease;
}}

.card:hover {{
  box-shadow: 0 12px 40px rgba(99, 102, 241, 0.15);
  transform: translateY(-2px);
}}

.card-header {{
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 20px;
  color: {TEXT_DARK};
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--border-color);
}}

div.stButton > button {{
  background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
  color: white;
  border-radius: 12px;
  padding: 12px 24px;
  font-weight: 600;
  border: none;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
  font-size: 14px;
}}

div.stButton > button:hover {{
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4);
  background: linear-gradient(135deg, var(--gradient-end), var(--gradient-start));
}}

.footer {{
  text-align: center;
  padding: 24px;
  color: {TEXT_MUTED};
  margin-top: 40px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 16px;
  border: 1px solid var(--border-color);
}}

.voice-library {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 20px;
  max-height: 500px;
  overflow-y: auto;
  padding: 10px;
}}

.voice-card {{
  background: rgba(255, 255, 255, 0.9);
  border-radius: 16px;
  padding: 20px;
  border: 1px solid var(--border-color);
  transition: all 0.3s ease;
}}

.voice-card:hover {{
  border-color: var(--accent-primary);
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(99, 102, 241, 0.15);
  background: white;
}}

.voice-name {{
  font-weight: 700;
  color: {TEXT_DARK};
  margin-bottom: 8px;
  font-size: 16px;
}}

.voice-category {{
  font-size: 13px;
  color: {TEXT_MUTED};
  margin-bottom: 8px;
  font-weight: 500;
}}

.voice-style {{
  font-size: 12px;
  color: {SUCCESS_COLOR};
  margin-bottom: 12px;
  font-weight: 500;
  background: rgba(16, 185, 129, 0.1);
  padding: 4px 8px;
  border-radius: 6px;
  display: inline-block;
}}

.stProgress > div > div > div {{
  background: linear-gradient(90deg, var(--gradient-start), var(--gradient-end));
  border-radius: 8px;
}}

/* 自定义Tabs样式 */
.stTabs {{
  margin-top: 16px;
}}

.stTabs > div > div > div {{
  gap: 8px;
}}

.stTabs > div > div > div > div {{
  color: {TEXT_DARK};
  border-radius: 12px;
  padding: 12px 20px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.7);
  transition: all 0.3s ease;
  font-weight: 500;
}}

.stTabs > div > div > div > div:hover {{
  background: rgba(255, 255, 255, 0.9);
  border-color: var(--accent-primary);
}}

.stTabs > div > div > div > div[data-baseweb="tab"][aria-selected="true"] {{
  background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
  color: white;
  border-color: transparent;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
  font-weight: 600;
}}

.stAudio {{
  margin: 12px 0;
  border-radius: 12px;
  overflow: hidden;
}}

.stSuccess {{
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 12px;
}}

.stError {{
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 12px;
}}

.stInfo {{
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 12px;
}}

/* 可滚动内容区域 */
.scrollable-content {{
  max-height: 400px;
  overflow-y: auto;
  padding-right: 8px;
}}

.scrollable-content::-webkit-scrollbar {{
  width: 6px;
}}

.scrollable-content::-webkit-scrollbar-track {{
  background: rgba(99, 102, 241, 0.1);
  border-radius: 3px;
}}

.scrollable-content::-webkit-scrollbar-thumb {{
  background: var(--accent-primary);
  border-radius: 3px;
}}

.scrollable-content::-webkit-scrollbar-thumb:hover {{
  background: var(--accent-secondary);
}}

/* 紧凑表格样式 */
.compact-table {{
  font-size: 14px;
}}

.compact-table .dataframe {{
  width: 100%;
}}

.compact-table .dataframe th {{
  background: rgba(99, 102, 241, 0.1);
  padding: 8px 12px;
}}

.compact-table .dataframe td {{
  padding: 6px 12px;
}}

/* 预览区域样式 */
.preview-container {{
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.5);
  margin: 16px 0;
}}

.preview-image {{
  max-width: 100%;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}}

/* 实时预览区域 */
.live-preview-container {{
  background: rgba(255, 255, 255, 0.9);
  border-radius: 16px;
  padding: 20px;
  border: 2px solid var(--border-color);
  box-shadow: 0 8px 32px rgba(99, 102, 241, 0.1);
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}}

.live-preview-title {{
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 20px;
  color: {TEXT_DARK};
  text-align: center;
}}

.live-preview-image {{
  max-width: 100%;
  max-height: 400px;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  margin-bottom: 20px;
}}

.live-preview-text {{
  text-align: center;
  margin: 10px 0;
  font-size: 16px;
}}

.live-preview-english {{
  font-size: 24px;
  font-weight: 700;
  color: {TEXT_DARK};
}}

.live-preview-phonetic {{
  font-size: 18px;
  color: {TEXT_MUTED};
  font-style: italic;
  font-family: 'Noto Sans IPA', 'Charis SIL', 'Arial Unicode MS', 'Lucida Sans Unicode', 'DejaVu Sans', sans-serif;
  font-weight: 400;
}}

.live-preview-chinese {{
  font-size: 20px;
  color: {TEXT_DARK};
}}
</style>
""", unsafe_allow_html=True)

# ---------- 公共工具函数 ----------
def now_ts() -> int:
    return int(time.time())

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def safe_remove(path: str):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def hash_text_meta(text: str, voice: str, speed: float, extra: dict = None) -> str:
    j = json.dumps({"t": text, "v": voice, "s": speed, "e": extra or {}}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(j.encode("utf-8")).hexdigest()

def cache_get(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.mp3")

def cache_exists(key: str) -> bool:
    p = cache_get(key)
    return os.path.exists(p) and os.path.getsize(p) > 0

def cache_store(src: str, key: str):
    dst = cache_get(key)
    try:
        shutil.copy(src, dst)
    except Exception:
        pass

# ---------- 字体检测与加载 ----------
def find_font():
    """跨平台查找支持中文和音标的字体 - 增强版本"""
    cand = []
    
    # 首先检查云环境字体
    if 'STREAMLIT_SHARING_MODE' in os.environ:
        cand = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
        ]
    elif sys.platform.startswith("win"):
        cand = [
            r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
            r"C:\Windows\Fonts\simhei.ttf",    # 黑体
            r"C:\Windows\Fonts\arialuni.ttf",  # Arial Unicode MS
            r"C:\Windows\Fonts\times.ttf",     # Times New Roman
        ]
    elif sys.platform.startswith("darwin"):
        cand = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Arial.ttf",
        ]
    else:
        cand = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    
    for p in cand:
        if os.path.exists(p):
            try:
                # 测试字体是否支持中文
                test_font = ImageFont.truetype(p, 12)
                # 测试中文字符渲染
                test_image = Image.new('RGB', (100, 30), color='white')
                test_draw = ImageDraw.Draw(test_image)
                test_draw.text((10, 10), "中文测试", font=test_font, fill='black')
                return p
            except Exception:
                continue
    
    # 如果找不到合适的字体，返回第一个存在的字体
    for p in cand:
        if os.path.exists(p):
            return p
    return None

DEFAULT_FONT = find_font()

def load_font(path, size):
    """加载字体，支持中文和音标"""
    try:
        # 优先使用用户上传的自定义字体
        if 'custom_font_path' in st.session_state and st.session_state.custom_font_path:
            return ImageFont.truetype(st.session_state.custom_font_path, size)
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
        if DEFAULT_FONT:
            return ImageFont.truetype(DEFAULT_FONT, size)
    except Exception as e:
        st.warning(f"字体加载失败: {e}，使用默认字体")
    
    # 最终回退到默认字体
    return ImageFont.load_default()

def load_phonetic_font(size):
    """专门加载音标字体"""
    # 优先使用专门支持音标的字体
    phonetic_fonts = []
    
    # 添加用户自定义字体
    if 'custom_font_path' in st.session_state and st.session_state.custom_font_path:
        phonetic_fonts.append(st.session_state.custom_font_path)
    
    # 添加专门支持音标的字体
    if sys.platform.startswith("win"):
        phonetic_fonts.extend([
            r"C:\Windows\Fonts\arialuni.ttf",  # Arial Unicode MS
            r"C:\Windows\Fonts\times.ttf",     # Times New Roman
            r"C:\Windows\Fonts\arial.ttf",     # Arial
        ])
    elif sys.platform.startswith("darwin"):
        phonetic_fonts.extend([
            "/System/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Times.ttc",
        ])
    else:
        phonetic_fonts.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
        ])
    
    # 添加默认字体
    if DEFAULT_FONT:
        phonetic_fonts.append(DEFAULT_FONT)
    
    # 尝试加载字体
    for font_path in phonetic_fonts:
        if font_path and os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    
    # 如果都失败，返回默认字体
    return load_font(None, size)

def load_chinese_font(size):
    """专门加载中文字体"""
    # 优先使用专门支持中文的字体
    chinese_fonts = []
    
    # 添加用户自定义字体
    if 'custom_font_path' in st.session_state and st.session_state.custom_font_path:
        chinese_fonts.append(st.session_state.custom_font_path)
    
    # 添加专门支持中文的字体
    if sys.platform.startswith("win"):
        chinese_fonts.extend([
            r"C:\Windows\Fonts\simhei.ttf",    # 黑体
            r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
            r"C:\Windows\Fonts\simsun.ttc",    # 宋体
            r"C:\Windows\Fonts\arialuni.ttf",  # Arial Unicode MS
        ])
    elif sys.platform.startswith("darwin"):
        chinese_fonts.extend([
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Arial Unicode.ttf",
        ])
    else:
        chinese_fonts.extend([
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ])
    
    # 添加默认字体
    if DEFAULT_FONT:
        chinese_fonts.append(DEFAULT_FONT)
    
    # 尝试加载字体
    for font_path in chinese_fonts:
        if font_path and os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    
    # 如果都失败，返回默认字体
    return load_font(None, size)

# ---------- 语音 / 预设库 ----------
# 扩展音色库
EN_MALE = [
    "en-US-GuyNeural", "en-US-BenjaminNeural", "en-GB-RyanNeural",
    "en-US-BrianNeural", "en-AU-WilliamNeural", "en-CA-LiamNeural",
    "en-GB-AlfieNeural", "en-GB-ThomasNeural", "en-IE-ConnorNeural"
]
EN_FEMALE = [
    "en-US-JennyNeural", "en-US-AriaNeural", "en-GB-SoniaNeural",
    "en-US-AmberNeural", "en-US-AnaNeural", "en-AU-NatashaNeural",
    "en-CA-ClaraNeural", "en-GB-LibbyNeural", "en-GB-MaisieNeural",
    "en-IE-EmilyNeural", "en-NZ-MollyNeural"
]
ZH_VOICES = [
    "zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-KangkangNeural",
    "zh-CN-YunxiaNeural", "zh-CN-YunyangNeural", "zh-CN-XiaoyiNeural",
    "zh-CN-XiaochenNeural", "zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural",
    "zh-TW-HsiaoChenNeural", "zh-TW-YunJheNeural"
]

# 音色风格描述
VOICE_STYLES = {
    # 英文女声风格
    "en-US-JennyNeural": "美式英语，清晰自然",
    "en-US-AriaNeural": "美式英语，温暖亲切", 
    "en-GB-SoniaNeural": "英式英语，优雅知性",
    "en-US-AmberNeural": "美式英语，柔和甜美",
    "en-US-AnaNeural": "美式英语，年轻活泼",
    "en-AU-NatashaNeural": "澳式英语，清新明亮",
    "en-CA-ClaraNeural": "加拿大英语，温和流畅",
    "en-GB-LibbyNeural": "英式英语，活泼生动",
    "en-GB-MaisieNeural": "英式英语，年轻活力",
    "en-IE-EmilyNeural": "爱尔兰英语，优雅动听",
    "en-NZ-MollyNeural": "新西兰英语，清新自然",
    
    # 英文男声风格
    "en-US-GuyNeural": "美式英语，沉稳专业",
    "en-US-BenjaminNeural": "美式英语，温暖可靠",
    "en-GB-RyanNeural": "英式英语，标准优雅",
    "en-US-BrianNeural": "美式英语，清晰有力",
    "en-AU-WilliamNeural": "澳式英语，阳刚自信",
    "en-CA-LiamNeural": "加拿大英语，温和稳重",
    "en-GB-AlfieNeural": "英式英语，深沉磁性",
    "en-GB-ThomasNeural": "英式英语，标准清晰",
    "en-IE-ConnorNeural": "爱尔兰英语，独特魅力",
    
    # 中文音色风格
    "zh-CN-XiaoxiaoNeural": "普通话，甜美少女音",
    "zh-CN-YunxiNeural": "普通话，温暖青年音",
    "zh-CN-KangkangNeural": "普通话，沉稳男声",
    "zh-CN-YunxiaNeural": "普通话，温柔女声",
    "zh-CN-YunyangNeural": "普通话，专业播音",
    "zh-CN-XiaoyiNeural": "普通话，活泼少女",
    "zh-CN-XiaochenNeural": "普通话，亲切女声",
    "zh-HK-HiuMaanNeural": "粤语，温柔女声",
    "zh-HK-WanLungNeural": "粤语，沉稳男声", 
    "zh-TW-HsiaoChenNeural": "台湾国语，甜美女声",
    "zh-TW-YunJheNeural": "台湾国语，阳光男声"
}

VOICE_LIBRARY = {
    "英文女声": EN_FEMALE, 
    "英文男声": EN_MALE, 
    "中文音色": ZH_VOICES,
}

PRESET_MODES = {
    "基础学习模式": [{"content":"英语","category":"英文女声","speed":1.0,"pause":0.3},{"content":"音标","category":"英文女声","speed":1.0,"pause":0.2}],
    "强化记忆模式": [{"content":"英语","category":"英文男声","speed":0.95,"pause":0.5},{"content":"中文","category":"中文音色","speed":1.0,"pause":0.8},{"content":"英语","category":"英文女声","speed":1.05,"pause":0.3}],
    "理解优先模式": [{"content":"中文","category":"中文音色","speed":1.0,"pause":0.5},{"content":"英语","category":"英文女声","speed":0.95,"pause":0.2}]
}

def recommend_preset(goal: str) -> str:
    if not goal:
        return "基础学习模式"
    g = goal.lower()
    if "记忆" in g or "背诵" in g:
        return "强化记忆模式"
    if "理解" in g or "翻译" in g:
        return "理解优先模式"
    return "基础学习模式"

def get_voice_display_name(voice_name: str) -> str:
    """获取音色的显示名称"""
    parts = voice_name.split("-")
    if len(parts) >= 3:
        return f"{parts[2]} ({parts[1]})"
    return voice_name

def get_voice_style(voice_name: str) -> str:
    """获取音色风格描述"""
    return VOICE_STYLES.get(voice_name, "专业语音合成")

# ---------- 模板 / 进度 存取 ----------
def save_template(name, style_conf, audio_segments, video_params):
    """保存模板，处理不可序列化的对象"""
    ensure_dir(TEMPLATE_DIR)
    p = os.path.join(TEMPLATE_DIR, f"{name}.json")
    
    # 创建可序列化的style_conf副本，移除Image对象
    serializable_style_conf = style_conf.copy()
    
    # 移除不可序列化的对象
    if 'bg_image' in serializable_style_conf:
        del serializable_style_conf['bg_image']
    
    # 确保所有值都是可序列化的
    for key, value in serializable_style_conf.items():
        if isinstance(value, (Image.Image,)):
            # 如果是PIL Image对象，移除它
            del serializable_style_conf[key]
    
    template_data = {
        "style": serializable_style_conf,
        "audio": audio_segments,
        "video": video_params
    }
    
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"保存模板失败: {e}")
        return False

def load_templates():
    ensure_dir(TEMPLATE_DIR)
    out=[]
    for f in os.listdir(TEMPLATE_DIR):
        if f.endswith(".json"):
            try:
                out.append((f[:-5], json.load(open(os.path.join(TEMPLATE_DIR,f),"r",encoding="utf-8"))))
            except:
                pass
    return out

def load_progress():
    try:
        return json.load(open(PROGRESS_FILE,"r",encoding="utf-8"))
    except:
        return {}

def save_progress(data):
    json.dump(data, open(PROGRESS_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

# ---------- TTS 辅助函数 ----------
def generate_edge_mp3(text: str, voice: str, speed: float, out_mp3: str) -> bool:
    """同步封装 edge-tts"""
    if not EDGE_TTS_AVAILABLE:
        return False
    
    pct = int((speed - 1.0) * 100)
    rate_str = f"{pct:+d}%"
    
    try:
        return asyncio.run(_edge_save_async(text, voice, out_mp3, rate_str))
    except Exception as e:
        return False

async def _edge_save_async(text: str, voice: str, out_path: str, rate_str: str = "+0%") -> bool:
    """异步调用 edge-tts 保存"""
    if not EDGE_TTS_AVAILABLE:
        return False
    try:
        comm = edge_tts.Communicate(text=text, voice=voice, rate=rate_str)
        await comm.save(out_path)
        return True
    except Exception as e:
        return False

def generate_tts_cached(text: str, voice_category: Optional[str], voice_choice: Optional[str], speed: float, engine_pref: str, out_mp3: str) -> bool:
    """缓存层：优先使用缓存"""
    if not text or text.strip() == "":
        return False
        
    voice_name = voice_choice or (VOICE_LIBRARY.get(voice_category, [None])[0] if voice_category else None)
    if not voice_name:
        return False
        
    key = hash_text_meta(text, voice_name or "default", speed)
    
    if cache_exists(key):
        try:
            shutil.copy(cache_get(key), out_mp3)
            return True
        except Exception:
            pass
    
    # 临时输出
    fd, tmpmp3 = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    ok = False
    
    # 优先使用在线引擎
    if EDGE_TTS_AVAILABLE:
        ok = generate_edge_mp3(text, voice_name, speed, tmpmp3)
    
    if ok and os.path.exists(tmpmp3) and os.path.getsize(tmpmp3) > 0:
        try:
            cache_store(tmpmp3, key)
            shutil.copy(cache_get(key), out_mp3)
            safe_remove(tmpmp3)
            return True
        except Exception:
            try:
                shutil.copy(tmpmp3, out_mp3)
                safe_remove(tmpmp3)
                return True
            except:
                safe_remove(tmpmp3)
                return False
    safe_remove(tmpmp3)
    return False

# ---------- 基本音频处理 ----------
def create_silent_mp3(out_path: str, duration_s: float) -> bool:
    """创建一段静音 mp3"""
    try:
        if ffmpeg_available():
            cmd = ["ffmpeg","-y","-f","lavfi","-i",f"anullsrc=r=44100:cl=mono","-t",str(duration_s), out_path]
            run_ffmpeg_command(cmd)
            return os.path.exists(out_path)
    except Exception as e:
        pass
    
    # 备用方案
    try:
        with open(out_path, "wb") as f: 
            f.write(b"")
        return True
    except:
        return False

def concat_audios_ffmpeg(audio_paths: List[str], out_mp3: str) -> None:
    """使用 ffmpeg concat 合并多个 mp3 文件"""
    if not audio_paths:
        raise ValueError("audio_paths empty")
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg missing for audio concat")
    
    listfile = out_mp3 + "_list.txt"
    with open(listfile, "w", encoding="utf-8") as f:
        for p in audio_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    
    cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",listfile,"-c","copy",out_mp3]
    run_ffmpeg_command(cmd)
    
    if not os.path.exists(out_mp3):
        raise RuntimeError("Audio concat failed: output file not created")
    
    safe_remove(listfile)

# ---------- 预览音频生成函数 ----------
def generate_preview_audio(df, row_index, audio_segments):
    """生成预览音频"""
    if df is None or row_index >= len(df):
        return None
    
    tmpdir = tempfile.mkdtemp(prefix="preview_")
    try:
        row = df.iloc[row_index]
        en = str(row.get("英语",""))
        ph = str(row.get("音标",""))
        cn = str(row.get("中文",""))
        
        seg_paths = []
        
        for seg_idx, seg in enumerate(audio_segments):
            text = en if seg["content"]=="英语" else (ph if seg["content"]=="音标" else cn)
            out_mp3 = os.path.join(tmpdir, f"preview_{seg_idx}_{seg['content']}.mp3")
            
            ok = generate_tts_cached(text, seg["voice_category"], seg["voice_choice"], seg["speed"], "在线优先", out_mp3)
            if ok and os.path.exists(out_mp3):
                seg_paths.append(out_mp3)
            
            # 添加停顿
            if seg.get("pause",0) > 0:
                pause_path = os.path.join(tmpdir, f"pause_{seg_idx}.mp3")
                create_silent_mp3(pause_path, seg["pause"])
                seg_paths.append(pause_path)
        
        # 合并音频
        if seg_paths:
            merged_audio = os.path.join(tmpdir, "preview_merged.mp3")
            try:
                concat_audios_ffmpeg(seg_paths, merged_audio)
                return merged_audio
            except Exception as e:
                st.error(f"预览音频合并失败: {e}")
        
        return None
    except Exception as e:
        st.error(f"预览音频生成失败: {e}")
        return None
    finally:
        # 注意：这里不删除临时目录，因为音频文件还需要使用
        pass

# ---------- 音色样本库 ----------
def ensure_sample_voice(voice_name: str, sample_text: str = "Hello, this is a sample.") -> Optional[str]:
    """生成或返回缓存的音色示例 mp3 路径"""
    key = hashlib.sha1(f"sample::{voice_name}".encode()).hexdigest()
    out = cache_get(key)
    if os.path.exists(out):
        return out
    
    # 生成示例
    fd, tmpmp3 = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    ok = False
    
    if EDGE_TTS_AVAILABLE:
        ok = generate_edge_mp3(sample_text, voice_name, 1.0, tmpmp3)
    
    if ok and os.path.exists(tmpmp3):
        cache_store(tmpmp3, key)
        safe_remove(tmpmp3)
        return cache_get(key)
    
    safe_remove(tmpmp3)
    return None

# ---------- 音标字符映射表 ----------
PHONETIC_CHAR_MAP = {
    # 修复常见音标字符显示问题
    'ɡ': 'g',  # U+0261 拉丁文小写字母 SCRIPT G -> 普通 g
    'ə': 'ə',  # 保持原字符，但确保字体支持
    'θ': 'θ',  # 保持原字符
    'ð': 'ð',  # 保持原字符
    'ʃ': 'ʃ',  # 保持原字符
    'ʒ': 'ʒ',  # 保持原字符
    'ŋ': 'ŋ',  # 保持原字符
    'ɪ': 'ɪ',  # 保持原字符
    'ʊ': 'ʊ',  # 保持原字符
    'ʌ': 'ʌ',  # 保持原字符
    'ɑ': 'ɑ',  # 保持原字符
    'ɒ': 'ɒ',  # 保持原字符
    'ɔ': 'ɔ',  # 保持原字符
    'ɜ': 'ɜ',  # 保持原字符
    'æ': 'æ',  # 保持原字符
    'ˈ': "'",  # 重音符号 -> 单引号
    'ˌ': ",",  # 次重音符号 -> 逗号
    'ː': ':',  # 长音符号 -> 冒号
}

def convert_phonetic_text(text):
    """转换音标文本，最小化字符转换"""
    if not text:
        return ""
    
    # 只转换确实有问题的字符，保留所有标准音标符号
    converted = ''.join(PHONETIC_CHAR_MAP.get(char, char) for char in text)
    
    # 如果转换后与原文本不同，记录日志
    if converted != text:
        st.info(f"音标已优化显示: `/{text}/` → `/{converted}/`")
    
    return converted

# ---------- 页面顶部 / 导航 ----------
st.markdown(f'<div class="main-title">🎬 英语视频生成器 - 专业级多音色教学视频制作平台</div>', unsafe_allow_html=True)
st.markdown(f"""<div class="navbar">
  <div class="nav-btn">📁 数据管理</div>
  <div class="nav-btn">🔊 音频设置</div>
  <div class="nav-btn">👀 效果预览</div>
  <div class="nav-btn">📤 生成输出</div>
</div>""", unsafe_allow_html=True)

# ---------- 数据管理部分 ----------
st.markdown('<div class="card-header">📁 数据管理</div>', unsafe_allow_html=True)
uploaded = st.file_uploader("拖拽上传 Excel/CSV/TXT（必须列名：英语、中文，音标可选）", type=["xlsx","xls","csv","txt"])
df = None
if uploaded:
    try:
        if uploaded.name.lower().endswith((".csv",".txt")):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)
        cols = [str(c).strip() for c in df.columns]
        df.columns = cols
        if "英语" not in df.columns or "中文" not in df.columns:
            st.error("必须包含列名：'英语' 和 '中文'（精确匹配）。")
            df = None
        else:
            if "音标" not in df.columns:
                df["音标"] = ""
            st.success(f"解析成功，{len(df)} 行")
            st.write("前 10 行预览：")
            st.markdown('<div class="compact-table">', unsafe_allow_html=True)
            st.dataframe(df.head(10), width='stretch')
            
            if st.button("在页面中编辑数据", width='stretch'):
                edited = st.data_editor(df, num_rows="dynamic", width='stretch')
                df = edited.copy()
                st.success("已应用编辑")
    except Exception as e:
        st.error(f"解析失败：{e}")
else:
    st.info("未上传数据，示例：请上传包含列 英语 / 中文（可选 音标）的文件。")

# ---------- 音频设置部分 ----------
st.markdown('<div class="card-header">🔊 音频设置</div>', unsafe_allow_html=True)

# 使用选项卡组织音频设置
tab_audio_config, tab_voice_library, tab_voice_settings = st.tabs(["🎵 音频编排", "🎙️ 音色样本库", "⚙️ 音色设置"])

with tab_audio_config:
    st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
    
    engine_pref = st.selectbox("引擎偏好", ["在线优先"], key="ui_engine_pref")
    st.caption(f"系统离线可用: {PYTTSX3_AVAILABLE}；在线 edge-tts 可用: {EDGE_TTS_AVAILABLE}")

    # 智能推荐 + 预设选择
    learning_goal = st.text_input("学习目标（用于智能推荐）", value="", key="ui_learning_goal")
    recommended = recommend_preset(learning_goal)
    preset_choice = st.selectbox("预设播放模式", ["(自定义)"] + list(PRESET_MODES.keys()), index=1 if recommended in PRESET_MODES else 0, key="ui_preset_choice")

    # 音频段数 - 默认为3
    n_segments = st.number_input("音频段数", min_value=1, max_value=12, value=3, step=1, key="ui_n_segments")

    # 构建段配置表
    audio_segments = []
    for si in range(int(n_segments)):
        st.markdown(f"**段 {si+1}**", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1.5, 1.2, 1, 1])
        with c1:
            # 根据段索引设置默认内容
            if si == 0:
                content_index = 0  # 英语
            elif si == 1:
                content_index = 0  # 英语
            else:  # si >= 2
                content_index = 2  # 中文
            content = st.selectbox(f"段{si+1} 内容", ["英语", "音标", "中文"], index=content_index, key=f"ui_seg_content_{si}")
        with c2:
            # 根据段索引设置默认音色库
            if si == 0:
                category_index = 0  # 英文女声
            elif si == 1:
                category_index = 1  # 英文男声
            else:  # si >= 2
                category_index = 2  # 中文音色
            category = st.selectbox(f"段{si+1} 音色库", ["英文女声", "英文男声", "中文音色"], index=category_index, key=f"ui_seg_cat_{si}")
        with c3:
            # 从音色设置中获取默认音色
            voice_settings_key = f"default_voice_{category}"
            default_voice = st.session_state.get(voice_settings_key, VOICE_LIBRARY.get(category, [""])[0])
            
            presets = VOICE_LIBRARY.get(category, [])
            ls = ["(默认)"] + presets
            vc = st.selectbox(f"段{si+1} 具体音色", ls, 
                             index=0 if default_voice not in presets else presets.index(default_voice) + 1,
                             key=f"ui_seg_preset_{si}")
        with c4:
            speed = st.slider(f"段{si+1} 语速", 0.5, 2.0, 1.0, 0.1, key=f"ui_seg_speed_{si}")
            pause = st.number_input(f"段{si+1} 停顿 (秒)", min_value=0.0, max_value=5.0, value=0.3, step=0.1, key=f"ui_seg_pause_{si}")
        
        voice_choice = None
        if vc != "(默认)":
            voice_choice = vc
        
        # 将配置添加到 audio_segments 列表
        audio_segments.append({
            "content": content,
            "voice_category": category,
            "voice_choice": voice_choice,
            "speed": speed,
            "pause": pause,
            "engine_pref": engine_pref
        })

with tab_voice_library:
    st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
    
    # 使用选项卡组织不同音色分类
    tab1, tab2, tab3 = st.tabs(["🎙️ 英文女声", "🎙️ 英文男声", "🎙️ 中文音色"])
    
    with tab1:
        st.markdown('<div class="voice-library">', unsafe_allow_html=True)
        for voice in EN_FEMALE:
            sample_path = ensure_sample_voice(voice, "This is a sample of female English voice.")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f'<div class="voice-name">{get_voice_display_name(voice)}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="voice-category">英文女声</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="voice-style">{get_voice_style(voice)}</div>', unsafe_allow_html=True)
            with col2:
                if sample_path and os.path.exists(sample_path):
                    st.audio(sample_path, format="audio/mp3")
                else:
                    st.warning("样本生成中...")
        
    
    with tab2:
        st.markdown('<div class="voice-library">', unsafe_allow_html=True)
        for voice in EN_MALE:
            sample_path = ensure_sample_voice(voice, "This is a sample of male English voice.")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f'<div class="voice-name">{get_voice_display_name(voice)}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="voice-category">英文男声</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="voice-style">{get_voice_style(voice)}</div>', unsafe_allow_html=True)
            with col2:
                if sample_path and os.path.exists(sample_path):
                    st.audio(sample_path, format="audio/mp3")
                else:
                    st.warning("样本生成中...")
        
    
    with tab3:
        st.markdown('<div class="voice-library">', unsafe_allow_html=True)
        for voice in ZH_VOICES:
            sample_path = ensure_sample_voice(voice, "这是一个中文音色样本。")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f'<div class="voice-name">{get_voice_display_name(voice)}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="voice-category">中文音色</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="voice-style">{get_voice_style(voice)}</div>', unsafe_allow_html=True)
            with col2:
                if sample_path and os.path.exists(sample_path):
                    st.audio(sample_path, format="audio/mp3")
                else:
                    st.warning("样本生成中...")

with tab_voice_settings:
    st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
    st.markdown("### 默认音色设置")
    st.info("在这里设置各类音色的默认选择，音频编排中的音色选择会默认使用这里的设置")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 英文女声")
        default_female = st.selectbox(
            "默认英文女声音色",
            options=EN_FEMALE,
            index=0,
            format_func=lambda x: f"{get_voice_display_name(x)} - {get_voice_style(x)}",
            key="default_voice_英文女声"
        )
    
    with col2:
        st.markdown("#### 英文男声")
        default_male = st.selectbox(
            "默认英文男声音色",
            options=EN_MALE,
            index=0,
            format_func=lambda x: f"{get_voice_display_name(x)} - {get_voice_style(x)}",
            key="default_voice_英文男声"
        )
    
    with col3:
        st.markdown("#### 中文音色")
        default_chinese = st.selectbox(
            "默认中文音色",
            options=ZH_VOICES,
            index=0,
            format_func=lambda x: f"{get_voice_display_name(x)} - {get_voice_style(x)}",
            key="default_voice_中文音色"
        )

# ---------- Frame rendering ----------
def render_frame(en, ph, cn, conf, size=(1280,720)):
    """渲染单帧图像 - 修复中文和音标显示问题"""
    W,H = size
    
    try:
        # 应用文字区域宽度比例
        text_area_width = int(W * conf.get("text_area_width_ratio", 0.85))
        text_start_x = (W - text_area_width) // 2
        
        # 创建背景
        if conf.get("bg_mode") == "image" and conf.get("bg_image"):
            # 使用背景图片
            bg_img = conf["bg_image"]
            # 调整背景图片大小以适应帧尺寸
            bg_img = bg_img.resize((W, H), Image.Resampling.LANCZOS)
            base = bg_img.convert("RGB")
        else:
            # 使用纯色背景
            bg_color = conf.get("bg_color", "#D1E1EF")  # 默认背景颜色
            base = Image.new("RGB", (W,H), bg_color)
        
        draw = ImageDraw.Draw(base)

        # 🔥 修复：使用专门的字体加载函数
        font_en = load_font(None, conf.get("english_size", 28))
        font_ph = load_phonetic_font(conf.get("phonetic_size", 22))
        font_cn = load_chinese_font(conf.get("chinese_size", 28))

        # 计算文本位置
        english_color = conf.get("english_color", "#000000")
        phonetic_color = conf.get("phonetic_color", "#E6BF20")
        chinese_color = conf.get("chinese_color", "#000000")
        
        # 计算总高度
        total_height = (
            conf.get("english_size", 28) + 
            conf.get("phonetic_size", 22) + 
            conf.get("chinese_size", 28) +
            conf.get("english_phonetic_gap", 10) +
            conf.get("phonetic_cn_gap", 10)
        )
        
        start_y = (H - total_height) // 2
        
        # 如果启用文字背景板，绘制背景
        if conf.get("text_bg_enable", False):
            padding = conf.get("text_padding", 20)
            bg_alpha = int(conf.get("text_bg_alpha", 0.35) * 255)
            bg_color = conf.get("text_bg_color", "#FFFFFF")
            bg_radius = conf.get("text_bg_radius", 12)
            
            # 创建半透明背景
            bg_rect = Image.new('RGBA', (text_area_width, total_height + padding * 2), (255, 255, 255, 0))
            bg_draw = ImageDraw.Draw(bg_rect)
            
            try:
                rgb_color = ImageColor.getrgb(bg_color)
                rgba_color = (*rgb_color, bg_alpha)
                bg_draw.rounded_rectangle(
                    [(0, 0), (text_area_width, total_height + padding * 2)],
                    radius=bg_radius,
                    fill=rgba_color
                )
            except Exception:
                rgba_color = (255, 255, 255, bg_alpha)
                bg_draw.rounded_rectangle(
                    [(0, 0), (text_area_width, total_height + padding * 2)],
                    radius=bg_radius,
                    fill=rgba_color
                )
            
            base.paste(bg_rect, (text_start_x, start_y - padding), bg_rect)
        
        # 英语
        y = start_y
        try:
            bbox = draw.textbbox((0, 0), en, font=font_en)
            text_width = bbox[2] - bbox[0]
            x = text_start_x + (text_area_width - text_width) // 2
            draw.text((x, y), en, font=font_en, fill=english_color)
        except:
            x = text_start_x + (text_area_width - len(en) * 20) // 2
            draw.text((x, y), en, font=font_en, fill=english_color)
        
        y += conf.get("english_size", 28) + conf.get("english_phonetic_gap", 10)
        
        # 音标 - 使用转换后的文本
        if ph and ph.strip():
            converted_ph = convert_phonetic_text(ph)
            try:
                bbox = draw.textbbox((0, 0), converted_ph, font=font_ph)
                text_width = bbox[2] - bbox[0]
                x = text_start_x + (text_area_width - text_width) // 2
                draw.text((x, y), converted_ph, font=font_ph, fill=phonetic_color)
            except Exception as e:
                # 如果音标渲染失败，尝试使用英文字体
                try:
                    bbox = draw.textbbox((0, 0), converted_ph, font=font_en)
                    text_width = bbox[2] - bbox[0]
                    x = text_start_x + (text_area_width - text_width) // 2
                    draw.text((x, y), converted_ph, font=font_en, fill=phonetic_color)
                except:
                    # 最终备选：显示原始文本
                    x = text_start_x + (text_area_width - len(converted_ph) * 15) // 2
                    draw.text((x, y), converted_ph, font=font_en, fill=phonetic_color)
            
            y += conf.get("phonetic_size", 22) + conf.get("phonetic_cn_gap", 10)
        
        # 中文 - 使用专门的中文字体
        try:
            bbox = draw.textbbox((0, 0), cn, font=font_cn)
            text_width = bbox[2] - bbox[0]
            x = text_start_x + (text_area_width - text_width) // 2
            draw.text((x, y), cn, font=font_cn, fill=chinese_color)
        except Exception as e:
            # 如果中文字体渲染失败，尝试使用英文字体
            try:
                bbox = draw.textbbox((0, 0), cn, font=font_en)
                text_width = bbox[2] - bbox[0]
                x = text_start_x + (text_area_width - text_width) // 2
                draw.text((x, y), cn, font=font_en, fill=chinese_color)
            except Exception as e2:
                # 最终备选：使用默认位置
                x = text_start_x + (text_area_width - len(cn) * 25) // 2
                draw.text((x, y), cn, font=font_en, fill=chinese_color)

        return base
    except Exception as e:
        st.error(f"帧渲染失败: {e}")
        error_img = Image.new("RGB", (W, H), conf.get("bg_color", "#D1E1EF"))
        draw = ImageDraw.Draw(error_img)
        draw.text((50, H//2), "渲染错误", fill="red")
        return error_img

# ---------- 效果预览部分 ----------
st.markdown('<div class="card-header">👀 效果预览</div>', unsafe_allow_html=True)

if uploaded is not None and df is not None:
    # 创建两列布局：左侧样式设计，右侧实时预览
    preview_col1, preview_col2 = st.columns([1, 1])
    
    with preview_col1:
        st.markdown('<div class="card-header">🎨 样式设计</div>', unsafe_allow_html=True)
        
        # 使用选项卡组织样式设置
        tab_bg, tab_text, tab_layout, tab_advanced = st.tabs(["🎨 背景设置", "🔤 文字样式", "📐 布局调整", "⚙️ 高级设置"])
        
        with tab_bg:
            st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
            # --- 背景设置 ---
            bg_col1, bg_col2 = st.columns([1,1])
            with bg_col1:
                bg_mode = st.selectbox("背景类型", ["纯色背景", "图片背景"], key="ui_bg_mode")
            with bg_col2:
                ui_bg_color = st.color_picker("背景颜色", "#D1E1EF", key="ui_bg_color")
            ui_bg_image = None
            if bg_mode == "图片背景":
                bg_file = st.file_uploader("上传背景图片 (JPG/PNG)", type=["jpg","jpeg","png"], key="ui_bgimg")
                if bg_file:
                    try:
                        ui_bg_image = Image.open(bg_file).convert("RGBA")
                        st.image(ui_bg_image, caption="背景预览", use_container_width=True)
                    except Exception:
                        st.error("无法读取背景图片")
        
        with tab_text:
            st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
            
            # --- 文字样式 ---
            st.markdown("**文字样式**")
            col_en, col_ph, col_cn = st.columns(3)
            with col_en:
                en_size = st.slider("英语字号", 0, 160, 28, key="ui_en_size")  # 默认改为28
                en_color = st.color_picker("英语颜色", "#000000", key="ui_en_color")
            with col_ph:
                ph_size = st.slider("音标字号", 0, 120, 22, key="ui_ph_size")  # 默认改为22
                ph_color = st.color_picker("音标颜色", "#E6BF20", key="ui_ph_color")
            with col_cn:
                cn_size = st.slider("中文字号", 0, 120, 28, key="ui_cn_size")  # 默认改为28
                cn_color = st.color_picker("中文颜色", "#000000", key="ui_cn_color")
            
            # 音标显示解决方案
            st.markdown("**音标显示解决方案**")
            st.success("""
            **已启用音标显示优化方案：**
            - ✅ 使用 Google Fonts 的 Noto Sans IPA 字体（专门支持音标）
            - ✅ 使用 Charis SIL 字体作为备选（专门为语言学设计）
            - ✅ 自动字符映射确保兼容性
            - ✅ 支持自定义字体上传
            """)
            
            # 字体信息显示
            st.markdown("**字体信息**")
            if 'custom_font_path' in st.session_state and st.session_state.custom_font_path:
                st.success(f"✅ 当前使用自定义字体")
            elif DEFAULT_FONT:
                font_name = os.path.basename(DEFAULT_FONT)
                st.info(f"📝 系统字体: {font_name}")
            else:
                st.warning("⚠️ 使用默认字体，音标显示可能不正常")
        
        with tab_layout:
            st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
            
            # --- 背景板与间距 ---
            st.markdown("**背景板与间距**")
            b1, b2, b3, b4 = st.columns(4)
            with b1:
                text_bg_enable = st.checkbox("启用文字背景板", value=True, key="ui_text_bg_enable")
            with b2:
                text_bg_color = st.color_picker("文字背景颜色", "#FFFFFF", key="ui_text_bg_color")
            with b3:
                text_bg_alpha = st.slider("背景透明度", 0.0, 1.0, 0.35, 0.05, key="ui_text_bg_alpha")
            with b4:
                text_bg_radius = st.slider("背景圆角", 0, 60, 12, key="ui_text_bg_radius")

            g1, g2, g3, g4 = st.columns(4)
            with g1:
                english_ph_gap = st.slider("英语→音标间距", 0, 200, 10, key="ui_gap_en_ph")
            with g2:
                ph_cn_gap = st.slider("音标→中文间距", 0, 200, 10, key="ui_gap_ph_cn")
            with g3:
                line_spacing = st.slider("行间距", 0, 50, 6, key="ui_line_spacing")
            with g4:
                text_padding = st.slider("文字内边距", 0, 120, 20, key="ui_text_padding")
            
            # --- 文字区域设置 ---
            st.markdown("**文字区域设置**")
            t1, t2 = st.columns(2)
            with t1:
                text_area_ratio = st.slider("文字区域宽度比例", 0.3, 1.0, 0.85, key="ui_text_area_ratio")
        
        with tab_advanced:
            st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
            
            # 自定义字体上传
            st.markdown("**自定义字体**")
            st.info("上传支持音标和中文的字体文件（TTF/OTF格式）")
            custom_font_file = st.file_uploader("上传自定义字体文件", type=["ttf", "otf"], key="ui_custom_font")
            if custom_font_file:
                try:
                    # 保存自定义字体到临时文件
                    custom_font_path = os.path.join(tempfile.gettempdir(), f"custom_font_{hashlib.md5(custom_font_file.getvalue()).hexdigest()}.ttf")
                    with open(custom_font_path, "wb") as f:
                        f.write(custom_font_file.getvalue())
                    st.session_state.custom_font_path = custom_font_path
                    st.success("✅ 自定义字体上传成功！")
                except Exception as e:
                    st.error(f"字体文件上传失败: {e}")
            
            # 字体测试
            st.markdown("**字体测试**")
            test_text = st.text_input("测试文本", value="Hello /həˈloʊ/ 你好", key="ui_font_test")
            if test_text:
                test_font_path = st.session_state.get('custom_font_path', DEFAULT_FONT)
                try:
                    test_font = ImageFont.truetype(test_font_path, 20) if test_font_path else ImageFont.load_default()
                    test_img = Image.new('RGB', (400, 50), color='white')
                    test_draw = ImageDraw.Draw(test_img)
                    test_draw.text((10, 10), test_text, font=test_font, fill='black')
                    st.image(test_img, caption="字体测试预览", use_container_width=True)
                    
                    # 显示转换后的音标
                    if '/' in test_text:
                        phonetic_part = test_text.split('/')[1] if len(test_text.split('/')) > 1 else ""
                        converted_phonetic = convert_phonetic_text(phonetic_part)
                        st.write(f"原始音标: {phonetic_part}")
                        st.write(f"转换后: /{converted_phonetic}/")
                except Exception as e:
                    st.error(f"字体测试失败: {e}")
    
    with preview_col2:
        st.markdown('<div class="card-header">👁️ 实时预览</div>', unsafe_allow_html=True)
        
        # 选择预览的行
        preview_row = st.selectbox(
            "选择预览的行",
            options=list(range(len(df))),
            format_func=lambda i: f"{i+1} - {df.iloc[i]['英语'][:30]}...",
            key="preview_row"
        )
        
        # 实时生成预览
        if st.button("🔄 更新预览", width='stretch'):
            st.session_state.force_preview_update = True
        
        # 汇总 style_conf
        style_conf = {
            "bg_mode": "image" if ui_bg_image else "color",
            "bg_color": ui_bg_color,
            "bg_image": ui_bg_image,
            "english_size": en_size,
            "english_color": en_color,
            "phonetic_size": ph_size,
            "phonetic_color": ph_color,
            "chinese_size": cn_size,
            "chinese_color": cn_color,
            "text_bg_enable": text_bg_enable,
            "text_bg_color": text_bg_color,
            "text_bg_alpha": text_bg_alpha,
            "text_bg_radius": text_bg_radius,
            "text_padding": text_padding,
            "text_area_width_ratio": text_area_ratio,
            "english_phonetic_gap": english_ph_gap,
            "phonetic_cn_gap": ph_cn_gap,
            "line_spacing": line_spacing,
        }
        
        # 实时渲染预览
        row = df.iloc[preview_row]
        en = str(row.get("英语",""))
        ph = str(row.get("音标",""))
        cn = str(row.get("中文",""))
        
        # 显示音标转换信息
        if ph and ph.strip():
            converted_ph = convert_phonetic_text(ph)
            if ph != converted_ph:
                st.info(f"音标已自动转换: `/{ph}/` → `/{converted_ph}/`")
            else:
                st.success(f"音标无需转换: `/{ph}/`")
        
        # 生成预览图像
        preview_image = render_frame(en, ph, cn, style_conf, (640, 360))
        
        # 显示实时预览
        st.markdown('<div class="live-preview-container">', unsafe_allow_html=True)
        st.markdown('<div class="live-preview-title">实时预览效果</div>', unsafe_allow_html=True)
        st.image(preview_image, caption="样式预览", use_container_width=True)
        
        # 显示预览文本
        st.markdown(f'<div class="live-preview-text live-preview-english">{en}</div>', unsafe_allow_html=True)
        if ph and ph.strip():
            converted_ph_display = convert_phonetic_text(ph)
            st.markdown(f'<div class="live-preview-text live-preview-phonetic">/{converted_ph_display}/</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="live-preview-text live-preview-chinese">{cn}</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 音频预览部分
        st.markdown("### 🔊 音频预览")
        if st.button("生成音频预览", width='stretch'):
            with st.spinner("正在生成音频预览..."):
                preview_audio = generate_preview_audio(df, preview_row, audio_segments)
                
                if preview_audio and os.path.exists(preview_audio):
                    st.audio(preview_audio, format="audio/mp3")
                    st.success("音频预览生成完成！")
                else:
                    st.error("音频预览生成失败")
        
else:
    st.warning("请先上传数据文件以启用预览功能")

# ---------- 获取音频时长 ----------
def get_audio_duration(audio_path: str) -> float:
    """获取音频文件的时长（秒）"""
    try:
        if PYDUB_AVAILABLE:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # 转换为秒
        else:
            # 备用方案：使用 ffprobe
            ffprobe_path = find_ffmpeg_path().replace("ffmpeg", "ffprobe")
            cmd = [
                ffprobe_path, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", audio_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return float(result.stdout.strip())
    except Exception as e:
        # 如果无法获取时长，返回默认值
        return 3.0

# ---------- 清除生成的视频文件 ----------
def clear_generated_videos():
    """清除所有生成的视频文件"""
    try:
        # 清除缓存目录中的视频文件
        pattern = os.path.join(CACHE_DIR, "generated_video_*.mp4")
        video_files = glob.glob(pattern)
        
        deleted_count = 0
        for video_file in video_files:
            try:
                os.remove(video_file)
                deleted_count += 1
            except Exception as e:
                st.warning(f"无法删除文件 {video_file}: {e}")
        
        return deleted_count
    except Exception as e:
        st.error(f"清除视频文件时出错: {e}")
        return 0

# ---------- 合成视频 ----------
def merge_video_audio(video_path, audio_path, out_path):
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg missing for merge_video_audio")
    cmd = [
        "ffmpeg","-y","-i",video_path,"-i",audio_path,
        "-c:v","copy","-c:a","aac","-shortest",out_path
    ]
    run_ffmpeg_command(cmd)

def generate_video_pipeline(df, rows, style_conf, audio_segments, video_params, progress_cb=None):
    """整合生成流程 - 修复版本"""
    tmpdir = tempfile.mkdtemp(prefix="gen_")
    try:
        W,H = video_params.get("resolution",(1280,720))
        fps = video_params.get("fps",12)
        
        frame_files = []
        audios = []
        total_steps = len(rows) * len(audio_segments) + 2  # +2 用于音频合并和视频合成
        step = 0
        
        for rid in rows:
            row = df.iloc[rid]
            en = str(row.get("英语",""))
            ph = str(row.get("音标",""))
            cn = str(row.get("中文",""))
            
            # 渲染当前单词的画面
            img = render_frame(en, ph, cn, style_conf, (W,H))
            
            # 音频生成
            seg_paths = []
            total_audio_duration = 0
            
            for seg_idx, seg in enumerate(audio_segments):
                text = en if seg["content"]=="英语" else (ph if seg["content"]=="音标" else cn)
                out_mp3 = os.path.join(tmpdir, f"{rid}_{seg_idx}_{seg['content']}.mp3")
                
                ok = generate_tts_cached(text, seg["voice_category"], seg["voice_choice"], seg["speed"], "在线优先", out_mp3)
                if ok and os.path.exists(out_mp3):
                    # 获取实际音频时长
                    audio_duration = get_audio_duration(out_mp3)
                    total_audio_duration += audio_duration
                    seg_paths.append(out_mp3)
                else:
                    # 如果TTS失败，使用默认时长
                    default_duration = 3.0
                    total_audio_duration += default_duration
                    create_silent_mp3(out_mp3, default_duration)
                    seg_paths.append(out_mp3)
                
                # 添加停顿
                if seg.get("pause",0) > 0:
                    pause_path = os.path.join(tmpdir, f"pause_{rid}_{seg_idx}.mp3")
                    create_silent_mp3(pause_path, seg["pause"])
                    total_audio_duration += seg["pause"]
                    seg_paths.append(pause_path)
                
                step += 1
                if progress_cb:
                    progress_cb(step/total_steps)

            # 合并当前行的音频
            if seg_paths:
                merged_audio = os.path.join(tmpdir, f"{rid}_merged.mp3")
                try:
                    concat_audios_ffmpeg(seg_paths, merged_audio)
                    audios.append(merged_audio)
                    
                    # 根据音频时长生成对应数量的帧
                    frames_this_word = int(total_audio_duration * fps)
                    for i in range(frames_this_word):
                        fname = os.path.join(tmpdir, f"{rid}_{i:04d}.png")
                        img.save(fname)
                        frame_files.append(fname)
                        
                except Exception as e:
                    st.error(f"音频合并失败: {e}")
                    # 使用默认帧数作为备选
                    frames_this_word = int(3.0 * fps)  # 默认3秒
                    for i in range(frames_this_word):
                        fname = os.path.join(tmpdir, f"{rid}_{i:04d}.png")
                        img.save(fname)
                        frame_files.append(fname)

        # 检查是否有足够的帧
        if not frame_files:
            st.error("没有生成任何帧，无法合成视频")
            return None
            
        # 合成视频（无音频）
        list_txt = os.path.join(tmpdir, "imgs.txt")
        with open(list_txt, "w", encoding="utf-8") as f:
            for p in frame_files:
                f.write(f"file '{p}'\n")
                f.write(f"duration {1.0/fps}\n")  # 每帧的持续时间
        
        video_no_audio = os.path.join(tmpdir, "video.mp4")
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", 
            "-i", list_txt, "-r", str(fps), "-pix_fmt", "yuv420p", 
            video_no_audio
        ]
        
        try:
            run_ffmpeg_command(cmd)
        except Exception as e:
            st.error(f"视频合成失败: {e}")
            return None
        
        # 合并所有音频
        if audios:
            final_audio = os.path.join(tmpdir, "final_audio.mp3")
            try:
                concat_audios_ffmpeg(audios, final_audio)
            except Exception as e:
                st.error(f"最终音频合并失败: {e}")
                return None
            
            # 合并音视频
            out_video = os.path.join(tmpdir, "final_out.mp4")
            cmd = [
                "ffmpeg", "-y", "-i", video_no_audio, "-i", final_audio,
                "-c:v", "copy", "-c:a", "aac", "-shortest", out_video
            ]
            try:
                run_ffmpeg_command(cmd)
            except Exception as e:
                st.error(f"音视频合并失败: {e}")
                return None
        else:
            out_video = video_no_audio
        
        if os.path.exists(out_video):
            # 关键修复：将视频文件复制到永久位置
            permanent_video_path = os.path.join(CACHE_DIR, f"generated_video_{int(time.time())}.mp4")
            try:
                shutil.copy2(out_video, permanent_video_path)
                return permanent_video_path
            except Exception as e:
                # 如果复制失败，仍然返回原始路径
                return out_video
        else:
            st.error("输出视频文件不存在")
            return None
            
    except Exception as e:
        st.error(f"生成流程异常: {e}")
        import traceback
        st.error(f"详细错误: {traceback.format_exc()}")
        return None
    finally:
        # 清理临时文件
        try:
            shutil.rmtree(tmpdir)
        except:
            pass

# ---------- 生成与下载部分 ----------
st.markdown('<div class="card-header">📤 生成与下载</div>', unsafe_allow_html=True)

# FFmpeg 检测和安装指引
ffmpeg_path = find_ffmpeg_path()
if not ffmpeg_available():
    st.error("⚠️ FFmpeg 未找到，视频生成功能不可用")
    
    if 'STREAMLIT_SHARING_MODE' in os.environ:
        st.info("""
        **Streamlit Cloud 环境检测**
        
        在 Streamlit Cloud 上，请确保 requirements.txt 包含：
        ```
        imageio[ffmpeg]>=2.33.0
        ```
        """)
    elif sys.platform.startswith("darwin"):
        st.info("""
        **macOS FFmpeg 安装：**
        ```bash
        brew install ffmpeg
        ```
        """)
    else:
        st.info("""
        **FFmpeg 安装指南：**
        
        **Windows:**
        1. 下载: https://ffmpeg.org/download.html
        2. 解压到 C:\\ffmpeg
        3. 添加 C:\\ffmpeg\\bin 到系统 PATH
        
        **Linux:**
        ```bash
        sudo apt-get install ffmpeg
        ```
        """)

# 视频清除机制
st.markdown("### 🧹 视频清除机制")
col_clear1, col_clear2 = st.columns([2, 1])
with col_clear1:
    st.info("清除之前生成的视频文件，释放存储空间")
with col_clear2:
    if st.button("🗑️ 清除所有生成的视频", width='stretch'):
        deleted_count = clear_generated_videos()
        if deleted_count > 0:
            st.success(f"✅ 已清除 {deleted_count} 个视频文件")
        else:
            st.info("没有找到可清除的视频文件")

# 在生成视频部分使用 audio_segments
if uploaded is not None and df is not None:
    total = len(df)
    
    # 默认选择所有行（全部）
    default_rows = list(range(total))  # 默认选择所有行
    
    rows = st.multiselect(
        "选择生成的行", 
        options=list(range(total)), 
        format_func=lambda i: f"{i+1} - {df.iloc[i]['英语'][:30]}...", 
        default=default_rows
    )
    
    if rows:
        if st.button("▶️ 开始生成视频", width='stretch', disabled=not ffmpeg_available()):
            # 预检查
            if not ffmpeg_available():
                st.error("FFmpeg 不可用，无法生成视频")
                st.stop()
                
            if df is None:
                st.error("没有数据可处理")
                st.stop()
                
            if not rows:
                st.error("请选择要生成的行")
                st.stop()
            
            progress = st.progress(0.0)
            status = st.empty()
            
            def cb(p):
                progress.progress(p)
                status.text(f"进度: {int(p*100)}%")
            
            params = {"resolution":(1280,720),"fps":12}
            status.text("生成中...")
            
            try:
                outp = generate_video_pipeline(df, rows, style_conf, audio_segments, params, progress_cb=cb)
                
                if outp and os.path.exists(outp):
                    st.success("✅ 视频生成完成")
                    with open(outp,"rb") as f:
                        st.video(f.read())
                    with open(outp,"rb") as f:
                        st.download_button("📥 下载视频", f, file_name="travel_english.mp4", width='stretch')
                else:
                    st.error("❌ 生成失败，请查看错误信息")
            except Exception as e:
                st.error(f"❌ 生成错误: {str(e)}")
                with st.expander("查看详细错误信息"):
                    st.code(traceback.format_exc())
    else:
        st.info("请选择至少一行进行生成。")
else:
    st.info("请先上传数据文件以启用视频生成功能")

# ---------- 侧边栏：模板与进度 ----------
st.sidebar.header("📦 模板与任务")
templates = load_templates()
if st.sidebar.button("保存当前配置为模板", width='stretch'):
    name = f"模板_{time.strftime('%H%M%S')}"
    success = save_template(name, style_conf, audio_segments, {"resolution":(1280,720),"fps":12})
    if success:
        st.sidebar.success(f"已保存模板 {name}")
    else:
        st.sidebar.error("保存模板失败，请查看错误信息")

if templates:
    st.sidebar.subheader("已保存的模板")
    for tname, tdata in templates:
        if st.sidebar.button(f"应用模板 {tname}", width='stretch'):
            # 应用模板时，只应用可序列化的样式配置
            for key, value in tdata["style"].items():
                if key in style_conf and not isinstance(style_conf.get(key), (Image.Image,)):
                    style_conf[key] = value
            audio_segments[:] = tdata["audio"]
            st.sidebar.info(f"已应用模板 {tname}")

# 学习进度
st.sidebar.header("📚 学习进度")
prog = load_progress()
st.sidebar.write(f"已学习记录条目：{len(prog)}")
if st.sidebar.button("清除学习记录", width='stretch'):
    save_progress({})
    st.sidebar.success("学习记录已清除")

# ---------- 环境提示 ----------
st.sidebar.header("🔧 系统环境")
st.sidebar.write(f"✅ 操作系统: {sys.platform}")
st.sidebar.write(f"✅ ffmpeg: {'可用' if ffmpeg_available() else '缺失'}")
if ffmpeg_path:
    st.sidebar.write(f"📍 路径: {ffmpeg_path}")
st.sidebar.write(f"✅ pyttsx3: {'可用' if PYTTSX3_AVAILABLE else '缺失'}")
st.sidebar.write(f"✅ edge-tts: {'可用' if EDGE_TTS_AVAILABLE else '缺失'}")
st.sidebar.write(f"✅ pydub: {'可用' if PYDUB_AVAILABLE else '缺失'}")

# 字体检测信息
if 'custom_font_path' in st.session_state and st.session_state.custom_font_path:
    st.sidebar.success("✅ 字体: 使用自定义字体")
elif DEFAULT_FONT:
    font_name = os.path.basename(DEFAULT_FONT)
    st.sidebar.info(f"✅ 字体: {font_name}")
else:
    st.sidebar.warning("⚠️ 字体: 使用默认字体")

# 检测运行环境
if 'STREAMLIT_SHARING_MODE' in os.environ:
    st.sidebar.info("🌐 Streamlit Cloud 环境")
else:
    st.sidebar.info("💻 本地运行环境")

# ---------- 页脚 ----------
st.markdown(
    f"""
    <div class='footer'>
    © 2025 英语视频生成器 • 技术支持：AI 多媒体实验室  
    环境：FFmpeg {"✅ 已检测" if ffmpeg_available() else "⚠️ 未检测"} | 平台: {sys.platform}
    </div>
    """,
    unsafe_allow_html=True)

