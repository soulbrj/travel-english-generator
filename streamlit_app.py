import streamlit as st
import pandas as pd
import numpy as np
import os
import tempfile
import subprocess
import shutil
import traceback
import asyncio
import imageio.v2 as imageio
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests
import time

# -------------------- 页面设置 --------------------
st.set_page_config(page_title="旅行英语视频生成器（模式B离线版）", page_icon="🎬", layout="wide")

st.markdown("""
<style>
    .main-header {
        font-size: 2.3rem;
        font-weight: 700;
        color: #334155;
        text-align: center;
        margin-bottom: 1rem;
    }
    .stProgress > div > div > div > div {
        background-color: #6366F1;
    }
    div[data-testid="stFileUploader"] section {
        background-color: #F8FAFC;
        border-radius: 10px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-header'>🎬 旅行英语视频生成器 — 离线模式B（每行独立拼接）</div>", unsafe_allow_html=True)
st.info("💡 上传 Excel（包含列：英语、中文、音标），并上传离线音频文件，如 1-1.mp3、1-2.mp3、1-3.mp3、1-4.mp3。")

# -------------------- 加载 ffmpeg --------------------
def check_ffmpeg():
    return shutil.which("ffmpeg") is not None

# -------------------- 加载 edge-tts（用于试听） --------------------
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

# -------------------- 工具函数 --------------------
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


def get_font(size, bold=False):
    choices = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "arial.ttf"
    ]
    for f in choices:
        try:
            return ImageFont.truetype(f, size)
        except:
            continue
    return ImageFont.load_default()


def create_frame(english, chinese, phonetic, width=1920, height=1080,
                 bg_color=(10,10,10), bg_image=None,
                 eng_color=(255,255,255), chn_color=(180,220,255), pho_color=(255,240,120),
                 eng_size=80, chn_size=60, pho_size=50,
                 text_bg_enabled=True, text_bg_color=(255,255,255,180), text_bg_padding=20,
                 text_bg_radius=30, bold_text=True):

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

    lines = wrap_text(english, 40)
    total_height = sum(draw.textbbox((0,0), line, font=eng_font)[3] for line in lines)
    total_height += 150

    y = (height - total_height)//2
    for line in lines:
        w = draw.textlength(line, font=eng_font)
        x = (width - w)//2
        draw.text((x, y), line, font=eng_font, fill=eng_color)
        y += eng_size + 15

    if phonetic:
        w = draw.textlength(phonetic, font=pho_font)
        x = (width - w)//2
        draw.text((x, y), phonetic, font=pho_font, fill=pho_color)
        y += pho_size + 20

    lines = wrap_text(chinese, 20)
    for line in lines:
        w = draw.textlength(line, font=chn_font)
        x = (width - w)//2
        draw.text((x, y), line, font=chn_font, fill=chn_color)
        y += chn_size + 10

    return img


# -------------------- 音频试听 --------------------
def preview_voice(voice_name, text, speed=1.0):
    if not EDGE_TTS_AVAILABLE:
        return None
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    try:
        asyncio.run(edge_tts.Communicate(text, voice_name).save(tmp.name))
        with open(tmp.name, "rb") as f:
            return f.read()
    except Exception:
        return None
    finally:
        os.remove(tmp.name)


# -------------------- Excel 上传 --------------------
uploaded_excel = st.file_uploader("📄 上传 Excel 文件", type=["xlsx"])
if uploaded_excel:
    try:
        df = pd.read_excel(uploaded_excel)
        if not all(col in df.columns for col in ["英语", "中文", "音标"]):
            st.error("Excel 必须包含列：英语、中文、音标")
            st.stop()
        st.success(f"✅ 成功加载 {len(df)} 行句子。")
        st.dataframe(df.head(10))
    except Exception as e:
        st.error(f"读取 Excel 失败: {e}")
        st.stop()
else:
    df = None

# -------------------- 背景设置 --------------------
col1, col2 = st.columns(2)
with col1:
    bg_type = st.radio("背景类型", ["纯色背景", "上传图片"], horizontal=True)
    if bg_type == "纯色背景":
        bg_hex = st.color_picker("选择背景颜色", "#0b1220")
        bg_color = tuple(int(bg_hex[i:i+2], 16) for i in (1,3,5))
        bg_image = None
    else:
        bg_file = st.file_uploader("上传背景图片", type=["jpg","png"])
        if bg_file:
            bg_image = Image.open(bg_file)
            st.image(bg_image, caption="背景预览", use_column_width=True)
        else:
            bg_image = None
            bg_color = (10,10,10)

with col2:
    eng_color = st.color_picker("英语颜色", "#FFFFFF")
    chn_color = st.color_picker("中文颜色", "#B4E0FF")
    pho_color = st.color_picker("音标颜色", "#FFF07A")

# -------------------- 上传离线音频 --------------------
st.markdown("### 🎵 上传离线音频文件（模式B）")
st.info("命名规则：1-1.mp3、1-2.mp3、1-3.mp3、1-4.mp3 等；缺失部分自动使用静音。")
uploaded_audios = st.file_uploader("上传音频文件", type=["mp3"], accept_multiple_files=True)
uploaded_audio_map = {}
if uploaded_audios:
    for f in uploaded_audios:
        base = os.path.splitext(f.name)[0]
        uploaded_audio_map[base.lower()] = f.read()

# -------------------- 试听功能 --------------------
if EDGE_TTS_AVAILABLE:
    st.markdown("### 🎧 试听音色")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("试听英文男声"):
            audio = preview_voice("en-US-GuyNeural", "Hello! This is an English male voice.")
            if audio: st.audio(audio, format="audio/mp3")
            else: st.warning("试听失败")
    with col_b:
        if st.button("试听英文女声"):
            audio = preview_voice("en-US-JennyNeural", "Hello! This is an English female voice.")
            if audio: st.audio(audio, format="audio/mp3")
            else: st.warning("试听失败")
    with col_c:
        if st.button("试听中文女声"):
            audio = preview_voice("zh-CN-XiaoxiaoNeural", "你好！这是中文语音。")
            if audio: st.audio(audio, format="audio/mp3")
            else: st.warning("试听失败")
else:
    st.warning("⚠️ edge-tts 不可用（离线环境），试听功能禁用。")

# -------------------- 参数 --------------------
st.markdown("### ⚙️ 参数设置")
col3, col4 = st.columns(2)
with col3:
    fps = st.slider("视频帧率", 8, 30, 20)
    per_duration = st.slider("每段时长（秒）", 2, 6, 4)
with col4:
    pause_duration = st.slider("段间静音（秒）", 0.0, 2.0, 0.5)
def write_concat_list(file_list, out_list_path):
    """
    将 file_list 写入 out_list_path（每行 file 'path'），
    在写入前对单引号进行安全转义，避免 ffmpeg 解析问题或 Python 语法问题。
    """
    with open(out_list_path, "w", encoding="utf-8") as f:
        for p in file_list:
            safe_path = p.replace("'", "'\\''")
            f.write("file '%s'\n" % safe_path)
    return out_list_path

# 创建静音音频（mp3）
def create_silent_audio(duration, out_path):
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str(duration),
            "-q:a", "9", "-acodec", "libmp3lame",
            out_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception as e:
        st.warning(f"创建静音音频失败: {e}")
        return False

# 调整音频时长（存在则裁切/填充，不存在则创建静音）
def adjust_audio_to_duration(in_path, duration, out_path):
    if not in_path or not os.path.exists(in_path):
        return create_silent_audio(duration, out_path)
    try:
        cmd = [
            "ffmpeg", "-y", "-i", in_path,
            "-t", str(duration),
            "-af", "apad",
            "-acodec", "libmp3lame",
            out_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception as e:
        # fallback to silent
        return create_silent_audio(duration, out_path)

# 用 ffmpeg concat 合并多个音频（或视频）
def ffmpeg_concat(file_list, out_path, is_video=False):
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt", encoding="utf-8") as f:
        list_path = f.name
        for p in file_list:
            safe_p = p.replace("'", "'\\''")
            f.write("file '%s'\n" % safe_p)
    try:
        if is_video:
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path]
        else:
            # 对音频使用 concat 协议（若失败可改为 re-encode）
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except subprocess.CalledProcessError as e:
        # 如果直接 concat 失败，尝试重编码策略（对音频）
        try:
            if not is_video:
                # 逐个转码再 concat（更兼容）
                temp_dir = os.path.dirname(list_path)
                reencoded = []
                for idx, p in enumerate(file_list):
                    tgt = os.path.join(temp_dir, f"reenc_{idx}.mp3")
                    cmd2 = ["ffmpeg", "-y", "-i", p, "-acodec", "libmp3lame", "-ar", "44100", tgt]
                    subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    if os.path.exists(tgt) and os.path.getsize(tgt) > 0:
                        reencoded.append(tgt)
                if reencoded:
                    # 写新 list
                    with open(list_path, "w", encoding="utf-8") as f2:
                        for p in reencoded:
                            safe_p = p.replace("'", "'\\''")
                            f2.write("file '%s'\n" % safe_p)
                    cmd3 = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path]
                    subprocess.run(cmd3, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    return os.path.exists(out_path) and os.path.getsize(out_path) > 0
        except Exception:
            pass
        return False
    finally:
        try:
            os.remove(list_path)
        except:
            pass

# TTS 生成（仅在环境支持 edge-tts 或 HTTP 降级时会起作用）
# 为简洁我们在这里如果 EDGE_TTS_AVAILABLE 则尽量使用它（不会报错）
def generate_tts_audio(text, voice, out_path, speed=1.0):
    # 若环境没有 edge-tts，则直接返回 None（外网受限时会这样）
    if not EDGE_TTS_AVAILABLE:
        return None
    try:
        # 使用 edge-tts 异步接口保存
        # edge_tts.Communicate(...).save(...) 在 sync 环境可能需 asyncio.run
        coro = edge_tts.Communicate(text, voice).save(out_path)
        asyncio.run(coro)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
        else:
            try:
                os.remove(out_path)
            except:
                pass
            return None
    except Exception:
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except:
            pass
        return None

# 主生成：每行单独生成片段并拼接（保留原有行为）
def generate_and_concat(df, settings, uploaded_audio_map, status_placeholder, progress_bar):
    """
    逻辑：
    - 对于每一行，生成一段无声视频（重复帧覆盖该行总时长）
    - 为每一行构建音频片段列表（按 segment 顺序），每段音频调整为 per_duration，段间插入 pause 静音
    - 合并该行音频为一个文件，再与该行无声视频合并为 line_final
    - 最后 concat 所有 line_final -> output_video.mp4
    """
    if not check_ffmpeg():
        st.error("未检测到 ffmpeg，请确保 ffmpeg 已安装并可用。")
        return None

    tmpdir = tempfile.mkdtemp(prefix="tvb_")
    try:
        fps = settings.get("fps", 20)
        per_dur = settings.get("per_duration", 4)
        pause_dur = settings.get("pause_duration", 0.5)
        width = settings.get("width", 1920)
        height = settings.get("height", 1080)
        eng_color = settings.get("eng_color", (255,255,255))
        chn_color = settings.get("chn_color", (180,220,255))
        pho_color = settings.get("pho_color", (255,240,120))
        eng_size = settings.get("eng_size", 80)
        chn_size = settings.get("chn_size", 60)
        pho_size = settings.get("pho_size", 48)
        bg_image_local = settings.get("bg_image", None)
        bg_color_local = settings.get("bg_color", (10,10,10))
        text_bg_enabled = settings.get("text_bg_enabled", True)
        voice_map = settings.get("voice_map", {
            "英文男声": "en-US-GuyNeural",
            "英文女声": "en-US-JennyNeural",
            "中文音色": "zh-CN-XiaoxiaoNeural"
        })
        segment_order = settings.get("segment_order", ["英文男声","英文女声","中文音色","英文男声"])

        total_lines = len(df)
        line_outputs = []
        for idx, row in df.iterrows():
            i = idx + 1
            status_placeholder.info(f"正在处理第 {i}/{total_lines} 行：准备音频与帧...")
            # 1) 准备音频部分
            per_line_audio_items = []
            for seg_idx, seg in enumerate(segment_order, start=1):
                key = f"{i}-{seg_idx}"
                # 优先使用上传的离线音频（uploaded_audio_map 的 key 可能是 '1-1' 或 '01-01' 等，我们在上传时已以 base 名称存储）
                uploaded_key_variants = [key, key.lower(), key.replace('-', '-').lower()]
                audio_src = None
                # 上传 map 的 key 存储可能是原始 base（如 "1-1"）或小写，已处理
                if uploaded_audio_map:
                    # try direct match
                    if key in uploaded_audio_map:
                        val = uploaded_audio_map[key]
                        # val 是 bytes（上传时读取的）
                        pth = os.path.join(tmpdir, f"uploaded_{key}.mp3")
                        with open(pth, "wb") as _f:
                            _f.write(val)
                        audio_src = pth
                    elif key.lower() in uploaded_audio_map:
                        val = uploaded_audio_map[key.lower()]
                        pth = os.path.join(tmpdir, f"uploaded_{key}.mp3")
                        with open(pth, "wb") as _f:
                            _f.write(val)
                        audio_src = pth
                # 如果没有上传音频，则尝试 TTS（可能因网络受限失败）
                if not audio_src:
                    voice = voice_map.get(seg, list(voice_map.values())[0])
                    text_to_speak = str(row.get("英语","")) if "英文" in seg else str(row.get("中文",""))
                    tts_out = os.path.join(tmpdir, f"tts_{i}_{seg_idx}.mp3")
                    tts_res = generate_tts_audio(text_to_speak, voice, tts_out, speed=1.0)
                    if tts_res:
                        audio_src = tts_res
                    else:
                        audio_src = None
                # 将该段调整为 per_dur 时长（或静音）
                dst_adjusted = os.path.join(tmpdir, f"line_{i}_seg_{seg_idx}_adj.mp3")
                ok = adjust_audio_to_duration(audio_src, per_dur, dst_adjusted)
                if not ok:
                    # create silent as fallback
                    create_silent_audio(per_dur, dst_adjusted)
                per_line_audio_items.append(dst_adjusted)
                # 如果不是最后一段，加 pause
                if seg_idx < len(segment_order):
                    pause_file = os.path.join(tmpdir, f"line_{i}_pause_{seg_idx}.mp3")
                    create_silent_audio(pause_dur, pause_file)
                    per_line_audio_items.append(pause_file)

            # 合并该行音频
            per_line_concat = os.path.join(tmpdir, f"line_{i}_audio.mp3")
            ok_concat = ffmpeg_concat(per_line_audio_items, per_line_concat, is_video=False)
            if not ok_concat:
                # fallback: create single silent of expected duration
                total_segments = len(segment_order)
                total_dur_line = total_segments * per_dur + (total_segments - 1) * pause_dur
                create_silent_audio(total_dur_line, per_line_concat)

            # 2) 生成该行无声视频（重复帧足够时长）
            total_frames_for_line = len(segment_order) * int(round(per_dur * fps)) + (len(segment_order)-1) * int(round(pause_dur * fps))
            frame_image = create_frame(
                english=str(row.get("英语","")),
                chinese=str(row.get("中文","")),
                phonetic=str(row.get("音标","")) if pd.notna(row.get("音标","")) else "",
                width=width, height=height,
                bg_color=bg_color_local, bg_image=bg_image_local,
                eng_color=eng_color, chn_color=chn_color, pho_color=pho_color,
                eng_size=eng_size, chn_size=chn_size, pho_size=pho_size,
                text_bg_enabled=text_bg_enabled
            )
            frame_arr = np.array(frame_image.convert("RGB"))
            line_video_path = os.path.join(tmpdir, f"line_{i}_video.mp4")
            writer = imageio.get_writer(line_video_path, fps=fps, macro_block_size=1, format="FFMPEG", codec="libx264")
            try:
                for _ in range(total_frames_for_line):
                    writer.append_data(frame_arr)
            except Exception as e:
                st.warning(f"写入第 {i} 行帧时出错: {e}")
            finally:
                writer.close()

            # 3) 合并视频与该行音频 -> final line file
            line_final = os.path.join(tmpdir, f"line_{i}_final.mp4")
            try:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", line_video_path,
                    "-i", per_line_concat,
                    "-c:v", "copy", "-c:a", "aac", "-shortest",
                    line_final
                ]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                if os.path.exists(line_final) and os.path.getsize(line_final) > 0:
                    line_outputs.append(line_final)
                else:
                    # fallback to silent video if merge failed
                    line_outputs.append(line_video_path)
            except Exception:
                # on any error fallback silent video
                line_outputs.append(line_video_path)

            # update progress
            progress_bar.progress(0.3 + 0.6 * ((idx+1)/total_lines))
            status_placeholder.info(f"第 {i}/{total_lines} 行处理完成")

        # all lines done -> concat all line_outputs
        status_placeholder.info("正在拼接所有片段，请稍候...")
        final_out = os.path.join(tmpdir, "output_video.mp4")
        concat_ok = ffmpeg_concat(line_outputs, final_out, is_video=True)
        if not concat_ok:
            # 尝试重编码拼接（更兼容）
            list_file = os.path.join(tmpdir, "videos_list.txt")
            write_concat_list(line_outputs, list_file)
            try:
                cmd2 = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c:v", "libx264", "-c:a", "aac", final_out]
                subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except Exception as e:
                st.error(f"最终拼接失败: {e}")
                return None

        if os.path.exists(final_out) and os.path.getsize(final_out) > 0:
            # copy final_out to current working dir for persistence
            try:
                shutil.copy(final_out, os.path.join(os.getcwd(), "output_video.mp4"))
            except:
                pass
            with open(final_out, "rb") as f:
                data = f.read()
            status_placeholder.success("视频生成完成：output_video.mp4")
            progress_bar.progress(1.0)
            return data
        else:
            st.error("最终视频文件不存在或为空")
            return None

    except Exception as e:
        st.error(f"生成过程异常：{e}")
        st.text(traceback.format_exc())
        return None
    finally:
        # 清理临时目录（如需调试可注释掉）
        try:
            shutil.rmtree(tmpdir)
        except:
            pass


# -------------------- 生成按钮与触发 --------------------
if df is not None:
    st.markdown("### 🚀 开始生成")
    if st.button("🎬 生成视频（使用上传音频优先，缺失则静音或尝试 TTS）"):
        status_ph = st.empty()
        pbar = st.progress(0.0)
        # 构造 settings
        settings = {
            "fps": fps,
            "per_duration": per_duration,
            "pause_duration": pause_duration,
            "width": 1920,
            "height": 1080,
            "eng_color": tuple(int(eng_color[i:i+2],16) for i in (1,3,5)) if isinstance(eng_color,str) else eng_color,
            "chn_color": tuple(int(chn_color[i:i+2],16) for i in (1,3,5)) if isinstance(chn_color,str) else chn_color,
            "pho_color": tuple(int(pho_color[i:i+2],16) for i in (1,3,5)) if isinstance(pho_color,str) else pho_color,
            "eng_size": eng_size,
            "chn_size": chn_size,
            "pho_size": pho_size,
            "bg_image": bg_image,
            "bg_color": bg_color,
            "text_bg_enabled": True,
            "voice_map": {
                "英文男声": "en-US-GuyNeural",
                "英文女声": "en-US-JennyNeural",
                "中文音色": "zh-CN-XiaoxiaoNeural"
            },
            "segment_order": ["英文男声","英文女声","中文音色","英文男声"]
        }
        # 触发生成
        try:
            video_bytes = generate_and_concat(df, settings, uploaded_audio_map, status_ph, pbar)
            if video_bytes:
                st.video(video_bytes)
                st.download_button("📥 下载 output_video.mp4", data=video_bytes, file_name="output_video.mp4", mime="video/mp4")
            else:
                st.error("生成失败，请查看上方错误信息。")
        except Exception as e:
            st.error(f"未捕获的异常：{e}")
            st.text(traceback.format_exc())
