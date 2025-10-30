import streamlit as st
import pandas as pd
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio
import tempfile
import shutil
from gtts import gTTS
from pydub import AudioSegment
import subprocess
import traceback
import base64

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
    st.session_state.audio_available = True

# --------------------------
# 核心功能函数
# --------------------------
def check_ffmpeg():
    """检查ffmpeg是否可用"""
    return shutil.which('ffmpeg') is not None

def get_font_path():
    """获取可用的字体路径"""
    # 常见系统中文字体路径
    font_paths = [
        # Windows
        "C:/Windows/Fonts/simhei.ttf",  # 黑体
        "C:/Windows/Fonts/simsun.ttc",  # 宋体
        # Linux
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        # macOS
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            return path
    
    # 如果都找不到，尝试加载默认字体
    try:
        return ImageFont.load_default()
    except:
        return None

def get_font(size):
    """获取字体（兼容不同环境）"""
    font_path = get_font_path()
    try:
        if font_path and isinstance(font_path, str):
            return ImageFont.truetype(font_path, size)
        else:
            # 使用默认字体
            return ImageFont.load_default().font_variant(size=size)
    except:
        try:
            return ImageFont.load_default()
        except:
            # 最后备选方案
            class DefaultFont:
                def getbbox(self, text):
                    return (0, 0, len(text) * size // 2, size)
            return DefaultFont()

def wrap_text(text, max_chars):
    """文本自动换行处理"""
    if not text or str(text).strip().lower() in ['nan', 'none', '']:
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
                    lines.append(word[i:i+max_chars])
                current = []
            else:
                current = [word]
    
    if current:
        lines.append(' '.join(current))
    
    return lines if lines else [""]

def create_frame(english, chinese, phonetic, width=1280, height=720, 
                bg_color=(0,0,0), bg_image=None,
                eng_color=(255,255,255), chn_color=(0,255,255), pho_color=(255,255,0),
                eng_size=60, chn_size=50, pho_size=40):
    """创建单帧图像（文字居中显示）"""
    # 创建背景
    if bg_image and hasattr(bg_image, 'resize'):
        try:
            img = bg_image.resize((width, height), Image.Resampling.LANCZOS).convert('RGB')
        except:
            img = Image.new('RGB', (width, height), bg_color)
    else:
        img = Image.new('RGB', (width, height), bg_color)
    
    draw = ImageDraw.Draw(img)
    
    # 获取字体
    eng_font = get_font(eng_size)
    chn_font = get_font(chn_size)
    pho_font = get_font(pho_size)
    
    # 文本换行处理
    eng_lines = wrap_text(english, 30)
    chn_lines = wrap_text(chinese, 15)
    pho_lines = wrap_text(phonetic, 35) if phonetic and str(phonetic).strip().lower() not in ['nan', 'none', ''] else []
    
    # 计算文本总高度
    line_spacing = 10
    total_height = 0
    
    # 计算英语文本高度
    for line in eng_lines:
        try:
            bbox = eng_font.getbbox(line) if hasattr(eng_font, 'getbbox') else (0, 0, len(line) * eng_size // 2, eng_size)
            total_height += bbox[3] - bbox[1]
        except:
            total_height += eng_size
    
    total_height += line_spacing * max(0, len(eng_lines) - 1)
    
    # 计算中文文本高度
    if chn_lines:
        total_height += 20  # 段落间距
        for line in chn_lines:
            try:
                bbox = chn_font.getbbox(line) if hasattr(chn_font, 'getbbox') else (0, 0, len(line) * chn_size // 2, chn_size)
                total_height += bbox[3] - bbox[1]
            except:
                total_height += chn_size
        total_height += line_spacing * max(0, len(chn_lines) - 1)
    
    # 计算音标文本高度
    if pho_lines:
        total_height += 15  # 段落间距
        for line in pho_lines:
            try:
                bbox = pho_font.getbbox(line) if hasattr(pho_font, 'getbbox') else (0, 0, len(line) * pho_size // 2, pho_size)
                total_height += bbox[3] - bbox[1]
            except:
                total_height += pho_size
        total_height += line_spacing * max(0, len(pho_lines) - 1)
    
    # 计算起始Y坐标（垂直居中）
    y = (height - total_height) // 2
    
    # 绘制英语
    for line in eng_lines:
        try:
            bbox = eng_font.getbbox(line) if hasattr(eng_font, 'getbbox') else (0, 0, len(line) * eng_size // 2, eng_size)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except:
            w, h = len(line) * eng_size // 2, eng_size
            
        x = (width - w) // 2
        # 文本阴影（增强可读性）
        shadow_color = (0, 0, 0, 128)
        try:
            draw.text((x+2, y+2), line, font=eng_font, fill=shadow_color)
            draw.text((x, y), line, font=eng_font, fill=eng_color)
        except:
            # 如果字体绘制失败，使用基本绘制
            draw.rectangle([x, y, x+w, y+h], fill=bg_color)
            draw.text((x, y), line, fill=eng_color)
        
        y += h + line_spacing
    
    # 绘制中文
    if chn_lines:
        y += 10  # 段落间距
        for line in chn_lines:
            try:
                bbox = chn_font.getbbox(line) if hasattr(chn_font, 'getbbox') else (0, 0, len(line) * chn_size // 2, chn_size)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except:
                w, h = len(line) * chn_size // 2, chn_size
                
            x = (width - w) // 2
            try:
                draw.text((x+2, y+2), line, font=chn_font, fill=shadow_color)
                draw.text((x, y), line, font=chn_font, fill=chn_color)
            except:
                draw.rectangle([x, y, x+w, y+h], fill=bg_color)
                draw.text((x, y), line, fill=chn_color)
            
            y += h + line_spacing
    
    # 绘制音标
    if pho_lines:
        y += 5  # 段落间距
        for line in pho_lines:
            try:
                bbox = pho_font.getbbox(line) if hasattr(pho_font, 'getbbox') else (0, 0, len(line) * pho_size // 2, pho_size)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except:
                w, h = len(line) * pho_size // 2, pho_size
                
            x = (width - w) // 2
            try:
                draw.text((x+2, y+2), line, font=pho_font, fill=shadow_color)
                draw.text((x, y), line, font=pho_font, fill=pho_color)
            except:
                draw.rectangle([x, y, x+w, y+h], fill=bg_color)
                draw.text((x, y), line, fill=pho_color)
            
            y += h + line_spacing
    
    return img

def generate_audio(text, lang='en', speed=1.0):
    """生成TTS音频"""
    try:
        if not text or str(text).strip().lower() in ['nan', 'none', '']:
            return None
            
        tts = gTTS(text=str(text), lang=lang, slow=speed < 0.9)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tts.save(f.name)
            return f.name
    except Exception as e:
        st.warning(f"音频生成失败: {str(e)}")
        st.session_state.audio_available = False
        return None

def merge_audio_files(audio_paths, target_duration):
    """合并音频并匹配视频时长"""
    if not audio_paths or all(path is None for path in audio_paths):
        return None
        
    combined = AudioSegment.silent(duration=0)
    for path in audio_paths:
        if not path:
            continue
        try:
            audio = AudioSegment.from_mp3(path)
            # 确保音频时长与视频帧时长一致
            target_ms = int(target_duration * 1000)
            if len(audio) > target_ms:
                audio = audio[:target_ms]
            else:
                # 不足时补静音
                silence = AudioSegment.silent(duration=target_ms - len(audio))
                audio += silence
            combined += audio
            # 清理临时文件
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            st.warning(f"音频片段处理失败: {str(e)}")
            continue
    
    return combined if len(combined) > 0 else None

def merge_video_audio(video_path, audio_path, output_path):
    """用ffmpeg合并音视频"""
    if not check_ffmpeg():
        st.error("未找到ffmpeg，将生成无音频视频")
        return None
    
    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            return output_path
        else:
            st.warning(f"音视频合并失败，将提供无音频版本: {result.stderr[:200]}")
            return None
    except Exception as e:
        st.warning(f"音视频合并异常: {str(e)}")
        return None

def create_sample_excel():
    """创建示例Excel文件"""
    sample_data = {
        '英语': [
            "Hello, how are you?",
            "Where is the nearest restaurant?",
            "How much does this cost?",
            "Thank you very much",
            "Good morning"
        ],
        '中文': [
            "你好，最近怎么样？",
            "最近的餐厅在哪里？",
            "这个多少钱？",
            "非常感谢",
            "早上好"
        ],
        '音标': [
            "/həˈloʊ, haʊ ɑːr juː/",
            "/wer ɪz ðə ˈnɪrɪst ˈrɛstərənt/",
            "/haʊ mʌtʃ dʌz ðɪs kɒst/",
            "/θæŋk juː ˈvɛri mʌtʃ/",
            "/ɡʊd ˈmɔːrnɪŋ/"
        ]
    }
    return pd.DataFrame(sample_data)

# --------------------------
# 页面UI与逻辑
# --------------------------
st.title("🎬 旅游英语视频生成器")
st.markdown("生成包含英语句子、中文翻译和音标的带音频视频")

# 检查ffmpeg状态
if not check_ffmpeg():
    st.warning("⚠️ 未检测到ffmpeg，音频功能可能受限")

# 提供示例文件下载
st.header("📋 示例文件")
sample_df = create_sample_excel()
st.dataframe(sample_df, height=200)

# 将示例数据转换为Excel供下载
sample_excel = sample_df.to_csv(index=False).encode('utf-8')
st.download_button(
    "下载示例Excel文件",
    data=sample_excel,
    file_name="travel_english_sample.csv",
    mime="text/csv"
)

# 1. 文件上传
st.header("1. 上传Excel文件")
uploaded_file = st.file_uploader("选择Excel文件", type=['xlsx', 'xls', 'csv'])

df = None
if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        required_cols = ['英语', '中文', '音标']
        missing = [c for c in required_cols if c not in df.columns]
        
        if missing:
            st.error(f"Excel缺少必要列: {', '.join(missing)}")
            st.info("请确保文件包含以下列：英语、中文、音标")
        else:
            st.success(f"文件上传成功！共 {len(df)} 条数据")
            st.dataframe(df.head(10), height=300)
            
    except Exception as e:
        st.error(f"文件处理错误: {str(e)}")
        st.info("请检查文件格式是否正确")

if df is not None and not df.empty:
    # 2. 自定义设置
    st.header("2. 自定义设置")
    
    # 背景设置
    bg_type = st.radio("背景类型", ["纯色", "图片"])
    bg_color = (0, 0, 0)
    
    if bg_type == "纯色":
        bg_hex = st.color_picker("背景颜色", "#000000")
        bg_color = tuple(int(bg_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        st.session_state.bg_image = None
    else:
        bg_file = st.file_uploader("上传背景图片", type=['jpg', 'jpeg', 'png'])
        if bg_file:
            try:
                st.session_state.bg_image = Image.open(bg_file)
                st.image(st.session_state.bg_image, caption="背景预览", width=300)
            except Exception as e:
                st.error(f"图片处理失败: {str(e)}")
                st.session_state.bg_image = None
    
    # 文字设置
    st.subheader("文字样式")
    col1, col2, col3 = st.columns(3)
    with col1:
        eng_color_hex = st.color_picker("英语颜色", "#FFFFFF")
        eng_color = tuple(int(eng_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        eng_size = st.slider("英语字号", 20, 100, 60)
    with col2:
        chn_color_hex = st.color_picker("中文颜色", "#00FFFF")
        chn_color = tuple(int(chn_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        chn_size = st.slider("中文字号", 20, 100, 50)
    with col3:
        pho_color_hex = st.color_picker("音标颜色", "#FFFF00")
        pho_color = tuple(int(pho_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        pho_size = st.slider("音标字号", 16, 80, 40)
    
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
    
    # 3. 预览
    st.header("3. 预览效果")
    preview_idx = st.slider("选择预览行", 0, len(df)-1, 0)
    row = df.iloc[preview_idx]
    
    try:
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
        st.image(preview_img, caption=f"预览: {row['英语'][:50]}...", use_column_width=True)
    except Exception as e:
        st.error(f"预览生成失败: {str(e)}")
    
    # 4. 生成视频
    st.header("4. 生成视频")
    
    if st.button("🎬 开始生成视频", type="primary", use_container_width=True):
        with st.spinner("正在生成视频，这可能需要一些时间..."):
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    # 生成视频帧
                    frames = []
                    audio_paths = []
                    total_frames = len(df) * duration * fps
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, row in df.iterrows():
                        status_text.text(f"处理第 {idx + 1}/{len(df)} 句: {row['英语'][:30]}...")
                        
                        # 生成单帧
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
                        
                        # 重复帧以达到时长
                        for _ in range(duration * fps):
                            frames.append(np.array(frame.convert('RGB')))
                        
                        # 生成对应音频
                        if st.session_state.audio_available:
                            audio_path = generate_audio(
                                text=str(row['英语']),
                                lang=tts_lang_code,
                                speed=tts_speed
                            )
                            audio_paths.append(audio_path)
                        
                        # 更新进度
                        current_progress = min((idx + 1) / len(df), 1.0)
                        progress_bar.progress(current_progress)
                    
                    status_text.text("正在保存视频...")
                    
                    # 保存视频（无音频）
                    video_path = os.path.join(temp_dir, "video_no_audio.mp4")
                    try:
                        imageio.mimsave(video_path, frames, fps=fps, quality=8)
                    except Exception as e:
                        st.error(f"视频保存失败: {str(e)}")
                        return
                    
                    final_video_path = video_path
                    has_audio = False
                    
                    # 处理音频
                    if st.session_state.audio_available and audio_paths and any(audio_paths):
                        status_text.text("正在处理音频...")
                        combined_audio = merge_audio_files(audio_paths, duration)
                        
                        if combined_audio and len(combined_audio) > 0:
                            audio_path = os.path.join(temp_dir, "combined_audio.mp3")
                            try:
                                combined_audio.export(audio_path, format="mp3")
                                
                                # 合并音视频
                                final_video_path = os.path.join(temp_dir, "video_with_audio.mp4")
                                if merge_video_audio(video_path, audio_path, final_video_path):
                                    has_audio = True
                                    st.success("✅ 已生成带音频的视频")
                                else:
                                    st.warning("⚠️ 音频合并失败，提供无音频版本")
                            except Exception as e:
                                st.warning(f"音频处理失败: {str(e)}，提供无音频版本")
                        else:
                            st.warning("⚠️ 无有效音频生成，提供无音频版本")
                    else:
                        st.info("ℹ️ 生成无音频视频")
                    
                    # 提供下载
                    try:
                        with open(final_video_path, "rb") as f:
                            video_bytes = f.read()
                        
                        progress_bar.progress(1.0)
                        status_text.text("视频生成完成！")
                        
                        st.success("🎉 视频生成完成！")
                        
                        # 显示视频预览
                        st.video(video_bytes)
                        
                        # 下载按钮
                        file_suffix = "_with_audio" if has_audio else "_no_audio"
                        st.download_button(
                            f"📥 下载视频{'（含音频）' if has_audio else '（无音频）'}",
                            data=video_bytes,
                            file_name=f"travel_english_video{file_suffix}.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )
                        
                    except Exception as e:
                        st.error(f"视频文件读取失败: {str(e)}")
                        
            except Exception as e:
                st.error(f"生成失败: {str(e)}")
                st.code(traceback.format_exc())
else:
    st.info("👆 请先上传Excel文件或使用示例数据")

# 页脚信息
st.markdown("---")
st.markdown("### 💡 使用说明")
st.markdown("""
1. **准备数据**: Excel/CSV文件需包含"英语"、"中文"、"音标"三列
2. **上传文件**: 支持.xlsx, .xls, .csv格式
3. **自定义设置**: 调整背景、文字样式、时长等参数
4. **预览效果**: 确认样式是否符合预期
5. **生成视频**: 点击按钮开始生成，耐心等待完成
""")
