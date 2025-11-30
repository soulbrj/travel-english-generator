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
FONT_DIR = os.path.join(APP_TMP, "fonts")  # 新增字体目录

for p in (APP_TMP, CACHE_DIR, SAMPLES_DIR, TEMPLATE_DIR, FONT_DIR):
    os.makedirs(p, exist_ok=True)

# ---------- 字体处理 ----------
# 确保中文字体可用
def get_available_fonts():
    """获取可用字体列表，优先确保中文字体"""
    # 预定义一些常见的中文字体名称
    chinese_fonts = [
        "SimHei", "WenQuanYi Micro Hei", "Heiti TC",  # 黑体
        "Microsoft YaHei", "Microsoft JhengHei",     # 微软雅黑
        "SimSun", "NSimSun",                         # 宋体
        "SimKai",                                    # 楷体
        "SimFang",                                   # 仿宋
    ]
    
    # 尝试从系统获取字体
    try:
        from matplotlib.font_manager import findSystemFonts, FontProperties
        system_fonts = findSystemFonts()
        available_fonts = []
        for font_path in system_fonts:
            try:
                font_name = FontProperties(fname=font_path).get_name()
                available_fonts.append((font_name, font_path))
            except:
                continue
        
        # 检查是否有可用的中文字体
        for font_name in chinese_fonts:
            for name, path in available_fonts:
                if font_name.lower() in name.lower():
                    return name, path
        
        # 如果没有找到中文字体，尝试使用默认字体
        if available_fonts:
            return available_fonts[0]
    except:
        pass
    
    # 如果所有方法都失败，尝试下载一个开源中文字体
    return download_default_font()

def download_default_font():
    """下载一个默认的中文字体"""
    try:
        import requests
        
        # 选择一个开源中文字体（这里使用思源黑体）
        font_url = "https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/SourceHanSansSC-Regular.otf"
        font_path = os.path.join(FONT_DIR, "SourceHanSansSC-Regular.otf")
        
        if not os.path.exists(font_path):
            response = requests.get(font_url)
            with open(font_path, 'wb') as f:
                f.write(response.content)
        
        return "Source Han Sans SC", font_path
    except:
        # 如果下载失败，返回默认字体
        return "Arial Unicode MS", None

# 获取可用字体
CHINESE_FONT_NAME, CHINESE_FONT_PATH = get_available_fonts()
ENGLISH_FONT_NAME = "Charis SIL"
PHONETIC_FONT_NAME = "Charis SIL"

def get_font(size, font_type='chinese'):
    """获取指定大小和类型的字体"""
    try:
        if font_type == 'chinese':
            if CHINESE_FONT_PATH:
                return ImageFont.truetype(CHINESE_FONT_PATH, size)
            # 尝试使用系统中文字体
            for font_name in ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "Microsoft YaHei"]:
                try:
                    return ImageFont.truetype(font_name, size)
                except:
                    continue
        elif font_type == 'english':
            try:
                return ImageFont.truetype(ENGLISH_FONT_NAME, size)
            except:
                pass
        elif font_type == 'phonetic':
            try:
                return ImageFont.truetype(PHONETIC_FONT_NAME, size)
            except:
                pass
        
        #  fallback to default font
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

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
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap');

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

/* 使用组合字体，确保中文显示 */
.english-text {{
    font-family: 'Charis SIL', 'Noto Sans SC', sans-serif;
}}

.phonetic-text {{
    font-family: 'Charis SIL', 'Arial Unicode MS', 'Noto Sans SC', sans-serif;
}}

.chinese-text {{
    font-family: 'Noto Sans SC', 'Noto Sans TC', 'Microsoft YaHei', 'Heiti TC', sans-serif;
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
</style>
""", unsafe_allow_html=True)

# 以下是原代码中剩余的功能实现部分，保持不变
# ...
