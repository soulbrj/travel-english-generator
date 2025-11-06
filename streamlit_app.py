# streamlit_app.py
"""
旅行英语视频生成器 — 离线优先（并支持在线回退）
包含：
- Excel 数据导入与验证（强制列名：英语、中文、音标（可选））
- 视频样式定制（背景、文字样式、文字背景板、间距等）
- 多音色音频系统（离线 pyttsx3 优先 / edge-tts 回退）
- 4 段音频顺序编排与混合
- 视频生成（PIL 渲染帧 + FFmpeg 合成）
- 实时预览与下载
"""
import os
import io
import sys
import shutil
import tempfile
import asyncio
import threading
import time
import math
import traceback
from typing import List, Dict, Tuple, Optional

import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import imageio.v2 as imageio
import subprocess
import base64

# TTS engines
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

# ------------------------
# Config
# ------------------------
MAX_ROWS_SUGGEST = 50  # 建议不超过 50 行生成
DEFAULT_RESOLUTIONS = {
    "640x360": (640, 360),
    "854x480": (854, 480),
    "1280x720": (1280, 720),
    "1920x1080": (1920, 1080),
}

# Default fonts: try to find system fonts for Chinese and phonetics
def find_font_candidates():
    # Candidate paths - best effort
    cand = []
    if sys.platform.startswith("win"):
        cand += [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
        ]
    elif sys.platform.startswith("darwin"):
        cand += [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/STHeiti Medium.ttc",
        ]
    else:
        # linux common
        cand += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    for p in cand:
        if os.path.exists(p):
            return p
    return None

DEFAULT_FONT_PATH = find_font_candidates()

# ------------------------
# Utilities
# ------------------------
def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None

def ensure_dir(d):
    os.makedirs(d, exist_ok=True)

def safe_remove(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

# ------------------------
# Excel Data Handling
# ------------------------
REQUIRED_COLUMNS = ["英语", "中文", "音标"]  # 音标可选，但列名必须存在（可为空）

def validate_and_load_excel(uploaded_file) -> Tuple[Optional[pd.DataFrame], List[str]]:
    """
    验证 Excel 文件，要求包含必须列名（英语、中文、音标）；
    返回 (df, errors)
    """
    errors = []
    try:
        df = pd.read_excel(uploaded_file)
    except Exception as e:
        errors.append(f"Excel 解析失败: {e}")
        return None, errors

    cols = list(df.columns)
    # Normalize columns by stripping spaces
    cols_clean = [str(c).strip() for c in cols]
    df.columns = cols_clean

    # Check for at least 英语 and 中文 columns; 音标列可存在或不存在
    if "英语" not in df.columns or "中文" not in df.columns:
        errors.append("必须包含列名：'英语' 和 '中文' (精确匹配)。音标列为可选，但推荐添加 '音标' 列。")
        return None, errors

    # Ensure '音标' column exists; if not, create empty
    if "音标" not in df.columns:
        df["音标"] = ""

    # Basic format checks: non-empty 英语列
    if df["英语"].isnull().all():
        errors.append("英语列全部为空，请检查数据。")
        return None, errors

    # Trim whitespace
    df["英语"] = df["英语"].astype(str).map(lambda s: s.strip())
    df["中文"] = df["中文"].astype(str).map(lambda s: s.strip())
    df["音标"] = df["音标"].astype(str).map(lambda s: s.strip())

    # Optional limit enforcement warning
    if len(df) > 500:
        errors.append("警告：上传文件行数较多（>500），建议分批生成以降低内存与时间开销。")

    return df, errors

# ------------------------
# TTS: voice libraries and generation
# ------------------------
# We'll provide a simulated voice library mapping. For edge-tts use official voice names if installed.
# For pyttsx3, available voices depend on system; we will list them when available.

def list_local_voices():
    """Return list of dict {'id','name'} from pyttsx3 if available"""
    out = []
    if not PYTTSX3_AVAILABLE:
        return out
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        for v in voices:
            try:
                out.append({"id": getattr(v, "id", None), "name": getattr(v, "name", str(v))})
            except Exception:
                continue
        try:
            engine.stop()
        except:
            pass
    except Exception:
        pass
    return out

# Predefined voice sets (names are suggestions; availability depends on engine)
EN_MALE_PRESETS = [
    "en-US-GuyNeural", "en-US-BenjaminNeural", "en-GB-RyanNeural", "en-AU-WilliamNeural",
    "en-US-Tom", "en-US-Mark", "en-GB-Oliver", "en-IE-Darragh"
][:8]

EN_FEMALE_PRESETS = [
    "en-US-JennyNeural", "en-US-AriaNeural", "en-GB-SoniaNeural", "en-AU-NatashaNeural",
    "en-US-Jessica", "en-US-Linda", "en-GB-Emma"
][:7]

ZH_PRESETS = [
    "zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-KangkangNeural", "zh-CN-XiaoyouNeural",
    "zh-CN-YunfeiNeural", "zh-CN-YunjianNeural", "zh-CN-YunxiNeural",
    "zh-TW-HsiaoChenNeural", "zh-TW-YunJheNeural", "zh-CN-XiaohanNeural",
    "zh-CN-XiaoyanNeural", "zh-CN-NannanNeural", "zh-CN-MeiNeural",
    "zh-CN-YatingNeural", "zh-CN-YifeiNeural"
][:15]

# Aggregate voices to present in UI for selection by category
VOICE_LIBRARY = {
    "英文男声": EN_MALE_PRESETS,
    "英文女声": EN_FEMALE_PRESETS,
    "中文音色": ZH_PRESETS
}

# TTS generation functions
def save_pyttsx3_wav(text: str, voice_id: Optional[str], rate: int, out_wav: str) -> bool:
    """Save text to wav using pyttsx3; return True if success"""
    if not PYTTSX3_AVAILABLE:
        return False
    try:
        engine = pyttsx3.init()
        if voice_id:
            try:
                engine.setProperty("voice", voice_id)
            except Exception:
                pass
        engine.setProperty("rate", rate)
        engine.save_to_file(text, out_wav)
        engine.runAndWait()
        try:
            engine.stop()
        except:
            pass
        return os.path.exists(out_wav) and os.path.getsize(out_wav) > 0
    except Exception:
        return False

def wav_to_mp3_ffmpeg(wav_path: str, mp3_path: str) -> bool:
    if not check_ffmpeg():
        return False
    cmd = ["ffmpeg", "-y", "-i", wav_path, "-q:a", "4", "-acodec", "libmp3lame", mp3_path]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0
    except Exception:
        return False

def generate_offline_mp3(text: str, voice_id: Optional[str], speed: float, out_mp3: str) -> bool:
    """
    Generate mp3 using pyttsx3 (wav -> mp3). speed is multiplier (0.5-2.0)
    """
    fd, tmpwav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    rate_wpm = int(200 * speed)
    ok = save_pyttsx3_wav(text, voice_id, rate_wpm, tmpwav)
    if not ok:
        safe_remove(tmpwav)
        return False
    ok2 = wav_to_mp3_ffmpeg(tmpwav, out_mp3)
    safe_remove(tmpwav)
    return ok2

# edge-tts async wrapper for saving mp3
async def _edge_save_async(text: str, voice: str, out_path: str, rate_str: str = "+0%"):
    try:
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate_str)
        await communicate.save(out_path)
        return True
    except Exception:
        return False

