import streamlit as st
import pandas as pd
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio
import tempfile
import shutil
from pydub import AudioSegment
import subprocess
import traceback

# 尝试导入 gTTS（如果没有安装则禁用语音功能）
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except Exception:
    GTTS_AVAILABLE = False

# 页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide"
)

# 初始化会话状态
if 'bg_image' not in st.session_state:
    st.session_state.bg_image = None
if 'audio_available' not in st.session_state:
    # 只有在 gTTS 可用并且本机/部署环境允许外网请求时才可能真正可用
    st.session_state.audio_available = GTTS_AVAILABLE


# --------------------------
# 工具函数
# --------------------------
def check_ffmpeg():
    """检查ffmpeg是否可用"""
    return shutil.which('ffmpeg') is not None


def wrap_text(text, max_chars):
    """文本自动换行处理"""
    if not text or str(text).strip().lower() == 'nan':
        return [""]

    text = str(text).strip()
    # 中文适配：减少每行字符数
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
            # 处理超长单词
            if len(word) > max_chars:
                for i in range(0, len(word), max_chars):
                    lines.append(word[i:i + max_chars])
                current = []
            else:
                current = [word]
    if current:
        lines.append(' '.join(current))
    return lines


def get_font(size):
    """获取字体（兼容不同环境）"""
    try:
        # 尝试常见中文/通用字体
        for font_name in ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "Arial Unicode MS", "NotoSansCJK-Regular.ttc"]:
            try:
                return ImageFont.truetype(font_name, size)
            except Exception:
                continue
        # 默认
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()


def create_frame(english, chinese, phonetic, width=1280, height=720,
                 bg_color=(0, 0, 0), bg_image=None,
                 eng_color=(255, 255, 255), chn_color=(0, 255, 255), pho_color=(255, 255, 0),
                 eng_size=60, chn_size=50, pho_size=40):
    """创建单帧图像（文字居中显示）
    顺序：英语（上） -> 音标（中） -> 中文（下）
    """
    # 背景
    if bg_image:
        try:
            img = bg_image.resize((width, height), Image.Resampling.LANCZOS).convert('RGB')
        except Exception:
            img = Image.new('RGB', (width, height), bg_color)
    else:
        img = Image.new('RGB', (width, height), bg_color)

    draw = ImageDraw.Draw(img)
    eng_font = get_font(eng_size)
    chn_font = get_font(chn_size)
    pho_font = get_font(pho_size)

    # 文本换行
    eng_lines = wrap_text(english, 30)
    chn_lines = wrap_text(chinese, 15)
    pho_lines = wrap_text(phonetic, 35) if phonetic else []

    # 计算总高度（英语 -> 音标 -> 中文）
    line_spacing = 10
    total_height = 0

    # 英语高度
    for line in eng_lines:
        _, _, _, h = draw.textbbox((0, 0), line, font=eng_font)
        total_height += h
    total_height += line_spacing * (len(eng_lines) - 1)

    # 音标高度
    if pho_lines:
        total_height += 20  # 段落间距
        for line in pho_lines:
            _, _, _, h = draw.textbbox((0, 0), line, font=pho_font)
            total_height += h
        total_height += line_spacing * (len(pho_lines) - 1)

    # 中文高度
    if chn_lines:
        total_height += 20
        for line in chn_lines:
            _, _, _, h = draw.textbbox((0, 0), line, font=chn_font)
            total_height += h
        total_height += line_spacing * (len(chn_lines) - 1)

    # 起始 y（垂直居中）
    y = (height - total_height) // 2

    # 绘制英语
    for line in eng_lines:
        w, h = draw.textbbox((0, 0), line, font=eng_font)[2:]
        x = (width - w) // 2
        # 阴影增强可读性
        draw.text((x + 1, y + 1), line, font=eng_font, fill=(0, 0, 0, 128))
        draw.text((x, y), line, font=eng_font, fill=eng_color)
        y += h + line_spacing

    # 绘制音标（放在英语下）
    if pho_lines:
        y += 10
        for line in pho_lines:
            w, h = draw.textbbox((0, 0), line, font=pho_font)[2:]
            x = (width - w) // 2
            draw.text((x + 1, y + 1), line, font=pho_font, fill=(0, 0, 0, 128))
            draw.text((x, y), line, font=pho_font, fill=pho_color)
            y += h + line_spacing

    # 绘制中文（放在音标下）
    if chn_lines:
        y += 10
        for line in chn_lines:
            w, h = draw.textbbox((0, 0), line, font=chn_font)[2:]
            x = (width - w) // 2
            draw.text((x + 1, y + 1), line, font=chn_font, fill=(0, 0, 0, 128))
            draw.text((x, y), line, font=chn_font, fill=chn_color)
            y += h + line_spacing

    return img


