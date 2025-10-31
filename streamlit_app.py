import streamlit as st
import pandas as pd
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import imageio.v2 as imageio
import tempfile
import shutil
from pydub import AudioSegment
import subprocess
import traceback
import asyncio

# 检查ffmpeg是否可用
def check_ffmpeg():
    ffmpeg_path = shutil.which('ffmpeg')  # 检查ffmpeg是否在PATH中
    if not ffmpeg_path:
        st.warning("未检测到 ffmpeg。请安装 ffmpeg 并确保 PATH 配置正确。")
    else:
        st.success(f"检测到 ffmpeg：{ffmpeg_path}")
    return ffmpeg_path

# 检查ffmpeg
check_ffmpeg()  # 在应用启动时检查ffmpeg

# edge-tts 用于多音色 TTS
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

# 页面配置
st.set_page_config(page_title="旅行英语视频生成器", page_icon="🎬", layout="wide")

# 会话状态
if 'bg_image' not in st.session_state:
    st.session_state.bg_image = None
if 'audio_available' not in st.session_state:
    st.session_state.audio_available = EDGE_TTS_AVAILABLE

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

def get_font(size):
    try:
        candidates = [
            "SimHei", "msyh.ttc", "NotoSansCJK-Regular.ttc",
            "WenQuanYi Micro Hei", "Arial Unicode MS", "DejaVuSans.ttf"
        ]
        for f in candidates:
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

def create_frame(english, chinese, phonetic, width=1280, height=720,
                 bg_color=(0,0,0), bg_image=None,
                 eng_color=(255,255,255), chn_color=(0,255,255), pho_color=(255,255,0),
                 eng_size=60, chn_size=50, pho_size=40):
    """
    创建一帧图片
    顺序：英语（上） -> 音标（中） -> 中文（下）
    """
    if bg_image:
        try:
            img = ImageOps.fit(bg_image.convert('RGB'), (width, height), Image.Resampling.LANCZOS)
        except Exception:
            img = Image.new('RGB', (width, height), bg_color)
    else:
        img = Image.new('RGB', (width, height), bg_color)

    draw = ImageDraw.Draw(img)
    eng_font = get_font(eng_size)
    chn_font = get_font(chn_size)
    pho_font = get_font(pho_size)

    eng_lines = wrap_text(english, 30)
    chn_lines = wrap_text(chinese, 15)
    pho_lines = wrap_text(phonetic, 35) if phonetic else []

    line_spacing = 10
    total_height = 0

    # 英语高度
    for line in eng_lines:
        _, _, _, h = draw.textbbox((0,0), line, font=eng_font)
        total_height += h
    total_height += line_spacing * (len(eng_lines)-1)

    # 音标高度
    if pho_lines:
        total_height += 20
        for line in pho_lines:
            _, _, _, h = draw.textbbox((0,0), line, font=pho_font)
            total_height += h
        total_height += line_spacing * (len(pho_lines)-1)

    # 中文高度
    if chn_lines:
        total_height += 20
        for line in chn_lines:
            _, _, _, h = draw.textbbox((0,0), line, font=chn_font)
            total_height += h
        total_height += line_spacing * (len(chn_lines)-1)

    y = (height - total_height)//2

    # 绘制英语
    for line in eng_lines:
        w, h = draw.textbbox((0,0), line, font=eng_font)[2:]
        x = (width - w)//2
        draw.text((x+1, y+1), line, font=eng_font, fill=(0,0,0,128))
        draw.text((x, y), line, font=eng_font, fill=eng_color)
        y += h + line_spacing

    # 音标（在英语下）
    if pho_lines:
        y += 10
        for line in pho_lines:
            w, h = draw.textbbox((0,0), line, font=pho_font)[2:]
            x = (width - w)//2
            draw.text((x+1, y+1), line, font=pho_font, fill=(0,0,0,128))
            draw.text((x, y), line, font=pho_font, fill=pho_color)
            y += h + line_spacing

    # 中文（在音标下）
    if chn_lines:
        y += 10
        for line in chn_lines:
            w, h = draw.textbbox((0,0), line, font=chn_font)[2:]
            x = (width - w)//2
            draw.text((x+1, y+1), line, font=chn_font, fill=(0,0,0,128))
            draw.text((x, y), line, font=chn_font, fill=chn_color)
            y += h + line_spacing

    return img

# -----------------------
# Edge TTS helpers
# -----------------------
VOICE_OPTIONS = {
    "English - Female (US) - aria_us_female": "en-US-AriaNeural",
    "English - Female (US) - Jenny": "en-US-JennyNeural",
    "English - Male (US) - Guy": "en-US-GuyNeural",
    "English - Female (UK) - Kate": "en-GB-LibbyNeural",
    "Chinese - Female (CN) - Xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "Chinese - Male (CN) - Yunfeng": "zh-CN-YunfengNeural"
}

