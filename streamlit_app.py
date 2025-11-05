# streamlit_app.py
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
import base64
import socket
import time
import threading
import queue
import requests

# -----------------------
# 配置：固定分辨率 1920x1080
# -----------------------
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080

# -----------------------
# 工具：检查 ffmpeg
# -----------------------
def check_ffmpeg():
    return shutil.which("ffmpeg") is not None

# edge-tts 优先用于试听/在线生成（如果可用）
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

st.set_page_config(page_title="旅行英语视频生成器（离线模式B - 每行单独片段拼接）",
                   page_icon="🎬", layout="wide")

# CSS 美化
st.markdown("""
<style>
    .main-header { font-size: 2.6rem; font-weight:700; text-align:center; margin-bottom:1rem; }
    .section-header { font-size:1.25rem; font-weight:600; margin-top:1rem; margin-bottom:0.5rem; }
    .preview-section { background:#f8fafc; padding:1rem; border-radius:8px; margin-bottom:1rem; }
</style>
""", unsafe_allow_html=True)

# 会话状态
if 'bg_image' not in st.session_state:
    st.session_state.bg_image = None

# -----------------------
# 字体/绘图辅助函数（与之前类似）
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

def get_font(size, bold=False):
    # 尝试常见字体，回退到 load_default
    choices = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "arial.ttf",
        "NotoSansCJK-Regular.ttc"
    ]
    for f in choices:
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default()

def create_frame(english, chinese, phonetic, width=VIDEO_WIDTH, height=VIDEO_HEIGHT,
                 bg_color=(10,10,10), bg_image=None,
                 eng_color=(255,255,255), chn_color=(180,220,255), pho_color=(255,240,120),
                 eng_size=80, chn_size=60, pho_size=50,
                 text_bg_enabled=True, text_bg_color=(255,255,255,180), text_bg_padding=20,
                 text_bg_radius=30, text_bg_width=None, text_bg_height=None,
                 bold_text=True, eng_pho_spacing=30, pho_chn_spacing=30, line_spacing=15):
    if bg_image:
        try:
            img = ImageOps.fit(bg_image.convert('RGB'), (width, height), Image.Resampling.LANCZOS)
        except Exception:
            img = Image.new('RGB', (width, height), bg_color)
    else:
        img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    eng_font = get_font(eng_size, bold=bold_text)
    chn_font = get_font(chn_size, bold=bold_text)
    pho_font = get_font(pho_size, bold=bold_text)

    eng_lines = wrap_text(english, 40)
    chn_lines = wrap_text(chinese, 20)
    pho_lines = wrap_text(phonetic, 45) if phonetic else []

    total_height = 0
    for line in eng_lines:
        bbox = draw.textbbox((0,0), line, font=eng_font)
        total_height += (bbox[3]-bbox[1])
    total_height += line_spacing * (len(eng_lines)-1)

    if pho_lines:
        total_height += eng_pho_spacing
        for line in pho_lines:
            bbox = draw.textbbox((0,0), line, font=pho_font)
            total_height += (bbox[3]-bbox[1])
        total_height += line_spacing * (len(pho_lines)-1)

    if chn_lines:
        total_height += pho_chn_spacing
        for line in chn_lines:
            bbox = draw.textbbox((0,0), line, font=chn_font)
            total_height += (bbox[3]-bbox[1])
        total_height += line_spacing * (len(chn_lines)-1)

    if text_bg_enabled:
        max_w = 0
        for line in eng_lines:
            bbox = draw.textbbox((0,0), line, font=eng_font)
            max_w = max(max_w, bbox[2]-bbox[0])
        for line in pho_lines:
            bbox = draw.textbbox((0,0), line, font=pho_font)
            max_w = max(max_w, bbox[2]-bbox[0])
        for line in chn_lines:
            bbox = draw.textbbox((0,0), line, font=chn_font)
            max_w = max(max_w, bbox[2]-bbox[0])

        if text_bg_width is None:
            bg_w = max_w + text_bg_padding*2
        else:
            bg_w = text_bg_width
        if text_bg_height is None:
            bg_h = total_height + text_bg_padding*2
        else:
            bg_h = text_bg_height

        bx = (width - bg_w)//2
        by = (height - bg_h)//2
        layer = Image.new('RGBA', (bg_w, bg_h), (0,0,0,0))
        ldraw = ImageDraw.Draw(layer)
        if text_bg_radius > 0:
            ldraw.rounded_rectangle([(0,0),(bg_w,bg_h)], radius=text_bg_radius, fill=text_bg_color)
        else:
            ldraw.rectangle([(0,0),(bg_w,bg_h)], fill=text_bg_color)
        img.paste(layer, (bx,by), layer)

    y = (height - total_height)//2

    for line in eng_lines:
        bbox = draw.textbbox((0,0), line, font=eng_font)
        w = bbox[2]-bbox[0]
        x = (width - w)//2
        draw.text((x+3,y+3), line, font=eng_font, fill=(0,0,0,120))
        draw.text((x,y), line, font=eng_font, fill=eng_color)
        y += bbox[3]-bbox[1] + line_spacing

    if pho_lines:
        y += eng_pho_spacing
        for line in pho_lines:
            bbox = draw.textbbox((0,0), line, font=pho_font)
            w = bbox[2]-bbox[0]
            x = (width - w)//2
            draw.text((x+2,y+2), line, font=pho_font, fill=(0,0,0,120))
            draw.text((x,y), line, font=pho_font, fill=pho_color)
            y += bbox[3]-bbox[1] + line_spacing

    if chn_lines:
        y += pho_chn_spacing
        for line in chn_lines:
            bbox = draw.textbbox((0,0), line, font=chn_font)
            w = bbox[2]-bbox[0]
            x = (width - w)//2
            draw.text((x+2,y+2), line, font=chn_font, fill=(0,0,0,120))
            draw.text((x,y), line, font=chn_font, fill=chn_color)
            y += bbox[3]-bbox[1] + line_spacing

    return img

