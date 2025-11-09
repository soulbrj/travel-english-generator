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
LIGHTWEIGHT_MODE = True  # 启用轻量模式，减少依赖

# 兼容 Streamlit Cloud 的临时目录处理
APP_TMP = os.path.join(tempfile.gettempdir(), "english_video_app")
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

# ---------- 简化版 FFmpeg 检测 ----------
def ffmpeg_available() -> bool:
    """简化版FFmpeg检测，不强制依赖"""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

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
    page_title="🎬 英语学习视频生成器",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+IPA:wght@400;700&display=swap');

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

* {{
    font-family: 'Noto Sans SC', sans-serif !important;
}}

.stApp {{
  background: linear-gradient(135deg, {PRIMARY_LIGHT} 0%, {SECONDARY_LIGHT} 100%) !important;
  color: {TEXT_DARK} !important;
}}

.main-title {{
  background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
  color: white;
  padding: 20px;
  border-radius: 16px;
  font-size: 24px;
  font-weight: 700;
  text-align: center;
  margin-bottom: 20px;
  box-shadow: 0 8px 25px rgba(99, 102, 241, 0.2);
}}

.card {{
  background: var(--card-bg);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 16px;
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.1);
}}

.card-header {{
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 16px;
  color: {TEXT_DARK};
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}}

div.stButton > button {{
  background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
  color: white;
  border-radius: 10px;
  padding: 10px 20px;
  font-weight: 600;
  border: none;
  transition: all 0.3s ease;
  box-shadow: 0 2px 10px rgba(99, 102, 241, 0.3);
  font-size: 14px;
}}

div.stButton > button:hover {{
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
}}

.stSuccess {{
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 10px;
  padding: 16px;
}}

.stInfo {{
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 10px;
  padding: 16px;
}}