def generate_audio(text, lang='en', speed=1.0):
    """生成TTS音频；若 gTTS 不可用则返回 None（不抛异常）"""
    if not st.session_state.audio_available or not GTTS_AVAILABLE:
        return None
    try:
        # gTTS 的 slow 参数是布尔：True -> 慢速；这里我们把 speed<0.9 视为慢速
        tts = gTTS(text=text, lang=lang, slow=speed < 0.9)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tts.save(f.name)
            return f.name
    except Exception as e:
        # 出错时禁用后续音频生成并显示警告
        st.warning(f"音频生成失败（已禁用音频功能）：{e}")
        st.session_state.audio_available = False
        return None


def merge_audio_files(audio_paths, target_duration):
    """合并音频并匹配每句时长（秒）"""
    combined = AudioSegment.empty()
    for path in audio_paths:
        if not path:
            # 如果某句没有音频（生成失败或不可用），补静音
            silence = AudioSegment.silent(duration=int(target_duration * 1000))
            combined += silence
            continue
        try:
            audio = AudioSegment.from_mp3(path)
            if len(audio) > target_duration * 1000:
                audio = audio[:int(target_duration * 1000)]
            else:
                silence = AudioSegment.silent(duration=int(target_duration * 1000) - len(audio))
                audio += silence
            combined += audio
            # 清理临时文件
            try:
                os.remove(path)
            except Exception:
                pass
        except Exception as e:
            st.warning(f"处理音频片段失败：{e}")
            silence = AudioSegment.silent(duration=int(target_duration * 1000))
            combined += silence
    return combined


def merge_video_audio(video_path, audio_path, output_path):
    """用 ffmpeg 合并音视频流（需要系统安装 ffmpeg）"""
    if not check_ffmpeg():
        st.error("未找到 ffmpeg，无法合并音视频（请安装 ffmpeg）。")
        return None

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', audio_path,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-strict', 'experimental',
        output_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            st.error(f"ffmpeg 错误：{result.stderr}")
            return None
        return output_path
    except Exception as e:
        st.error(f"合并音视频失败：{e}")
        return None


# --------------------------
# Streamlit UI
# --------------------------
st.title("🎬 旅游英语视频生成器")
st.markdown("生成包含英语、音标和中文的带音频视频（支持颜色/字号/背景/语速）")

# gTTS 状态提示
if GTTS_AVAILABLE:
    st.info("检测到 gTTS：语音功能可用（如果网络和环境允许）。")
else:
    st.warning("未检测到 gTTS：语音功能已禁用。如需启用，请在 shell 中运行 `pip install gTTS`，然后重启程序。")

# 检查 ffmpeg
if not check_ffmpeg():
    st.warning("⚠️ 未检测到 ffmpeg。若需要视频带音频，请安装 ffmpeg 并确保命令行可用（ffmpeg -version）。")

