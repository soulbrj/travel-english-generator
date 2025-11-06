import os
import shutil
import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio
import tempfile
import subprocess
import asyncio
import base64
import textwrap

# ------------------------------
# 离线优先 TTS 支持
# ------------------------------
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


def check_ffmpeg():
    return shutil.which("ffmpeg") is not None


# ------------------------------
# Streamlit 基本配置
# ------------------------------
st.set_page_config(
    page_title="旅行英语视频生成器",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main {
        background-color: #f8fafc;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        background-color: #2563eb;
        color: white;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #1e40af;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "bg_image" not in st.session_state:
    st.session_state.bg_image = None


# ------------------------------
# 文本渲染 & 帧生成函数
# ------------------------------
def wrap_text(text, font, max_width):
    lines = []
    words = text.split(" ")
    line = ""
    for word in words:
        if font.getlength(line + word) <= max_width:
            line += word + " "
        else:
            lines.append(line)
            line = word + " "
    lines.append(line)
    return lines


def create_frame(text, phonetic, translation, size=(1920, 1080)):
    img = Image.new("RGB", size, color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    main_font = ImageFont.truetype("arial.ttf", 80)
    phonetic_font = ImageFont.truetype("arial.ttf", 60)
    trans_font = ImageFont.truetype("arial.ttf", 70)

    lines = wrap_text(text, main_font, 1600)
    y = 250
    for line in lines:
        w = main_font.getlength(line)
        draw.text(((size[0] - w) / 2, y), line, font=main_font, fill=(0, 0, 0))
        y += 100

    if phonetic:
        w = phonetic_font.getlength(phonetic)
        draw.text(((size[0] - w) / 2, y + 30), phonetic, font=phonetic_font, fill=(100, 100, 100))
    if translation:
        w = trans_font.getlength(translation)
        draw.text(((size[0] - w) / 2, y + 150), translation, font=trans_font, fill=(50, 50, 50))
    return img


# ------------------------------
# 离线 pyttsx3 TTS
# ------------------------------
def list_pyttsx3_voices():
    voices_info = []
    try:
        engine = pyttsx3.init()
        for v in engine.getProperty("voices"):
            voices_info.append({"id": v.id, "name": v.name})
        engine.stop()
    except Exception:
        pass
    return voices_info


def save_pyttsx3_to_wav(text, voice_id, rate_wpm, out_wav):
    try:
        engine = pyttsx3.init()
        if voice_id:
            engine.setProperty("voice", voice_id)
        engine.setProperty("rate", rate_wpm)
        engine.save_to_file(text, out_wav)
        engine.runAndWait()
        engine.stop()
        return True
    except Exception:
        return False


def wav_to_mp3(wav_path, mp3_path):
    if not check_ffmpeg():
        return False
    cmd = ["ffmpeg", "-y", "-i", wav_path, "-q:a", "4", "-acodec", "libmp3lame", mp3_path]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except Exception:
        return False


def generate_offline_audio(text, voice_id=None, speed=1.0, out_path=None):
    if not PYTTSX3_AVAILABLE:
        return None
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
    tmp_wav = out_path + ".wav"
    rate_wpm = int(200 * speed)
    if save_pyttsx3_to_wav(text, voice_id, rate_wpm, tmp_wav):
        if wav_to_mp3(tmp_wav, out_path):
            os.remove(tmp_wav)
            return out_path
    if os.path.exists(tmp_wav):
        os.remove(tmp_wav)
    return None


# ------------------------------
# edge-tts 备用在线接口
# ------------------------------
async def _edge_tts_save(text, voice, out_path, rate="+0%"):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(out_path)
        return True
    except Exception:
        return False


def generate_edge_audio(text, voice, speed=1.0, out_path=None):
    if not EDGE_TTS_AVAILABLE:
        return None
    pct = int((speed - 1.0) * 100)
    rate = f"{pct:+d}%"
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
    try:
        asyncio.run(_edge_tts_save(text, voice, out_path, rate))
        return out_path if os.path.exists(out_path) else None
    except Exception:
        return None


# ------------------------------
# 通用生成接口（离线优先）
# ------------------------------
def generate_tts_audio(text, voice_id=None, tts_speed=1.0):
    # 1) 离线
    if PYTTSX3_AVAILABLE:
        mp3 = generate_offline_audio(text, voice_id, tts_speed)
        if mp3:
            return mp3
    # 2) 在线回退
    if EDGE_TTS_AVAILABLE:
        mp3 = generate_edge_audio(text, voice_id or "en-US-JennyNeural", tts_speed)
        if mp3:
            return mp3
    return None


# ------------------------------
# 音频合并、视频生成
# ------------------------------
def merge_audio_files(audio_paths, output_path):
    if not check_ffmpeg():
        raise RuntimeError("缺少 ffmpeg")
    txt = "\n".join([f"file '{a}'" for a in audio_paths])
    list_file = output_path + "_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        f.write(txt)
    cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", output_path, "-y"]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.remove(list_file)


def merge_video_audio(video_path, audio_path, out_path):
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        out_path,
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


# ------------------------------
# 主界面
# ------------------------------
st.title("🎬 旅行英语视频生成器（离线版支持）")

uploaded_file = st.file_uploader("上传 Excel 文件（包含英文、音标、中文）", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.dataframe(df.head())

# 语音设置
st.subheader("🎤 语音设置")
voice_options = list_pyttsx3_voices()
if voice_options:
    voice_choice = st.selectbox("选择离线语音", [v["name"] for v in voice_options])
    selected_voice_id = [v["id"] for v in voice_options if v["name"] == voice_choice][0]
else:
    st.warning("⚠️ 系统中没有可用的离线语音，将尝试使用在线 Edge TTS。")
    selected_voice_id = "en-US-JennyNeural"

speed = st.slider("语速调整", 0.5, 1.5, 1.0, 0.1)

# 试听
if st.button("🔊 试听"):
    preview_path = generate_tts_audio("Hello, welcome to offline mode!", selected_voice_id, speed)
    if preview_path and os.path.exists(preview_path):
        audio_bytes = open(preview_path, "rb").read()
        st.audio(audio_bytes, format="audio/mp3")
        os.remove(preview_path)
    else:
        st.error("试听失败，请检查 TTS 设置或语音引擎。")

# 生成视频
if st.button("🎞️ 生成视频"):
    if uploaded_file is None:
        st.error("请先上传 Excel 文件！")
    else:
        st.info("开始生成，请稍候...")
        tmp_dir = tempfile.mkdtemp()
        audio_paths = []
        frame_paths = []

        for i, row in df.iterrows():
            en = str(row[0])
            ph = str(row[1]) if len(row) > 1 else ""
            cn = str(row[2]) if len(row) > 2 else ""

            img = create_frame(en, ph, cn)
            frame_path = os.path.join(tmp_dir, f"frame_{i:03d}.png")
            img.save(frame_path)
            frame_paths.append(frame_path)

            audio_path = generate_tts_audio(en, selected_voice_id, speed)
            if audio_path:
                audio_paths.append(audio_path)
            else:
                st.warning(f"❌ 第 {i+1} 行音频生成失败")

        # 拼接音频
        if audio_paths:
            merged_audio = os.path.join(tmp_dir, "merged.mp3")
            merge_audio_files(audio_paths, merged_audio)
            video_out = os.path.join(tmp_dir, "output.mp4")
            imageio.mimsave(video_out, [imageio.imread(p) for p in frame_paths], fps=0.8)
            final_out = os.path.join(tmp_dir, "final.mp4")
            merge_video_audio(video_out, merged_audio, final_out)

            with open(final_out, "rb") as f:
                st.download_button("📥 下载视频", f, file_name="travel_english.mp4")

        shutil.rmtree(tmp_dir, ignore_errors=True)