# -----------------------
# TTS helpers (edge-tts 优先，线程+新 loop)
# -----------------------
def run_coro_in_new_loop(coro, timeout=None):
    q = queue.Queue()
    def _runner():
        try:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            res = new_loop.run_until_complete(coro)
            q.put(("ok", res))
        except Exception as e:
            q.put(("err", e))
        finally:
            try:
                new_loop.close()
            except:
                pass
    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout)
    try:
        status, payload = q.get_nowait()
    except queue.Empty:
        raise TimeoutError("TTS 线程执行超时")
    if status == "ok":
        return payload
    else:
        raise payload

async def _edge_save_async(text, voice, out_path, rate="+0%"):
    com = edge_tts.Communicate(text, voice, rate=rate)
    await com.save(out_path)
    return True

def _edge_save_sync(text, voice, out_path, rate="+0%"):
    return run_coro_in_new_loop(_edge_save_async(text, voice, out_path, rate), timeout=60)

def web_tts_via_http_ssml(text, voice, rate_percent=0, out_path=None, timeout=30):
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
    ssml = f"""<speak version='1.0' xml:lang='en-US'><voice xml:lang='en-US' name='{voice}'><prosody rate='{rate_percent}%'>{escape_ssml_text(text)}</prosody></voice></speak>"""
    headers = {
        "User-Agent":"Mozilla/5.0",
        "Content-Type":"application/ssml+xml",
        "X-Microsoft-OutputFormat":"audio-16khz-128kbitrate-mono-mp3",
        "Origin":"https://edge.microsoft.com",
        "Referer":"https://edge.microsoft.com/"
    }
    url = "https://speech.platform.bing.com/consumer/speech/synthesize"
    try:
        resp = requests.post(url, data=ssml.encode("utf-8"), headers=headers, timeout=timeout, stream=True)
        if resp.status_code == 200:
            with open(out_path, "wb") as f:
                for ch in resp.iter_content(chunk_size=4096):
                    if ch:
                        f.write(ch)
            if os.path.exists(out_path) and os.path.getsize(out_path)>0:
                return out_path
            try:
                os.unlink(out_path)
            except:
                pass
            return None
        else:
            try:
                os.unlink(out_path)
            except:
                pass
            return None
    except Exception:
        try:
            if os.path.exists(out_path):
                os.unlink(out_path)
        except:
            pass
        return None