def generate_edge_mp3(text: str, voice: str, speed: float, out_mp3: str) -> bool:
    if not EDGE_TTS_AVAILABLE:
        return False
    pct = int((speed - 1.0) * 100)
    rate_str = f"{pct:+d}%"
    try:
        # run async function
        return asyncio.run(_edge_save_async(text, voice, out_mp3, rate_str))
    except Exception:
        return False

def generate_tts_segment(text: str, voice_category: str, voice_choice: str, speed: float, engine_pref: str, out_mp3: str) -> bool:
    """
    engine_pref: "离线优先" or "在线优先"
    voice_category: category from VOICE_LIBRARY keys or "local"
    voice_choice: for local engines may be pyttsx3 id
    """
    # Try offline first if preferred
    if engine_pref == "离线优先" and PYTTSX3_AVAILABLE:
        # voice_choice can be id for local voices. For preset edge names, pyttsx3 will likely ignore.
        ok = generate_offline_mp3(text, voice_choice if voice_choice else None, speed, out_mp3)
        if ok:
            return True
    # Try edge if available (voice_choice may be edge name)
    if EDGE_TTS_AVAILABLE:
        # If voice_choice not provided, pick default depending on category
        voice = None
        if voice_choice:
            voice = voice_choice
        else:
            if voice_category in VOICE_LIBRARY and VOICE_LIBRARY[voice_category]:
                voice = VOICE_LIBRARY[voice_category][0]
        if voice:
            ok = generate_edge_mp3(text, voice, speed, out_mp3)
            if ok:
                return True
    # Finally try offline if not tried yet
    if PYTTSX3_AVAILABLE:
        ok = generate_offline_mp3(text, voice_choice if voice_choice else None, speed, out_mp3)
        if ok:
            return True
    return False

