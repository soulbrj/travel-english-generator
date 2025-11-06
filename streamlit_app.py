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
from PIL import Image, ImageDraw, ImageFont, ImageOps

# imageio import (video writing later)
import imageio.v2 as imageio

# ---------- 配置 & 常量 ----------
LIGHTWEIGHT_MODE = False  # True -> 更轻量, 禁用队列/模板/进度

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

# imageio-ffmpeg auto-provision attempt (helps in some cloud envs)
IMAGEIO_FFMPEG = False
try:
    import imageio_ffmpeg as iioff
    ffexe = iioff.get_ffmpeg_exe()
    if ffexe and os.path.exists(ffexe):
        IMAGEIO_FFMPEG = True
        os.environ["PATH"] += os.pathsep + os.path.dirname(ffexe)
except Exception:
    IMAGEIO_FFMPEG = False

def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None or IMAGEIO_FFMPEG

# ---------- 高级UI theme & CSS (紫蓝色系浅色高级感) ----------
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

/* 页面基础样式 */
.stApp {{
  background: linear-gradient(135deg, {PRIMARY_LIGHT} 0%, {SECONDARY_LIGHT} 100%) !important;
  color: {TEXT_DARK} !important;
  font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
}}

/* 主标题 */
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
  border: none;
  backdrop-filter: blur(10px);
  position: relative;
  overflow: hidden;
}}

.main-title::before {{
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(45deg, transparent 30%, rgba(255,255,255,0.1) 50%, transparent 70%);
  animation: shimmer 3s infinite linear;
}}

@keyframes shimmer {{
  0% {{ transform: translateX(-100%); }}
  100% {{ transform: translateX(100%); }}
}}