def escape_ssml_text(text):
    return str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def generate_edge_audio(text, voice, speed=1.0, out_path=None, retry=2):
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
    if EDGE_TTS_AVAILABLE:
        pct = int((speed-1.0)*100)
        rate = f"{pct:+d}%"
        last = None
        for i in range(retry):
            try:
                _edge_save_sync(text, voice, out_path, rate)
                if os.path.exists(out_path) and os.path.getsize(out_path)>0:
                    return out_path
                else:
                    last = RuntimeError("edge-tts did not produce file")
                    if os.path.exists(out_path):
                        try: os.unlink(out_path)
                        except: pass
                    time.sleep(1)
            except Exception as e:
                last = e
                if os.path.exists(out_path):
                    try: os.unlink(out_path)
                    except: pass
                time.sleep(1)
        st.warning(f"TTS: edge-tts 多次尝试失败，尝试 HTTP 降级。示例：{last}")
    # HTTP 降级尝试
    pct2 = int((speed-1.0)*100)
    for i in range(retry):
        res = web_tts_via_http_ssml(text, voice, rate_percent=pct2, out_path=out_path, timeout=25)
        if res and os.path.exists(res) and os.path.getsize(res)>0:
            return res
        if os.path.exists(out_path):
            try: os.unlink(out_path)
            except: pass
        time.sleep(1)
    # 全部失败
    return None

def preview_voice(voice_name, text, speed=1.0):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    tmp_path = tmp.name
    if EDGE_TTS_AVAILABLE:
        try:
            run_coro_in_new_loop(_edge_save_async(text, voice_name, tmp_path, rate=f"{int((speed-1.0)*100):+d}%"), timeout=30)
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path)>0:
                with open(tmp_path,"rb") as f:
                    data = f.read()
                try: os.unlink(tmp_path)
                except: pass
                return data
        except Exception:
            if os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except: pass
    # HTTP 降级
    res = web_tts_via_http_ssml(text, voice_name, rate_percent=int((speed-1.0)*100), out_path=tmp_path, timeout=25)
    if res and os.path.exists(res) and os.path.getsize(res)>0:
        with open(res,"rb") as f:
            data = f.read()
        try: os.unlink(res)
        except: pass
        return data
    if os.path.exists(tmp_path):
        try: os.unlink(tmp_path)
        except: pass
    return None

# -----------------------
# ffmpeg helpers：静音、调整时长、concat 列表写入
# -----------------------
def create_silent_audio(duration, out_path):
    cmd = ["ffmpeg","-y","-f","lavfi","-i",f"anullsrc=r=44100:cl=stereo","-t",str(duration), "-q:a","9","-acodec","libmp3lame", out_path]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return os.path.exists(out_path) and os.path.getsize(out_path)>0
    except Exception:
        return False

def adjust_audio_duration(input_path, target_duration, out_path):
    if not input_path or not os.path.exists(input_path):
        return create_silent_audio(target_duration, out_path)
    cmd = ["ffmpeg","-y","-i",input_path,"-t",str(target_duration),"-af","apad","-acodec","libmp3lame", out_path]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return os.path.exists(out_path) and os.path.getsize(out_path)>0
    except Exception:
        return create_silent_audio(target_duration, out_path)

