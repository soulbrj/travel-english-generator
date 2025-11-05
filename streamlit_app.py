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
import socket
import time

# -----------------------
# 工具函数
# -----------------------
def check_ffmpeg():
    ffmpeg_path = shutil.which("ffmpeg")
    return ffmpeg_path is not None

def is_internet_available(host="speech.platform.bing.com", port=443, timeout=3):
    """检查微软语音服务是否可访问"""
    try:
        socket.create_connection((host, port), timeout=timeout)
        return True
    except OSError:
        return False

# -----------------------
# Edge-TTS 初始化
# -----------------------
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

# -----------------------
# Streamlit 页面配置
# -----------------------
st.set_page_config(page_title="旅行英语视频生成器", page_icon="🎬", layout="wide")

# -----------------------
# 异步 TTS 生成（安全封装）
# -----------------------
async def _edge_tts_save_async(text: str, voice_name: str, out_path: str, rate: str = "+0%"):
    try:
        communicate = edge_tts.Communicate(text, voice_name, rate=rate)
        await communicate.save(out_path)
        return True
    except Exception as e:
        st.warning(f"TTS生成失败: {e}")
        return False

def generate_edge_audio(text, voice, speed=1.0, out_path=None, retry=2):
    """安全 TTS 生成，支持重试与网络检测"""
    if not EDGE_TTS_AVAILABLE:
        st.warning("Edge TTS 模块未安装")
        return None

    if not is_internet_available():
        st.warning("无法连接微软语音服务，将使用静音代替。")
        return None

    pct = int((speed - 1.0) * 100)
    rate_str = f"{pct:+d}%"

    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)

    async def _safe_call():
        return await _edge_tts_save_async(text, voice, out_path, rate_str)

    for attempt in range(1, retry + 1):
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                future = asyncio.ensure_future(_safe_call())
                asyncio.get_event_loop().run_until_complete(future)
                result = future.result()
            else:
                result = asyncio.run(_safe_call())

            if result and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return out_path
            else:
                st.warning(f"TTS 第 {attempt} 次生成无音频数据，重试中...")
                time.sleep(1)
        except Exception as e:
            st.warning(f"TTS生成异常（第{attempt}次）: {e}")
            time.sleep(1)

    st.error("❌ TTS 多次生成失败，将使用静音。")
    if os.path.exists(out_path):
        os.unlink(out_path)
    return None

def preview_voice(voice_name, text, speed=1.0):
    """生成试听音频"""
    if not EDGE_TTS_AVAILABLE:
        st.warning("Edge TTS 模块不可用")
        return None

    if not is_internet_available():
        st.warning("无法连接微软语音服务，试听将使用静音。")
        return None

    pct = int((speed - 1.0) * 100)
    rate_str = f"{pct:+d}%"

    async def _preview():
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp.close()
        communicate = edge_tts.Communicate(text, voice_name, rate=rate_str)
        await communicate.save(temp.name)
        if os.path.exists(temp.name) and os.path.getsize(temp.name) > 0:
            with open(temp.name, "rb") as f:
                data = f.read()
            os.unlink(temp.name)
            return data
        return None

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            future = asyncio.ensure_future(_preview())
            asyncio.get_event_loop().run_until_complete(future)
            audio_bytes = future.result()
        else:
            audio_bytes = asyncio.run(_preview())
        return audio_bytes
    except Exception as e:
        st.warning(f"试听失败: {e}")
        return None

# -----------------------
# 其他视频生成、绘制逻辑
# -----------------------

def wrap_text(text, max_chars):
    if not text or str(text).strip().lower() == "nan":
        return [""]
    text = str(text).strip()
    if any("\u4e00" <= c <= "\u9fff" for c in text):
        max_chars = min(max_chars, 15)
    words = text.split()
    lines, current = [], []
    for word in words:
        test_line = " ".join(current + [word])
        if len(test_line) <= max_chars:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            if len(word) > max_chars:
                for i in range(0, len(word), max_chars):
                    lines.append(word[i:i + max_chars])
                current = []
            else:
                current = [word]
    if current:
        lines.append(" ".join(current))
    return lines

def get_font(size, bold=False):
    try:
        if bold:
            candidates = ["arialbd.ttf", "simhei.ttf", "msyhbd.ttc"]
        else:
            candidates = ["arial.ttf", "msyh.ttc", "simsun.ttc"]
        for c in candidates:
            try:
                return ImageFont.truetype(c, size)
            except:
                continue
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