# ------------------------
# Rendering: frame generation (PIL)
# ------------------------
def smart_wrap_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """
    Smart wrap that handles mixed English/Chinese: break on spaces for English, or by character for Chinese.
    """
    lines = []
    # If contains spaces, prefer wrapping at spaces
    if " " in text:
        words = text.split(" ")
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            bbox = draw.textbbox((0,0), test, font=font)
            wlen = bbox[2] - bbox[0]
            if wlen <= max_width or cur == "":
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
    else:
        # no spaces: treat as CJK - wrap by characters
        cur = ""
        for ch in text:
            test = cur + ch
            bbox = draw.textbbox((0,0), test, font=font)
            if bbox[2] - bbox[0] <= max_width:
                cur = test
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
    return lines

def render_frame_image(
    en_text: str,
    phonetic: str,
    zh_text: str,
    conf: dict,
    size: Tuple[int,int],
    font_paths: dict
) -> Image.Image:
    """
    Render a single frame image with given texts and style config.
    conf: dict includes background (color or image), style settings for each layer,
          text background panel settings, spacing, paddings, etc.
    font_paths: dict {'main': path, 'phonetic': path, 'chinese': path}
    """
    W, H = size
    # Start with background
    if conf.get("bg_mode") == "image" and conf.get("bg_image_obj") is not None:
        # use uploaded image and adaptively fill
        bg_img = conf["bg_image_obj"].convert("RGBA")
        # Resize to fill while keeping aspect ratio (cover)
        bg_w, bg_h = bg_img.size
        ratio = max(W/bg_w, H/bg_h)
        new_w = int(bg_w*ratio)
        new_h = int(bg_h*ratio)
        bg_img = bg_img.resize((new_w, new_h), Image.LANCZOS)
        # crop center
        x1 = (new_w - W)//2
        y1 = (new_h - H)//2
        bg_crop = bg_img.crop((x1, y1, x1+W, y1+H)).convert("RGB")
        base = bg_crop
    else:
        # solid color
        color = conf.get("bg_color", "#FFFFFF")
        base = Image.new("RGB", (W,H), color)
    draw = ImageDraw.Draw(base)

    # Fonts
    def load_font(path, size_px):
        try:
            if path and os.path.exists(path):
                return ImageFont.truetype(path, size_px)
            elif DEFAULT_FONT_PATH:
                return ImageFont.truetype(DEFAULT_FONT_PATH, size_px)
            else:
                return ImageFont.load_default()
        except Exception:
            try:
                return ImageFont.truetype(DEFAULT_FONT_PATH, size_px)
            except Exception:
                return ImageFont.load_default()

    font_main = load_font(font_paths.get("main"), conf.get("english_size", 80))
    font_ph = load_font(font_paths.get("phonetic"), conf.get("phonetic_size", 60))
    font_cn = load_font(font_paths.get("chinese"), conf.get("chinese_size", 70))

    # Compute text area width
    content_width = int(W * conf.get("text_area_width_ratio", 0.9))
    padding = conf.get("text_padding", 20)
    # Wrap lines
    # create a temporary draw for measuring
    tmp_draw = ImageDraw.Draw(Image.new("RGB",(10,10)))
    en_lines = smart_wrap_text(tmp_draw, en_text, font_main, content_width - 2*padding)
    ph_lines = smart_wrap_text(tmp_draw, phonetic, font_ph, content_width - 2*padding) if phonetic else []
    cn_lines = smart_wrap_text(tmp_draw, zh_text, font_cn, content_width - 2*padding)

    # Compute total height
    line_spacing = conf.get("line_spacing", 10)
    en_h = sum([tmp_draw.textbbox((0,0), l, font=font_main)[3] - tmp_draw.textbbox((0,0), l, font=font_main)[1] + line_spacing for l in en_lines])
    ph_h = sum([tmp_draw.textbbox((0,0), l, font=font_ph)[3] - tmp_draw.textbbox((0,0), l, font=font_ph)[1] + line_spacing for l in ph_lines])
    cn_h = sum([tmp_draw.textbbox((0,0), l, font=font_cn)[3] - tmp_draw.textbbox((0,0), l, font=font_cn)[1] + line_spacing for l in cn_lines])

    total_text_h = en_h + ph_h + cn_h + conf.get("english_phonetic_gap", 10) + conf.get("phonetic_cn_gap", 10)

    # Positioning: center vertically
    start_y = (H - total_text_h) // 2

    # Optional text background plate
    if conf.get("text_bg_enable", False):
        plate_w = int(content_width)
        plate_h = int(total_text_h + 2*padding)
        plate_x = (W - plate_w)//2
        plate_y = start_y - padding
        plate_color = conf.get("text_bg_color", "#000000")
        plate_alpha = int(255 * conf.get("text_bg_alpha", 0.5))
        radius = conf.get("text_bg_radius", 20)
        # build rounded rectangle with alpha
        plate = Image.new("RGBA", (plate_w, plate_h), (0,0,0,0))
        plate_draw = ImageDraw.Draw(plate)
        # draw rounded rect
        rect_color = hex_to_rgb(plate_color) + (plate_alpha,)
        round_rect(plate_draw, [0,0,plate_w,plate_h], radius, fill=rect_color)
        base = base.convert("RGBA")
        base.alpha_composite(plate, dest=(plate_x, plate_y))
        base = base.convert("RGB")
        draw = ImageDraw.Draw(base)

    # Draw english lines
    cur_y = start_y
    for line in en_lines:
        bbox = draw.textbbox((0,0), line, font=font_main)
        w = bbox[2] - bbox[0]
        x = (W - w)//2
        draw.text((x, cur_y), line, font=font_main, fill=conf.get("english_color", "#000000"))
        cur_y += bbox[3] - bbox[1] + line_spacing

    cur_y += conf.get("english_phonetic_gap", 10)
    for line in ph_lines:
        bbox = draw.textbbox((0,0), line, font=font_ph)
        w = bbox[2] - bbox[0]
        x = (W - w)//2
        draw.text((x, cur_y), line, font=font_ph, fill=conf.get("phonetic_color", "#666666"))
        cur_y += bbox[3] - bbox[1] + line_spacing

    cur_y += conf.get("phonetic_cn_gap", 10)
    for line in cn_lines:
        bbox = draw.textbbox((0,0), line, font=font_cn)
        w = bbox[2] - bbox[0]
        x = (W - w)//2
        draw.text((x, cur_y), line, font=font_cn, fill=conf.get("chinese_color", "#222222"))
        cur_y += bbox[3] - bbox[1] + line_spacing

    return base

