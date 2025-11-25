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
import traceback
import subprocess
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
  margin-bottom: 16px;
  font-weight: 500;
}}

.stProgress > div > div > div {{
  background: linear-gradient(90deg, var(--gradient-start), var(--gradient-end));
  border-radius: 8px;
}}

/* 自定义Tabs样式 */
.stTabs {{
  margin-top: 16px;
}}

.stTabs > div > div > div > div[data-baseweb="tab"][aria-selected="true"] {{
  background: transparent !important;
  color: var(--accent-primary) !important;
  border-bottom: 3px solid var(--accent-primary) !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  font-weight: 700;
}}

.stTabs > div > div > div {{
  gap: 8px;
}}

.stTabs > div > div > div > div {{
  color: var(--text-dark);
  border-radius: 0;
  padding: 12px 20px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  transition: all 0.3s ease;
  font-weight: 500;
}}

.stTabs > div > div > div > div:hover  {{
  background: rgba(99, 102, 241, 0.05);
  border-bottom: 2px solid rgba(99, 102, 241, 0.3);
  color: var(--accent-primary);
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
}}

.live-preview-chinese {{
  font-size: 20px;
  color: {TEXT_DARK};
}}

/* 删除按钮样式 */
.delete-btn {{
  background: linear-gradient(135deg, #ef4444, #dc2626) !important;
  color: white !important;
  border-radius: 8px !important;
  padding: 6px 12px !important;
  font-weight: 500 !important;
  border: none !important;
  transition: all 0.3s ease !important;
  font-size: 12px !important;
  margin-top: 8px !important;
}}

.delete-btn:hover {{
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3) !important;
  background: linear-gradient(135deg, #dc2626, #b91c1c) !important;
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
    """查找支持中文和音标符号的字体 - 增强版本"""
    cand = []
    
    # 优先选择支持中文的字体
    if sys.platform.startswith("win"):
        # Windows系统字体路径
        windows_fonts_dir = r"C:\Windows\Fonts"
        cand = [
            # 中文字体（优先）
            os.path.join(windows_fonts_dir, "simhei.ttf"),        # 黑体 - 很好的中文支持
            os.path.join(windows_fonts_dir, "msyh.ttc"),          # 微软雅黑 - 现代中文支持
            os.path.join(windows_fonts_dir, "msyhbd.ttc"),        # 微软雅黑 Bold
            os.path.join(windows_fonts_dir, "simsun.ttc"),        # 宋体 - 传统中文支持
            os.path.join(windows_fonts_dir, "simsunb.ttf"),       # 宋体 Bold
            # 支持音标的字体
            os.path.join(windows_fonts_dir, "arialuni.ttf"),      # Arial Unicode MS - 支持音标和中文
            os.path.join(windows_fonts_dir, "seguisym.ttf"),      # Segoe UI Symbol - 支持音标
            # 英文字体
            os.path.join(windows_fonts_dir, "arial.ttf"),         # Arial - 英文支持
            os.path.join(windows_fonts_dir, "times.ttf"),         # Times New Roman
        ]
                
    elif sys.platform.startswith("darwin"):
        # macOS 字体路径
        cand = [
            "/System/Library/Fonts/PingFang.ttc",                 # 苹方 - 很好的中文支持
            "/System/Library/Fonts/STHeiti Light.ttc",            # 黑体-简
            "/System/Library/Fonts/STHeiti Medium.ttc",           # 黑体-中
            "/System/Library/Fonts/Arial Unicode.ttf",            # Arial Unicode
            "/Library/Fonts/Arial Unicode.ttf",                   # Arial Unicode (备用路径)
        ]
    else:
        # Linux 字体路径
        cand = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",     # 文泉驿微米黑
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",       # 文泉驿正黑
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",    # DejaVu Sans
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", # Liberation Sans
        ]
    
    # 返回第一个存在的字体
    for font_path in cand:
        if os.path.exists(font_path):
            print(f"找到字体: {font_path}")  # 调试信息
            return font_path
    
    # 如果找不到任何字体，尝试系统默认字体
    try:
        default_font = ImageFont.load_default()
        print("使用系统默认字体")  # 调试信息
        return None  # 返回None表示使用默认字体
    except:
        print("无法加载任何字体")  # 调试信息
        return None

DEFAULT_FONT = find_font()

def load_font(path, size, bold=False):
    """加载字体，如果失败则使用备用字体"""
    # 如果path为None，使用默认字体
    if path is None:
        try:
            return ImageFont.load_default()
        except:
            # 创建基本的字体
            return ImageFont.load_default()
    
    try:
        if os.path.exists(path):
            font = ImageFont.truetype(path, size)
            return font
        else:
            raise FileNotFoundError(f"字体文件不存在: {path}")
    except Exception as e:
        print(f"字体加载失败 {path}: {e}")
    
    # 尝试备用字体 - 跨平台通用字体
    backup_fonts = []
    if sys.platform.startswith("win"):
        backup_fonts = [
            r"C:\Windows\Fonts\simhei.ttf",      # 黑体
            r"C:\Windows\Fonts\msyh.ttc",        # 微软雅黑
            r"C:\Windows\Fonts\arial.ttf",       # Arial
        ]
    elif sys.platform.startswith("darwin"):
        backup_fonts = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Arial.ttf",
        ]
    else:
        backup_fonts = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    
    for font_path in backup_fonts:
        try:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    
    # 最后使用默认字体
    try:
        return ImageFont.load_default()
    except:
        # 如果连默认字体都失败，创建一个基本的字体
        return ImageFont.load_default()

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

# ---------- 模板 / 进度 存取 ----------
def save_template(name, style_conf, audio_segments, video_params):
    ensure_dir(TEMPLATE_DIR)
    p = os.path.join(TEMPLATE_DIR, f"{name}.json")
    json.dump({"style":style_conf,"audio":audio_segments,"video":video_params}, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

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

# ---------- TTS 测试函数 ----------
def test_edge_tts():
    """测试 edge-tts 是否正常工作"""
    if not EDGE_TTS_AVAILABLE:
        return "edge-tts 不可用"
    
    try:
        import edge_tts
        # 测试简单的英文文本
        communicate = edge_tts.Communicate(text="Hello world", voice="en-US-JennyNeural")
        test_file = os.path.join(CACHE_DIR, "test_tts.mp3")
        communicate.save(test_file)
        
        if os.path.exists(test_file) and os.path.getsize(test_file) > 1024:
            return f"✅ edge-tts 工作正常，文件大小: {os.path.getsize(test_file)} 字节"
        else:
            return f"❌ edge-tts 生成的文件异常，大小: {os.path.getsize(test_file) if os.path.exists(test_file) else 0} 字节"
            
    except Exception as e:
        return f"❌ edge-tts 测试失败: {str(e)}"

# ---------- TTS 辅助函数 ----------
def generate_edge_mp3(text: str, voice: str, speed: float, out_mp3: str) -> bool:
    """同步封装 edge-tts - 增强版本"""
    if not EDGE_TTS_AVAILABLE:
        st.error("❌ edge-tts 不可用")
        return False
    
    # 检查文本是否有效
    if not text or text.strip() == "":
        st.warning("⚠️ 文本为空，跳过TTS生成")
        return False
    
    # 清理文本，移除可能的问题字符
    text = text.strip()
    
    pct = int((speed - 1.0) * 100)
    rate_str = f"{pct:+d}%"
    
    try:
        st.info(f"🔊 生成TTS: '{text[:50]}...' (音色: {voice}, 语速: {speed})")
        
        # 直接同步调用
        import edge_tts
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate_str)
        
        # 同步保存
        communicate.save(out_mp3)
        
        # 等待文件写入完成
        import time
        time.sleep(0.5)
        
        # 检查生成的文件
        if os.path.exists(out_mp3):
            file_size = os.path.getsize(out_mp3)
            if file_size > 2048:  # 至少2KB，正常TTS文件应该大于这个值
                st.success(f"✅ TTS生成成功: {file_size} 字节")
                return True
            else:
                st.warning(f"⚠️ 生成的音频文件过小: {file_size} 字节 (期望 > 2KB)")
                # 删除无效文件
                safe_remove(out_mp3)
                return False
        else:
            st.error("❌ TTS生成失败: 文件未创建")
            return False
            
    except Exception as e:
        st.error(f"❌ TTS生成异常: {str(e)}")
        # 删除可能创建的不完整文件
        safe_remove(out_mp3)
        return False

def generate_tts_with_fallback(text: str, voice_category: Optional[str], voice_choice: Optional[str], speed: float, out_mp3: str) -> bool:
    """带备选方案的TTS生成"""
    voice_name = voice_choice or (VOICE_LIBRARY.get(voice_category, [None])[0] if voice_category else None)
    if not voice_name:
        st.error("❌ 未指定音色")
        return False
    
    # 方案1: 使用 edge-tts
    if EDGE_TTS_AVAILABLE:
        if generate_edge_mp3(text, voice_name, speed, out_mp3):
            return True
        else:
            st.warning("⚠️ edge-tts 失败，尝试备选方案")
    
    # 方案2: 使用 pyttsx3（离线）
    if PYTTSX3_AVAILABLE:
        try:
            st.info("🔄 尝试使用 pyttsx3 (离线TTS)")
            engine = pyttsx3.init()
            
            # 设置语速
            engine.setProperty('rate', 150 * speed)  # 基础语速150，根据speed调整
            
            # 尝试设置音色
            voices = engine.getProperty('voices')
            if voices:
                # 简单尝试匹配音色
                if "female" in voice_name.lower() or "jenny" in voice_name.lower() or "aria" in voice_name.lower():
                    for voice in voices:
                        if "female" in voice.name.lower() or "zira" in voice.name.lower():
                            engine.setProperty('voice', voice.id)
                            break
                else:
                    for voice in voices:
                        if "male" in voice.name.lower() or "david" in voice.name.lower():
                            engine.setProperty('voice', voice.id)
                            break
            
            # 保存到文件
            engine.save_to_file(text, out_mp3)
            engine.runAndWait()
            
            # 检查文件
            if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1024:
                st.success("✅ pyttsx3 TTS 生成成功")
                return True
            else:
                st.warning("⚠️ pyttsx3 生成的文件异常")
                safe_remove(out_mp3)
                
        except Exception as e:
            st.error(f"❌ pyttsx3 失败: {str(e)}")
            safe_remove(out_mp3)
    
    # 方案3: 创建静音文件作为最后备选
    st.warning("⚠️ 所有TTS方案都失败，创建静音文件")
    return create_silent_mp3(out_mp3, 3.0)  # 3秒静音

def generate_tts_cached(text: str, voice_category: Optional[str], voice_choice: Optional[str], speed: float, engine_pref: str, out_mp3: str) -> bool:
    """缓存层：优先使用缓存 - 增强版本"""
    if not text or text.strip() == "":
        st.warning("⚠️ 文本为空")
        return False
        
    voice_name = voice_choice or (VOICE_LIBRARY.get(voice_category, [None])[0] if voice_category else None)
    if not voice_name:
        st.error("❌ 未指定音色")
        return False
        
    key = hash_text_meta(text, voice_name or "default", speed)
    
    # 检查缓存
    if cache_exists(key):
        try:
            cached_file = cache_get(key)
            if os.path.exists(cached_file) and os.path.getsize(cached_file) > 2048:
                shutil.copy(cached_file, out_mp3)
                st.success("✅ 使用缓存音频")
                return True
            else:
                st.warning("⚠️ 缓存文件异常，重新生成")
                safe_remove(cached_file)
        except Exception as e:
            st.warning(f"⚠️ 缓存读取失败: {e}")
    
    # 临时输出
    fd, tmpmp3 = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    
    # 使用增强的TTS生成函数
    ok = generate_tts_with_fallback(text, voice_category, voice_choice, speed, tmpmp3)
    
    if ok and os.path.exists(tmpmp3) and os.path.getsize(tmpmp3) > 1024:
        try:
            # 存储到缓存
            cache_store(tmpmp3, key)
            # 复制到输出路径
            shutil.copy(cache_get(key), out_mp3)
            safe_remove(tmpmp3)
            return True
        except Exception as e:
            st.warning(f"⚠️ 缓存存储失败: {e}")
            try:
                shutil.copy(tmpmp3, out_mp3)
                safe_remove(tmpmp3)
                return True
            except:
                safe_remove(tmpmp3)
                return False
    else:
        safe_remove(tmpmp3)
        st.error("❌ TTS生成完全失败")
        return False

# ---------- 基本音频处理 ----------
def create_silent_mp3(out_path: str, duration_s: float) -> bool:
    """创建一段静音 mp3"""
    try:
        # 首先尝试使用pydub
        if PYDUB_AVAILABLE:
            from pydub import AudioSegment
            silent_audio = AudioSegment.silent(duration=int(duration_s * 1000))  # 毫秒
            silent_audio.export(out_path, format="mp3")
            return os.path.exists(out_path)
        # 其次尝试ffmpeg
        elif ffmpeg_available():
            cmd = ["ffmpeg","-y","-f","lavfi","-i",f"anullsrc=r=44100:cl=mono","-t",str(duration_s), out_path]
            run_ffmpeg_command(cmd)
            return os.path.exists(out_path)
        else:
            # 如果都没有，我们尝试用wave创建一个WAV文件，然后转换？但是这里要求mp3，没有转换工具。
            # 如果以上都不可用，我们只能创建一个无效的空文件。
            with open(out_path, "wb") as f: 
                f.write(b"")
            return True
    except Exception as e:
        print(f"创建静音文件失败: {e}")
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
    """生成预览音频 - 同步版本"""
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
            
            # 同步生成TTS
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
    """生成或返回缓存的音色示例 mp3 路径 - 同步版本"""
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

# ---------- TXT文件解析函数 ----------
def parse_txt_file(uploaded_file):
    """解析TXT文件内容为DataFrame"""
    content = uploaded_file.read().decode('utf-8')
    lines = content.strip().split('\n')
    
    data = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 解析格式：英语 - 音标 - 中文
        parts = line.split(' - ', 2)  # 最多分割成3部分
        if len(parts) == 3:
            english, phonetic, chinese = parts
            data.append({
                '英语': english.strip(),
                '音标': phonetic.strip(),
                '中文': chinese.strip()
            })
        elif len(parts) == 2:
            # 如果没有音标，只有英语和中文
            english, chinese = parts
            data.append({
                '英语': english.strip(),
                '音标': '',
                '中文': chinese.strip()
            })
        else:
            # 如果格式不匹配，尝试其他分隔符
            if ' - ' in line:
                # 已经尝试过，跳过
                continue
            elif ' /' in line and '/ ' in line:
                # 尝试解析包含音标的格式
                phonetic_start = line.find(' /')
                phonetic_end = line.find('/ ')
                if phonetic_start != -1 and phonetic_end != -1:
                    english = line[:phonetic_start].strip()
                    phonetic = line[phonetic_start:phonetic_end+1].strip()
                    chinese = line[phonetic_end+1:].strip()
                    data.append({
                        '英语': english,
                        '音标': phonetic,
                        '中文': chinese
                    })
                else:
                    # 如果还是无法解析，将整行作为英语
                    data.append({
                        '英语': line.strip(),
                        '音标': '',
                        '中文': ''
                    })
            else:
                # 如果还是无法解析，将整行作为英语
                data.append({
                    '英语': line.strip(),
                    '音标': '',
                    '中文': ''
                })
    
    return pd.DataFrame(data)

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
            if uploaded.name.lower().endswith(".txt"):
                # 使用新的TXT文件解析函数
                df = parse_txt_file(uploaded)
            else:
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
        st.info("TXT文件格式要求：每行格式为 '英语句子 - 音标 - 中文解释'")
else:
    st.info("未上传数据，示例：请上传包含列 英语 / 中文（可选 音标）的文件。")

# ---------- 音频设置部分 ----------
st.markdown('<div class="card-header">🔊 音频设置</div>', unsafe_allow_html=True)

# 使用选项卡组织音频设置
tab_audio_config, tab_voice_library, tab_voice_settings = st.tabs(["🎵 音频编排", "🎙️ 音色样本库", "⚙️ 音色设置"])

with tab_audio_config:
    st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
    
    # 网络状态检查
    st.markdown("### 🌐 网络状态检查")
    col1, col2 = st.columns(2)
    
    with col1:
        if EDGE_TTS_AVAILABLE:
            st.success("✅ edge-tts: 已安装")
        else:
            st.error("❌ edge-tts: 未安装")
            
    with col2:
        # 简单的网络连通性测试
        try:
            import urllib.request
            urllib.request.urlopen("http://www.microsoft.com", timeout=5)
            st.success("✅ 网络连接: 正常")
        except:
            st.error("❌ 网络连接: 可能有问题")
    
    engine_pref = st.selectbox("引擎偏好", ["在线优先", "离线优先"], key="ui_engine_pref")
    st.caption(f"系统离线可用: {PYTTSX3_AVAILABLE}；在线 edge-tts 可用: {EDGE_TTS_AVAILABLE}")

    # 智能推荐 + 预设选择
    learning_goal = st.text_input("学习目标（用于智能推荐）", value="", key="ui_learning_goal")
    recommended = recommend_preset(learning_goal)
    preset_choice = st.selectbox("预设播放模式", ["(自定义)"] + list(PRESET_MODES.keys()), index=1 if recommended in PRESET_MODES else 0, key="ui_preset_choice")

    # 初始化音频段 - 修复：默认使用英文女生、英文男生、中文音色
    if 'audio_segments' not in st.session_state:
        st.session_state.audio_segments = [
            {"content": "英语", "voice_category": "英文女声", "voice_choice": None, "speed": 1.0, "pause": 0.3},
            {"content": "英语", "voice_category": "英文男声", "voice_choice": None, "speed": 1.0, "pause": 0.3},
            {"content": "中文", "voice_category": "中文音色", "voice_choice": None, "speed": 1.0, "pause": 0.5}
        ]

    # 应用预设
    if preset_choice != "(自定义)" and preset_choice in PRESET_MODES:
        if st.button("应用预设"):
            st.session_state.audio_segments = PRESET_MODES[preset_choice].copy()
            st.success(f"已应用 {preset_choice} 预设")
            st.rerun()

    # 构建段配置表
    audio_segments = st.session_state.audio_segments
    
    # 添加新段的按钮
    if st.button("➕ 添加音频段", key="add_audio_segment"):
        st.session_state.audio_segments.append({
            "content": "英语", 
            "voice_category": "英文女声", 
            "voice_choice": None, 
            "speed": 1.0, 
            "pause": 0.3
        })
        st.rerun()

    for si, seg in enumerate(audio_segments):
        st.markdown(f"**段 {si+1}**", unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns([1.5, 1.2, 1, 1, 0.8])
        
        with c1:
            content = st.selectbox(
                f"段{si+1} 内容", 
                ["英语", "音标", "中文"], 
                index=["英语", "音标", "中文"].index(seg["content"]),
                key=f"ui_seg_content_{si}"
            )
            st.session_state.audio_segments[si]["content"] = content
            
        with c2:
            category = st.selectbox(
                f"段{si+1} 音色库", 
                ["英文女声", "英文男声", "中文音色"], 
                index=["英文女声", "英文男声", "中文音色"].index(seg["voice_category"]),
                key=f"ui_seg_cat_{si}"
            )
            st.session_state.audio_segments[si]["voice_category"] = category
            
        with c3:
            # 从音色设置中获取默认音色
            voice_settings_key = f"default_voice_{category}"
            default_voice = st.session_state.get(voice_settings_key, VOICE_LIBRARY.get(category, [""])[0])
            
            presets = VOICE_LIBRARY.get(category, [])
            ls = ["(默认)"] + presets
            current_choice = seg["voice_choice"] or "(默认)"
            
            vc = st.selectbox(
                f"段{si+1} 具体音色", 
                ls, 
                index=ls.index(current_choice) if current_choice in ls else 0,
                key=f"ui_seg_preset_{si}"
            )
            st.session_state.audio_segments[si]["voice_choice"] = None if vc == "(默认)" else vc
            
        with c4:
            speed = st.slider(
                f"段{si+1} 语速", 
                0.5, 2.0, seg["speed"], 0.1, 
                key=f"ui_seg_speed_{si}"
            )
            st.session_state.audio_segments[si]["speed"] = speed
            
            pause = st.number_input(
                f"段{si+1} 停顿 (秒)", 
                min_value=0.0, max_value=5.0, value=seg["pause"], step=0.1, 
                key=f"ui_seg_pause_{si}"
            )
            st.session_state.audio_segments[si]["pause"] = pause
            
        with c5:
            # 删除按钮
            if len(audio_segments) > 1:  # 至少保留一个段
                if st.button("🗑️", key=f"delete_seg_{si}", help="删除此音频段"):
                    st.session_state.audio_segments.pop(si)
                    st.rerun()
            else:
                st.write("")  # 占位

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
            index=EN_FEMALE.index("en-GB-SoniaNeural") if "en-GB-SoniaNeural" in EN_FEMALE else 0,
            format_func=get_voice_display_name,
            key="default_voice_英文女声"
        )
    
    with col2:
        st.markdown("#### 英文男声")
        default_male = st.selectbox(
            "默认英文男声音色",
            options=EN_MALE,
            index=EN_MALE.index("en-GB-RyanNeural") if "en-GB-RyanNeural" in EN_MALE else 0,
            format_func=get_voice_display_name,
            key="default_voice_英文男声"
        )
    
    with col3:
        st.markdown("#### 中文音色")
        default_chinese = st.selectbox(
            "默认中文音色",
            options=ZH_VOICES,
            index=ZH_VOICES.index("zh-CN-XiaoxiaoNeural") if "zh-CN-XiaoxiaoNeural" in ZH_VOICES else 0,
            format_func=get_voice_display_name,
            key="default_voice_中文音色"
        )

# ---------- Frame rendering ----------
def render_frame(en, ph, cn, conf, size=(1280,720)):
    """渲染单帧图像 - 增强字体处理"""
    W,H = size
    
    try:
        # 应用文字区域宽度比例
        text_area_width = int(W * conf.get("text_area_width_ratio", 0.88))
        text_start_x = (W - text_area_width) // 2
        
        # 创建背景
        if conf.get("bg_mode") == "image" and conf.get("bg_image"):
            # 使用背景图片
            bg_img = conf["bg_image"]
            # 调整背景图片大小以适应帧尺寸
            bg_img = bg_img.resize((W, H), Image.Resampling.LANCZOS)
            
            # 应用背景透明度
            bg_alpha = conf.get("bg_image_alpha", 1.0)
            if bg_alpha < 1.0:
                # 创建透明背景
                base = Image.new("RGBA", (W, H), (255, 255, 255, 0))
                # 将背景图片转换为RGBA
                bg_img = bg_img.convert("RGBA")
                # 调整透明度
                if bg_img.mode == 'RGBA':
                    # 分离alpha通道
                    r, g, b, a = bg_img.split()
                    # 调整alpha通道
                    a = a.point(lambda i: i * bg_alpha)
                    bg_img = Image.merge('RGBA', (r, g, b, a))
                base.paste(bg_img, (0, 0), bg_img)
            else:
                base = bg_img.convert("RGB")
        else:
            # 使用纯色背景
            bg_color = conf.get("bg_color", "#D1E1EF")  # 默认背景颜色
            base = Image.new("RGB", (W,H), bg_color)
        
        draw = ImageDraw.Draw(base)

        # 加载字体 - 使用用户选择的字体或默认字体
        selected_font_path = conf.get("font_path", DEFAULT_FONT)
        
        # 加载英文字体（使用用户选择的字体）
        font_en = load_font(selected_font_path, conf.get("english_size", 46))
        font_ph = load_font(selected_font_path, conf.get("phonetic_size", 30))
        
        # 为中文字体准备备用字体
        # 如果用户选择的字体不支持中文，使用系统默认的支持中文的字体
        chinese_font_path = selected_font_path
        if selected_font_path:
            # 检查选择的字体是否可能不支持中文
            font_name_lower = selected_font_path.lower()
            if not any(keyword in font_name_lower for keyword in 
                      ['simhei', 'msyh', 'simsun', 'pingfang', 'stheit', 'wqy', 'arialuni']):
                # 如果不包含中文字体关键词，使用默认字体作为中文备用
                chinese_font_path = DEFAULT_FONT
        
        font_cn = load_font(chinese_font_path, conf.get("chinese_size", 46))

        # 计算文本位置
        english_color = conf.get("english_color", "#000000")  # 默认黑色
        phonetic_color = conf.get("phonetic_color", "#E6BF20")  # 默认音标颜色
        chinese_color = conf.get("chinese_color", "#000000")  # 默认黑色
        
        # 获取加粗设置
        english_bold = conf.get("english_bold", False)
        phonetic_bold = conf.get("phonetic_bold", False)
        chinese_bold = conf.get("chinese_bold", False)
        
        # 计算总高度
        total_height = (
            conf.get("english_size", 46) + 
            conf.get("phonetic_size", 30) + 
            conf.get("chinese_size", 46) +
            conf.get("english_phonetic_gap", 10) +
            conf.get("phonetic_cn_gap", 10)
        )
        
        start_y = (H - total_height) // 2
        
        # 如果启用文字背景板，绘制背景
        if conf.get("text_bg_enable", False):
            # 计算背景区域
            padding = conf.get("text_padding", 20)
            bg_alpha = int(conf.get("text_bg_alpha", 0.35) * 255)
            bg_color = conf.get("text_bg_color", "#FFFFFF")
            bg_radius = conf.get("text_bg_radius", 12)
            
            # 创建半透明背景
            bg_rect = Image.new('RGBA', (text_area_width, total_height + padding * 2), (255, 255, 255, 0))
            bg_draw = ImageDraw.Draw(bg_rect)
            
            # 绘制圆角矩形 - 修复颜色转换问题
            try:
                # 使用 ImageColor.getrgb 将颜色字符串转换为 RGB 元组
                rgb_color = ImageColor.getrgb(bg_color)
                # 添加 alpha 通道
                rgba_color = (*rgb_color, bg_alpha)
                bg_draw.rounded_rectangle(
                    [(0, 0), (text_area_width, total_height + padding * 2)],
                    radius=bg_radius,
                    fill=rgba_color
                )
            except Exception as e:
                # 如果颜色转换失败，使用白色作为备选
                rgba_color = (255, 255, 255, bg_alpha)
                bg_draw.rounded_rectangle(
                    [(0, 0), (text_area_width, total_height + padding * 2)],
                    radius=bg_radius,
                    fill=rgba_color
                )
            
            # 将背景合成到主图像上
            base.paste(bg_rect, (text_start_x, start_y - padding), bg_rect)
        
        # 英语文本渲染
        y = start_y
        try:
            # 使用更简单的方法计算文本位置
            bbox = draw.textbbox((0, 0), en, font=font_en)
            text_width = bbox[2] - bbox[0]
            x = text_start_x + (text_area_width - text_width) // 2
            
            # 应用加粗效果
            if english_bold:
                # 绘制多次实现加粗效果
                for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                    draw.text((x+dx, y+dy), en, font=font_en, fill=english_color)
            
            draw.text((x, y), en, font=font_en, fill=english_color)
        except Exception as e:
            # 如果高级方法失败，使用简单方法
            try:
                # 估算文本宽度
                approx_width = len(en) * conf.get("english_size", 46) // 2
                x = text_start_x + (text_area_width - approx_width) // 2
                
                # 应用加粗效果
                if english_bold:
                    for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                        draw.text((x+dx, y+dy), en, font=font_en, fill=english_color)
                
                draw.text((x, y), en, font=font_en, fill=english_color)
            except Exception as e2:
                # 如果仍然失败，使用默认位置
                x = text_start_x + 20
                draw.text((x, y), en, font=font_en, fill=english_color)
        
        y += conf.get("english_size", 46) + conf.get("english_phonetic_gap", 10)
        
        # 音标文本渲染 - 专门修复音标显示
        if ph and ph.strip():
            try:
                # 处理音标符号 - 确保使用正确的字体
                bbox = draw.textbbox((0, 0), ph, font=font_ph)
                text_width = bbox[2] - bbox[0]
                x = text_start_x + (text_area_width - text_width) // 2
                
                # 应用加粗效果
                if phonetic_bold:
                    for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                        draw.text((x+dx, y+dy), ph, font=font_ph, fill=phonetic_color)
                
                draw.text((x, y), ph, font=font_ph, fill=phonetic_color)
            except Exception as e:
                try:
                    # 估算文本宽度
                    approx_width = len(ph) * conf.get("phonetic_size", 30) // 2
                    x = text_start_x + (text_area_width - approx_width) // 2
                    
                    # 应用加粗效果
                    if phonetic_bold:
                        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                            draw.text((x+dx, y+dy), ph, font=font_ph, fill=phonetic_color)
                    
                    draw.text((x, y), ph, font=font_ph, fill=phonetic_color)
                except Exception as e2:
                    x = text_start_x + 20
                    draw.text((x, y), ph, font=font_ph, fill=phonetic_color)
            
            y += conf.get("phonetic_size", 30) + conf.get("phonetic_cn_gap", 10)
        
        # 中文文本渲染 - 使用专门的中文字体
        try:
            # 测试中文文本渲染
            bbox = draw.textbbox((0, 0), cn, font=font_cn)
            text_width = bbox[2] - bbox[0]
            x = text_start_x + (text_area_width - text_width) // 2
            
            # 应用加粗效果
            if chinese_bold:
                for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                    draw.text((x+dx, y+dy), cn, font=font_cn, fill=chinese_color)
            
            draw.text((x, y), cn, font=font_cn, fill=chinese_color)
        except Exception as e:
            # 如果中文渲染失败，尝试使用系统默认字体
            try:
                font_cn_fallback = load_font(DEFAULT_FONT, conf.get("chinese_size", 46))
                bbox = draw.textbbox((0, 0), cn, font=font_cn_fallback)
                text_width = bbox[2] - bbox[0]
                x = text_start_x + (text_area_width - text_width) // 2
                
                # 应用加粗效果
                if chinese_bold:
                    for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                        draw.text((x+dx, y+dy), cn, font=font_cn_fallback, fill=chinese_color)
                
                draw.text((x, y), cn, font=font_cn_fallback, fill=chinese_color)
            except Exception as e2:
                # 如果仍然失败，使用默认位置和默认字体
                x = text_start_x + 20
                try:
                    draw.text((x, y), cn, font=font_en, fill=chinese_color)
                except:
                    # 最终备选：使用默认字体
                    default_font = ImageFont.load_default()
                    draw.text((x, y), cn, font=default_font, fill=chinese_color)

        return base
    except Exception as e:
        st.error(f"帧渲染失败: {e}")
        # 创建错误图像
        error_img = Image.new("RGB", (W, H), conf.get("bg_color", "#D1E1EF"))
        draw = ImageDraw.Draw(error_img)
        # 使用默认字体显示错误信息
        try:
            draw.text((50, H//2), f"渲染错误: {str(e)}", fill="red")
        except:
            pass
        return error_img

# ---------- 效果预览部分 ----------
st.markdown('<div class="card-header">👀 效果预览</div>', unsafe_allow_html=True)

# 显示当前使用的字体信息
if DEFAULT_FONT:
    st.sidebar.success(f"当前字体: {os.path.basename(DEFAULT_FONT)}")
else:
    st.sidebar.warning("未找到系统字体，使用默认字体")

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
                ui_bg_color = st.color_picker("背景颜色", "#D1E1EF", key="ui_bg_color")  # 默认背景颜色
            
            ui_bg_image = None
            if bg_mode == "图片背景":
                bg_file = st.file_uploader("上传背景图片 (JPG/PNG)", type=["jpg","jpeg","png"], key="ui_bgimg")
                if bg_file:
                    try:
                        ui_bg_image = Image.open(bg_file).convert("RGBA")
                        st.image(ui_bg_image, caption="背景预览", width='stretch')
                    except Exception:
                        st.error("无法读取背景图片")
                
                # 背景图片透明度设置
                bg_image_alpha = st.slider("背景图片透明度", 0.0, 1.0, 1.0, 0.05, key="ui_bg_image_alpha")
                st.caption("1.0为完全不透明，0.0为完全透明")
        
        with tab_text:
            st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
            
            # --- 文字样式 ---
            st.markdown("**文字样式**")
            col_en, col_ph, col_cn = st.columns(3)
            with col_en:
                en_size = st.slider("英语字号", 0, 160, 46, key="ui_en_size")
                en_color = st.color_picker("英语颜色", "#000000", key="ui_en_color")  # 默认黑色
                english_bold = st.checkbox("英语加粗", value=False, key="ui_english_bold")
            with col_ph:
                ph_size = st.slider("音标字号", 0, 120, 30, key="ui_ph_size")
                ph_color = st.color_picker("音标颜色", "#E6BF20", key="ui_ph_color")  # 默认音标颜色
                phonetic_bold = st.checkbox("音标加粗", value=False, key="ui_phonetic_bold")
            with col_cn:
                cn_size = st.slider("中文字号", 0, 120, 46, key="ui_cn_size")
                cn_color = st.color_picker("中文颜色", "#000000", key="ui_cn_color")  # 默认黑色
                chinese_bold = st.checkbox("中文加粗", value=False, key="ui_chinese_bold")
            
            
        
        with tab_layout:
            st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
            
            # --- 背景板与间距 ---
            st.markdown("**背景板与间距**")
            b1, b2, b3, b4 = st.columns(4)
            with b1:
                text_bg_enable = st.checkbox("启用文字背景板", value=True, key="ui_text_bg_enable")  # 默认启用
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
            
            
        
            with tab_advanced:
                st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
    
                # --- 字体选择设置 ---
                st.markdown("**字体设置**")
                
                # 获取系统可用字体列表
                available_fonts = []
                
                # 定义支持中文的字体（优先级高）
                chinese_support_fonts = []
                # 定义英文字体（优先级低）
                english_fonts = []
    
    if sys.platform.startswith("win"):
        # Windows 字体路径
        windows_fonts_dir = r"C:\Windows\Fonts"
        font_candidates = [
            ("times.ttf", "Times New Roman", False),  # 将 Times New Roman 放在前面
            ("simhei.ttf", "黑体", True),
            ("msyh.ttc", "微软雅黑", True),
            ("msyhbd.ttc", "微软雅黑 Bold", True),
            ("simsun.ttc", "宋体", True),
            ("simsunb.ttf", "宋体 Bold", True),
            ("arialuni.ttf", "Arial Unicode MS", True),  # 支持中文和音标
            ("seguisym.ttf", "Segoe UI Symbol", False),
            ("arial.ttf", "Arial", False),
            ("cour.ttf", "Courier New", False)
        ]
        for font_file, font_name, supports_chinese in font_candidates:
            font_path = os.path.join(windows_fonts_dir, font_file)
            if os.path.exists(font_path):
                if supports_chinese:
                    chinese_support_fonts.append((font_path, font_name))
                else:
                    english_fonts.append((font_path, font_name))
    
    elif sys.platform.startswith("darwin"):
        # macOS 字体路径
        mac_fonts = [
            ("/System/Library/Fonts/Times.ttf", "Times New Roman", False),  # 将 Times New Roman 放在前面
            ("/System/Library/Fonts/PingFang.ttc", "苹方", True),
            ("/System/Library/Fonts/STHeiti Light.ttc", "黑体-简", True),
            ("/System/Library/Fonts/STHeiti Medium.ttc", "黑体-中", True),
            ("/System/Library/Fonts/Arial Unicode.ttf", "Arial Unicode", True),
            ("/Library/Fonts/Arial Unicode.ttf", "Arial Unicode", True),
            ("/System/Library/Fonts/Arial.ttf", "Arial", False),
        ]
        for font_path, font_name, supports_chinese in mac_fonts:
            if os.path.exists(font_path):
                if supports_chinese:
                    chinese_support_fonts.append((font_path, font_name))
                else:
                    english_fonts.append((font_path, font_name))
    
    else:
        # Linux 字体路径
        linux_fonts = [
            ("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", "Liberation Serif", False),  # Linux 上类似 Times New Roman 的字体
            ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "文泉驿微米黑", True),
            ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "文泉驿正黑", True),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVu Sans", False),
            ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "Liberation Sans", False),
        ]
        for font_path, font_name, supports_chinese in linux_fonts:
            if os.path.exists(font_path):
                if supports_chinese:
                    chinese_support_fonts.append((font_path, font_name))
                else:
                    english_fonts.append((font_path, font_name))
    
    # 合并字体列表：英文字体在前，中文字体在后
    available_fonts = english_fonts + chinese_support_fonts
    
    # 添加默认字体选项
    if DEFAULT_FONT:
        default_font_name = os.path.basename(DEFAULT_FONT)
        # 检查默认字体是否已经在列表中
        if not any(DEFAULT_FONT in font[0] for font in available_fonts):
            # 检查默认字体是否支持中文
            supports_chinese = any(chinese_font in DEFAULT_FONT.lower() for chinese_font in 
                                 ['simhei', 'msyh', 'simsun', 'pingfang', 'stheit', 'wqy'])
            display_name = f"系统默认 ({default_font_name})"
            if supports_chinese:
                display_name += " ✓ 支持中文"
            available_fonts.insert(0, (DEFAULT_FONT, display_name))
    
    # 创建字体选择下拉菜单
    if available_fonts:
        # 提取字体名称列表用于下拉菜单
        font_options = [font[1] for font in available_fonts]
        font_paths = [font[0] for font in available_fonts]
        
        # 默认选择 Times New Roman
        default_index = 0
        for i, font in enumerate(available_fonts):
            if "Times New Roman" in font[1] or "Liberation Serif" in font[1]:
                default_index = i
                break
        
        selected_font_index = st.selectbox(
            "选择字体（Times New Roman 为默认字体）",
            range(len(font_options)),
            format_func=lambda i: font_options[i],
            index=default_index,
            key="ui_font_selector"
        )
        
        selected_font_path = font_paths[selected_font_index]
        selected_font_name = font_options[selected_font_index]
        
        # 显示字体支持信息
        if any(keyword in selected_font_name for keyword in ["支持中文", "黑体", "雅黑", "宋体", "苹方", "文泉驿"]):
            st.success(f"已选择字体: {selected_font_name}")
        elif "Times New Roman" in selected_font_name or "Liberation Serif" in selected_font_name:
            st.info(f"已选择字体: {selected_font_name} - 英文显示优化")
        else:
            st.warning(f"已选择字体: {selected_font_name} - 可能不支持中文显示")
        
        # 字体预览
        st.markdown("**字体预览**")
        preview_text = "Hello 你好 /həˈloʊ/"
        try:
            # 创建预览图像
            preview_img = Image.new("RGB", (500, 80), "white")
            draw = ImageDraw.Draw(preview_img)
            font_preview = load_font(selected_font_path, 24)
            
            # 绘制预览文本
            draw.text((10, 10), preview_text, fill="black", font=font_preview)
            
            # 检查中文是否正常显示
            try:
                # 创建一个小的测试图像来检查中文渲染
                test_img = Image.new("RGB", (100, 30), "white")
                test_draw = ImageDraw.Draw(test_img)
                test_draw.text((10, 10), "你好", fill="black", font=font_preview)
                
                # 检查像素是否都是白色（意味着没有渲染）
                pixels = list(test_img.getdata())
                if all(pixel == (255, 255, 255) for pixel in pixels):
                    st.error("⚠️ 警告：当前字体可能不支持中文显示，中文将显示为方框")
                else:
                    st.success("✅ 字体支持中文显示")
            except Exception:
                pass
                
            st.image(preview_img, caption=f"字体预览: {preview_text}", width=500)
        except Exception as e:
            st.warning(f"字体预览生成失败: {e}")
    else:
        st.warning("未检测到系统字体，将使用默认字体")
        selected_font_path = None
    
    # --- 区域设置 ---
    t1, t2 = st.columns(2)
    with t1:
        text_area_ratio = st.slider("文字区域宽度比例", 0.3, 1.0, 0.88, key="ui_text_area_ratio")
    
    # 字体信息显示
    if selected_font_path:
        st.info(f"当前使用字体: {selected_font_name}")
        st.info(f"字体路径: {selected_font_path}")
    else:
        st.warning("未选择字体，使用默认字体")
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
        
        # 汇总 style_conf - 添加字体路径
        style_conf = {
            "font_path": selected_font_path,  # 添加字体路径
            "bg_mode": "image" if ui_bg_image else "color",
            "bg_color": ui_bg_color,
            "bg_image": ui_bg_image,
            "bg_image_alpha": bg_image_alpha if bg_mode == "图片背景" else 1.0,
            "english_size": en_size,
            "english_color": en_color,
            "english_bold": english_bold,
            "phonetic_size": ph_size,
            "phonetic_color": ph_color,
            "phonetic_bold": phonetic_bold,
            "chinese_size": cn_size,
            "chinese_color": cn_color,
            "chinese_bold": chinese_bold,
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
        
        # 生成预览图像
        preview_image = render_frame(en, ph, cn, style_conf, (640, 360))
        
        # 显示实时预览
        st.markdown('<div class="live-preview-container">', unsafe_allow_html=True)
        st.markdown('<div class="live-preview-title">实时预览效果</div>', unsafe_allow_html=True)
        st.image(preview_image, caption="样式预览", width='stretch')
        
        # 显示预览文本
        st.markdown(f'<div class="live-preview-text live-preview-english">{en}</div>', unsafe_allow_html=True)
        if ph and ph.strip():
            st.markdown(f'<div class="live-preview-text live-preview-phonetic">/{ph}/</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="live-preview-text live-preview-chinese">{cn}</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 音频预览部分
        st.markdown("### 🔊 音频预览")
        if st.button("生成音频预览", width='stretch'):
            with st.spinner("正在生成音频预览..."):
                # 生成预览音频 - 现在函数已经定义
                preview_audio = generate_preview_audio(df, preview_row, st.session_state.audio_segments)
                
                if preview_audio and os.path.exists(preview_audio):
                    st.audio(preview_audio, format="audio/mp3")
                    st.success("音频预览生成完成！")
                else:
                    st.error("音频预览生成失败")
        
else:
    st.warning("请先上传数据文件以启用预览功能")

# ---------- 获取音频时长 ----------
def get_audio_duration(audio_path: str) -> float:
    """获取音频文件的时长（秒）- 改进版本"""
    try:
        if PYDUB_AVAILABLE:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # 转换为秒
        elif ffmpeg_available():
            # 使用 ffprobe 获取时长
            ffmpeg_path = find_ffmpeg_path()
            ffprobe_path = ffmpeg_path.replace("ffmpeg", "ffprobe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = ffprobe_path.replace("ffmpeg.exe", "ffprobe.exe")
            
            cmd = [
                ffprobe_path, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", audio_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                st.warning(f"ffprobe 失败: {result.stderr}")
                return 3.0  # 默认3秒
    except Exception as e:
        st.warning(f"获取音频时长失败: {e}")
    
    # 如果无法获取时长，返回默认值
    return 3.0

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
    """整合生成流程 - 同步版本"""
    tmpdir = tempfile.mkdtemp(prefix="gen_")
    try:
        W,H = video_params.get("resolution",(1920,1080))
        fps = video_params.get("fps",12)
        
        frame_files = []
        audios = []
        total_steps = len(rows) * len(audio_segments) + 2
        step = 0
        
        # 添加音频生成统计
        audio_success_count = 0
        audio_fail_count = 0
        
        for rid in rows:
            row = df.iloc[rid]
            en = str(row.get("英语",""))
            ph = str(row.get("音标",""))
            cn = str(row.get("中文",""))
            
            # 渲染当前单词的画面
            img = render_frame(en, ph, cn, style_conf, (W,H))
            
            # 音频生成 - 同步处理
            seg_paths = []
            total_audio_duration = 0
            
            for seg_idx, seg in enumerate(audio_segments):
                text = en if seg["content"]=="英语" else (ph if seg["content"]=="音标" else cn)
                out_mp3 = os.path.join(tmpdir, f"{rid}_{seg_idx}_{seg['content']}.mp3")
                
                # 同步生成TTS
                st.info(f"生成音频 {rid+1}-{seg_idx+1}: {text[:50]}...")
                ok = generate_tts_cached(text, seg["voice_category"], seg["voice_choice"], seg["speed"], "在线优先", out_mp3)
                
                if ok and os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 0:
                    # 获取实际音频时长
                    audio_duration = get_audio_duration(out_mp3)
                    total_audio_duration += audio_duration
                    seg_paths.append(out_mp3)
                    audio_success_count += 1
                    st.success(f"✅ 音频生成成功: {audio_duration:.2f}秒")
                else:
                    # 如果TTS失败，使用默认时长
                    st.warning(f"⚠️ TTS失败，使用静音替代: {text[:30]}...")
                    default_duration = 3.0
                    total_audio_duration += default_duration
                    if create_silent_mp3(out_mp3, default_duration):
                        seg_paths.append(out_mp3)
                        audio_fail_count += 1
                    else:
                        st.error(f"❌ 静音文件创建失败")
                
                # 添加停顿
                if seg.get("pause",0) > 0:
                    pause_path = os.path.join(tmpdir, f"pause_{rid}_{seg_idx}.mp3")
                    if create_silent_mp3(pause_path, seg["pause"]):
                        total_audio_duration += seg["pause"]
                        seg_paths.append(pause_path)
                
                step += 1
                if progress_cb:
                    progress_cb(step/total_steps)

            # 合并当前行的音频
            if seg_paths:
                merged_audio = os.path.join(tmpdir, f"{rid}_merged.mp3")
                try:
                    st.info("合并音频片段...")
                    concat_audios_ffmpeg(seg_paths, merged_audio)
                    
                    if os.path.exists(merged_audio) and os.path.getsize(merged_audio) > 0:
                        audios.append(merged_audio)
                        st.success(f"✅ 音频合并成功")
                        
                        # 根据音频时长生成对应数量的帧
                        frames_this_word = max(1, int(total_audio_duration * fps))
                        for i in range(frames_this_word):
                            fname = os.path.join(tmpdir, f"{rid}_{i:04d}.png")
                            img.save(fname)
                            frame_files.append(fname)
                    else:
                        st.error("❌ 合并后的音频文件无效")
                        # 使用默认帧数作为备选
                        frames_this_word = int(3.0 * fps)
                        for i in range(frames_this_word):
                            fname = os.path.join(tmpdir, f"{rid}_{i:04d}.png")
                            img.save(fname)
                            frame_files.append(fname)
                        
                except Exception as e:
                    st.error(f"音频合并失败: {e}")
                    # 使用默认帧数作为备选
                    frames_this_word = int(3.0 * fps)
                    for i in range(frames_this_word):
                        fname = os.path.join(tmpdir, f"{rid}_{i:04d}.png")
                        img.save(fname)
                        frame_files.append(fname)

        # 显示音频生成统计
        st.info(f"音频生成统计: 成功 {audio_success_count} 个, 失败 {audio_fail_count} 个")
        
        # 检查是否有足够的帧
        if not frame_files:
            st.error("没有生成任何帧，无法合成视频")
            return None
            
        # 检查是否有音频
        if not audios:
            st.error("没有生成任何音频，视频将无声")
            # 创建静音音频
            silent_audio = os.path.join(tmpdir, "silent_audio.mp3")
            if create_silent_mp3(silent_audio, 10.0):
                audios.append(silent_audio)
                st.warning("使用静音替代音频")
            
        # 合成视频（无音频）
        st.info("合成视频帧...")
        list_txt = os.path.join(tmpdir, "imgs.txt")
        with open(list_txt, "w", encoding="utf-8") as f:
            for p in frame_files:
                f.write(f"file '{p}'\n")
                f.write(f"duration {1.0/fps}\n")
        
        video_no_audio = os.path.join(tmpdir, "video.mp4")
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", 
            "-i", list_txt, "-r", str(fps), "-pix_fmt", "yuv420p", 
            video_no_audio
        ]
        
        try:
            run_ffmpeg_command(cmd)
            st.success("✅ 视频帧合成成功")
        except Exception as e:
            st.error(f"视频合成失败: {e}")
            return None
        
        # 合并所有音频
        if audios:
            st.info("合并所有音频...")
            final_audio = os.path.join(tmpdir, "final_audio.mp3")
            try:
                concat_audios_ffmpeg(audios, final_audio)
                
                # 检查最终音频
                if os.path.exists(final_audio) and os.path.getsize(final_audio) > 0:
                    audio_duration = get_audio_duration(final_audio)
                    st.success(f"✅ 最终音频合并成功，时长: {audio_duration:.2f}秒")
                else:
                    st.error("❌ 最终音频文件无效")
                    return None
                
            except Exception as e:
                st.error(f"最终音频合并失败: {e}")
                return None
            
            # 合并音视频
            st.info("合并音视频...")
            out_video = os.path.join(tmpdir, "final_out.mp4")
            cmd = [
                "ffmpeg", "-y", "-i", video_no_audio, "-i", final_audio,
                "-c:v", "copy", "-c:a", "aac", "-shortest", out_video
            ]
            try:
                run_ffmpeg_command(cmd)
                st.success("✅ 音视频合并成功")
                
                # 检查最终视频的音频流
                if ffmpeg_available():
                    ffprobe_cmd = [
                        "ffprobe", "-i", out_video, "-show_streams", 
                        "-select_streams", "a", "-loglevel", "error"
                    ]
                    result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        st.success("✅ 视频包含音频流")
                    else:
                        st.warning("⚠️ 视频可能不包含音频流")
                
            except Exception as e:
                st.error(f"音视频合并失败: {e}")
                return None
        else:
            out_video = video_no_audio
            st.warning("⚠️ 没有音频，生成无声视频")
        
        if os.path.exists(out_video):
            # 检查最终视频文件
            video_size = os.path.getsize(out_video)
            if video_size > 0:
                st.success(f"✅ 视频生成完成，文件大小: {video_size} 字节")
                # 关键修复：将视频文件复制到永久位置
                permanent_video_path = os.path.join(CACHE_DIR, f"generated_video_{int(time.time())}.mp4")
                try:
                    shutil.copy2(out_video, permanent_video_path)
                    return permanent_video_path
                except Exception as e:
                    st.warning(f"复制到永久位置失败: {e}，使用临时文件")
                    return out_video
            else:
                st.error("❌ 生成的视频文件为空")
                return None
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

# 在生成视频部分使用 audio_segments
if uploaded is not None and df is not None:
    total = len(df)
    
    # 修复：默认选择所有行
    default_rows = list(range(total))  # 选择所有行
    
    rows = st.multiselect(
        "选择生成的行", 
        options=list(range(total)), 
        format_func=lambda i: f"{i+1} - {df.iloc[i]['英语'][:30]}...", 
        default=default_rows  # 修复：默认选择所有行
    )
    
    # 修复：添加视频分辨率设置
    st.markdown("### 视频质量设置")
    
    # 视频分辨率选择
    resolution_options = {
        "1920x1080 (全高清)": (1920, 1080),
        "1280x720 (高清)": (1280, 720),
        "854x480 (标清)": (854, 480)
    }
    
    selected_resolution = st.selectbox(
        "视频分辨率",
        options=list(resolution_options.keys()),
        index=0,  # 默认选择1920x1080
        key="video_resolution"
    )
    
    video_resolution = resolution_options[selected_resolution]
    
    # 系统状态检查
    st.markdown("### 🔍 系统状态检查")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if EDGE_TTS_AVAILABLE:
            st.success("✅ TTS引擎: 可用")
        else:
            st.error("❌ TTS引擎: 不可用")
    
    with col2:
        if ffmpeg_available():
            st.success("✅ FFmpeg: 可用")
        else:
            st.error("❌ FFmpeg: 不可用")
    
    with col3:
        if df is not None and len(rows) > 0:
            st.success(f"✅ 数据: {len(rows)} 行")
        else:
            st.error("❌ 数据: 无效")
    
    # 音频配置检查
    st.markdown("### 🔊 音频配置检查")
    st.write(f"音频段数量: {len(st.session_state.audio_segments)}")
    for i, seg in enumerate(st.session_state.audio_segments):
        st.write(f"段 {i+1}: {seg['content']} - {seg['voice_category']} - 语速: {seg['speed']} - 停顿: {seg['pause']}秒")
    
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
            
            # 检查音频配置
            if not st.session_state.audio_segments:
                st.error("没有配置音频段")
                st.stop()
            
            progress = st.progress(0.0)
            status = st.empty()
            
            def cb(p):
                progress.progress(p)
                status.text(f"进度: {int(p*100)}%")
            
            # 修复：使用用户选择的视频分辨率
            params = {"resolution": video_resolution, "fps": 12}
            status.text("生成中...")
            
            try:
                outp = generate_video_pipeline(df, rows, style_conf, st.session_state.audio_segments, params, progress_cb=cb)
                
                if outp and os.path.exists(outp):
                    st.success("✅ 视频生成完成")
                    
                    # 显示视频信息
                    video_size = os.path.getsize(outp)
                    st.info(f"视频文件大小: {video_size} 字节 ({video_size/1024/1024:.2f} MB)")
                    
                    # 播放视频
                    with open(outp,"rb") as f:
                        video_bytes = f.read()
                        st.video(video_bytes)
                    
                    # 下载按钮
                    with open(outp,"rb") as f:
                        st.download_button(
                            "📥 下载视频", 
                            f, 
                            file_name=f"english_video_{int(time.time())}.mp4", 
                            mime="video/mp4",
                            width='stretch'
                        )
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
    save_template(name, style_conf, st.session_state.audio_segments, {"resolution":(1920,1080),"fps":12})  # 修复：默认分辨率改为1920x1080
    st.sidebar.success(f"已保存模板 {name}")
if templates:
    st.sidebar.subheader("已保存的模板")
    for tname, tdata in templates:
        if st.sidebar.button(f"应用模板 {tname}", width='stretch'):
            style_conf.update(tdata["style"])
            st.session_state.audio_segments = tdata["audio"].copy()
            st.sidebar.info(f"已应用模板 {tname}")

# TTS 测试功能
st.sidebar.header("🔧 系统测试")
if st.sidebar.button("测试 TTS 功能"):
    result = test_edge_tts()
    st.sidebar.info(result)

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
    unsafe_allow_html=True
)
