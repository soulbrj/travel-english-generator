import streamlit as st
import pandas as pd
import time
import io
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio
from io import BytesIO
import base64
import tempfile

# 设置页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 旅游英语视频生成器")
st.markdown("### 🌐 高级自定义视频生成 - 修复版")

# 初始化session state
if 'background_image' not in st.session_state:
    st.session_state.background_image = None

# 特性介绍
col1, col2, col3 = st.columns(3)
with col1:
    st.info("🎨 完全自定义\n\n颜色、字体、背景随意调整")

with col2:
    st.info("🖼️ 背景图片\n\n支持自定义背景或纯色")

with col3:
    st.info("🔤 字体支持\n\n完美显示中文和音标")

# 文件上传
st.header("📤 第一步：上传Excel文件")
uploaded_file = st.file_uploader("选择Excel文件", type=['xlsx', 'xls'], 
                                help="Excel文件必须包含'英语','中文','音标'三列")

def create_custom_font(size):
    """创建自定义字体对象来模拟字号效果"""
    # 创建一个虚拟的字体对象来维护字号信息
    class CustomFont:
        def __init__(self, size):
            self.size = size
            # 估算字符宽度（像素）
            self.char_width = max(8, size // 2)
            self.char_height = size + 10
    
    return CustomFont(size)

def wrap_text(text, max_chars, font=None):
    """将文本按最大字符数换行"""
    if not text or str(text) == 'nan':
        return [""]
    
    text = str(text)
    # 如果是中文，减少每行字符数
    if any('\u4e00' <= char <= '\u9fff' for char in text):
        max_chars = min(max_chars, 15)  # 中文每行最多15字
    
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        if len(test_line) <= max_chars:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            # 处理超长单词
            if len(word) > max_chars:
                for i in range(0, len(word), max_chars):
                    lines.append(word[i:i+max_chars])
                current_line = []
            else:
                current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines if lines else [text[:max_chars]]

def create_video_frame(text_english, text_chinese, text_phonetic, width=1280, height=720, 
                      bg_color=(0, 0, 0), bg_image=None, 
                      english_color=(255, 255, 255), chinese_color=(0, 255, 255), phonetic_color=(255, 255, 0),
                      english_size=60, chinese_size=50, phonetic_size=40,
                      text_bg_color=(0, 0, 0, 180), text_bg_radius=20):
    """创建单个视频帧"""
    
    # 创建图像
    if bg_image:
        img = bg_image.resize((width, height)).convert('RGB')
    else:
        img = Image.new('RGB', (width, height), color=bg_color)
    
    draw = ImageDraw.Draw(img)
    
    # 创建字体对象（模拟字号效果）
    english_font = create_custom_font(english_size)
    chinese_font = create_custom_font(chinese_size)
    phonetic_font = create_custom_font(phonetic_size)
    
    # 计算文本区域总高度
    english_lines = wrap_text(text_english, 35)
    chinese_lines = wrap_text(text_chinese, 15)  # 中文每行较少字符
    phonetic_lines = wrap_text(text_phonetic, 40) if text_phonetic and str(text_phonetic).strip() and str(text_phonetic) != 'nan' else []
    
    total_text_height = (len(english_lines) * english_font.char_height + 
                        len(chinese_lines) * chinese_font.char_height + 
                        len(phonetic_lines) * phonetic_font.char_height + 80)
    
    # 创建文本背景区域
    text_bg_width = width - 100
    text_bg_height = total_text_height + 40
    text_bg_x = 50
    text_bg_y = (height - text_bg_height) // 2
    
    # 绘制圆角矩形背景
    for i in range(text_bg_radius):
        radius = text_bg_radius - i
        alpha = int(text_bg_color[3] * (1 - i/text_bg_radius))
        bg_color_with_alpha = text_bg_color[:3] + (alpha,)
        
        # 绘制四个角的圆弧
        for corner_x, corner_y in [(text_bg_x, text_bg_y), 
                                  (text_bg_x + text_bg_width - 2*radius, text_bg_y),
                                  (text_bg_x, text_bg_y + text_bg_height - 2*radius),
                                  (text_bg_x + text_bg_width - 2*radius, text_bg_y + text_bg_height - 2*radius)]:
            for x in range(radius):
                for y in range(radius):
                    if (x - radius)**2 + (y - radius)**2 <= radius**2:
                        img.putpixel((corner_x + x, corner_y + y), text_bg_color[:3])
                        img.putpixel((corner_x + text_bg_width - radius + x, corner_y + y), text_bg_color[:3])
                        img.putpixel((corner_x + x, corner_y + text_bg_height - radius + y), text_bg_color[:3])
                        img.putpixel((corner_x + text_bg_width - radius + x, corner_y + text_bg_height - radius + y), text_bg_color[:3])
    
    # 绘制矩形主体
    for x in range(text_bg_width - 2*text_bg_radius):
        for y in range(text_bg_height):
            img.putpixel((text_bg_x + text_bg_radius + x, text_bg_y + y), text_bg_color[:3])
    
    for y in range(text_bg_height - 2*text_bg_radius):
        for x in range(text_bg_width):
            img.putpixel((text_bg_x + x, text_bg_y + text_bg_radius + y), text_bg_color[:3])
    
    # 绘制文本
    y_position = text_bg_y + 30
    
    # 绘制英语句子
    for i, line in enumerate(english_lines):
        text_width = len(line) * english_font.char_width
        x = text_bg_x + (text_bg_width - text_width) // 2
        y = y_position + i * english_font.char_height
        
        # 绘制文本阴影（增强可读性）
        shadow_color = (0, 0, 0)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), line, fill=shadow_color)
        
        # 绘制主文本
        draw.text((x, y), line, fill=english_color)
    
    y_position += len(english_lines) * english_font.char_height + 20
    
    # 绘制中文翻译
    for i, line in enumerate(chinese_lines):
        text_width = len(line) * chinese_font.char_width
        x = text_bg_x + (text_bg_width - text_width) // 2
        y = y_position + i * chinese_font.char_height
        
        # 绘制文本阴影
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), line, fill=shadow_color)
        
        draw.text((x, y), line, fill=chinese_color)
    
    y_position += len(chinese_lines) * chinese_font.char_height + 15
    
    # 绘制音标
    for i, line in enumerate(phonetic_lines):
        text_width = len(line) * phonetic_font.char_width
        x = text_bg_x + (text_bg_width - text_width) // 2
        y = y_position + i * phonetic_font.char_height
        
        # 绘制文本阴影
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), line, fill=shadow_color)
        
        draw.text((x, y), line, fill=phonetic_color)
    
    # 添加底部信息
    info_text = "旅游英语学习视频"
    info_width = len(info_text) * 10
    info_x = (width - info_width) // 2
    info_y = height - 40
    
    # 信息文本阴影
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            draw.text((info_x + dx, info_y + dy), info_text, fill=(0, 0, 0))
    
    draw.text((info_x, info_y), info_text, fill=(150, 150, 150))
    
    return img