def concat_files_with_ffmpeg(file_paths, out_path, is_video=False):
    # write list file
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as f:
        for p in file_paths:
            # ffmpeg concat requires escaped single quotes if present
            f.write(f"file '{p.replace(\"'\",\"'\\\\''\")}'\n")
        list_path = f.name
    try:
        if is_video:
            cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",list_path,"-c","copy", out_path]
        else:
            # force re-encode to mp3 (to avoid codec mismatch)
            cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",list_path,"-c","copy", out_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return os.path.exists(out_path) and os.path.getsize(out_path)>0
    except subprocess.CalledProcessError as e:
        return False
    finally:
        try: os.unlink(list_path)
        except: pass

# -----------------------
# 主生成逻辑：每行生成单独片段并拼接
# -----------------------
def generate_video_per_line(df, settings, uploaded_audio_map, status_placeholder, progress_bar):
    """
    - 对于每一行：
       1) 生成该行的无声视频文件（重复帧达到 per_duration*segments + pauses）
       2) 为该行拼接 4 段音频（优先使用 uploaded_audio_map; 否则尝试 TTS；再失败用静音）
       3) 将该行视频和该行音频合并成 line_final_{i}.mp4
    - 最后按行顺序 concat 所有 line_final files -> output_video.mp4
    """
    if not check_ffmpeg():
        st.error("未检测到 ffmpeg，无法执行音频/视频处理。请安装 ffmpeg。")
        return None

    tmpdir = tempfile.mkdtemp(prefix="video_build_")
    try:
        per_duration = settings['per_duration']
        pause_duration = settings['pause_duration']
        fps = settings['fps']
        per_frames = int(round(per_duration * fps))
        pause_frames = int(round(pause_duration * fps))
        width = settings['width']
        height = settings['height']
        eng_color = settings['eng_color']
        chn_color = settings['chn_color']
        pho_color = settings['pho_color']
        eng_size = settings['eng_size']
        chn_size = settings['chn_size']
        pho_size = settings['pho_size']
        text_bg_enabled = settings['text_bg_enabled']
        text_bg_color = settings['text_bg_color']
        text_bg_padding = settings['text_bg_padding']
        text_bg_radius = settings['text_bg_radius']
        text_bg_width = settings['text_bg_width']
        text_bg_height = settings['text_bg_height']
        bold_text = settings['bold_text']
        segment_order = settings['segment_order']
        voice_mapping = settings['voice_mapping']
        tts_speed = settings['tts_speed']
        eng_pho_spacing = settings['eng_pho_spacing']
        pho_chn_spacing = settings['pho_chn_spacing']
        line_spacing = settings['line_spacing']
        bg_image = settings['bg_image']
        bg_color = settings['bg_color']

        line_video_files = []
        total = len(df)
        # For progress: audio preparation (0-0.3), per-line video generation (0.3-0.7), merging & concat (0.7-1.0)
        for idx, row in df.iterrows():
            i = idx + 1  # 1-indexed naming
            status_placeholder.info(f"准备第 {i} 行的音频与视频...")
            # --- 1) 准备该行的 4 段音频（适配时长） ---
            per_line_audio_parts = []
            for seg_idx, seg_name in enumerate(segment_order, start=1):
                expected_key = f"{i}-{seg_idx}"
                audio_src_path = None
                # check uploaded map
                if uploaded_audio_map and expected_key in uploaded_audio_map:
                    val = uploaded_audio_map[expected_key]
                    if isinstance(val, bytes):
                        p = os.path.join(tmpdir, f"uploaded_{expected_key}.mp3")
                        with open(p,"wb") as f:
                            f.write(val)
                        audio_src_path = p
                    elif isinstance(val, str) and os.path.exists(val):
                        audio_src_path = val
                # if not uploaded, attempt TTS using voice_mapping (voice, text_type)
                if not audio_src_path:
                    voice, text_type = voice_mapping[seg_name]
                    text_to_speak = str(row['英语']) if text_type=="english" else str(row['中文'])
                    # produce temp tts file
                    tts_path = os.path.join(tmpdir, f"tts_{i}_{seg_idx}.mp3")
                    tts_res = generate_edge_audio(text_to_speak, voice, speed=tts_speed, out_path=tts_path)
                    if tts_res and os.path.exists(tts_res) and os.path.getsize(tts_res)>0:
                        audio_src_path = tts_res
                    else:
                        audio_src_path = None
                # adjust to per_duration
                adjusted = os.path.join(tmpdir, f"line_{i}_seg_{seg_idx}_adj.mp3")
                ok = adjust_audio_duration(audio_src_path, per_duration, adjusted)
                if not ok:
                    # fallback create silent
                    create_silent_audio(per_duration, adjusted)
                per_line_audio_parts.append(adjusted)
                # add pause if not last segment
                if seg_idx < len(segment_order):
                    pause_file = os.path.join(tmpdir, f"line_{i}_pause_{seg_idx}.mp3")
                    create_silent_audio(pause_duration, pause_file)
                    per_line_audio_parts.append(pause_file)

                # update progress (audio prep portion)
                current_audio_index = (idx*len(segment_order) + seg_idx)
                audio_progress = min(0.3, (current_audio_index / (len(df)*len(segment_order))) * 0.3)
                progress_bar.progress(audio_progress)

            # concat per-line audio into one file
            per_line_audio_concat = os.path.join(tmpdir, f"line_{i}_audio_concat.mp3")
            concat_ok = concat_files_with_ffmpeg(per_line_audio_parts, per_line_audio_concat, is_video=False)
            if not concat_ok:
                # fallback: create a silent audio of expected duration
                total_segments = len(segment_order)
                total_duration = total_segments * per_duration + (total_segments-1)*pause_duration
                create_silent_audio(total_duration, per_line_audio_concat)

            # --- 2) 生成该行的无声视频（重复帧） ---
            # create frames for this line (single frame enough because we repeat)
            eng = str(row['英语'])
            chn = str(row['中文'])
            pho = str(row['音标']) if pd.notna(row['音标']) else ""
            frame_img = create_frame(
                english=eng, chinese=chn, phonetic=pho,
                width=width, height=height, bg_color=bg_color, bg_image=bg_image,
                eng_color=eng_color, chn_color=chn_color, pho_color=pho_color,
                eng_size=eng_size, chn_size=chn_size, pho_size=pho_size,
                text_bg_enabled=text_bg_enabled, text_bg_color=text_bg_color,
                text_bg_padding=text_bg_padding, text_bg_radius=text_bg_radius,
                text_bg_width=text_bg_width, text_bg_height=text_bg_height,
                bold_text=bold_text, eng_pho_spacing=eng_pho_spacing,
                pho_chn_spacing=pho_chn_spacing, line_spacing=line_spacing
            )
            frame_array = np.array(frame_img.convert('RGB'))
            # compute total frames for this line: segments * per_frames + pauses * pause_frames
            total_frames_line = len(segment_order)*per_frames + (len(segment_order)-1)*pause_frames
            line_video_path = os.path.join(tmpdir, f"line_{i}_video.mp4")
            writer = imageio.get_writer(line_video_path, fps=fps, macro_block_size=1, format='FFMPEG', codec='libx264')
            try:
                for fno in range(total_frames_line):
                    writer.append_data(frame_array)
            except Exception as e:
                st.warning(f"写入第 {i} 行视频帧异常: {e}")
            finally:
                writer.close()

            # --- 3) 合并该行视频与该行音频 -> line_final_i.mp4 ---
            line_final = os.path.join(tmpdir, f"line_{i}_final.mp4")
            cmd = [
                "ffmpeg","-y","-i", line_video_path, "-i", per_line_audio_concat,
                "-c:v","copy","-c:a","aac","-shortest", line_final
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                if os.path.exists(line_final) and os.path.getsize(line_final)>0:
                    line_video_files.append(line_final)
                else:
                    # if failed, fall back to silent video
                    line_video_files.append(line_video_path)
            except subprocess.CalledProcessError as e:
                # on error, keep silent video
                line_video_files.append(line_video_path)

            # update progress after generating this line video
            # audio portion covered up to 0.3, video generation up to 0.7
            progress_bar.progress(0.3 + 0.4 * ((idx+1)/len(df)))

        # --- concat all line_final files into final output ---
        status_placeholder.info("正在拼接所有片段...")
        final_out = os.path.join(tmpdir, "output_video.mp4")
        concat_ok = concat_files_with_ffmpeg(line_video_files, final_out, is_video=True)
        if not concat_ok:
            # fallback try to use ffmpeg with re-encode (safer)
            # build list file
            listf = os.path.join(tmpdir, "video_list.txt")
            with open(listf,"w") as f:
                for p in line_video_files:
                    f.write(f"file '{p.replace(\"'\",\"'\\\\''\")}'\n")
            cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",listf,"-c:v","libx264","-c:a","aac",final_out]
            try:
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except Exception as e:
                st.error("视频拼接失败：" + str(e))
                return None

        if os.path.exists(final_out) and os.path.getsize(final_out)>0:
            with open(final_out,"rb") as f:
                data = f.read()
            # optionally copy final output to current working dir for persistence
            shutil.copy(final_out, os.path.join(os.getcwd(), "output_video.mp4"))
            progress_bar.progress(1.0)
            status_placeholder.success("生成完成：output_video.mp4")
            return data
        else:
            st.error("最终视频文件不存在或为空")
            return None

    except Exception as e:
        st.error(f"生成过程异常: {e}")
        st.text(traceback.format_exc())
        return None
    finally:
        # don't delete immediately if you want to inspect tmpdir; but we cleanup here
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

# -----------------------
# UI 主流程（保留上传音频模式B 与试听）
# -----------------------
st.markdown("<div class='main-header'>🎬 旅行英语视频生成器 — 每行单独片段拼接（1920×1080）</div>", unsafe_allow_html=True)
st.markdown("上传 Excel（含列：英语、中文、音标）并上传每行 4 段音频（命名：行号-段号.mp3）或使用在线 TTS 生成缺失部分。")

uploaded = st.file_uploader("选择 Excel 文件", type=["xlsx","xls"], key="excel_uploader")
df = None
if uploaded:
    try:
        df = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"读取 Excel 失败：{e}")
        df = None