# Helper: rounded rectangle draw
def round_rect(draw: ImageDraw.Draw, box, radius, fill):
    x1,y1,x2,y2 = box
    draw.rounded_rectangle(box, radius=radius, fill=fill)

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    lv = len(hex_color)
    if lv == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    elif lv == 3:
        return tuple(int(hex_color[i]*2, 16) for i in range(3))
    else:
        return (0,0,0)

# ------------------------
# Video generation pipeline
# ------------------------
def generate_video_from_df(
    df: pd.DataFrame,
    selected_rows: List[int],
    style_conf: dict,
    audio_conf_list: List[dict],
    video_params: dict,
    font_paths: dict,
    progress_callback=None
) -> Optional[str]:
    """
    Generate video for selected rows.
    audio_conf_list: for each of 4 segments per row, dict with fields:
        {'lang': 'EN','category': '英文男声','voice': 'name','speed':1.0,'pause':0.5}
    video_params: {'resolution':(w,h),'fps':int,'duration_per_segment':float}
    """
    tmp_root = tempfile.mkdtemp(prefix="tts_video_")
    try:
        W,H = video_params['resolution']
        fps = video_params.get('fps', 12)
        seg_dur = video_params.get('duration_per_segment', 3.0)
        frames_per_segment = max(1, int(math.ceil(seg_dur * fps)))
        # aggregate audio files per row
        total_steps = len(selected_rows) * 4 + len(selected_rows) * 3 + 5  # rough steps for progress
        step = 0

        frame_files = []
        audio_files = []

        for idx_i, row_idx in enumerate(selected_rows):
            row = df.iloc[row_idx]
            en = str(row.get("英语",""))
            ph = str(row.get("音标",""))
            cn = str(row.get("中文",""))

            # For each of 4 audio segments, build text to speak according to audio_conf_list
            # Segment mapping example: [Segment1: en], [Segment2: en (alt)], [Segment3: zh], [Segment4: en]
            seg_audio_paths = []
            for seg_i, aconf in enumerate(audio_conf_list):
                text_to_speak = ""
                if aconf.get('content') == '英语':
                    text_to_speak = en
                elif aconf.get('content') == '音标':
                    text_to_speak = ph if ph else en
                elif aconf.get('content') == '中文':
                    text_to_speak = cn
                else:
                    text_to_speak = en

                # create unique mp3 path
                mp3_path = os.path.join(tmp_root, f"row{row_idx}_seg{seg_i}.mp3")
                engine_pref = aconf.get('engine_pref','离线优先')
                voice_choice = aconf.get('voice_choice')
                voice_category = aconf.get('voice_category')
                speed = float(aconf.get('speed',1.0))
                # generate (try parallel for edge voices)
                ok = generate_tts_segment(text_to_speak, voice_category, voice_choice, speed, engine_pref, mp3_path)
                if not ok:
                    # if fail, create silent audio placeholder of seg_dur length
                    create_silent_mp3(mp3_path, seg_dur)
                # add pause if set
                pause = float(aconf.get('pause',0.0))
                if pause > 0:
                    # append a silent mp3 for pause
                    pause_path = os.path.join(tmp_root, f"row{row_idx}_seg{seg_i}_pause.mp3")
                    create_silent_mp3(pause_path, pause)
                    seg_audio_paths.append(mp3_path)
                    seg_audio_paths.append(pause_path)
                else:
                    seg_audio_paths.append(mp3_path)
                step += 1
                if progress_callback:
                    progress_callback(min(1.0, step/total_steps))

            # merge segment audios into one audio for this row
            row_audio = os.path.join(tmp_root, f"row{row_idx}_audio.mp3")
            try:
                concat_audios_ffmpeg(seg_audio_paths, row_audio)
            except Exception:
                # fallback: try simple copy of first
                if seg_audio_paths:
                    shutil.copy(seg_audio_paths[0], row_audio)
            audio_files.append(row_audio)

            # render frames for this row: create frames_per_segment frames per segment but we can duplicate same frame
            # create single frame image and then duplicate
            frame_img = render_frame_image(en, ph, cn, style_conf, (W,H), font_paths)
            # Save frames as images
            frames_for_row = []
            for f_i in range(frames_per_segment * 4):  # 4 segments * frames per segment
                fname = os.path.join(tmp_root, f"row{row_idx}_frame_{f_i:04d}.png")
                frame_img.save(fname)
                frames_for_row.append(fname)
            frame_files.extend(frames_for_row)
            step += 1
            if progress_callback:
                progress_callback(min(1.0, step/total_steps))

        # Now create video from frames (ffmpeg)
        # To avoid writing huge temp videos, we create an image sequence video then add concatenated audio
        video_no_audio = os.path.join(tmp_root, "video_no_audio.mp4")
        try:
            # imageio can write video from image sequence
            images = [imageio.imread(p) for p in frame_files]
            # write as mp4
            imageio.mimsave(video_no_audio, images, fps=fps)
        except Exception as e:
            # fallback: use ffmpeg to create video from images list
            # Create list file
            list_txt = os.path.join(tmp_root, "imgs.txt")
            with open(list_txt, "w", encoding="utf-8") as f:
                for p in frame_files:
                    f.write(f"file '{p}'\n")
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_txt, "-vsync", "vfr", "-pix_fmt", "yuv420p", "-r", str(fps), video_no_audio]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Merge all row audios into one big audio
        final_audio = os.path.join(tmp_root, "final_audio.mp3")
        concat_audios_ffmpeg(audio_files, final_audio)
        # Combine video_no_audio + final_audio into final video
        final_video = os.path.join(tmp_root, "final_output.mp4")
        merge_video_audio(video_no_audio, final_audio, final_video)
        if progress_callback:
            progress_callback(1.0)
        return final_video
    except Exception as e:
        traceback.print_exc()
        return None
    finally:
        # Note: we don't immediately delete tmp_root so user can download; caller should clean up if needed
        pass