def generate_video_from_dataframe(df, video_title, settings):
    """从DataFrame生成视频"""
    # 使用临时文件而不是内存缓冲区
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        width, height = settings['resolution']
        fps = settings['fps']
        duration_per_sentence = settings['duration_per_sentence']
        
        # 准备背景图片
        bg_image = None
        if settings['background_type'] == 'image' and st.session_state.background_image:
            try:
                bg_image = Image.open(st.session_state.background_image).convert('RGB')
            except:
                bg_image = None
        
        # 创建视频写入器 - 直接写入文件
        with imageio.get_writer(temp_path, fps=fps, 
                              codec='libx264', 
                              quality=8,
                              macro_block_size=1) as writer:  # 避免分辨率整除问题
            
            total_frames = len(df) * duration_per_sentence * fps + 3 * fps
            current_frame = 0
            
            # 为每个句子生成视频帧
            for idx, row in df.iterrows():
                english = str(row['英语']) if pd.notna(row['英语']) else ""
                chinese = str(row['中文']) if pd.notna(row['中文']) else ""
                phonetic = str(row['音标']) if pd.notna(row['音标']) and str(row['音标']) != 'nan' else ""
                
                frames_for_sentence = duration_per_sentence * fps
                
                for frame_idx in range(frames_for_sentence):
                    frame_img = create_video_frame(
                        english, chinese, phonetic, width, height,
                        bg_color=settings['bg_color'],
                        bg_image=bg_image,
                        english_color=settings['english_color'],
                        chinese_color=settings['chinese_color'],
                        phonetic_color=settings['phonetic_color'],
                        english_size=settings['english_size'],
                        chinese_size=settings['chinese_size'],
                        phonetic_size=settings['phonetic_size'],
                        text_bg_color=settings['text_bg_color'],
                        text_bg_radius=settings['text_bg_radius']
                    )
                    
                    frame_array = np.array(frame_img)
                    writer.append_data(frame_array)
                    
                    current_frame += 1
                    yield current_frame / total_frames
            
            # 添加结束帧
            end_frames = 3 * fps
            end_img = create_end_frame(width, height, len(df), video_title, settings)
            for i in range(end_frames):
                end_array = np.array(end_img)
                writer.append_data(end_array)
                yield (total_frames - 3 * fps + i) / total_frames
        
        # 读取生成的文件到内存
        with open(temp_path, 'rb') as f:
            video_buffer = BytesIO(f.read())
        
        return video_buffer
        
    finally:
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except:
            pass