/* 导航栏 */
.navbar {{
  display: flex;
  gap: 12px;
  justify-content: center;
  padding: 16px 0;
  margin-bottom: 32px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 16px;
  backdrop-filter: blur(10px);
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

/* 卡片样式 */
.card {{
  background: var(--card-bg);
  border-radius: 20px;
  padding: 24px;
  margin-bottom: 20px;
  border: 1px solid var(--border-color);
  backdrop-filter: blur(10px);
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

/* 按钮样式 */
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

/* 滑块样式 */
.stSlider > div {{
  padding: 8px 0;
}}

.stSlider > div > div {{
  background: linear-gradient(90deg, var(--gradient-start), var(--gradient-end));
}}

/* 选择框样式 */
.stSelectbox > div > div {{
  background: white;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  transition: all 0.3s ease;
}}

.stSelectbox > div > div:hover {{
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}}

/* 文件上传样式 */
.stFileUploader > div {{
  background: white;
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  transition: all 0.3s ease;
}}

.stFileUploader > div:hover {{
  border-color: var(--accent-primary);
  background: rgba(99, 102, 241, 0.02);
}}

/* 数据编辑器样式 */
.stDataFrame {{
  background: white;
  border-radius: 12px;
  border: 1px solid var(--border-color);
}}

/* 页脚 */
.footer {{
  text-align: center;
  padding: 24px;
  color: {TEXT_MUTED};
  margin-top: 40px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 16px;
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-color);
}}

/* 语音样本库样式 */
.voice-library {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 20px;
}}

.voice-card {{
  background: rgba(255, 255, 255, 0.9);
  border-radius: 16px;
  padding: 20px;
  border: 1px solid var(--border-color);
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
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

/* 进度条样式 */
.stProgress > div > div > div {{
  background: linear-gradient(90deg, var(--gradient-start), var(--gradient-end));
  border-radius: 8px;
}}

/* 选项卡样式 */
.stTabs {{
  margin-top: 16px;
}}

.stTabs > div > div > div {{
  background: transparent;
  gap: 8px;
}}

.stTabs > div > div > div > div {{
  color: {TEXT_DARK};
  border-radius: 12px;
  padding: 12px 20px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.7);
  transition: all 0.3s ease;
}}

.stTabs > div > div > div > div[data-baseweb="tab"][aria-selected="true"] {{
  background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
  color: white;
  border-color: transparent;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
}}

.stTabs > div > div > div > div:hover {{
  background: rgba(255, 255, 255, 0.9);
  border-color: var(--accent-primary);
}}

/* 音频播放器样式 */
.stAudio {{
  margin: 12px 0;
  border-radius: 12px;
  overflow: hidden;
}}

/* 紧凑间距调整 */
.stSlider > div {{ padding: 8px 0; }}

/* 颜色选择器样式 */
.stColorPicker > div > div {{
  border-radius: 12px;
  border: 1px solid var(--border-color);
  overflow: hidden;
}}

/* 侧边栏样式 */
.css-1d391kg {{
  background: linear-gradient(135deg, {PRIMARY_LIGHT} 0%, {SECONDARY_LIGHT} 100%);
}}

section[data-testid="stSidebar"] > div {{
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
}}

/* 成功/错误消息样式 */
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

/* 多选组件样式 */
.stMultiSelect > div > div > div {{
  background: white;
  border: 1px solid var(--border-color);
  border-radius: 12px;
}}

.stMultiSelect > div > div > div:hover {{
  border-color: var(--accent-primary);
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
    cand = []
    if sys.platform.startswith("win"):
        cand = [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]
    elif sys.platform.startswith("darwin"):
        cand = ["/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]
    else:
        cand = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"]
    for p in cand:
        if os.path.exists(p):
            return p
    return None

DEFAULT_FONT = find_font()

def load_font(path, size):
    try:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
        if DEFAULT_FONT:
            return ImageFont.truetype(DEFAULT_FONT, size)
    except Exception:
        pass
    return ImageFont.load_default()

# ---------- 语音 / 预设库（简要） ----------
EN_MALE = ["en-US-GuyNeural","en-US-BenjaminNeural","en-GB-RyanNeural"]
EN_FEMALE = ["en-US-JennyNeural","en-US-AriaNeural","en-GB-SoniaNeural"]
ZH_VOICES = ["zh-CN-XiaoxiaoNeural","zh-CN-YunxiNeural","zh-CN-KangkangNeural"]
VOICE_LIBRARY = {"英文男声": EN_MALE, "英文女声": EN_FEMALE, "中文音色": ZH_VOICES}

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

# ---------- 页面顶部 / 导航 ----------
st.markdown(f'<div class="main-title">🎬 英语视频生成器 - 专业级多音色教学视频制作平台</div>', unsafe_allow_html=True)
st.markdown(f"""<div class="navbar">
  <div class="nav-btn">📁 数据管理</div>
  <div class="nav-btn">🎨 样式设计</div>
  <div class="nav-btn">🔊 音频编排</div>
  <div class="nav-btn">⚙️ 高级设置</div>
  <div class="nav-btn">📤 生成输出</div>
</div>""", unsafe_allow_html=True)

# ---------- 左侧：数据管理（上传/预览/编辑） ----------
left_col, right_col = st.columns([0.4, 0.6])

with left_col:
    st.markdown('<div class="card">', unsafe_allow_html=True)
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
                st.dataframe(df.head(10), use_container_width=True)
                if st.button("在页面中编辑数据", use_container_width=True):
                    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
                    df = edited.copy()
                    st.success("已应用编辑")
        except Exception as e:
            st.error(f"解析失败：{e}")
    else:
        st.info("未上传数据，示例：请上传包含列 英语 / 中文（可选 音标）的文件。")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- 右侧：样式设计模块 ----------
with right_col:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header">🎨 样式设计</div>', unsafe_allow_html=True)

    # --- 背景设置（3 列） ---
    bg_col1, bg_col2, bg_col3 = st.columns([1,1,1])
    with bg_col1:
        bg_mode = st.selectbox("背景类型", ["纯色背景", "图片背景"], key="ui_bg_mode")
    with bg_col2:
        ui_bg_color = st.color_picker("背景颜色", "#f8fafc", key="ui_bg_color")
    with bg_col3:
        ui_logo_file = st.file_uploader("Logo (PNG)", type=["png"], key="ui_logo")

    ui_bg_image = None
    if bg_mode == "图片背景":
        bg_file = st.file_uploader("上传背景图片 (JPG/PNG)", type=["jpg","jpeg","png"], key="ui_bgimg")
        if bg_file:
            try:
                ui_bg_image = Image.open(bg_file).convert("RGBA")
                st.image(ui_bg_image, caption="背景预览", use_container_width=True)
            except Exception:
                st.error("无法读取背景图片")

    ui_logo_img = None
    if ui_logo_file:
        try:
            ui_logo_img = Image.open(ui_logo_file).convert("RGBA")
        except:
            ui_logo_img = None

    # --- 文字样式（3 列并排：英语 / 音标 / 中文） ---
    st.markdown("**文字样式**")
    col_en, col_ph, col_cn = st.columns(3)
    with col_en:
        en_size = st.slider("英语字号", 0, 160, 60, key="ui_en_size")
        en_color = st.color_picker("英语颜色", "#1e293b", key="ui_en_color")
    with col_ph:
        ph_size = st.slider("音标字号", 0, 120, 40, key="ui_ph_size")
        ph_color = st.color_picker("音标颜色", "#475569", key="ui_ph_color")
    with col_cn:
        cn_size = st.slider("中文字号", 0, 120, 50, key="ui_cn_size")
        cn_color = st.color_picker("中文颜色", "#334155", key="ui_cn_color")

    # --- 背景板与间距（4 列） ---
    st.markdown("**背景板与间距**")
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        text_bg_enable = st.checkbox("启用文字背景板", value=False, key="ui_text_bg_enable")
    with b2:
        text_bg_color = st.color_picker("文字背景颜色", "#ffffff", key="ui_text_bg_color")
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

    # --- 区域/字体文件（2 列） ---
    t1, t2 = st.columns(2)
    with t1:
        text_area_ratio = st.slider("文字区域宽度比例", 0.3, 1.0, 0.85, key="ui_text_area_ratio")
    with t2:
        ph_font_file = st.file_uploader("上传音标字体 (.ttf/.otf)", type=["ttf","otf"], key="ui_ph_font")
        ph_font_path = None
        if ph_font_file:
            try:
                ph_font_path = os.path.join(APP_TMP, f"ph_font_{now_ts()}.ttf")
                with open(ph_font_path, "wb") as fp:
                    fp.write(ph_font_file.read())
            except Exception:
                ph_font_path = None

    # --- 汇总 style_conf 供后续使用 ---
    style_conf = {
        "bg_mode": "image" if ui_bg_image else "color",
        "bg_color": ui_bg_color,
        "bg_image": ui_bg_image,
        "logo_img": ui_logo_img,
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
        "phonetic_font": ph_font_path
    }

    st.markdown("</div>", unsafe_allow_html=True)

# ---------- 左侧：模板/进度 ----------
with left_col:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header">📦 模板与学习记录</div>', unsafe_allow_html=True)
    if not LIGHTWEIGHT_MODE:
        if st.button("显示已保存模板", use_container_width=True):
            templates = load_templates()
            if templates:
                for tname, tdata in templates:
                    st.write(f"- {tname}")
            else:
                st.write("尚无模板。")
        prog = load_progress()
        st.write(f"已学习记录条目：{len(prog)}")
    else:
        st.write("轻量模式：模板/进度功能已禁用以加速启动。")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- TTS 辅助函数 ----------
def save_pyttsx3_wav(text: str, voice_id: Optional[str], rate_wpm: int, out_wav: str) -> bool:
    """使用 pyttsx3 保存 wav（如果可用）"""
    if not PYTTSX3_AVAILABLE:
        return False
    try:
        engine = pyttsx3.init()
        if voice_id:
            try:
                engine.setProperty("voice", voice_id)
            except Exception:
                pass
        engine.setProperty("rate", rate_wpm)
        engine.save_to_file(text, out_wav)
        engine.runAndWait()
        try:
            engine.stop()
        except:
            pass
        return os.path.exists(out_wav) and os.path.getsize(out_wav) > 0
    except Exception as e:
        print("pyttsx3 save wav error:", e)
        return False

def wav_to_mp3_ffmpeg(wav_path: str, mp3_path: str, bitrate: str = "128k") -> bool:
    """用 ffmpeg 把 wav 转 mp3"""
    if ffmpeg_available():
        cmd = ["ffmpeg", "-y", "-i", wav_path, "-q:a", "4", "-b:a", bitrate, mp3_path]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return os.path.exists(mp3_path)
        except Exception as e:
            print("wav_to_mp3_ffmpeg failed:", e)
            return False
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
        print("edge async error:", e)
        return False

def generate_edge_mp3(text: str, voice: str, speed: float, out_mp3: str) -> bool:
    """同步封装 edge-tts（通过 asyncio.run）"""
    if not EDGE_TTS_AVAILABLE:
        return False
    pct = int((speed - 1.0) * 100)
    rate_str = f"{pct:+d}%"
    try:
        return asyncio.run(_edge_save_async(text, voice, out_mp3, rate_str))
    except Exception as e:
        print("generate_edge_mp3 failed:", e)
        return False

def generate_offline_mp3(text: str, voice_id: Optional[str], speed: float, out_mp3: str) -> bool:
    """使用 pyttsx3 生成 wav，再转 mp3（需要 ffmpeg）"""
    fd, tmpwav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    rate_wpm = int(180 * speed)
    ok = save_pyttsx3_wav(text, voice_id, rate_wpm, tmpwav)
    if not ok:
        safe_remove(tmpwav)
        return False
    ok2 = wav_to_mp3_ffmpeg(tmpwav, out_mp3)
    safe_remove(tmpwav)
    return ok2

def generate_tts_cached(text: str, voice_category: Optional[str], voice_choice: Optional[str], speed: float, engine_pref: str, out_mp3: str) -> bool:
    """缓存层：优先使用缓存，按 engine_pref 选择离线/在线"""
    voice_name = voice_choice or (VOICE_LIBRARY.get(voice_category, [None])[0] if voice_category else None)
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
    if engine_pref == "离线优先":
        if PYTTSX3_AVAILABLE:
            ok = generate_offline_mp3(text, voice_choice, speed, tmpmp3)
        if not ok and EDGE_TTS_AVAILABLE:
            ok = generate_edge_mp3(text, voice_name or voice_choice, speed, tmpmp3)
    else:
        if EDGE_TTS_AVAILABLE:
            ok = generate_edge_mp3(text, voice_name or voice_choice, speed, tmpmp3)
        if not ok and PYTTSX3_AVAILABLE:
            ok = generate_offline_mp3(text, voice_choice, speed, tmpmp3)
    if ok and os.path.exists(tmpmp3):
        try:
            cache_store(tmpmp3, key)
            shutil.copy(cache_get(key), out_mp3)
            safe_remove(tmpmp3)
            return True
        except Exception:
            try:
                shutil.copy(tmpmp3, out_mp3); safe_remove(tmpmp3); return True
            except:
                safe_remove(tmpmp3)
                return False
    safe_remove(tmpmp3)
    return False

# ---------- 基本音频处理 ----------
def create_silent_mp3(out_path: str, duration_s: float) -> bool:
    """创建一段静音 mp3（用 ffmpeg）"""
    try:
        if ffmpeg_available():
            cmd = ["ffmpeg","-y","-f","lavfi","-i",f"anullsrc=r=44100:cl=mono","-t",str(duration_s), out_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return os.path.exists(out_path)
    except Exception as e:
        print("create_silent_mp3 ffmpeg error:", e)
    # fallback：创建空文件（播放时可能无声）
    try:
        with open(out_path, "wb") as f: f.write(b"")
        return True
    except:
        return False

def concat_audios_ffmpeg(audio_paths: List[str], out_mp3: str) -> None:
    """使用 ffmpeg concat 合并多个 mp3 文件（要求 ffmpeg 可用）"""
    if not audio_paths:
        raise ValueError("audio_paths empty")
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg missing for audio concat")
    listfile = out_mp3 + "_list.txt"
    with open(listfile, "w", encoding="utf-8") as f:
        for p in audio_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",listfile,"-c","copy",out_mp3]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    safe_remove(listfile)

def audio_trim(src: str, out: str, start: float, end: float) -> bool:
    """裁剪音频区间到 out"""
    try:
        if PYDUB_AVAILABLE:
            seg = AudioSegment.from_file(src)
            new = seg[int(start*1000):int(end*1000)]
            new.export(out, format="mp3")
            return True
        if ffmpeg_available():
            cmd = ["ffmpeg","-y","-i",src,"-ss",str(start),"-to",str(end),"-c","copy",out]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return os.path.exists(out)
    except Exception as e:
        print("audio_trim error:", e)
    return False

def audio_adjust_volume(src: str, out: str, db_change: float) -> bool:
    """调整音量，db_change 可以为正负"""
    try:
        if PYDUB_AVAILABLE:
            seg = AudioSegment.from_file(src)
            new = seg + db_change
            new.export(out, format="mp3")
            return True
        if ffmpeg_available():
            vol = f"{db_change}dB"
            cmd = ["ffmpeg","-y","-i",src,"-filter:a",f"volume={vol}",out]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return os.path.exists(out)
    except Exception as e:
        print("audio_adjust_volume error:", e)
    return False

def audio_mix_with_bg(foreground: str, background: str, out_path: str, fg_db: float = 0.0, bg_db: float = -12.0) -> bool:
    """将 foreground 混入 background（background 长度>=foreground，若短则循环）"""
    try:
        if PYDUB_AVAILABLE:
            fg = AudioSegment.from_file(foreground)
            bg = AudioSegment.from_file(background)
            if len(bg) < len(fg):
                times = int(math.ceil(len(fg)/len(bg)))
                bg = bg * times
            bg = bg[:len(fg)]
            fg = fg + fg_db
            bg = bg + bg_db
            mixed = bg.overlay(fg)
            mixed.export(out_path, format="mp3")
            return True
        if ffmpeg_available():
            cmd = [
                "ffmpeg","-y","-i",background,"-i",foreground,
                "-filter_complex", f"[0:a]volume={bg_db}dB[bg];[1:a]volume={fg_db}dB[fg];[bg][fg]amix=inputs=2:duration=shortest",
                "-b:a","192k", out_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            return os.path.exists(out_path)
    except Exception as e:
        print("audio_mix_with_bg error:", e)
    return False

# ---------- 音色样本库 & 试听 UI ----------
def ensure_sample_voice(voice_name: str, sample_text: str = "Hello, this is a sample.") -> Optional[str]:
    """生成或返回缓存的音色示例 mp3 路径"""
    key = hashlib.sha1(f"sample::{voice_name}".encode()).hexdigest()
    out = cache_get(key)
    if os.path.exists(out):
        return out
    # 生成示例（优先线上）
    fd, tmpmp3 = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    ok = False
    if EDGE_TTS_AVAILABLE:
        ok = generate_edge_mp3(sample_text, voice_name, 1.0, tmpmp3)
    if not ok and PYTTSX3_AVAILABLE:
        ok = generate_offline_mp3(sample_text, None, 1.0, tmpmp3)
    if ok and os.path.exists(tmpmp3):
        cache_store(tmpmp3, key)
        safe_remove(tmpmp3)
        return cache_get(key)
    safe_remove(tmpmp3)
    return None

def get_voice_category(voice_name: str) -> str:
    """根据音色名称获取分类"""
    if voice_name in EN_MALE:
        return "英文男声"
    elif voice_name in EN_FEMALE:
        return "英文女声"
    elif voice_name in ZH_VOICES:
        return "中文音色"
    return "其他"

def get_voice_display_name(voice_name: str) -> str:
    """获取音色的显示名称"""
    parts = voice_name.split("-")
    if len(parts) >= 3:
        return f"{parts[2]} ({parts[1]})"
    return voice_name

# ---------- 音频编排交互 UI ----------
with right_col:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header">🔊 音频编排与音色管理</div>', unsafe_allow_html=True)

    engine_pref = st.selectbox("引擎偏好", ["离线优先", "在线优先"], key="ui_engine_pref")
    st.caption(f"系统离线可用: {PYTTSX3_AVAILABLE}；在线 edge-tts 可用: {EDGE_TTS_AVAILABLE}")

    # 智能推荐 + 预设选择
    learning_goal = st.text_input("学习目标（用于智能推荐）", value="", key="ui_learning_goal")
    recommended = recommend_preset(learning_goal)
    preset_choice = st.selectbox("预设播放模式", ["(自定义)"] + list(PRESET_MODES.keys()), index=1 if recommended in PRESET_MODES else 0, key="ui_preset_choice")

    # 音频段数（灵活）
    n_segments = st.number_input("音频段数", min_value=1, max_value=12, value=4, step=1, key="ui_n_segments")

    # 构建段配置表（并行显示）
    audio_segments = []
    for si in range(int(n_segments)):
        st.markdown(f"**段 {si+1}**", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1.5, 1.2, 1, 1])
        with c1:
            content = st.selectbox(f"段{si+1} 内容", ["英语", "音标", "中文"], key=f"ui_seg_content_{si}")
        with c2:
            category = st.selectbox(f"段{si+1} 音色库", ["英文女声", "英文男声", "中文音色", "系统本地"], key=f"ui_seg_cat_{si}")
        with c3:
            vc = "(默认)"
            if category == "系统本地" and PYTTSX3_AVAILABLE:
                try:
                    eng = pyttsx3.init()
                    voices = eng.getProperty("voices")
                    ls = ["(默认)"] + [getattr(v, "name", str(v)) for v in voices]
                    vc = st.selectbox(f"段{si+1} 本地语音", ls, key=f"ui_seg_local_{si}")
                except:
                    vc = st.selectbox(f"段{si+1} 本地语音", ["(默认)"], key=f"ui_seg_local_{si}")
            else:
                presets = VOICE_LIBRARY.get(category, [])
                ls = ["(默认)"] + presets
                vc = st.selectbox(f"段{si+1} 具体音色", ls, key=f"ui_seg_preset_{si}")
        with c4:
            speed = st.slider(f"段{si+1} 语速", 0.5, 2.0, 1.0, 0.1, key=f"ui_seg_speed_{si}")
            pause = st.number_input(f"段{si+1} 停顿 (秒)", min_value=0.0, max_value=5.0, value=0.3, step=0.1, key=f"ui_seg_pause_{si}")
        # normalize voice_choice value
        voice_choice = None
        if category == "系统本地" and vc != "(默认)":
            voice_choice = vc
        elif vc != "(默认)":
            voice_choice = vc
        audio_segments.append({
            "content": content,
            "voice_category": category,
            "voice_choice": voice_choice,
            "speed": speed,
            "pause": pause,
            "engine_pref": engine_pref
        })

    # ---------- 重新设计的试听部分 ----------
    st.markdown('<div class="card-header">🎵 音色样本库</div>', unsafe_allow_html=True)
    
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
        st.markdown('</div>', unsafe_allow_html=True)
    
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
        st.markdown('</div>', unsafe_allow_html=True)
    
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
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 视频生成引擎 / 进度与模板 / 队列 / 预览与下载
# =========================

# ---------- Frame rendering ----------
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    lv = len(hex_color)
    if lv == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    if lv == 3:
        return tuple(int(hex_color[i]*2, 16) for i in range(3))
    return (0, 0, 0)

def smart_wrap(draw, text, font, max_width):
    """自动换行，兼顾中英文"""
    if not text:
        return []
    words = []
    cur = ""
    for ch in text:
        t = cur + ch
        if draw.textlength(t, font=font) <= max_width:
            cur = t
        else:
            words.append(cur)
            cur = ch
    if cur:
        words.append(cur)
    return words

def render_frame(en, ph, cn, conf, size=(1280,720)):
    """渲染单帧图像"""
    W,H = size
    bg_color = conf.get("bg_color", PRIMARY_LIGHT)
    base = Image.new("RGB", (W,H), bg_color)
    draw = ImageDraw.Draw(base)

    # 加载字体
    font_en = load_font(DEFAULT_FONT, conf.get("english_size", 60))
    font_ph = load_font(DEFAULT_FONT, conf.get("phonetic_size", 40))
    font_cn = load_font(DEFAULT_FONT, conf.get("chinese_size", 50))

    # 三层文本
    text_area = int(W * conf.get("text_area_width_ratio", 0.85))
    padding = conf.get("text_padding", 20)
    ls = conf.get("line_spacing", 6)
    en_lines = smart_wrap(draw, en, font_en, text_area)
    ph_lines = smart_wrap(draw, ph, font_ph, text_area)
    cn_lines = smart_wrap(draw, cn, font_cn, text_area)

    total_h = (len(en_lines)+len(ph_lines)+len(cn_lines))*50 + 40
    start_y = (H - total_h)//2
    y = start_y

    # 英语
    for line in en_lines:
        w = draw.textlength(line, font=font_en)
        draw.text(((W-w)//2, y), line, font=font_en, fill=conf.get("english_color", TEXT_DARK))
        y += conf.get("english_size",60) + ls
    y += conf.get("english_phonetic_gap", 10)

    # 音标
    for line in ph_lines:
        w = draw.textlength(line, font=font_ph)
        draw.text(((W-w)//2, y), line, font=font_ph, fill=conf.get("phonetic_color", "#475569"))
        y += conf.get("phonetic_size",40) + ls
    y += conf.get("phonetic_cn_gap", 10)

    # 中文
    for line in cn_lines:
        w = draw.textlength(line, font=font_cn)
        draw.text(((W-w)//2, y), line, font=font_cn, fill=conf.get("chinese_color", "#334155"))
        y += conf.get("chinese_size",50) + ls

    return base

# ---------- 合成视频 ----------
def merge_video_audio(video_path, audio_path, out_path):
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg missing for merge_video_audio")
    cmd = [
        "ffmpeg","-y","-i",video_path,"-i",audio_path,
        "-c:v","copy","-c:a","aac","-shortest",out_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def generate_video_pipeline(df, rows, style_conf, audio_segments, video_params, progress_cb=None):
    """整合生成流程"""
    tmpdir = tempfile.mkdtemp(prefix="gen_")
    try:
        W,H = video_params.get("resolution",(1280,720))
        fps = video_params.get("fps",12)
        seg_dur = video_params.get("duration_per_segment",3.0)
        frames_per_seg = int(seg_dur * fps)
        frame_files = []
        audios = []
        total_steps = len(rows) * len(audio_segments)
        step = 0
        for rid in rows:
            row = df.iloc[rid]
            en = str(row.get("英语",""))
            ph = str(row.get("音标",""))
            cn = str(row.get("中文",""))
            # === 音频生成 ===
            seg_paths = []
            for seg in audio_segments:
                text = en if seg["content"]=="英语" else (ph if seg["content"]=="音标" else cn)
                out_mp3 = os.path.join(tmpdir, f"{rid}_{seg['content']}.mp3")
                ok = generate_tts_cached(text, seg["voice_category"], seg["voice_choice"], seg["speed"], seg["engine_pref"], out_mp3)
                if not ok:
                    create_silent_mp3(out_mp3, seg_dur)
                seg_paths.append(out_mp3)
                if seg.get("pause",0)>0:
                    pause_path = os.path.join(tmpdir, f"pause_{rid}_{seg['content']}.mp3")
                    create_silent_mp3(pause_path, seg["pause"])
                    seg_paths.append(pause_path)
                step += 1
                if progress_cb:
                    progress_cb(step/total_steps)
            merged_audio = os.path.join(tmpdir, f"{rid}_merged.mp3")
            concat_audios_ffmpeg(seg_paths, merged_audio)
            audios.append(merged_audio)

            # === 画面渲染 ===
            img = render_frame(en, ph, cn, style_conf, (W,H))
            for i in range(frames_per_seg):
                fname = os.path.join(tmpdir, f"{rid}_{i:04d}.png")
                img.save(fname)
                frame_files.append(fname)

        # === 合成视频 ===
        list_txt = os.path.join(tmpdir, "imgs.txt")
        with open(list_txt, "w", encoding="utf-8") as f:
            for p in frame_files:
                f.write(f"file '{p}'\n")
                f.write("duration 0.04\n")
        video_no_audio = os.path.join(tmpdir, "video.mp4")
        subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",list_txt,"-vsync","vfr","-pix_fmt","yuv420p", video_no_audio],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        final_audio = os.path.join(tmpdir, "final_audio.mp3")
        concat_audios_ffmpeg(audios, final_audio)
        out_video = os.path.join(tmpdir, "final_out.mp4")
        merge_video_audio(video_no_audio, final_audio, out_video)
        return out_video
    except Exception as e:
        st.error(f"生成失败: {e}")
        traceback.print_exc()
        return None

# ---------- 后台任务队列 ----------
TASK_QUEUE = Queue()
TASK_STATUS = {}

def worker():
    while True:
        task = TASK_QUEUE.get()
        if task is None:
            break
        tid = task["id"]
        TASK_STATUS[tid] = {"status":"running","progress":0.0}
        try:
            res = generate_video_pipeline(task["df"], task["rows"], task["style"], task["audio_segments"], task["video_params"], progress_cb=lambda p: TASK_STATUS[tid].update({"progress":p}))
            TASK_STATUS[tid].update({"status":"done","result":res})
        except Exception as e:
            TASK_STATUS[tid].update({"status":"failed","error":str(e)})
        TASK_QUEUE.task_done()

if "worker_started" not in st.session_state:
    t = Thread(target=worker, daemon=True)
    t.start()
    st.session_state["worker_started"] = True

# ---------- 生成与下载 UI ----------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-header">📤 生成与预览 / 下载</div>', unsafe_allow_html=True)

if uploaded is not None and df is not None:
    total = len(df)
    rows = st.multiselect("选择生成的行", options=list(range(total)), format_func=lambda i: f"{i+1} - {df.iloc[i]['英语']}", default=list(range(min(total,3))))
    if rows:
        if st.button("▶️ 开始生成视频", use_container_width=True):
            progress = st.progress(0.0)
            status = st.empty()
            def cb(p):
                progress.progress(p)
                status.text(f"进度: {int(p*100)}%")
            params = {"resolution":(1280,720),"fps":12,"duration_per_segment":3.0}
            status.text("生成中...")
            outp = generate_video_pipeline(df, rows, style_conf, audio_segments, params, progress_cb=cb)
            if outp and os.path.exists(outp):
                st.success("✅ 视频生成完成")
                with open(outp,"rb") as f:
                    st.video(f.read())
                with open(outp,"rb") as f:
                    st.download_button("📥 下载视频", f, file_name="travel_english.mp4", use_container_width=True)
            else:
                st.error("❌ 生成失败")
    else:
        st.info("请选择至少一行进行生成。")
st.markdown('</div>', unsafe_allow_html=True)

# ---------- 模板保存 / 加载 ----------
st.sidebar.header("模板与任务")
templates = load_templates()
if st.sidebar.button("保存当前配置为模板", use_container_width=True):
    name = f"模板_{time.strftime('%H%M%S')}"
    save_template(name, style_conf, audio_segments, {"resolution":(1280,720),"fps":12})
    st.sidebar.success(f"已保存模板 {name}")
if templates:
    for tname, tdata in templates:
        if st.sidebar.button(f"应用模板 {tname}", use_container_width=True):
            style_conf.update(tdata["style"])
            audio_segments[:] = tdata["audio"]
            st.sidebar.info(f"已应用模板 {tname}")

# ---------- 环境提示 ----------
st.sidebar.subheader("环境检测")
st.sidebar.write(f"✅ ffmpeg: {'可用' if ffmpeg_available() else '缺失'}")
st.sidebar.write(f"✅ pyttsx3: {'可用' if PYTTSX3_AVAILABLE else '缺失'}")
st.sidebar.write(f"✅ edge-tts: {'可用' if EDGE_TTS_AVAILABLE else '缺失'}")
st.sidebar.write(f"✅ pydub: {'可用' if PYDUB_AVAILABLE else '缺失'}")

if not ffmpeg_available():
    st.sidebar.warning("未检测到 ffmpeg，请在云端环境安装。")

# ---------- 页脚 ----------
st.markdown(
    f"""
    <div class='footer'>
    © 2025 英语视频生成器 • 技术支持：AI 多媒体实验室  
    环境：FFmpeg {"✅ 已检测" if ffmpeg_available() else "⚠️ 未检测"}  
    </div>
    """,
    unsafe_allow_html=True
)