# FFmpeg helpers
def concat_audios_ffmpeg(audio_paths: List[str], out_mp3: str):
    if not audio_paths:
        raise ValueError("audio_paths empty")
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg not found")
    # create list file
    listfile = out_mp3 + "_list.txt"
    with open(listfile, "w", encoding="utf-8") as f:
        for p in audio_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out_mp3]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    safe_remove(listfile)

def create_silent_mp3(out_path: str, duration_s: float):
    # Create silent wav using ffmpeg then convert to mp3
    if not check_ffmpeg():
        # fallback: write tiny file
        with open(out_path, "wb") as f:
            f.write(b"")
        return
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono", "-t", str(duration_s), "-q:a", "9", out_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def merge_video_audio(video_path: str, audio_path: str, out_path: str):
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg not found")
    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path, "-c:v", "copy", "-c:a", "aac", "-shortest", out_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ------------------------
# Streamlit UI
# ------------------------
st.set_page_config(page_title="旅行英语视频生成器 - 离线优先", layout="wide")
st.title("🎬 旅行英语视频生成器（离线优先 + 在线回退）")

col_l, col_r = st.columns([2, 1])

with col_l:
    st.header("1. 数据管理")
    uploaded = st.file_uploader("上传 Excel 文件（.xlsx / .xls，必须列名：英语、中文、音标（可选））", type=["xlsx","xls"])
    df = None
    df_errors = []
    if uploaded is not None:
        df, df_errors = validate_and_load_excel(uploaded)
        if df is None:
            for e in df_errors:
                st.error(e)
        else:
            st.success(f"文件解析成功，共 {len(df)} 行。")
            if df_errors:
                for e in df_errors:
                    st.warning(e)

    if df is not None:
        st.subheader("实时数据预览（前 10 行）")
        st.dataframe(df.head(10))

    st.markdown("---")
    st.header("2. 视频样式定制")

    # Background mode
    bg_mode = st.selectbox("背景类型", ["纯色背景","图片背景"])
    style_conf = {}
    if bg_mode == "纯色背景":
        bg_color = st.color_picker("选择背景颜色", "#ffffff")
        style_conf["bg_mode"] = "color"
        style_conf["bg_color"] = bg_color
        style_conf["bg_image_obj"] = None
    else:
        uploaded_bg = st.file_uploader("上传背景图片（JPG/PNG）", type=["jpg","jpeg","png"], key="bgimg")
        style_conf["bg_mode"] = "image"
        style_conf["bg_color"] = "#ffffff"
        if uploaded_bg:
            try:
                bg_img = Image.open(uploaded_bg)
                style_conf["bg_image_obj"] = bg_img.copy()
                st.image(bg_img, caption="背景预览", use_column_width=True)
            except Exception:
                st.error("背景图片读取失败")
                style_conf["bg_image_obj"] = None
        else:
            style_conf["bg_image_obj"] = None

    st.subheader("文字样式系统（英语 / 音标 / 中文）")
    # fonts (we allow custom upload of font files for phonetic if user wants)
    main_font_size = st.slider("英语字号", 40, 160, 80)
    en_color = st.color_picker("英语颜色", "#000000")
    en_bold = st.checkbox("英语加粗", value=False)
    phonetic_font_path = None
    phonetic_font_file = st.file_uploader("上传音标专用字体（可选 .ttf）", type=["ttf","otf"], key="phonetic_font")
    if phonetic_font_file:
        # save to temp
        fp = os.path.join(tempfile.gettempdir(), f"phonetic_{int(time.time())}.ttf")
        with open(fp, "wb") as f:
            f.write(phonetic_font_file.read())
        phonetic_font_path = fp

    phonetic_size = st.slider("音标字号", 24, 120, 56)
    ph_color = st.color_picker("音标颜色", "#666666")
    chinese_size = st.slider("中文字号", 24, 140, 68)
    cn_color = st.color_picker("中文颜色", "#222222")
    cn_bold = st.checkbox("中文加粗", value=False)

    # text background plate
    st.subheader("文字背景板（可选）")
    text_bg_enable = st.checkbox("启用文字背景板", value=False)
    text_bg_color = st.color_picker("背景板颜色", "#000000")
    text_bg_alpha = st.slider("背景板透明度", 0.0, 1.0, 0.35)
    text_bg_radius = st.slider("背景板圆角", 0, 100, 12)
    text_bg_padding = st.slider("文字背景板内边距", 0, 200, 20)
    text_area_width_ratio = st.slider("文本区域宽度比例", 0.3, 1.0, 0.85)

    # spacing
    st.subheader("间距与换行")
    english_phonetic_gap = st.slider("英语 - 音标 间距(px)", 0, 200, 10)
    phonetic_cn_gap = st.slider("音标 - 中文 间距(px)", 0, 200, 10)
    line_spacing = st.slider("行间距(px)", 0, 50, 6)

    # Packing style_conf
    style_conf.update({
        "english_size": main_font_size,
        "english_color": en_color,
        "english_bold": en_bold,
        "phonetic_size": phonetic_size,
        "phonetic_color": ph_color,
        "phonetic_font_path": phonetic_font_path,
        "chinese_size": chinese_size,
        "chinese_color": cn_color,
        "chinese_bold": cn_bold,
        "text_bg_enable": text_bg_enable,
        "text_bg_color": text_bg_color,
        "text_bg_alpha": text_bg_alpha,
        "text_bg_radius": text_bg_radius,
        "text_padding": text_bg_padding,
        "text_area_width_ratio": text_area_width_ratio,
        "english_phonetic_gap": english_phonetic_gap,
        "phonetic_cn_gap": phonetic_cn_gap,
        "line_spacing": line_spacing,
        "bg_mode": "image" if bg_mode == "图片背景" else "color"
    })