def create_end_frame(width, height, sentence_count, title, settings):
    """创建结束帧"""
    if settings['background_type'] == 'image' and st.session_state.background_image:
        try:
            img = Image.open(st.session_state.background_image).convert('RGB')
            img = img.resize((width, height))
        except:
            img = Image.new('RGB', (width, height), color=settings['bg_color'])
    else:
        img = Image.new('RGB', (width, height), color=settings['bg_color'])
    
    draw = ImageDraw.Draw(img)
    
    # 结束文字
    texts = [
        ("视频结束", settings['chinese_color']),
        (f"共学习 {sentence_count} 个句子", (200, 200, 200)),
        ("谢谢观看", settings['phonetic_color']),
        (title, settings['english_color'])
    ]
    
    # 计算总高度
    total_height = sum([60 if i == 3 else 40 for i in range(len(texts))]) + 20 * (len(texts) - 1)
    y_start = (height - total_height) // 2
    
    for i, (text, color) in enumerate(texts):
        font_size = 60 if i == 3 else 40  # 标题用大字号
        font = create_custom_font(font_size)
        text_width = len(text) * font.char_width
        x = (width - text_width) // 2
        y = y_start
        
        # 文本阴影
        shadow_color = (0, 0, 0)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), text, fill=shadow_color)
        
        draw.text((x, y), text, fill=color)
        y_start += font_size + 20
    
    return img

def get_video_download_link(video_buffer, filename):
    """生成视频下载链接"""
    video_buffer.seek(0)
    b64 = base64.b64encode(video_buffer.read()).decode()
    href = f'<a href="data:video/mp4;base64,{b64}" download="{filename}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px; font-size: 16px; margin: 10px;">📥 下载MP4视频文件</a>'
    return href