async def _edge_tts_save(ssml_text: str, voice_name: str, out_path: str):
    communicator = edge_tts.Communicate(ssml=ssml_text, voice=voice_name)
    await communicator.save(out_path)

def generate_edge_audio(text, voice, speed=1.0, out_path=None):
    if not EDGE_TTS_AVAILABLE:
        return None
    pct = int((speed - 1.0) * 100)
    pct_str = f"{pct:+d}%"
    ssml = f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>" \
           f"<voice name='{voice}'><prosody rate='{pct_str}'>{escape_xml(text)}</prosody></voice></speak>"
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix='.mp3')
        os.close(fd)
    try:
        asyncio.run(_edge_tts_save(ssml, voice, out_path))
        return out_path
    except Exception as e:
        st.warning(f"edge-tts 生成音频失败: {e}")
        return None

def escape_xml(s: str):
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace("'", "&apos;")
             .replace('"', "&quot;"))

# -----------------------
# 音频合并 / 视频合并
# -----------------------
def merge_audio_files(audio_paths, target_duration):
    combined = AudioSegment.empty()
    for p in audio_paths:
        if not p:
            combined += AudioSegment.silent(duration=int(target_duration*1000))
            continue
        try:
            audio = AudioSegment.from_file(p)
            if len(audio) > target_duration*1000:
                audio = audio[:int(target_duration*1000)]
            else:
                audio = audio + AudioSegment.silent(duration=int(target_duration*1000) - len(audio))
            combined += audio
            try:
                os.remove(p)
            except:
                pass
        except Exception as e:
            st.warning(f"处理音频片段失败: {e}")
            combined += AudioSegment.silent(duration=int(target_duration*1000))
    return combined

def merge_video_audio(video_path, audio_path, output_path):
    if not check_ffmpeg():
        st.error("未检测到 ffmpeg，无法合并音频。")
        return None
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-strict", "experimental",
        output_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            st.error(f"ffmpeg 合并失败: {res.stderr}")
            return None
        return output_path
    except Exception as e:
        st.error(f"调用 ffmpeg 失败: {e}")
        return None

# -----------------------
# UI 与主流程
# -----------------------
st.title("🎬 旅行英语视频生成器（文字 + 背景图，支持多音色）")
st.markdown("上传 Excel（列名：英语、中文、音标），自定义样式与音色，生成视频并下载。")

# edge-tts 状态
if EDGE_TTS_AVAILABLE:
    st.success("edge-tts 已安装：支持多音色 TTS。")
else:
    st.warning("未检测到 edge-tts：多音色语音功能不可用。请运行 `pip install edge-tts` 并确保网络可用。")

# 检查 ffmpeg
check_ffmpeg()  # 调用ffmpeg检测