.stWarning {{
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 10px;
  padding: 16px;
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

/* 实时预览区域 */
.live-preview-container {{
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  padding: 20px;
  border: 2px solid var(--border-color);
  box-shadow: 0 8px 25px rgba(99, 102, 241, 0.1);
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
  max-height: 300px;
  border-radius: 12px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
  margin-bottom: 20px;
}}

.live-preview-text {{
  text-align: center;
  margin: 8px 0;
  font-size: 16px;
}}

.live-preview-english {{
  font-size: 22px;
  font-weight: 700;
  color: {TEXT_DARK};
  font-family: 'Arial', sans-serif;
}}

.live-preview-phonetic {{
  font-size: 16px;
  color: {TEXT_MUTED};
  font-style: italic;
  font-family: 'Noto Sans IPA', 'Arial Unicode MS', sans-serif;
  font-weight: 400;
}}

.live-preview-chinese {{
  font-size: 18px;
  color: {TEXT_DARK};
  font-family: 'Noto Sans SC', sans-serif;
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

# ---------- 字体处理 ----------
def get_default_font():
    """获取默认字体，优先使用Google Fonts"""
    return None  # 使用CSS中定义的字体

def load_font(size, font_path=None):
    """加载字体"""
    try:
        # 优先使用系统字体
        system_fonts = [
            "NotoSansSC-Regular.ttf", "Arial.ttf", "simhei.ttf", "msyh.ttc"
        ]
        
        for font_name in system_fonts:
            try:
                return ImageFont.truetype(font_name, size)
            except:
                continue
                
        # 使用默认字体
        return ImageFont.load_default()
    except Exception as e:
        return ImageFont.load_default()

def load_phonetic_font(size):
    """加载音标字体"""
    try:
        # 尝试加载音标专用字体
        phonetic_fonts = [
            "NotoSansIPA-Regular.ttf", "Arial.ttf", "Times.ttf"
        ]
        
        for font_name in phonetic_fonts:
            try:
                return ImageFont.truetype(font_name, size)
            except:
                continue
                
        return load_font(size)
    except:
        return load_font(size)

# ---------- 语音 / 预设库 ----------
EN_MALE = [
    "en-US-GuyNeural", "en-US-BenjaminNeural", "en-GB-RyanNeural",
]
EN_FEMALE = [
    "en-US-JennyNeural", "en-US-AriaNeural", "en-GB-SoniaNeural",
]
ZH_VOICES = [
    "zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-XiaoyiNeural",
]

VOICE_STYLES = {
    "en-US-JennyNeural": "美式英语，清晰自然",
    "en-US-AriaNeural": "美式英语，温暖亲切", 
    "en-GB-SoniaNeural": "英式英语，优雅知性",
    "en-US-GuyNeural": "美式英语，沉稳专业",
    "en-US-BenjaminNeural": "美式英语，温暖可靠",
    "en-GB-RyanNeural": "英式英语，标准优雅",
    "zh-CN-XiaoxiaoNeural": "普通话，甜美少女音",
    "zh-CN-YunxiNeural": "普通话，温暖青年音",
    "zh-CN-XiaoyiNeural": "普通话，活泼少女",
}

VOICE_LIBRARY = {
    "英文女声": EN_FEMALE, 
    "英文男声": EN_MALE, 
    "中文音色": ZH_VOICES,
}

PRESET_MODES = {
    "基础学习模式": [
        {"content":"英语","category":"英文女声","speed":1.0,"pause":0.3},
        {"content":"音标","category":"英文女声","speed":1.0,"pause":0.2}
    ],
    "强化记忆模式": [
        {"content":"英语","category":"英文男声","speed":0.95,"pause":0.5},
        {"content":"中文","category":"中文音色","speed":1.0,"pause":0.8},
        {"content":"英语","category":"英文女声","speed":1.05,"pause":0.3}
    ],
    "理解优先模式": [
        {"content":"中文","category":"中文音色","speed":1.0,"pause":0.5},
        {"content":"英语","category":"英文女声","speed":0.95,"pause":0.2}
    ]
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

# ---------- 简化版音频处理 ----------
def create_silent_audio(duration_s: float) -> bytes:
    """创建静音音频数据"""
    # 返回空的音频数据
    return b""

def concat_audios_simple(audio_paths: List[str]) -> bytes:
    """简化版音频合并"""
    # 返回第一个音频文件的内容
    if audio_paths and os.path.exists(audio_paths[0]):
        with open(audio_paths[0], 'rb') as f:
            return f.read()
    return b""

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
        
        # 返回第一个音频文件作为预览
        if seg_paths:
            return seg_paths[0]
        
        return None
    except Exception as e:
        st.error(f"预览音频生成失败: {e}")
        return None

# ---------- 音标字符映射表 ----------
PHONETIC_CHAR_MAP = {
    'ɡ': 'g',
    'ˈ': "'",
    'ˌ': ",",
    'ː': ':',
}

def convert_phonetic_text(text):
    """转换音标文本"""
    if not text:
        return ""
    
    converted = ''.join(PHONETIC_CHAR_MAP.get(char, char) for char in text)
    return converted

# ---------- 页面顶部 / 导航 ----------
st.markdown(f'<div class="main-title">🎬 英语学习视频生成器</div>', unsafe_allow_html=True)

# ---------- 数据管理部分 ----------
st.markdown('<div class="card-header">📁 数据管理</div>', unsafe_allow_html=True)
uploaded = st.file_uploader("上传Excel/CSV文件（需要包含英语、中文列）", type=["xlsx","xls","csv"])
df = None
if uploaded:
    try:
        if uploaded.name.lower().endswith((".csv")):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)
        
        if "英语" not in df.columns or "中文" not in df.columns:
            st.error("文件必须包含'英语'和'中文'列")
            df = None
        else:
            if "音标" not in df.columns:
                df["音标"] = ""
            st.success(f"成功加载 {len(df)} 条数据")
            st.dataframe(df.head(5), use_container_width=True)
    except Exception as e:
        st.error(f"文件解析失败：{e}")
else:
    st.info("请上传包含英语和中文列的数据文件")

# ---------- 音频设置部分 ----------
st.markdown('<div class="card-header">🔊 音频设置</div>', unsafe_allow_html=True)

# 使用选项卡组织音频设置
tab_audio_config, tab_voice_library = st.tabs(["🎵 音频编排", "🎙️ 音色库"])

with tab_audio_config:
    st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
    
    # 音频段数
    n_segments = st.number_input("音频段落数量", min_value=1, max_value=6, value=4, step=1, key="ui_n_segments")

    # 构建段配置表
    audio_segments = []
    
    # 默认音频编排设置
    default_segments = [
        {"content": "英语", "category": "英文女声", "voice_choice": None, "speed": 1.0, "pause": 0.3},
        {"content": "英语", "category": "英文男声", "voice_choice": None, "speed": 1.0, "pause": 0.3},
        {"content": "中文", "category": "中文音色", "voice_choice": None, "speed": 1.0, "pause": 0.5},
        {"content": "英语", "category": "英文女声", "voice_choice": None, "speed": 1.0, "pause": 0.3}
    ]
    
    for si in range(int(n_segments)):
        st.markdown(f"**段落 {si+1}**", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1.5, 1.2, 1, 1])
        
        # 获取默认值
        default_seg = default_segments[si] if si < len(default_segments) else default_segments[0]
        
        with c1:
            content = st.selectbox(f"内容", ["英语", "音标", "中文"], 
                                 index=["英语", "音标", "中文"].index(default_seg["content"]), 
                                 key=f"ui_seg_content_{si}")
        with c2:
            category = st.selectbox(f"音色类型", ["英文女声", "英文男声", "中文音色"], 
                                  index=["英文女声", "英文男声", "中文音色"].index(default_seg["category"]), 
                                  key=f"ui_seg_cat_{si}")
        with c3:
            presets = VOICE_LIBRARY.get(category, [])
            voice_choice = st.selectbox(f"具体音色", ["自动选择"] + presets, 
                                      key=f"ui_seg_preset_{si}")
        with c4:
            speed = st.slider(f"语速", 0.5, 2.0, default_seg["speed"], 0.1, key=f"ui_seg_speed_{si}")
        
        # 将配置添加到 audio_segments 列表
        audio_segments.append({
            "content": content,
            "voice_category": category,
            "voice_choice": voice_choice if voice_choice != "自动选择" else None,
            "speed": speed,
            "pause": default_seg["pause"],
            "engine_pref": "在线优先"
        })

with tab_voice_library:
    st.markdown('<div class="scrollable-content">', unsafe_allow_html=True)
    
    # 使用选项卡组织不同音色分类
    tab1, tab2, tab3 = st.tabs(["🎙️ 英文女声", "🎙️ 英文男声", "🎙️ 中文音色"])
    
    with tab1:
        for voice in EN_FEMALE:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{get_voice_display_name(voice)}**")
                    st.caption(get_voice_style(voice))
                with col2:
                    if st.button("试听", key=f"sample_{voice}"):
                        st.info("试听功能需要网络连接")
    
    with tab2:
        for voice in EN_MALE:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{get_voice_display_name(voice)}**")
                    st.caption(get_voice_style(voice))
                with col2:
                    if st.button("试听", key=f"sample_{voice}"):
                        st.info("试听功能需要网络连接")
    
    with tab3:
        for voice in ZH_VOICES:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{get_voice_display_name(voice)}**")
                    st.caption(get_voice_style(voice))
                with col2:
                    if st.button("试听", key=f"sample_{voice}"):
                        st.info("试听功能需要网络连接")

# ---------- Frame rendering ----------
def render_frame(en, ph, cn, conf, size=(640, 360)):
    """渲染单帧图像 - 优化中文显示"""
    W,H = size
    
    try:
        # 创建背景
        bg_color = conf.get("bg_color", "#F0F8FF")
        base = Image.new("RGB", (W,H), bg_color)
        draw = ImageDraw.Draw(base)

        # 加载字体
        font_en = load_font(conf.get("english_size", 36))
        font_cn = load_font(conf.get("chinese_size", 32))
        phonetic_font = load_phonetic_font(conf.get("phonetic_size", 24))

        # 颜色设置
        english_color = conf.get("english_color", "#000000")
        phonetic_color = conf.get("phonetic_color", "#E67E22")
        chinese_color = conf.get("chinese_color", "#000000")
        
        # 计算位置
        text_area_width = int(W * 0.9)
        text_start_x = (W - text_area_width) // 2
        
        # 计算总高度
        total_height = (
            conf.get("english_size", 36) + 
            conf.get("phonetic_size", 24) + 
            conf.get("chinese_size", 32) + 40
        )
        
        start_y = (H - total_height) // 2
        
        # 绘制文字背景板
        padding = 20
        bg_rect = Image.new('RGBA', (text_area_width, total_height + padding), (255, 255, 255, 200))
        base.paste(bg_rect, (text_start_x, start_y - padding//2), bg_rect)
        
        # 英语文本
        y = start_y
        bbox = draw.textbbox((0, 0), en, font=font_en)
        text_width = bbox[2] - bbox[0]
        x = text_start_x + (text_area_width - text_width) // 2
        draw.text((x, y), en, font=font_en, fill=english_color)
        
        # 音标文本
        y += conf.get("english_size", 36) + 10
        converted_ph = convert_phonetic_text(ph)
        bbox = draw.textbbox((0, 0), f"/{converted_ph}/", font=phonetic_font)
        text_width = bbox[2] - bbox[0]
        x = text_start_x + (text_area_width - text_width) // 2
        draw.text((x, y), f"/{converted_ph}/", font=phonetic_font, fill=phonetic_color)
        
        # 中文文本
        y += conf.get("phonetic_size", 24) + 10
        bbox = draw.textbbox((0, 0), cn, font=font_cn)
        text_width = bbox[2] - bbox[0]
        x = text_start_x + (text_area_width - text_width) // 2
        draw.text((x, y), cn, font=font_cn, fill=chinese_color)

        return base
    except Exception as e:
        # 简化错误处理
        error_img = Image.new("RGB", (W, H), bg_color)
        draw = ImageDraw.Draw(error_img)
        draw.text((50, H//2), "渲染错误", fill="red")
        return error_img

# ---------- 效果预览部分 ----------
st.markdown('<div class="card-header">👀 效果预览</div>', unsafe_allow_html=True)

if uploaded is not None and df is not None:
    # 创建两列布局
    preview_col1, preview_col2 = st.columns([1, 1])
    
    with preview_col1:
        st.markdown("### 🎨 显示设置")
        
        # 背景设置
        bg_color = st.color_picker("背景颜色", "#F0F8FF")
        
        # 文字样式
        col1, col2, col3 = st.columns(3)
        with col1:
            en_size = st.slider("英语字号", 20, 60, 36)
            en_color = st.color_picker("英语颜色", "#000000")
        with col2:
            ph_size = st.slider("音标字号", 16, 40, 24)
            ph_color = st.color_picker("音标颜色", "#E67E22")
        with col3:
            cn_size = st.slider("中文字号", 20, 50, 32)
            cn_color = st.color_picker("中文颜色", "#000000")
        
        st.info("💡 使用Google Fonts确保中英文正常显示")
    
    with preview_col2:
        st.markdown("### 👁️ 实时预览")
        
        # 选择预览的行
        preview_row = st.selectbox(
            "选择预览的句子",
            options=list(range(len(df))),
            format_func=lambda i: f"{i+1}. {df.iloc[i]['英语'][:20]}...",
            key="preview_row"
        )
        
        # 汇总样式配置
        style_conf = {
            "bg_color": bg_color,
            "english_size": en_size,
            "english_color": en_color,
            "phonetic_size": ph_size,
            "phonetic_color": ph_color,
            "chinese_size": cn_size,
            "chinese_color": cn_color,
        }
        
        # 实时渲染预览
        row = df.iloc[preview_row]
        en = str(row.get("英语",""))
        ph = str(row.get("音标",""))
        cn = str(row.get("中文",""))
        
        # 生成预览图像
        preview_image = render_frame(en, ph, cn, style_conf)
        
        # 显示实时预览
        st.markdown('<div class="live-preview-container">', unsafe_allow_html=True)
        st.image(preview_image, use_container_width=True)
        
        # 显示预览文本
        st.markdown(f'<div class="live-preview-text live-preview-english">{en}</div>', unsafe_allow_html=True)
        if ph and ph.strip():
            converted_ph_display = convert_phonetic_text(ph)
            st.markdown(f'<div class="live-preview-text live-preview-phonetic">/{converted_ph_display}/</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="live-preview-text live-preview-chinese">{cn}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 音频预览
        st.markdown("### 🔊 音频预览")
        if st.button("生成音频预览", use_container_width=True):
            with st.spinner("生成中..."):
                preview_audio = generate_preview_audio(df, preview_row, audio_segments)
                if preview_audio:
                    st.audio(preview_audio, format="audio/mp3")
                    st.success("音频预览生成完成！")
                else:
                    st.error("音频生成失败，请检查网络连接")

# ---------- 生成与下载部分 ----------
st.markdown('<div class="card-header">📤 生成内容</div>', unsafe_allow_html=True)

if not ffmpeg_available():
    st.warning("""
    ⚠️ **视频生成功能受限**
    
    当前环境未检测到FFmpeg，视频生成功能不可用。
    但您仍然可以：
    - ✅ 生成单张学习卡片图片
    - ✅ 生成音频内容
    - ✅ 预览学习效果
    """)

if uploaded is not None and df is not None:
    # 生成学习卡片
    st.markdown("### 🖼️ 生成学习卡片")
    
    selected_rows = st.multiselect(
        "选择要生成卡片的句子", 
        options=list(range(len(df))),
        format_func=lambda i: f"{i+1}. {df.iloc[i]['英语'][:20]}...",
        default=[0] if len(df) > 0 else []
    )
    
    if st.button("🖨️ 生成学习卡片", use_container_width=True):
        if selected_rows:
            with st.spinner("生成学习卡片中..."):
                # 生成样式配置
                style_conf = {
                    "bg_color": bg_color,
                    "english_size": en_size,
                    "english_color": en_color,
                    "phonetic_size": ph_size,
                    "phonetic_color": ph_color,
                    "chinese_size": cn_size,
                    "chinese_color": cn_color,
                }
                
                # 创建ZIP文件包含所有图片
                import zipfile
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                    for idx in selected_rows:
                        row = df.iloc[idx]
                        en = str(row.get("英语",""))
                        ph = str(row.get("音标",""))
                        cn = str(row.get("中文",""))
                        
                        # 生成图片
                        img = render_frame(en, ph, cn, style_conf, (800, 450))
                        
                        # 保存到内存
                        img_buffer = io.BytesIO()
                        img.save(img_buffer, format='PNG')
                        
                        # 添加到ZIP
                        zip_file.writestr(f"card_{idx+1}_{en[:10]}.png", img_buffer.getvalue())
                
                # 提供下载
                st.success(f"成功生成 {len(selected_rows)} 张学习卡片")
                st.download_button(
                    label="📥 下载学习卡片包",
                    data=zip_buffer.getvalue(),
                    file_name="english_learning_cards.zip",
                    mime="application/zip",
                    use_container_width=True
                )
        else:
            st.warning("请选择至少一个句子")
    
    # 生成音频包
    st.markdown("### 🔊 生成音频包")
    
    if st.button("🎵 生成音频文件", use_container_width=True):
        if selected_rows:
            with st.spinner("生成音频文件中..."):
                # 创建ZIP文件包含所有音频
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                    for idx in selected_rows:
                        row = df.iloc[idx]
                        en = str(row.get("英语",""))
                        
                        # 生成第一个音频段
                        if audio_segments:
                            seg = audio_segments[0]
                            text = en if seg["content"]=="英语" else ""
                            
                            # 临时文件
                            fd, tmp_mp3 = tempfile.mkstemp(suffix=".mp3")
                            os.close(fd)
                            
                            if generate_tts_cached(text, seg["voice_category"], seg["voice_choice"], seg["speed"], "在线优先", tmp_mp3):
                                with open(tmp_mp3, 'rb') as f:
                                    zip_file.writestr(f"audio_{idx+1}_{en[:10]}.mp3", f.read())
                            
                            safe_remove(tmp_mp3)
                
                st.success(f"成功生成 {len(selected_rows)} 个音频文件")
                st.download_button(
                    label="📥 下载音频包",
                    data=zip_buffer.getvalue(),
                    file_name="english_audio_files.zip",
                    mime="application/zip",
                    use_container_width=True
                )
        else:
            st.warning("请选择至少一个句子")

# ---------- 侧边栏 ----------
st.sidebar.header("📦 功能")
st.sidebar.info("""
**主要功能：**
- 📁 数据管理
- 🔊 多音色音频
- 🎨 学习卡片
- 👀 实时预览
""")

st.sidebar.header("🔧 系统状态")
st.sidebar.write(f"✅ 语音合成: {'可用' if EDGE_TTS_AVAILABLE else '需安装'}")
st.sidebar.write(f"✅ 图片生成: 可用")
st.sidebar.write(f"🔶 视频合成: {'可用' if ffmpeg_available() else '需FFmpeg'}")

if not EDGE_TTS_AVAILABLE:
    st.sidebar.warning("安装语音合成: `pip install edge-tts`")

if not ffmpeg_available():
    st.sidebar.warning("视频功能需要安装FFmpeg")

st.sidebar.header("💡 使用提示")
st.sidebar.info("""
1. 上传包含英语和中文的CSV/Excel文件
2. 配置音频段落和音色
3. 调整显示样式
4. 生成学习卡片和音频
""")

# ---------- 页脚 ----------
st.markdown(
    """
    <div style='text-align: center; padding: 20px; color: #64748b; margin-top: 40px;'>
    © 2024 英语学习视频生成器 • 专注于英语学习内容制作
    </div>
    """,
    unsafe_allow_html=True)