def create_frame(english, chinese, phonetic, width=1280, height=720,
                 bg_color=(0,0,0), eng_color=(255,255,255),
                 chn_color=(173,216,230), pho_color=(255,255,0)):
    """生成单帧图片"""
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    eng_font = get_font(80, True)
    pho_font = get_font(50)
    chn_font = get_font(60)
    y = height // 2 - 100
    for line in wrap_text(english, 40):
        w, h = draw.textsize(line, font=eng_font)
        draw.text(((width - w)//2, y), line, fill=eng_color, font=eng_font)
        y += h + 10
    for line in wrap_text(phonetic, 45):
        w, h = draw.textsize(line, font=pho_font)
        draw.text(((width - w)//2, y), line, fill=pho_color, font=pho_font)
        y += h + 10
    for line in wrap_text(chinese, 20):
        w, h = draw.textsize(line, font=chn_font)
        draw.text(((width - w)//2, y), line, fill=chn_color, font=chn_font)
        y += h + 10
    return img

def create_silent_audio(duration, output_path):
    """生成静音音频"""
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(duration), output_path]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return os.path.exists(output_path)

def merge_video_audio(video_path, audio_path, output_path):
    """合并视频和音频"""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-shortest", output_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return os.path.exists(output_path)

def generate_video(df, settings, progress_bar):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            writer = imageio.get_writer(video_path, fps=settings["fps"], codec="libx264")
            audio_files = []
            for idx, row in df.iterrows():
                eng, chn = str(row["英语"]), str(row["中文"])
                pho = str(row["音标"]) if pd.notna(row["音标"]) else ""
                frame = np.array(create_frame(eng, chn, pho, width=settings["width"], height=settings["height"]))
                for _ in range(settings["fps"] * settings["duration"]):
                    writer.append_data(frame)
                progress_bar.progress((idx + 1) / len(df) * 0.7)
                audio_file = generate_edge_audio(eng, settings["voice"], speed=settings["speed"])
                if not audio_file:
                    audio_file = os.path.join(tmpdir, f"silent_{idx}.mp3")
                    create_silent_audio(settings["duration"], audio_file)
                audio_files.append(audio_file)
            writer.close()

            # 合并音频
            combined_audio = os.path.join(tmpdir, "combined.mp3")
            list_file = os.path.join(tmpdir, "list.txt")
            with open(list_file, "w") as f:
                for a in audio_files:
                    f.write(f"file '{a}'\n")
            subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", combined_audio])
            progress_bar.progress(0.9)

            final_path = os.path.join(tmpdir, "final.mp4")
            merge_video_audio(video_path, combined_audio, final_path)
            progress_bar.progress(1.0)
            with open(final_path, "rb") as f:
                return f.read()
    except Exception as e:
        st.error(f"视频生成失败: {e}")
        return None

# -----------------------
# Streamlit UI
# -----------------------
st.title("🎬 旅行英语视频生成器")

uploaded = st.file_uploader("上传Excel文件（需含英语、中文、音标列）", type=["xlsx"])
if uploaded:
    df = pd.read_excel(uploaded)
    if not {"英语", "中文", "音标"}.issubset(df.columns):
        st.error("缺少必要列：英语、中文、音标")
        st.stop()
    st.dataframe(df.head())
    st.success(f"共 {len(df)} 行数据")

    st.markdown("### 参数设置")
    width = st.selectbox("视频宽度", [640, 960, 1280, 1920], index=2)
    height = int(width * 9 / 16)
    fps = st.slider("帧率", 8, 30, 20)
    duration = st.slider("每条持续时间（秒）", 2, 8, 4)
    speed = st.slider("TTS语速", 0.5, 2.0, 1.0)
    voices = {
        "Aria (女声)": "en-US-AriaNeural",
        "Guy (男声)": "en-US-GuyNeural",
        "Xiaoxiao (中文女声)": "zh-CN-XiaoxiaoNeural",
    }
    voice_label = st.selectbox("选择音色", list(voices.keys()))
    voice = voices[voice_label]

    if st.button("🎥 生成视频"):
        progress = st.progress(0)
        settings = {
            "width": width,
            "height": height,
            "fps": fps,
            "duration": duration,
            "voice": voice,
            "speed": speed,
        }
        video_bytes = generate_video(df, settings, progress)
        if video_bytes:
            st.success("✅ 视频生成完成！")
            st.video(video_bytes)
            st.download_button("📥 下载视频", video_bytes, "output.mp4", "video/mp4")