with col_r:
    st.header("3. 多音色音频系统")
    st.markdown("每条数据支持 4 段音频串联（可混合不同音色）。")
    engine_pref = st.selectbox("引擎偏好", ["离线优先", "在线优先"])
    st.write("语音库（选择示例音色或使用系统本地音色）")
    local_voices = list_local_voices()
    local_voice_names = [v["name"] for v in local_voices] if local_voices else []
    st.write(f"系统本地语音数量: {len(local_voice_names)}")
    # Build UI for 4 segments
    audio_segments = []
    for seg_i in range(4):
        st.markdown(f"**段 {seg_i+1} 设置**")
        col_a, col_b = st.columns([1,1])
        with col_a:
            content = st.selectbox(f"段{seg_i+1} 内容", ["英语","音标","中文"], key=f"content_{seg_i}")
        with col_b:
            category = st.selectbox(f"段{seg_i+1} 音色库", ["英文男声","英文女声","中文音色","系统本地"], index=0, key=f"cat_{seg_i}")
        voice_choice = None
        voice_category = category
        if category == "系统本地":
            if local_voice_names:
                voice_choice = st.selectbox(f"段{seg_i+1} 本地语音选择", ["(默认)"]+local_voice_names, key=f"localvoice_{seg_i}")
                if voice_choice != "(默认)":
                    # map to actual id if possible
                    for v in local_voices:
                        if v["name"] == voice_choice:
                            voice_choice = v.get("id") or v.get("name")
                            break
            else:
                st.info("未检测到本地语音，系统将回退至在线语音。")
                voice_choice = None
                voice_category = "英文女声"
        else:
            # present presets
            presets = VOICE_LIBRARY.get(category, [])
            if presets:
                voice_choice = st.selectbox(f"段{seg_i+1} 具体音色", ["(默认)"] + presets, key=f"preset_{seg_i}")
                if voice_choice == "(默认)":
                    voice_choice = None

        speed = st.slider(f"段{seg_i+1} 语速 (0.5x-2.0x)", 0.5, 2.0, 1.0, 0.1, key=f"speed_{seg_i}")
        pause = st.slider(f"段{seg_i+1} 停顿 (秒)", 0.0, 3.0, 0.3, 0.1, key=f"pause_{seg_i}")
        audio_segments.append({
            "content": content,
            "voice_category": voice_category,
            "voice_choice": voice_choice,
            "speed": speed,
            "pause": pause,
            "engine_pref": engine_pref
        })

    st.markdown("---")
    st.subheader("试听功能")
    # allow preview of each segment with sample text
    sample_text = st.text_input("试听示例文本（若空则使用行文本）", value="Hello, this is a sample.")
    seg_preview_col = st.columns(4)
    for i in range(4):
        if seg_preview_col[i].button(f"试听段 {i+1}", key=f"preview_{i}"):
            conf = audio_segments[i]
            # use sample_text
            tmp_mp3 = os.path.join(tempfile.gettempdir(), f"preview_seg_{i}_{int(time.time())}.mp3")
            ok = generate_tts_segment(sample_text, conf['voice_category'], conf['voice_choice'], conf['speed'], conf['engine_pref'], tmp_mp3)
            if ok and os.path.exists(tmp_mp3):
                audio_bytes = open(tmp_mp3, "rb").read()
                st.audio(audio_bytes, format="audio/mp3")
                safe_remove(tmp_mp3)
            else:
                st.error("试听失败：请确认网络/本地语音是否可用，或切换引擎偏好。")

    st.markdown("---")
    st.subheader("4. 视频参数配置")
    res_choice = st.selectbox("分辨率", list(DEFAULT_RESOLUTIONS.keys()), index=3)
    resolution = DEFAULT_RESOLUTIONS[res_choice]
    fps = st.slider("帧率 (fps)", 8, 30, 12)
    duration_per_segment = st.slider("每段时长（秒）", 2.0, 8.0, 3.0, 0.5)
    st.markdown("进阶选项")
    max_rows = st.number_input("最多生成行数（为性能保守，建议 <= 50）", min_value=1, max_value=500, value=MAX_ROWS_SUGGEST)