# 上传文件
st.header("1. 上传Excel文件")
uploaded_file = st.file_uploader("选择Excel文件（必须包含列：英语、中文、音标）", type=['xlsx', 'xls'])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        required_cols = ['英语', '中文', '音标']
        missing = [c for c in required_cols if c not in df.columns]

        if missing:
            st.error(f"Excel 缺少必要列: {', '.join(missing)}")
        else:
            st.success("文件上传成功！")
            st.dataframe(df, height=200)

            # 自定义设置
            st.header("2. 自定义设置")

            # 背景设置
            bg_type = st.radio("背景类型", ["纯色", "图片"])
            bg_color = (0, 0, 0)
            if bg_type == "纯色":
                bg_hex = st.color_picker("背景颜色", "#000000")
                bg_color = tuple(int(bg_hex[i:i + 2], 16) for i in (1, 3, 5))
                st.session_state.bg_image = None
            else:
                bg_file = st.file_uploader("上传背景图片", type=['jpg', 'jpeg', 'png'])
                if bg_file:
                    try:
                        st.session_state.bg_image = Image.open(bg_file)
                        st.image(st.session_state.bg_image, caption="背景预览", width=300)
                    except Exception as e:
                        st.error(f"背景图片处理失败：{e}")
                        st.session_state.bg_image = None

            # 文字样式
            st.subheader("文字样式")
            col1, col2, col3 = st.columns(3)
            with col1:
                eng_color = st.color_picker("英语颜色", "#FFFFFF")
                eng_color = tuple(int(eng_color[i:i + 2], 16) for i in (1, 3, 5))
                eng_size = st.slider("英语字号", 20, 100, 60)
            with col2:
                pho_color = st.color_picker("音标颜色", "#FFFF00")
                pho_color = tuple(int(pho_color[i:i + 2], 16) for i in (1, 3, 5))
                pho_size = st.slider("音标字号", 16, 80, 40)
            with col3:
                chn_color = st.color_picker("中文颜色", "#00FFFF")
                chn_color = tuple(int(chn_color[i:i + 2], 16) for i in (1, 3, 5))
                chn_size = st.slider("中文字号", 20, 100, 50)

            # 视频与音频设置
            st.subheader("视频与音频")
            col4, col5 = st.columns(2)
            with col4:
                duration = st.slider("每句显示时间(秒)", 2, 10, 5)
                fps = st.slider("帧率", 10, 30, 24)
            with col5:
                tts_lang = st.selectbox("语音语言", ["英语", "中文"])
                tts_speed = st.slider("语音速度", 0.5, 2.0, 1.0)
                tts_lang_code = "en" if tts_lang == "英语" else "zh-CN"

            # 预览
            st.header("3. 预览效果")
            if not df.empty:
                preview_idx = st.slider("选择预览行", 0, len(df) - 1, 0)
                row = df.iloc[preview_idx]
                preview_img = create_frame(
                    english=str(row['英语']),
                    chinese=str(row['中文']),
                    phonetic=str(row['音标']) if pd.notna(row['音标']) else "",
                    bg_color=bg_color,
                    bg_image=st.session_state.bg_image,
                    eng_color=eng_color,
                    chn_color=chn_color,
                    pho_color=pho_color,
                    eng_size=eng_size,
                    chn_size=chn_size,
                    pho_size=pho_size
                )
                st.image(preview_img, caption="帧预览")

            # 生成视频
            st.header("4. 生成视频")
            if st.button("开始生成", type="primary"):
                with st.spinner("正在生成视频...（建议先用少量行和较低帧率测试）"):
                    try:
                        with tempfile.TemporaryDirectory() as temp_dir:
                            frames = []
                            audio_paths = []
                            total_frames = len(df) * duration * fps
                            progress = st.progress(0)
                            current = 0

                            # 逐行生成帧与音频（帧重复以达到时长）
                            for idx, row in df.iterrows():
                                frame = create_frame(
                                    english=str(row['英语']),
                                    chinese=str(row['中文']),
                                    phonetic=str(row['音标']) if pd.notna(row['音标']) else "",
                                    bg_color=bg_color,
                                    bg_image=st.session_state.bg_image,
                                    eng_color=eng_color,
                                    chn_color=chn_color,
                                    pho_color=pho_color,
                                    eng_size=eng_size,
                                    chn_size=chn_size,
                                    pho_size=pho_size
                                )
                                for _ in range(duration * fps):
                                    frames.append(np.array(frame.convert('RGB')))

                                # 生成音频（如果可用）
                                if st.session_state.audio_available:
                                    audio_path = generate_audio(
                                        text=str(row['英语']),
                                        lang=tts_lang_code,
                                        speed=tts_speed
                                    )
                                    audio_paths.append(audio_path)
                                else:
                                    audio_paths.append(None)

                                current += duration * fps
                                progress.progress(min(current / total_frames, 1.0))

                            # 保存无音频视频（临时）
                            video_path = os.path.join(temp_dir, "video_no_audio.mp4")
                            imageio.mimsave(video_path, frames, fps=fps)

                            final_video_path = video_path
                            # 如果音频可用且 ffmpeg 可用，合并音频
                            if st.session_state.audio_available and any(p is not None for p in audio_paths):
                                combined_audio = merge_audio_files(audio_paths, duration)
                                audio_path = os.path.join(temp_dir, "combined_audio.mp3")
                                combined_audio.export(audio_path, format="mp3")

                                final_video_path = os.path.join(temp_dir, "video_with_audio.mp4")
                                if not merge_video_audio(video_path, audio_path, final_video_path):
                                    final_video_path = video_path

                            # 读取并提供下载
                            with open(final_video_path, "rb") as f:
                                video_bytes = f.read()

                            st.success("✅ 视频生成完成！")
                            st.video(video_bytes)
                            st.download_button(
                                "下载视频",
                                data=video_bytes,
                                file_name="travel_english_video.mp4",
                                mime="video/mp4"
                            )
                            progress.progress(1.0)

                    except Exception as e:
                        st.error(f"生成失败: {str(e)}")
                        st.text(traceback.format_exc())

    except Exception as e:
        st.error(f"文件处理错误: {str(e)}")
else:
    st.info("请先上传包含 '英语'、'中文'、'音标' 三列的 Excel 文件")