def hex_to_rgb(hex_color):
    """将十六进制颜色转换为RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def hex_to_rgba(hex_color, alpha=255):
    """将十六进制颜色转换为RGBA"""
    rgb = hex_to_rgb(hex_color)
    return rgb + (alpha,)

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        
        required_columns = ['英语', '中文', '音标']
        if all(col in df.columns for col in required_columns):
            st.success(f"✅ 文件验证成功！共找到 {len(df)} 条句子")
            
            st.subheader("📊 数据预览")
            st.dataframe(df.head(10), use_container_width=True)
            
            # 视频设置
            st.header("⚙️ 第二步：视频设置")
            
            # 基础设置
            col1, col2 = st.columns(2)
            
            with col1:
                video_title = st.text_input("视频标题", "旅游英语学习视频")
                resolution_option = st.selectbox("分辨率", ["720p (1280x720)", "1080p (1920x1080)"])
                fps = st.selectbox("帧率", [24, 30], index=0)
                duration_per_sentence = st.slider("每句显示时间(秒)", 3, 10, 5)
                
            with col2:
                background_type = st.radio("背景类型", ["纯色背景", "图片背景"])
                if background_type == "图片背景":
                    bg_upload = st.file_uploader("上传背景图片", type=['jpg', 'jpeg', 'png'], key="bg_upload")
                    if bg_upload:
                        st.session_state.background_image = bg_upload
                        st.image(bg_upload, caption="背景图片预览", width=300)
            
            # 背景颜色设置（纯色背景时显示）
            if background_type == "纯色背景":
                bg_color = st.color_picker("背景颜色", "#000000")
                bg_color_rgb = hex_to_rgb(bg_color)
            else:
                bg_color_rgb = (0, 0, 0)  # 图片背景时使用黑色作为fallback
            
            # 文字样式设置
            st.subheader("🎨 文字样式设置")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**英语设置**")
                english_color = st.color_picker("英语颜色", "#FFFFFF", key="english")
                english_size = st.slider("英语字号", 30, 100, 60, key="english_size")
                
            with col2:
                st.markdown("**中文设置**")
                chinese_color = st.color_picker("中文颜色", "#00FFFF", key="chinese")
                chinese_size = st.slider("中文字号", 20, 80, 45, key="chinese_size")
                
            with col3:
                st.markdown("**音标设置**")
                phonetic_color = st.color_picker("音标颜色", "#FFFF00", key="phonetic")
                phonetic_size = st.slider("音标字号", 20, 60, 35, key="phonetic_size")
            
            # 文本背景设置
            st.subheader("🖼️ 文本背景设置")
            col1, col2 = st.columns(2)
            
            with col1:
                text_bg_color = st.color_picker("文本背景颜色", "#000000")
                text_bg_alpha = st.slider("背景透明度", 0, 255, 180, key="text_bg_alpha")
                
            with col2:
                text_bg_radius = st.slider("圆角半径", 0, 50, 20, key="text_bg_radius")
            
            text_bg_rgba = hex_to_rgba(text_bg_color, text_bg_alpha)
            
            # 视频预览
            st.subheader("🎥 实时预览")
            if len(df) > 0:
                preview_col1, preview_col2 = st.columns(2)
                
                with preview_col1:
                    # 创建预览帧
                    preview_bg_image = None
                    if background_type == "图片背景" and st.session_state.background_image:
                        try:
                            preview_bg_image = Image.open(st.session_state.background_image).convert('RGB')
                        except:
                            preview_bg_image = None
                    
                    preview_frame = create_video_frame(
                        str(df.iloc[0]['英语']), 
                        str(df.iloc[0]['中文']), 
                        str(df.iloc[0]['音标']),
                        width=600, height=400,
                        bg_color=bg_color_rgb,
                        bg_image=preview_bg_image,
                        english_color=hex_to_rgb(english_color),
                        chinese_color=hex_to_rgb(chinese_color),
                        phonetic_color=hex_to_rgb(phonetic_color),
                        english_size=english_size,
                        chinese_size=chinese_size,
                        phonetic_size=phonetic_size,
                        text_bg_color=text_bg_rgba,
                        text_bg_radius=text_bg_radius
                    )
                    st.image(preview_frame, caption="实时预览 - 第一句", use_column_width=True)
                
                with preview_col2:
                    st.info("""
                    **预览说明：**
                    - 左侧显示当前设置的效果
                    - 文字现在有圆角背景区域
                    - 字号变化应该明显可见
                    - 中文和音标应该正常显示
                    """)
            
            # 生成设置
            resolution_map = {
                "720p (1280x720)": (1280, 720),
                "1080p (1920x1080)": (1920, 1080)
            }
            
            settings = {
                'resolution': resolution_map[resolution_option],
                'fps': fps,
                'duration_per_sentence': duration_per_sentence,
                'background_type': 'color' if background_type == "纯色背景" else 'image',
                'bg_color': bg_color_rgb,
                'english_color': hex_to_rgb(english_color),
                'chinese_color': hex_to_rgb(chinese_color),
                'phonetic_color': hex_to_rgb(phonetic_color),
                'english_size': english_size,
                'chinese_size': chinese_size,
                'phonetic_size': phonetic_size,
                'text_bg_color': text_bg_rgba,
                'text_bg_radius': text_bg_radius
            }
            
            # 生成按钮
            st.header("🎬 第三步：生成MP4视频")
            
            if st.button("🚀 开始生成视频", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                time_estimate = st.empty()
                
                total_frames = len(df) * duration_per_sentence * fps + 3 * fps
                estimated_time = total_frames / fps
                
                st.info(f"""
                **视频规格：**
                - 总时长: {estimated_time:.1f}秒
                - 分辨率: {resolution_option}
                - 帧率: {fps}fps
                - 句子数量: {len(df)}句
                - 背景类型: {background_type}
                """)
                
                try:
                    progress_generator = generate_video_from_dataframe(df, video_title, settings)
                    
                    start_time = time.time()
                    video_buffer = None
                    
                    for progress in progress_generator:
                        progress_bar.progress(progress)
                        elapsed = time.time() - start_time
                        if progress > 0:
                            total_estimated = elapsed / progress
                            remaining = total_estimated - elapsed
                            status_text.text(f"生成进度: {progress*100:.1f}%")
                            time_estimate.text(f"预计剩余: {remaining:.0f}秒")
                    
                    # 获取最终的video_buffer
                    video_buffer = list(progress_generator)[-1] if hasattr(progress_generator, '__next__') else None
                    
                    if video_buffer:
                        st.balloons()
                        st.success("🎉 MP4视频生成完成！")
                        
                        filename = f"{video_title}.mp4"
                        download_link = get_video_download_link(video_buffer, filename)
                        
                        st.markdown(download_link, unsafe_allow_html=True)
                        
                        # 视频信息
                        st.subheader("📊 生成总结")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("视频时长", f"{estimated_time:.1f}秒")
                        with col2:
                            st.metric("文件大小", f"{len(video_buffer.getvalue()) / (1024*1024):.1f}MB")
                        with col3:
                            st.metric("分辨率", resolution_option.split(' ')[0])
                        with col4:
                            st.metric("帧率", f"{fps}fps")
                    else:
                        st.error("❌ 视频生成失败：无法创建视频文件")
                    
                except Exception as e:
                    st.error(f"❌ 视频生成失败：{str(e)}")
                    st.info("""
                    **故障排除建议：**
                    1. 减少句子数量（建议5-10句）
                    2. 使用720p分辨率
                    3. 确保有足够的存储空间
                    4. 重启应用重试
                    """)
                    
        else:
            st.error("❌ Excel文件必须包含'英语','中文','音标'三列")
            
    except Exception as e:
        st.error(f"❌ 文件读取失败：{str(e)}")

else:
    # 提供示例文件下载
    st.header("📝 示例文件")
    
    example_data = {
        '英语': ['Where is the gate?', 'Window seat, please.'],
        '中文': ['登机口在哪？', '请给我靠窗座位。'],
        '音标': ['/weə ɪz ðə ɡeɪt/', '/ˈwɪndəʊ siːt pliːz/']
    }
    example_df = pd.DataFrame(example_data)
    
    st.write("**示例数据格式**:")
    st.dataframe(example_df, use_container_width=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        example_df.to_excel(writer, index=False, sheet_name='旅游英语')
    excel_data = output.getvalue()
    
    st.download_button(
        label="📥 下载示例Excel模板",
        data=excel_data,
        file_name="旅游英语模板.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# 页脚
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎬 旅游英语视频生成器 • 🎨 完全自定义 • 🔤 中文支持</p>
</div>
""", unsafe_allow_html=True)