# 上传 Excel
st.header("1. 上传 Excel 文件")
uploaded = st.file_uploader("选择 Excel 文件（必须包含列：英语、中文、音标）", type=["xlsx", "xls"])
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
    st.dataframe(df, height=220)

    # 设置面板
    st.header("2. 自定义设置")
    col_bg, col_txt = st.columns([1,2])

    with col_bg:
        bg_type = st.radio("背景类型", ["纯色","图片"], index=1)
        if bg_type == "纯色":
            bg_hex = st.color_picker("背景颜色", "#000000")
            bg_color = tuple(int(bg_hex[i:i+2],16) for i in (1,3,5))
            st.session_state.bg_image = None
        else:
            bg_file = st.file_uploader("上传背景图片 (jpg/png)", type=["jpg","jpeg","png"], key="bg_img")
            if bg_file:
                try:
                    st.session_state.bg_image = Image.open(bg_file)
                    st.image(st.session_state.bg_image, caption="背景预览", use_column_width=False, width=300)
                except Exception as e:
                    st.error(f"打开背景图片失败：{e}")
                    st.session_state.bg_image = None
            bg_color = (0,0,0)

    with col_txt:
        st.subheader("文字样式（英语 / 音标 / 中文）")
        c1, c2, c3 = st.columns(3)
        with c1:
            eng_color = st.color_picker("英语颜色", "#FFFFFF")
            eng_color = tuple(int(eng_color[i:i+2],16) for i in (1,3,5))
            eng_size = st.slider("英语字号", 20, 100, 60)
        with c2:
            pho_color = st.color_picker("音标颜色", "#FFFF00")
            pho_color = tuple(int(pho_color[i:i+2],16) for i in (1,3,5))
            pho_size = st.slider("音标字号", 16, 80, 40)
        with c3:
            chn_color = st.color_picker("中文颜色", "#00FFFF")
            chn_color = tuple(int(chn_color[i:i+2],16) for i in (1,3,5))
            chn_size = st.slider("中文字号", 20, 100, 50)

    st.subheader("音频设置（多音色）")
    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        tts_lang = st.selectbox("语音语言", ["英语","中文"])
    with col_a2:
        # 选择 voice（从 VOICE_OPTIONS 中筛选语言匹配项）
        voice_choices = {k:v for k,v in VOICE_OPTIONS.items() if (("English" in k and tts_lang=="英语") or ("Chinese" in k and tts_lang=="中文") or (tts_lang=="英语" and "English" in k) or (tts_lang=="中文" and "Chinese" in k))}
        voice_label = st.selectbox("音色 (示例)", list(voice_choices.keys()))
        voice_name = voice_choices[voice_label]
    with col_a3:
        tts_speed = st.slider("语速 (0.5-2.0)", 0.5, 2.0, 1.0)

    st.subheader("视频参数")
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        per_duration = st.slider("每句时长（秒）", 2, 8, 4)
        fps = st.slider("帧率", 8, 30, 20)
    with col_v2:
        width = st.selectbox("分辨率宽度", [640, 960, 1280], index=2)
        height = int(width * 9 / 16)

    # 预览单行
    st.header("3. 预览单行")
    if not df.empty:
        idx = st.slider("选择要预览的行", 0, len(df)-1, 0)
        row = df.iloc[idx]
        preview_img = create_frame(
            english=str(row['英语']),
            chinese=str(row['中文']),
            phonetic=str(row['音标']) if pd.notna(row['音标']) else "",
            width=width, height=height,
            bg_color=bg_color, bg_image=st.session_state.bg_image,
            eng_color=eng_color, chn_color=chn_color, pho_color=pho_color,
            eng_size=eng_size, chn_size=chn_size, pho_size=pho_size
        )
        st.image(preview_img, caption="帧预览", use_column_width=False, width=width//2)

    # 生成按钮
    st.header("4. 生成视频")
    if st.button("开始生成视频"):
        with st.spinner("正在生成 — 会为每行生成帧和音频，请耐心等待（建议先用少量行测试）"):
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    frames = []
                    audio_paths = []
                    total_frames = len(df) * per_duration * fps
                    progress = st.progress(0)
                    current = 0

                    # 逐行生成
                    for i, row in df.iterrows():
                        eng = str(row['英语'])
                        chn = str(row['中文'])
                        pho = str(row['音标']) if pd.notna(row['音标']) else ""

                        # 创建一张帧图
                        frame_img = create_frame(
                            english=eng, chinese=chn, phonetic=pho,
                            width=width, height=height,
                            bg_color=bg_color, bg_image=st.session_state.bg_image,
                            eng_color=eng_color, chn_color=chn_color, pho_color=pho_color,
                            eng_size=eng_size, chn_size=chn_size, pho_size=pho_size
                        )
                        # 重复帧以达到时间
                        for _ in range(per_duration * fps):
                            frames.append(np.array(frame_img.convert('RGB')))

                        # 生成音频（edge-tts）
                        audio_file = None
                        if EDGE_TTS_AVAILABLE:
                            # 把要读的文本按语言选择不同字段（优先英语，如果想读中文可改）
                            speak_text = eng if tts_lang == "英语" else chn
                            audio_file = generate_edge_audio(speak_text, voice_name, speed=tts_speed)
                        audio_paths.append(audio_file)

                        current += per_duration * fps
                        progress.progress(min(current/total_frames, 1.0))

                    # 保存无声视频（临时）
                    video_no_audio = os.path.join(tmpdir, "video_no_audio.mp4")
                    imageio.mimsave(video_no_audio, frames, fps=fps)

                    final_video = video_no_audio
                    # 若有音频且 ffmpeg 可用，则合并
                    if any(p for p in audio_paths if p is not None) and check_ffmpeg():
                        combined = merge_audio_files(audio_paths, per_duration)
                        audio_out = os.path.join(tmpdir, "combined.mp3")
                        combined.export(audio_out, format="mp3")
                        video_with_audio = os.path.join(tmpdir, "video_with_audio.mp4")
                        merged = merge_video_audio(video_no_audio, audio_out, video_with_audio)
                        if merged:
                            final_video = merged

                    # 读取视频并展示与下载
                    with open(final_video, "rb") as f:
                        video_bytes = f.read()

                    st.success("视频生成完成！")
                    st.video(video_bytes)
                    st.download_button("下载视频", data=video_bytes, file_name="travel_english_video.mp4", mime="video/mp4")
                    progress.progress(1.0)

            except Exception as e:
                st.error(f"生成失败: {e}")
                st.text(traceback.format_exc())
