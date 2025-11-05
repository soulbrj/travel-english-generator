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
import time
from pathlib import Path

# 检查 ffmpeg 是否可用（增强版）
def check_ffmpeg():
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        st.error("未找到FFmpeg，请确保已正确安装并添加到系统PATH中")
        return None
    # 检查FFmpeg版本，确认可执行
    try:
        subprocess.run([ffmpeg_path, '-version'], check=True, capture_output=True, text=True)
        return ffmpeg_path
    except subprocess.CalledProcessError:
        st.error("FFmpeg存在但无法正常工作，请重新安装")
        return None

# edge-tts 用于多音色 TTS
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

# 页面配置
st.set_page_config(
    page_title="旅行英语视频生成器",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1f2937;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e5e7eb;
    }
    .info-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
    .success-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
    .warning-card {
        background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    .upload-section {
        border: 2px dashed #667eea;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        background: rgba(102, 126, 234, 0.05);
        margin: 1rem 0;
    }
    .preview-section {
        background: #f8fafc;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
    }
    .setting-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid #e5e7eb;
        margin: 0.5rem 0;
    }
    .voice-preview-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.5rem 1rem !important;
        font-size: 0.9rem !important;
    }
</style>
""", unsafe_allow_html=True)

# 会话状态
if 'bg_image' not in st.session_state:
    st.session_state.bg_image = None
if 'audio_available' not in st.session_state:
    st.session_state.audio_available = EDGE_TTS_AVAILABLE
if 'generated_video' not in st.session_state:
    st.session_state.generated_video = None
if 'temp_dir' not in st.session_state:
    st.session_state.temp_dir = None

# 创建可靠的临时目录
def create_temp_dir():
    try:
        # 优先使用系统临时目录
        temp_dir = tempfile.mkdtemp(prefix="travel_english_")
        # 验证权限
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        st.session_state.temp_dir = temp_dir
        return temp_dir
    except Exception as e:
        st.error(f"无法创建临时目录: {str(e)}")
        #  fallback到当前目录
        current_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(current_dir, exist_ok=True)
        st.session_state.temp_dir = current_dir
        return current_dir

# 清理临时文件
def cleanup_temp_files():
    if st.session_state.temp_dir and os.path.exists(st.session_state.temp_dir):
        try:
            shutil.rmtree(st.session_state.temp_dir)
            st.session_state.temp_dir = None
        except Exception as e:
            st.warning(f"清理临时文件时出错: {str(e)}")

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

def get_phonetic_font(size, bold=False):
    """专门用于音标显示的字体加载函数"""
    try:
        # 优先尝试直接加载已知的音标字体文件
        font_files = [
            "DoulosSIL-R.ttf",
            "CharisSIL-R.ttf",
            "NotoSansIPA-Regular.ttf",
            "ArialUni.ttf",
            "l_10646.ttf",
            "DejaVuSans.ttf",
        ]
        
        # 尝试从系统字体目录加载
        system_font_paths = [
            "/usr/share/fonts/",
            "C:/Windows/Fonts/",
            "~/Library/Fonts/",
            "/Library/Fonts/",
        ]
        
        # 尝试加载粗体
        if bold:
            bold_fonts = [
                "DoulosSIL-B.ttf",
                "CharisSIL-B.ttf",
                "NotoSansIPA-Bold.ttf",
                "ArialUniBold.ttf",
                "DejaVuSans-Bold.ttf",
            ]
            for font in bold_fonts:
                try:
                    return ImageFont.truetype(font, size)
                except:
                    pass
                for path in system_font_paths:
                    font_path = os.path.join(path, font)
                    if os.path.exists(font_path):
                        try:
                            return ImageFont.truetype(font_path, size)
                        except:
                            continue
        
        # 尝试加载常规字体
        for font in font_files:
            try:
                return ImageFont.truetype(font, size)
            except:
                pass
            for path in system_font_paths:
                font_path = os.path.join(path, font)
                if os.path.exists(font_path):
                    try:
                        return ImageFont.truetype(font_path, size)
                    except:
                        continue
        
        # 最后使用默认字体
        return ImageFont.load_default()
    except Exception as e:
        return ImageFont.load_default()

def get_font(size, font_type="default", bold=False):
    """获取字体，支持音标符号和中文"""
    if font_type == "phonetic":
        return get_phonetic_font(size, bold)
    
    try:
        chinese_fonts = [
            "simhei.ttf",
            "msyh.ttc",
            "simsun.ttc",
            "STHeiti Light.ttc",
            "PingFang.ttc",
            "Arial Unicode MS",
            "SimHei", 
            "Microsoft YaHei",
            "WenQuanYi Micro Hei",
            "NotoSansCJK-Regular.ttc",
            "FZSTK.TTF",
            "SourceHanSansCN-Regular.otf",
        ]
        
        if bold:
            bold_fonts = [
                "simhei.ttf",
                "msyhbd.ttc",
                "STHeiti Medium.ttc",
                "PingFang SC Semibold.ttc",
                "Arial Unicode MS",
                "SimHei",
                "Arial Bold",
                "Arial-Bold",
                "arialbd.ttf"
            ]
            for f in chinese_fonts:
                try:
                    if f in bold_fonts or any(bold_font in f.lower() for bold_font in ['bold', 'bd', 'black', 'heavy']):
                        return ImageFont.truetype(f, size)
                except Exception:
                    continue
            for f in bold_fonts:
                try:
                    return ImageFont.truetype(f, size)
                except Exception:
                    continue
        
        for f in chinese_fonts:
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
        
        return ImageFont.load_default()
    except Exception as e:
        return ImageFont.load_default()

def create_frame(english, chinese, phonetic, width=1920, height=1080,
                 bg_color=(0,0,0), bg_image=None,
                 eng_color=(255,255,255), chn_color=(173,216,230), pho_color=(255,255,0),
                 eng_size=80, chn_size=60, pho_size=50,
                 text_bg_enabled=False, text_bg_color=(255,255,255,180), text_bg_padding=20,
                 text_bg_radius=30, text_bg_width=None, text_bg_height=None,
                 bold_text=True, eng_pho_spacing=30, pho_chn_spacing=30, line_spacing=15):
    """创建一帧图片（修复ImageDraw作用域）"""
    from PIL import ImageDraw  # 显式导入确保作用域正确
    if bg_image:
        try:
            img = ImageOps.fit(bg_image.convert('RGB'), (width, height), Image.Resampling.LANCZOS)
        except Exception as e:
            st.warning(f"背景图片处理失败，使用纯色背景: {str(e)}")
            img = Image.new('RGB', (width, height), bg_color)
    else:
        img = Image.new('RGB', (width, height), bg_color)

    draw = ImageDraw.Draw(img)
    
    eng_font = get_font(eng_size, "phonetic", bold=bold_text)
    chn_font = get_font(chn_size, "chinese", bold=bold_text)
    pho_font = get_font(pho_size, "phonetic", bold=bold_text)

    eng_lines = wrap_text(english, 40)
    chn_lines = wrap_text(chinese, 20)
    pho_lines = wrap_text(phonetic, 45) if phonetic and str(phonetic).strip() else []

    total_height = 0

    # 计算英文部分高度
    for line in eng_lines:
        bbox = draw.textbbox((0,0), line, font=eng_font)
        h = bbox[3] - bbox[1]
        total_height += h
    total_height += line_spacing * (len(eng_lines)-1)

    # 计算音标部分高度
    if pho_lines and pho_lines[0].strip():
        total_height += eng_pho_spacing  # 使用可调节的英语-音标间距
        for line in pho_lines:
            bbox = draw.textbbox((0,0), line, font=pho_font)
            h = bbox[3] - bbox[1]
            total_height += h
        total_height += line_spacing * (len(pho_lines)-1)

    # 计算中文部分高度
    total_height += pho_chn_spacing  # 使用可调节的音标-中文间距
    for line in chn_lines:
        bbox = draw.textbbox((0,0), line, font=chn_font)
        h = bbox[3] - bbox[1]
        total_height += h
    total_height += line_spacing * (len(chn_lines)-1)

    # 计算起始Y坐标（垂直居中）
    start_y = (height - total_height) // 2

    # 绘制文本背景（如果启用）
    if text_bg_enabled:
        # 计算文本总宽度
        max_width = 0
        
        for line in eng_lines:
            bbox = draw.textbbox((0,0), line, font=eng_font)
            w = bbox[2] - bbox[0]
            max_width = max(max_width, w)
            
        if pho_lines and pho_lines[0].strip():
            for line in pho_lines:
                bbox = draw.textbbox((0,0), line, font=pho_font)
                w = bbox[2] - bbox[0]
                max_width = max(max_width, w)
                
        for line in chn_lines:
            bbox = draw.textbbox((0,0), line, font=chn_font)
            w = bbox[2] - bbox[0]
            max_width = max(max_width, w)
        
        # 应用背景宽度限制
        if text_bg_width:
            max_width = min(max_width, text_bg_width)
            
        # 计算背景位置和大小
        bg_x = (width - max_width) // 2 - text_bg_padding
        bg_y = start_y - text_bg_padding
        bg_w = max_width + 2 * text_bg_padding
        bg_h = total_height + 2 * text_bg_padding
        
        # 限制背景高度
        if text_bg_height:
            bg_h = min(bg_h, text_bg_height + 2 * text_bg_padding)
        
        # 绘制圆角矩形背景
        draw_rgba = ImageDraw.Draw(img, "RGBA")
        draw_rgba.rounded_rectangle(
            [bg_x, bg_y, bg_x + bg_w, bg_y + bg_h],
            radius=text_bg_radius,
            fill=text_bg_color
        )
        draw = ImageDraw.Draw(img)  # 切换回非RGBA绘制

    # 绘制英文
    current_y = start_y
    for line in eng_lines:
        bbox = draw.textbbox((0,0), line, font=eng_font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (width - w) // 2
        draw.text((x, current_y), line, font=eng_font, fill=eng_color)
        current_y += h + line_spacing

    # 绘制音标
    if pho_lines and pho_lines[0].strip():
        current_y += eng_pho_spacing - line_spacing  # 减去额外的line_spacing
        for line in pho_lines:
            bbox = draw.textbbox((0,0), line, font=pho_font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            x = (width - w) // 2
            draw.text((x, current_y), line, font=pho_font, fill=pho_color)
            current_y += h + line_spacing

    # 绘制中文
    current_y += pho_chn_spacing - line_spacing  # 减去额外的line_spacing
    for line in chn_lines:
        bbox = draw.textbbox((0,0), line, font=chn_font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (width - w) // 2
        draw.text((x, current_y), line, font=chn_font, fill=chn_color)
        current_y += h + line_spacing

    return img

# 生成音频函数（使用edge-tts）
async def generate_audio(text, voice, rate, output_path):
    try:
        # 过滤空文本
        text = text.strip()
        if not text:
            st.warning("音频文本为空，生成静音文件")
            # 创建一个空的MP3文件（实际可播放的静音文件）
            import wave
            import struct
            with wave.open(output_path, 'w') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(struct.pack('h', 0))
            return True
            
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_path)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        st.error(f"音频生成失败，文件为空: {output_path}")
        return False
    except Exception as e:
        st.error(f"音频生成错误: {str(e)}")
        return False

# 生成视频函数（增强版，修复路径和错误处理）
def generate_video(frames_dir, audio_path, output_path, fps=1, ffmpeg_path=None):
    if not ffmpeg_path:
        ffmpeg_path = check_ffmpeg()
        if not ffmpeg_path:
            return None
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)
    
    # 检查输入文件是否存在
    if not os.path.exists(audio_path):
        st.error(f"音频文件不存在: {audio_path}")
        return None
    
    # 检查音频文件大小
    if os.path.getsize(audio_path) == 0:
        st.warning("音频文件为空，将生成无声视频")
        # 创建一个1秒的静音音频避免FFmpeg错误
        import wave
        import struct
        with wave.open(audio_path, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(struct.pack('h', 0) * 16000)
    
    # 检查帧目录是否存在且有文件
    frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith(('.png', '.jpg', '.jpeg'))])
    if not frame_files:
        st.error(f"未找到帧图片文件在目录: {frames_dir}")
        return None
    
    # 验证帧文件命名格式
    try:
        # 检查是否是数字命名
        frame_numbers = []
        for f in frame_files:
            filename = os.path.splitext(f)[0]
            if filename.isdigit():
                frame_numbers.append(int(filename))
        
        if not frame_numbers:
            st.warning("帧文件命名不符合数字格式，重新命名...")
            # 重新命名帧文件为0001.png, 0002.png格式
            for i, f in enumerate(frame_files):
                ext = os.path.splitext(f)[1]
                new_name = f"{i+1:04d}{ext}"
                os.rename(os.path.join(frames_dir, f), os.path.join(frames_dir, new_name))
    except Exception as e:
        st.warning(f"帧文件重命名失败: {str(e)}")
        return None
        
    # 构建FFmpeg命令（使用绝对路径）
    frame_pattern = os.path.abspath(os.path.join(frames_dir, "%04d.png"))
    audio_path = os.path.abspath(audio_path)
    output_path = os.path.abspath(output_path)
    
    cmd = [
        ffmpeg_path, '-y',  # 覆盖输出文件
        '-framerate', str(fps),
        '-i', frame_pattern,
        '-i', audio_path,
        '-c:v', 'libx264',
        '-preset', 'fast',  # 平衡速度和质量
        '-crf', '23',  # 质量参数，越低越好
        '-c:a', 'aac',
        '-b:a', '192k',  # 音频比特率
        '-shortest',  # 以较短的为准（音频或视频）
        '-pix_fmt', 'yuv420p',  # 兼容所有播放器
        output_path
    ]
    
    # 执行命令并捕获输出
    try:
        st.info(f"FFmpeg命令: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        # 检查是否有错误
        if result.returncode != 0:
            st.error(f"FFmpeg执行错误 (代码 {result.returncode}):")
            st.code(result.stderr, language="text")
            return None
            
        # 验证输出文件是否存在
        if not os.path.exists(output_path):
            st.error(f"视频文件未生成，FFmpeg输出: {result.stderr}")
            return None
            
        if os.path.getsize(output_path) < 1024:  # 小于1KB视为失败
            st.error(f"生成的视频文件过小（{os.path.getsize(output_path)}字节），可能损坏")
            return None
            
        st.success(f"视频生成成功，文件大小: {os.path.getsize(output_path)/1024/1024:.2f}MB")
        return output_path
    except subprocess.TimeoutExpired:
        st.error("FFmpeg执行超时")
        return None
    except subprocess.CalledProcessError as e:
        st.error(f"FFmpeg执行错误: {e.stderr}")
        return None
    except Exception as e:
        st.error(f"视频生成过程中发生错误: {str(e)}")
        return None

# 主视频生成流程
def main_generate_process(data, settings):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # 1. 准备临时目录
        status_text.text("正在准备临时目录...")
        temp_dir = create_temp_dir()
        frames_dir = os.path.join(temp_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        progress_bar.progress(10)
        
        # 2. 生成音频
        status_text.text("正在生成音频...")
        audio_path = os.path.join(temp_dir, "audio.mp3")
        
        if EDGE_TTS_AVAILABLE and settings.get('use_audio', True):
            full_text = "\n".join([str(row['英语']).strip() for _, row in data.iterrows() if str(row['英语']).strip()])
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(generate_audio(
                full_text,
                settings.get('voice', 'en-US-JennyNeural'),
                settings.get('rate', '+0%'),
                audio_path
            ))
            loop.close()
            
            if not success:
                st.warning("音频生成失败，将生成无声视频")
        else:
            # 创建一个1秒的静音音频
            import wave
            import struct
            with wave.open(audio_path, 'w') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(struct.pack('h', 0) * 16000)
        progress_bar.progress(30)
        
        # 3. 生成帧图片
        status_text.text("正在生成帧图片...")
        valid_rows = data[(data['英语'].notna()) & (data['英语'].str.strip() != '')]
        if valid_rows.empty:
            st.error("没有有效的英语文本数据，无法生成视频")
            return None
            
        for i, (_, row) in enumerate(valid_rows.iterrows()):
            try:
                frame = create_frame(
                    english=str(row.get('英语', '')),
                    chinese=str(row.get('中文', '')),
                    phonetic=str(row.get('音标', '')),
                    width=settings.get('width', 1920),
                    height=settings.get('height', 1080),
                    bg_color=settings.get('bg_color', (0,0,0)),
                    bg_image=st.session_state.bg_image,
                    eng_color=settings.get('eng_color', (255,255,255)),
                    chn_color=settings.get('chn_color', (173,216,230)),
                    pho_color=settings.get('pho_color', (255,255,0)),
                    eng_size=settings.get('eng_size', 80),
                    chn_size=settings.get('chn_size', 60),
                    pho_size=settings.get('pho_size', 50),
                    text_bg_enabled=settings.get('text_bg_enabled', False),
                    text_bg_color=settings.get('text_bg_color', (255,255,255,180)),
                    text_bg_padding=settings.get('text_bg_padding', 20),
                    text_bg_radius=settings.get('text_bg_radius', 30),
                    bold_text=settings.get('bold_text', True)
                )
                frame_path = os.path.join(frames_dir, f"{i+1:04d}.png")
                frame.save(frame_path, quality=95)
                
                # 验证帧文件是否保存成功
                if not os.path.exists(frame_path) or os.path.getsize(frame_path) == 0:
                    st.error(f"帧图片保存失败: {frame_path}")
                    return None
                
                # 更新进度
                frame_progress = 30 + int(30 * (i + 1) / len(valid_rows))
                progress_bar.progress(min(frame_progress, 60))
            except Exception as e:
                st.error(f"生成第{i+1}帧时出错: {str(e)}")
                return None
        
        progress_bar.progress(60)
        
        # 4. 合成视频
        status_text.text("正在合成视频...")
        output_path = os.path.join(temp_dir, "output.mp4")
        video_path = generate_video(
            frames_dir=frames_dir,
            audio_path=audio_path,
            output_path=output_path,
            fps=settings.get('fps', 1)
        )
        
        if video_path and os.path.exists(video_path):
            progress_bar.progress(90)
            status_text.text("视频生成成功!")
            st.session_state.generated_video = video_path
            progress_bar.progress(100)
            return video_path
        else:
            status_text.text("视频生成失败")
            return None
            
    except Exception as e:
        status_text.text(f"发生错误: {str(e)}")
        st.error(traceback.format_exc())
        cleanup_temp_files()
        return None

# 页面内容
def main():
    st.markdown('<h1 class="main-header">旅行英语视频生成器</h1>', unsafe_allow_html=True)
    
    # 检查FFmpeg
    ffmpeg_available = check_ffmpeg() is not None
    if not ffmpeg_available:
        st.warning("⚠️ FFmpeg未正确配置，视频生成功能可能无法使用")
    
    # 侧边栏设置
    with st.sidebar:
        st.markdown('<h3 class="section-header">设置</h3>', unsafe_allow_html=True)
        
        # 上传Excel文件
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("上传Excel文件", type=["xlsx", "xls"])
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 背景设置
        st.markdown('<h4 class="section-header">背景设置</h4>', unsafe_allow_html=True)
        bg_option = st.radio("背景类型", ["纯色", "图片"])
        bg_color = (0, 0, 0)
        if bg_option == "纯色":
            bg_color_hex = st.color_picker("选择背景颜色", "#000000")
            # 转换为RGB
            try:
                bg_color = tuple(int(bg_color_hex[i:i+2], 16) for i in (1, 3, 5))
            except:
                bg_color = (0, 0, 0)
                st.warning("颜色格式错误，使用默认黑色")
            st.session_state.bg_image = None
        else:
            bg_image = st.file_uploader("上传背景图片", type=["jpg", "jpeg", "png"])
            if bg_image:
                try:
                    st.session_state.bg_image = Image.open(bg_image)
                    st.image(st.session_state.bg_image, caption="背景预览", use_column_width=True)
                except Exception as e:
                    st.error(f"图片加载失败: {str(e)}")
                    st.session_state.bg_image = None
        
        # 文本设置
        st.markdown('<h4 class="section-header">文本设置</h4>', unsafe_allow_html=True)
        eng_size = st.slider("英语字体大小", 20, 120, 80)
        pho_size = st.slider("音标字体大小", 10, 80, 50)
        chn_size = st.slider("中文字体大小", 20, 100, 60)
        
        eng_color_hex = st.color_picker("英语颜色", "#FFFFFF")
        try:
            eng_color = tuple(int(eng_color_hex[i:i+2], 16) for i in (1, 3, 5))
        except:
            eng_color = (255, 255, 255)
        
        pho_color_hex = st.color_picker("音标颜色", "#FFFF00")
        try:
            pho_color = tuple(int(pho_color_hex[i:i+2], 16) for i in (1, 3, 5))
        except:
            pho_color = (255, 255, 0)
        
        chn_color_hex = st.color_picker("中文颜色", "#ADD8E6")
        try:
            chn_color = tuple(int(chn_color_hex[i:i+2], 16) for i in (1, 3, 5))
        except:
            chn_color = (173, 216, 230)
        
        bold_text = st.checkbox("粗体文本", value=True)
        
        # 文本背景设置
        text_bg_enabled = st.checkbox("启用文本背景", value=False)
        text_bg_color = (255, 255, 255, 180)
        if text_bg_enabled:
            text_bg_color_hex = st.color_picker("文本背景颜色", "#FFFFFF")
            text_bg_alpha = st.slider("背景透明度", 0, 255, 180)
            try:
                text_bg_color = tuple(int(text_bg_color_hex[i:i+2], 16) for i in (1, 3, 5)) + (text_bg_alpha,)
            except:
                text_bg_color = (255, 255, 255, 180)
            text_bg_padding = st.slider("背景内边距", 5, 50, 20)
            text_bg_radius = st.slider("背景圆角", 0, 50, 30)
        else:
            text_bg_padding = 20
            text_bg_radius = 30
        
        # 音频设置
        st.markdown('<h4 class="section-header">音频设置</h4>', unsafe_allow_html=True)
        use_audio = st.checkbox("启用音频", value=EDGE_TTS_AVAILABLE)
        if EDGE_TTS_AVAILABLE and use_audio:
            voices = [
                "en-US-JennyNeural", "en-US-GuyNeural",
                "en-GB-SoniaNeural", "en-GB-RyanNeural",
                "en-AU-NatashaNeural", "en-AU-WilliamNeural"
            ]
            voice = st.selectbox("选择语音", voices)
            rate = st.slider("语速 (%)", -50, 50, 0)
            rate_str = f"+{rate}%" if rate >= 0 else f"{rate}%"
        else:
            voice = "en-US-JennyNeural"
            rate_str = "+0%"
            if not EDGE_TTS_AVAILABLE:
                st.warning("edge-tts未安装，无法生成音频")
        
        # 视频设置
        st.markdown('<h4 class="section-header">视频设置</h4>', unsafe_allow_html=True)
        resolutions = {
            "1080p (1920x1080)": (1920, 1080),
            "720p (1280x720)": (1280, 720),
            "480p (854x480)": (854, 480)
        }
        resolution = st.selectbox("分辨率", list(resolutions.keys()))
        width, height = resolutions[resolution]
        fps = st.slider("帧率 (每秒帧数)", 1, 10, 1)
        
        # 生成按钮
        st.markdown('<div style="margin-top: 2rem;">', unsafe_allow_html=True)
        generate_btn = st.button("生成视频")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 清理临时文件按钮
        if st.button("清理临时文件"):
            cleanup_temp_files()
            st.success("临时文件已清理")
    
    # 主内容区
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            required_columns = ['英语', '中文']
            if not all(col in df.columns for col in required_columns):
                st.error("Excel文件必须包含 '英语' 和 '中文' 列")
            else:
                # 添加缺失的'音标'列
                if '音标' not in df.columns:
                    df['音标'] = ''
                
                # 清理空行
                df = df.dropna(subset=['英语'])
                df = df[df['英语'].str.strip() != '']
                
                st.markdown('<h3 class="section-header">数据预览</h3>', unsafe_allow_html=True)
                st.dataframe(df)
                
                # 预览第一帧
                st.markdown('<h3 class="section-header">第一帧预览</h3>', unsafe_allow_html=True)
                if not df.empty:
                    first_row = df.iloc[0]
                    preview_frame = create_frame(
                        english=str(first_row['英语']),
                        chinese=str(first_row['中文']),
                        phonetic=str(first_row.get('音标', '')),
                        width=width,
                        height=height,
                        bg_color=bg_color,
                        bg_image=st.session_state.bg_image,
                        eng_color=eng_color,
                        chn_color=chn_color,
                        pho_color=pho_color,
                        eng_size=eng_size,
                        chn_size=chn_size,
                        pho_size=pho_size,
                        text_bg_enabled=text_bg_enabled,
                        text_bg_color=text_bg_color,
                        text_bg_padding=text_bg_padding,
                        text_bg_radius=text_bg_radius,
                        bold_text=bold_text
                    )
                    st.image(preview_frame, caption="第一帧预览", use_column_width=True)
                
                # 生成视频
                if generate_btn:
                    if not ffmpeg_available:
                        st.error("FFmpeg未正确配置，无法生成视频")
                        continue
                    
                    settings = {
                        'width': width,
                        'height': height,
                        'bg_color': bg_color,
                        'eng_color': eng_color,
                        'chn_color': chn_color,
                        'pho_color': pho_color,
                        'eng_size': eng_size,
                        'chn_size': chn_size,
                        'pho_size': pho_size,
                        'text_bg_enabled': text_bg_enabled,
                        'text_bg_color': text_bg_color,
                        'text_bg_padding': text_bg_padding,
                        'text_bg_radius': text_bg_radius,
                        'bold_text': bold_text,
                        'use_audio': use_audio and EDGE_TTS_AVAILABLE,
                        'voice': voice,
                        'rate': rate_str,
                        'fps': fps
                    }
                    
                    video_path = main_generate_process(df, settings)
                    
                    if video_path and os.path.exists(video_path):
                        st.markdown('<div class="success-card">视频生成成功！</div>', unsafe_allow_html=True)
                        
                        # 提供下载
                        with open(video_path, "rb") as f:
                            video_bytes = f.read()
                        st.download_button(
                            label="下载视频",
                            data=video_bytes,
                            file_name="travel_english_video.mp4",
                            mime="video/mp4"
                        )
                        
                        # 视频预览
                        st.markdown('<h3 class="section-header">视频预览</h3>', unsafe_allow_html=True)
                        st.video(video_path)
        except Exception as e:
            st.error(f"处理文件时出错: {str(e)}")
            st.error(traceback.format_exc())
            cleanup_temp_files()
    else:
        st.markdown('<div class="info-card">请在左侧上传包含"英语"和"中文"列的Excel文件开始生成视频</div>', unsafe_allow_html=True)
        # 找到对应的markdown块，确保三引号正确闭合
        st.markdown("""
        ### 使用说明
        1. 准备Excel文件，包含以下列：
       - 英语：需要显示的英文文本
       - 中文：对应的中文翻译
       - 音标（可选）：英文的音标

        2. 配置视频参数，包括背景、字体大小、颜色等

        3. 点击"生成视频"按钮开始生成

        4. 生成完成后可下载视频文件

        ### 依赖安装
        如果运行出错，请先安装依赖：
        ```bash
        pip install streamlit pandas pillow imageio edge-tts openpyxl

