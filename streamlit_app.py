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
import requests

# 设置页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 旅游英语视频生成器")
st.markdown("### 🌐 高级自定义视频生成 - 支持中文字体和背景图片")

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

def load_font(font_path, size):
    """加载字体，如果失败则返回默认字体"""
    try:
        return ImageFont.truetype(font_path, size)
    except:
        try:
            # 尝试系统默认字体
            return ImageFont.load_default()
        except:
            # 最后备选方案
            return None

def get_available_fonts():
    """获取可用字体列表"""
    fonts = {
        "默认字体": "default",
        "Arial": "arial.ttf",
        "Times New Roman": "times.ttf",
        "Courier New": "cour.ttf",
        # 中文字体 - 在Railway中可能不可用，但提供选项
        "微软雅黑": "msyh.ttc",
        "宋体": "simsun.ttc",
        "黑体": "simhei.ttf"
    }
    return fonts

def wrap_text(text, max_chars, font=None):
    """将文本按最大字符数换行"""
    if not text or str(text) == 'nan':
        return [""]
    
    text = str(text)
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        # 如果当前行加上新单词不超过最大字符数
        test_line = ' '.join(current_line + [word])
        if len(test_line) <= max_chars:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines if lines else [text[:max_chars]]

def create_video_frame(text_english, text_chinese, text_phonetic, width=1280, height=720, 
                      bg_color=(0, 0, 0), bg_image=None, 
                      english_color=(255, 255, 255), chinese_color=(0, 255, 255), phonetic_color=(255, 255, 0),
                      english_size=60, chinese_size=50, phonetic_size=40,
                      font_family="default"):
    """创建单个视频帧"""
    
    # 创建图像
    if bg_image:
        # 使用背景图片
        img = bg_image.resize((width, height))
        # 添加半透明黑色覆盖层，提高文字可读性
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 128))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    else:
        # 使用纯色背景
        img = Image.new('RGB', (width, height), color=bg_color)
    
    draw = ImageDraw.Draw(img)
    
    # 加载字体
    fonts = get_available_fonts()
    font_path = fonts.get(font_family, "default")
    
    english_font = load_font(font_path, english_size) if font_path != "default" else None
    chinese_font = load_font(font_path, chinese_size) if font_path != "default" else None
    phonetic_font = load_font(font_path, phonetic_size) if font_path != "default" else None
    
    # 计算文本位置
    y_start = height // 4
    
    # 绘制英语句子
    english_lines = wrap_text(text_english, 35)
    for i, line in enumerate(english_lines):
        y_pos = y_start + i * (english_size + 10)
        if english_font:
            try:
                bbox = draw.textbbox((0, 0), line, font=english_font)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                draw.text((x, y_pos), line, fill=english_color, font=english_font, align='center')
            except:
                # 字体渲染失败，使用默认方式
                x = (width - len(line) * (english_size // 2)) // 2
                draw.text((x, y_pos), line, fill=english_color, align='center')
        else:
            x = (width - len(line) * (english_size // 2)) // 2
            draw.text((x, y_pos), line, fill=english_color, align='center')
    
    # 绘制中文翻译
    chinese_y = y_start + len(english_lines) * (english_size + 10) + 30
    chinese_lines = wrap_text(text_chinese, 20)  # 中文每行较少字符
    for i, line in enumerate(chinese_lines):
        y_pos = chinese_y + i * (chinese_size + 10)
        if chinese_font:
            try:
                bbox = draw.textbbox((0, 0), line, font=chinese_font)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                draw.text((x, y_pos), line, fill=chinese_color, font=chinese_font, align='center')
            except:
                x = (width - len(line) * (chinese_size // 2)) // 2
                draw.text((x, y_pos), line, fill=chinese_color, align='center')
        else:
            x = (width - len(line) * (chinese_size // 2)) // 2
            draw.text((x, y_pos), line, fill=chinese_color, align='center')
    
    # 绘制音标
    phonetic_y = chinese_y + len(chinese_lines) * (chinese_size + 10) + 20
    if text_phonetic and str(text_phonetic).strip() and str(text_phonetic) != 'nan':
        phonetic_lines = wrap_text(text_phonetic, 40)
        for i, line in enumerate(phonetic_lines):
            y_pos = phonetic_y + i * (phonetic_size + 5)
            if phonetic_font:
                try:
                    bbox = draw.textbbox((0, 0), line, font=phonetic_font)
                    text_width = bbox[2] - bbox[0]
                    x = (width - text_width) // 2
                    draw.text((x, y_pos), line, fill=phonetic_color, font=phonetic_font, align='center')
                except:
                    x = (width - len(line) * (phonetic_size // 2)) // 2
                    draw.text((x, y_pos), line, fill=phonetic_color, align='center')
            else:
                x = (width - len(line) * (phonetic_size // 2)) // 2
                draw.text((x, y_pos), line, fill=phonetic_color, align='center')
    
    # 添加底部边框和信息
    border_height = 3
    draw.rectangle([0, height - 60, width, height - 60 + border_height], fill=(100, 100, 100))
    
    info_text = "旅游英语学习视频 - 自动生成"
    if chinese_font:
        try:
            bbox = draw.textbbox((0, 0), info_text, font=chinese_font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            draw.text((x, height - 40), info_text, fill=(150, 150, 150), font=chinese_font)
        except:
            x = (width - len(info_text) * 10) // 2
            draw.text((x, height - 40), info_text, fill=(150, 150, 150))
    else:
        x = (width - len(info_text) * 10) // 2
        draw.text((x, height - 40), info_text, fill=(150, 150, 150))
    
    return img

def generate_video_from_dataframe(df, video_title, settings):
    """从DataFrame生成视频"""
    video_buffer = BytesIO()
    
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
    
    # 创建视频写入器
    with imageio.get_writer(video_buffer, format='FFMPEG', mode='I', fps=fps, 
                          codec='libx264', quality=8, 
                          pixelformat='yuv420p') as writer:
        
        # 为每个句子生成视频帧
        total_frames = len(df) * duration_per_sentence * fps
        current_frame = 0
        
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
                    font_family=settings['font_family']
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
            yield (total_frames + i) / (total_frames + end_frames)

def create_end_frame(width, height, sentence_count, title, settings):
    """创建结束帧"""
    bg_image = None
    if settings['background_type'] == 'image' and st.session_state.background_image:
        try:
            bg_image = Image.open(st.session_state.background_image).convert('RGB')
            bg_image = bg_image.resize((width, height))
            overlay = Image.new('RGBA', (width, height), (0, 0, 0, 180))
            bg_image = Image.alpha_composite(bg_image.convert('RGBA'), overlay).convert('RGB')
        except:
            bg_image = None
    
    if not bg_image:
        bg_image = Image.new('RGB', (width, height), color=settings['bg_color'])
    
    draw = ImageDraw.Draw(bg_image)
    
    fonts = get_available_fonts()
    font_path = fonts.get(settings['font_family'], "default")
    large_font = load_font(font_path, 60) if font_path != "default" else None
    medium_font = load_font(font_path, 40) if font_path != "default" else None
    
    # 结束文字
    texts = [
        ("视频结束", settings['chinese_color']),
        (f"共学习 {sentence_count} 个句子", (200, 200, 200)),
        ("谢谢观看", settings['phonetic_color']),
        (title, settings['english_color'])
    ]
    
    y_pos = height // 4
    for text, color in texts:
        if large_font or medium_font:
            try:
                font = large_font if text == title else medium_font
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                draw.text((x, y_pos), text, fill=color, font=font, align='center')
            except:
                x = (width - len(text) * 15) // 2
                draw.text((x, y_pos), text, fill=color, align='center')
        else:
            x = (width - len(text) * 15) // 2
            draw.text((x, y_pos), text, fill=color, align='center')
        y_pos += 80
    
    return bg_image

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
                font_family = st.selectbox("字体", list(get_available_fonts().keys()))
            
            # 背景设置
            if background_type == "纯色背景":
                bg_color = st.color_picker("背景颜色", "#000000")
                bg_color_rgb = hex_to_rgb(bg_color)
                background_image = None
            else:
                bg_upload = st.file_uploader("上传背景图片", type=['jpg', 'jpeg', 'png'])
                if bg_upload:
                    st.session_state.background_image = bg_upload
                    st.image(bg_upload, caption="背景图片预览", width=300)
                    bg_color_rgb = (0, 0, 0)  # 图片背景时使用黑色作为fallback
                else:
                    st.warning("请上传背景图片")
                    bg_color_rgb = (0, 0, 0)
            
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
            
            # 视频预览
            st.subheader("🎥 实时预览")
            if len(df) > 0:
                preview_col1, preview_col2 = st.columns(2)
                
                with preview_col1:
                    # 创建预览帧
                    preview_frame = create_video_frame(
                        str(df.iloc[0]['英语']), 
                        str(df.iloc[0]['中文']), 
                        str(df.iloc[0]['音标']),
                        width=600, height=400,  # 较小的预览尺寸
                        bg_color=bg_color_rgb,
                        bg_image=Image.open(st.session_state.background_image).convert('RGB') if st.session_state.background_image else None,
                        english_color=hex_to_rgb(english_color),
                        chinese_color=hex_to_rgb(chinese_color),
                        phonetic_color=hex_to_rgb(phonetic_color),
                        english_size=english_size,
                        chinese_size=chinese_size,
                        phonetic_size=phonetic_size,
                        font_family=font_family
                    )
                    st.image(preview_frame, caption="实时预览 - 第一句", use_column_width=True)
                
                with preview_col2:
                    st.info("""
                    **预览说明：**
                    - 左侧显示当前设置的效果
                    - 中文和音标应该正常显示
                    - 颜色和大小可实时调整
                    - 背景图片会按比例缩放
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
                'font_family': font_family
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
                    video_buffer = BytesIO()
                    progress_generator = generate_video_from_dataframe(df, video_title, settings)
                    
                    start_time = time.time()
                    for progress in progress_generator:
                        progress_bar.progress(progress)
                        elapsed = time.time() - start_time
                        if progress > 0:
                            total_estimated = elapsed / progress
                            remaining = total_estimated - elapsed
                            status_text.text(f"生成进度: {progress*100:.1f}%")
                            time_estimate.text(f"预计剩余: {remaining:.0f}秒")
                    
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
                    
                except Exception as e:
                    st.error(f"❌ 视频生成失败：{str(e)}")
                    st.info("""
                    **故障排除建议：**
                    1. 减少句子数量（建议10-20句）
                    2. 使用纯色背景减少内存使用
                    3. 降低分辨率到720p
                    4. 检查背景图片格式
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

# 使用说明
with st.expander("📖 使用说明和技巧"):
    st.markdown("""
    ## 使用指南
    
    ### 解决中文乱码问题
    1. **选择合适字体**：尝试不同的字体选项
    2. **调整字号**：适当增大中文字号
    3. **使用纯色背景**：减少渲染复杂度
    
    ### 自定义选项说明
    - **背景图片**：支持JPG、PNG格式，会自动缩放
    - **字体选择**：不同字体对中文支持不同
    - **颜色设置**：可分别设置英文、中文、音标颜色
    - **字号调整**：根据句子长度调整合适字号
    
    ### 性能优化建议
    - 句子数量：10-20句最佳
    - 分辨率：720p处理更快
    - 背景：纯色背景比图片背景更快
    """)

# 页脚
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎬 旅游英语视频生成器 • 🎨 完全自定义 • 🔤 中文支持</p>
</div>
""", unsafe_allow_html=True)