# bottom area for Preview & Generate
st.markdown("---")
st.header("5. 预览与生成")

if df is None:
    st.info("请先上传并验证 Excel 数据，然后在右侧设置样式与音频参数。")
else:
    # Row selection for preview / generation
    total_rows = len(df)
    chosen_rows = st.multiselect("选择用于生成的视频行（支持多选；生成顺序即选择顺序）",
                                 options=list(range(total_rows)),
                                 format_func=lambda x: f"第 {x+1} 行: {str(df.iloc[x]['英语'])[:40]}",
                                 default=list(range(min(5, total_rows))))
    if len(chosen_rows) == 0:
        st.warning("尚未选择任何行用于生成。")

    # Single-frame preview
    st.subheader("单帧实时预览（所见即所得）")
    preview_row_idx = st.selectbox("选择预览行（仅影响画面预览，不会生成音频）", options=chosen_rows if chosen_rows else [0])
    if preview_row_idx is None and chosen_rows:
        preview_row_idx = chosen_rows[0]
    preview_row = df.iloc[preview_row_idx]
    preview_img = render_frame_image(
        str(preview_row.get("英语","")),
        str(preview_row.get("音标","")),
        str(preview_row.get("中文","")),
        style_conf,
        DEFAULT_RESOLUTIONS[res_choice],
        {"main": None, "phonetic": style_conf.get("phonetic_font_path"), "chinese": None}
    )
    st.image(preview_img, caption="单帧预览 (所见即所得)", use_column_width=True)

    # Generate button
    gen_col1, gen_col2 = st.columns([1,1])
    with gen_col1:
        if st.button("开始生成视频", type="primary"):
            if not check_ffmpeg():
                st.error("服务器未安装 ffmpeg，无法生成视频。请先安装 ffmpeg。")
            else:
                if len(chosen_rows) == 0:
                    st.error("请至少选择一行进行生成。")
                else:
                    if len(chosen_rows) > max_rows:
                        st.warning(f"选择的行数 ({len(chosen_rows)}) 超过设置的最大行数 ({max_rows})。请降低生成数量以免超时/内存问题。")
                    # Run generation in blocking (long) operation, with progress
                    progress_bar = st.progress(0.0)
                    status_text = st.empty()

                    def progress_cb(p):
                        try:
                            progress_bar.progress(p)
                            status_text.text(f"生成进度：{int(p*100)}%")
                        except Exception:
                            pass

                    video_params = {
                        "resolution": resolution,
                        "fps": fps,
                        "duration_per_segment": duration_per_segment
                    }

                    # Run generation (synchronous)
                    status_text.text("开始生成音频与帧，请耐心等待...")
                    tmp_video = generate_video_from_df(df, chosen_rows, style_conf, audio_segments, video_params,
                                                       {"main": None, "phonetic": style_conf.get("phonetic_font_path"), "chinese": None},
                                                       progress_callback=progress_cb)
                    if tmp_video and os.path.exists(tmp_video):
                        status_text.success("视频生成完成！准备下载...")
                        with open(tmp_video, "rb") as f:
                            video_bytes = f.read()
                        st.video(video_bytes)
                        st.download_button("📥 下载 MP4 视频", video_bytes, file_name="travel_english_video.mp4")
                        # cleanup
                        try:
                            safe_remove(os.path.dirname(tmp_video))
                        except Exception:
                            pass
                    else:
                        status_text.error("生成失败，请查看日志或检查 ffmpeg / TTS 引擎是否可用。")

    with gen_col2:
        if st.button("导出合并音频 (仅音频)"):
            # similar pipeline to merge audios only
            st.info("生成并合并音频...")
            tmpd = tempfile.mkdtemp(prefix="audio_merge_")
            audio_paths = []
            for ridx in chosen_rows:
                row = df.iloc[ridx]
                en = str(row.get("英语",""))
                ph = str(row.get("音标",""))
                cn = str(row.get("中文",""))
                # generate segments
                seg_paths = []
                for si, aconf in enumerate(audio_segments):
                    text = en if aconf["content"] == "英语" else (ph if aconf["content"]=="音标" else cn)
                    mp3p = os.path.join(tmpd, f"r{ridx}_s{si}.mp3")
                    ok = generate_tts_segment(text, aconf["voice_category"], aconf["voice_choice"], aconf["speed"], aconf["engine_pref"], mp3p)
                    if not ok:
                        create_silent_mp3(mp3p, duration_s=1.0)
                    seg_paths.append(mp3p)
                    # pause:
                    if aconf.get("pause",0)>0:
                        pausep = os.path.join(tmpd, f"r{ridx}_s{si}_pause.mp3")
                        create_silent_mp3(pausep, aconf.get("pause",0))
                        seg_paths.append(pausep)
                # merge segments for this row
                row_audio = os.path.join(tmpd, f"row{ridx}_merged.mp3")
                concat_audios_ffmpeg(seg_paths, row_audio)
                audio_paths.append(row_audio)
            final_audio = os.path.join(tmpd, "all_rows_merged.mp3")
            concat_audios_ffmpeg(audio_paths, final_audio)
            with open(final_audio, "rb") as f:
                st.download_button("📥 下载合并音频 (MP3)", f, file_name="merged_audio.mp3")
            # cleanup
            safe_remove(tmpd)
            st.success("音频合并并提供下载。")

st.markdown("---")
st.info("提示：\n- pyttsx3 为离线 TTS，质量随操作系统而不同。edge-tts 为在线高质量回退。\n- 请确保服务器安装 ffmpeg。若部署到 Railway/Streamlit Cloud，请在部署设置中安装 ffmpeg。")

# EOF