if df is not None:
    required = ['英语','中文','音标']
    miss = [c for c in required if c not in df.columns]
    if miss:
        st.error(f"Excel 缺少列：{', '.join(miss)}")
        st.stop()

    st.markdown("<div class='section-header'>📊 数据预览</div>", unsafe_allow_html=True)
    st.dataframe(df.head(10), height=220)
    st.info(f"共 {len(df)} 行。为保证速度建议不要超过 50 行（可分批处理）。")

    # 设置区域（保留之前的选项）
    st.markdown("<div class='section-header'>🎨 样式与音色设置</div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        bg_type = st.radio("背景类型", ["纯色","图片"], key="bg_type")
        if bg_type == "纯色":
            bg_hex = st.color_picker("背景颜色", "#0b1220", key="bg_color_picker")
            bg_color = tuple(int(bg_hex[i:i+2],16) for i in (1,3,5))
            st.session_state.bg_image = None
        else:
            bg_file = st.file_uploader("上传背景图片 (用于帧渲染)", type=["jpg","jpeg","png"], key="bg_image_uploader")
            if bg_file:
                try:
                    st.session_state.bg_image = Image.open(bg_file)
                    st.image(st.session_state.bg_image, caption="背景预览", use_column_width=True)
                except Exception as e:
                    st.error(f"打开背景图片失败: {e}")
                    st.session_state.bg_image = None
            bg_color = (10,10,10)

    with col2:
        st.markdown("文字样式")
        eng_color = st.color_picker("英语颜色", "#FFFFFF", key="eng_color")
        eng_color = tuple(int(eng_color[i:i+2],16) for i in (1,3,5))
        chn_color = st.color_picker("中文颜色", "#B4E0FF", key="chn_color")
        chn_color = tuple(int(chn_color[i:i+2],16) for i in (1,3,5))
        pho_color = st.color_picker("音标颜色", "#FFF07A", key="pho_color")
        pho_color = tuple(int(pho_color[i:i+2],16) for i in (1,3,5))
        eng_size = st.slider("英语字号", 40, 140, 80, key="eng_size")
        chn_size = st.slider("中文字号", 24, 100, 60, key="chn_size")
        pho_size = st.slider("音标字号", 20, 80, 48, key="pho_size")
        bold_text = st.checkbox("文字加粗", True, key="bold_text")

    st.markdown("<div class='section-header'>🔊 上传音频（模式B，每行4段）</div>", unsafe_allow_html=True)
    st.markdown("请按命名规则上传音频文件：行号-段号.mp3（例如：1-1.mp3, 1-2.mp3, ...）。若缺失会优先使用 TTS 生成（若不可用则用静音）。")
    uploaded_audio_files = st.file_uploader("上传 MP3（可多选）", type=["mp3"], accept_multiple_files=True, key="audio_uploader")

    uploaded_audio_map = {}
    if uploaded_audio_files:
        for f in uploaded_audio_files:
            name = f.name.strip()
            base = os.path.splitext(name)[0].lower()
            if "-" in base:
                a,b = base.split("-",1)
                if a.isdigit() and b.isdigit():
                    key = f"{int(a)}-{int(b)}"
                    try:
                        uploaded_audio_map[key] = f.read()
                    except Exception as e:
                        st.warning(f"读取 {name} 失败: {e}")
                else:
                    st.warning(f"忽略文件（命名不匹配）：{name}")
            else:
                st.warning(f"忽略文件（命名不匹配）：{name}")

    # 播放顺序与音色映射（UI）
    st.markdown("<div class='section-header'>🎛 播放顺序与音色（影响缺失音频的 TTS）</div>", unsafe_allow_html=True)
    colA, colB, colC, colD = st.columns(4)
    with colA:
        seg1 = st.selectbox("第1段", ["英文男声","英文女声","中文音色"], index=0, key="seg1")
    with colB:
        seg2 = st.selectbox("第2段", ["英文男声","英文女声","中文音色"], index=1, key="seg2")
    with colC:
        seg3 = st.selectbox("第3段", ["英文男声","英文女声","中文音色"], index=2, key="seg3")
    with colD:
        seg4 = st.selectbox("第4段", ["英文男声","英文女声","中文音色"], index=0, key="seg4")
    segment_order = [seg1, seg2, seg3, seg4]

    # 预定义 voices
    VOICE_OPTIONS = {
        "英文男声":"en-US-GuyNeural",
        "英文女声":"en-US-JennyNeural",
        "中文音色":"zh-CN-XiaoxiaoNeural"
    }
    # 试听区
    st.markdown("<div class='section-header'>🎧 试听（edge-tts，如环境支持）</div>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1:
        male_label = st.selectbox("英文男声", [k for k in VOICE_OPTIONS if "英文男声" in k], index=0, key="male_choice")
        male_voice = VOICE_OPTIONS["英文男声"]
        if st.button("试听男声", key="preview_male"):
            audio_bytes = preview_voice(male_voice, "Hello, this is a preview.", speed=1.0)
            if audio_bytes:
                st.audio(audio_bytes, format="audio/mp3")
            else:
                st.warning("试听失败（可能网络受限）")
    with c2:
        female_label = st.selectbox("英文女声", [k for k in VOICE_OPTIONS if "英文女声" in k], index=0, key="female_choice")
        female_voice = VOICE_OPTIONS["英文女声"]
        if st.button("试听女声", key="preview_female"):
            audio_bytes = preview_voice(female_voice, "Hello, this is a female voice preview.", speed=1.0)
            if audio_bytes:
                st.audio(audio_bytes, format="audio/mp3")
            else:
                st.warning("试听失败（可能网络受限）")
    with c3:
        chinese_voice = VOICE_OPTIONS["中文音色"]
        if st.button("试听中文", key="preview_chi"):
            audio_bytes = preview_voice(chinese_voice, "你好，这是中文语音预览。", speed=1.0)
            if audio_bytes:
                st.audio(audio_bytes, format="audio/mp3")
            else:
                st.warning("试听失败（可能网络受限）")

    tts_speed = st.slider("在线 TTS 语速（若使用）", 0.5, 2.0, 1.0, 0.1)
    pause_duration = st.slider("每段停顿时长（秒）", 0.0, 3.0, 0.5, 0.1)
    per_duration = st.slider("每段音频时长（秒）", 2, 8, 4, step=1)
    fps = st.slider("帧率 (FPS)", 8, 30, 20)

    # 生成按钮
    st.markdown("<div class='section-header'>🚀 生成视频</div>", unsafe_allow_html=True)
    if st.button("开始生成视频 (每行单独片段拼接)", key="start_gen"):
        status_placeholder = st.empty()
        progress_bar = st.progress(0.0)
        settings = {
            'width': VIDEO_WIDTH,
            'height': VIDEO_HEIGHT,
            'fps': fps,
            'per_duration': per_duration,
            'pause_duration': pause_duration,
            'bg_color': bg_color,
            'bg_image': st.session_state.bg_image,
            'eng_color': eng_color,
            'chn_color': chn_color,
            'pho_color': pho_color,
            'eng_size': eng_size,
            'chn_size': chn_size,
            'pho_size': pho_size,
            'text_bg_enabled': True,
            'text_bg_color': (255,255,255,180),
            'text_bg_padding': 20,
            'text_bg_radius': 24,
            'text_bg_width': None,
            'text_bg_height': None,
            'bold_text': bold_text,
            'segment_order': segment_order,
            'voice_mapping': {k: (VOICE_OPTIONS[k], "english" if "英文" in k else "chinese") for k in ["英文男声","英文女声","中文音色"]},
            'tts_speed': tts_speed,
            'eng_pho_spacing': 30,
            'pho_chn_spacing': 40,
            'line_spacing': 15
        }
        # run generation
        video_bytes = generate_video_per_line(df, settings, uploaded_audio_map, status_placeholder, progress_bar)
        if video_bytes:
            st.video(video_bytes)
            st.download_button("下载视频 output_video.mp4", data=video_bytes, file_name="output_video.mp4", mime="video/mp4")
        else:
            st.error("视频生成失败，请查看上方错误信息。")

# 侧边栏帮助
with st.sidebar:
    st.header("使用说明")
    st.markdown("""
- 请上传 Excel，包含列：**英语**、**中文**、**音标**（音标可选）。
- 上传音频（模式B）请按命名规则：**行号-段号.mp3**，例如 `1-1.mp3`、`1-2.mp3`。
- 若未上传某段音频，应用会尝试在线 TTS（若环境能联网），否则用静音占位。
- 最终输出 `output_video.mp4`（已复制到运行目录）。
- 请确保运行环境已安装 `ffmpeg`。
    """)
    st.markdown("如果需要我也可以提供本地批量生成音频的脚本（generate_audios.py），可一键从 Excel 生成所有 `行号-段号.mp3` 文件。")

# 隐藏默认 Streamlit 元素
st.markdown("""
<style>#MainMenu{visibility:hidden;}footer{visibility:hidden;}</style>
""", unsafe_allow_html=True)
