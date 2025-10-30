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

# 设置页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 旅游英语视频生成器")
st.markdown("### 🌐 直接生成MP4视频文件 - Railway部署")

# 特性介绍
col1, col2, col3 = st.columns(3)
with col1:
    st.info("📁 一键上传\n\n上传Excel文件，自动识别内容")

with col2:
    st.info("🎬 直接生成\n\n输出完整MP4视频文件")

with col3:
    st.info("📱 立即下载\n\n无需额外软件编辑")

# 文件上传
st.header("📤 第一步：上传Excel文件")
uploaded_file = st.file_uploader("选择Excel文件", type=['xlsx', 'xls'], 
                                help="Excel文件必须包含'英语','中文','音标'三列")

def create_video_frame(text_english, text_chinese, text_phonetic, width=1280, height=720, 
                      bg_color=(0, 0, 0), text_color=(255, 255, 255), duration=5):
    """创建单个视频帧"""
    # 创建图像
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    try:
        # 尝试加载字体（Railway环境中可能没有中文字体，使用默认字体）
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    except:
        font_large = None
        font_medium = None
        font_small = None
    
    # 计算文本位置
    y_start = height // 4
    
    # 绘制英语句子（白色，大字体）
    english_lines = wrap_text(text_english, 40)  # 每行最多40字符
    for i, line in enumerate(english_lines):
        y_pos = y_start + i * 60
        if font_large:
            bbox = draw.textbbox((0, 0), line, font=font_large)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            draw.text((x, y_pos), line, fill=text_color, font=font_large, align='center')
        else:
            x = (width - len(line) * 10) // 2
            draw.text((x, y_pos), line, fill=text_color, align='center')
    
    # 绘制中文翻译（青色）
    chinese_y = y_start + len(english_lines) * 60 + 40
    chinese_lines = wrap_text(text_chinese, 30)  # 中文每行较少字符
    for i, line in enumerate(chinese_lines):
        y_pos = chinese_y + i * 50
        if font_medium:
            bbox = draw.textbbox((0, 0), line, font=font_medium)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            draw.text((x, y_pos), line, fill=(0, 255, 255), font=font_medium, align='center')
        else:
            x = (width - len(line) * 15) // 2
            draw.text((x, y_pos), line, fill=(0, 255, 255), align='center')
    
    # 绘制音标（黄色）
    phonetic_y = chinese_y + len(chinese_lines) * 50 + 30
    if text_phonetic and str(text_phonetic).strip() and str(text_phonetic) != 'nan':
        if font_small:
            bbox = draw.textbbox((0, 0), text_phonetic, font=font_small)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            draw.text((x, phonetic_y), text_phonetic, fill=(255, 255, 0), font=font_small, align='center')
        else:
            x = (width - len(text_phonetic) * 8) // 2
            draw.text((x, phonetic_y), text_phonetic, fill=(255, 255, 0), align='center')
    
    # 添加进度指示器
    progress_height = 10
    progress_width = width - 100
    progress_x = 50
    progress_y = height - 50
    
    # 进度条背景
    draw.rectangle([progress_x, progress_y, progress_x + progress_width, progress_y + progress_height], 
                  fill=(100, 100, 100))
    
    # 添加底部信息
    info_text = "旅游英语学习视频 - 自动生成"
    if font_small:
        bbox = draw.textbbox((0, 0), info_text, font=font_small)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, height - 30), info_text, fill=(150, 150, 150), font=font_small)
    else:
        x = (width - len(info_text) * 8) // 2
        draw.text((x, height - 30), info_text, fill=(150, 150, 150))
    
    return img

def wrap_text(text, max_chars):
    """将文本按最大字符数换行"""
    if not text:
        return [""]
    
    words = str(text).split()
    lines = []
    current_line = []
    
    for word in words:
        # 如果当前行加上新单词不超过最大字符数
        if len(' '.join(current_line + [word])) <= max_chars:
            current_line.append(word)
        else:
            # 如果当前行已经有内容，保存它
            if current_line:
                lines.append(' '.join(current_line))
            # 如果单个单词就超过最大字符数，需要拆分
            if len(word) > max_chars:
                # 拆分长单词
                for i in range(0, len(word), max_chars-3):
                    lines.append(word[i:i+max_chars-3] + '...')
                current_line = []
            else:
                current_line = [word]
    
    # 添加最后一行
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines if lines else [str(text)[:max_chars]]

def generate_video_from_dataframe(df, video_title, fps=24, duration_per_sentence=5):
    """从DataFrame生成视频"""
    # 创建临时文件来存储视频
    video_buffer = BytesIO()
    
    # 视频参数
    width, height = 1280, 720
    
    # 创建视频写入器
    with imageio.get_writer(video_buffer, format='FFMPEG', mode='I', fps=fps, 
                          codec='libx264', quality=8, 
                          pixelformat='yuv420p') as writer:
        
        # 为每个句子生成视频帧
        for idx, row in df.iterrows():
            # 获取句子数据
            english = str(row['英语']) if pd.notna(row['英语']) else ""
            chinese = str(row['中文']) if pd.notna(row['中文']) else ""
            phonetic = str(row['音标']) if pd.notna(row['音标']) and str(row['音标']) != 'nan' else ""
            
            # 创建这个句子的所有帧
            frames_for_sentence = duration_per_sentence * fps
            
            for frame_idx in range(frames_for_sentence):
                # 创建帧
                frame_img = create_video_frame(english, chinese, phonetic, width, height)
                
                # 转换为numpy数组
                frame_array = np.array(frame_img)
                
                # 写入帧
                writer.append_data(frame_array)
                
                # 更新进度（可选）
                if frame_idx % 10 == 0:
                    yield (idx * frames_for_sentence + frame_idx) / (len(df) * frames_for_sentence)
        
        # 添加结束帧（显示总时长）
        end_frames = 2 * fps  # 2秒结束画面
        for i in range(end_frames):
            end_img = create_end_frame(width, height, len(df), video_title)
            end_array = np.array(end_img)
            writer.append_data(end_array)
            
            yield (len(df) * frames_for_sentence + i) / (len(df) * frames_for_sentence + end_frames)

def create_end_frame(width, height, sentence_count, title):
    """创建结束帧"""
    img = Image.new('RGB', (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    try:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
    except:
        font_large = None
        font_medium = None
    
    # 结束文字
    end_text = "视频结束"
    thank_text = "谢谢观看"
    info_text = f"共学习 {sentence_count} 个句子"
    title_text = title
    
    # 绘制标题
    y_pos = height // 3
    if font_large:
        bbox = draw.textbbox((0, 0), title_text, font=font_large)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y_pos), title_text, fill=(255, 255, 255), font=font_large)
    else:
        x = (width - len(title_text) * 12) // 2
        draw.text((x, y_pos), title_text, fill=(255, 255, 255))
    
    # 绘制结束文字
    y_pos += 80
    if font_large:
        bbox = draw.textbbox((0, 0), end_text, font=font_large)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y_pos), end_text, fill=(0, 255, 255), font=font_large)
    else:
        x = (width - len(end_text) * 12) // 2
        draw.text((x, y_pos), end_text, fill=(0, 255, 255))
    
    # 绘制感谢文字
    y_pos += 60
    if font_medium:
        bbox = draw.textbbox((0, 0), thank_text, font=font_medium)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y_pos), thank_text, fill=(255, 255, 0), font=font_medium)
    else:
        x = (width - len(thank_text) * 10) // 2
        draw.text((x, y_pos), thank_text, fill=(255, 255, 0))
    
    # 绘制信息文字
    y_pos += 50
    if font_medium:
        bbox = draw.textbbox((0, 0), info_text, font=font_medium)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y_pos), info_text, fill=(200, 200, 200), font=font_medium)
    else:
        x = (width - len(info_text) * 10) // 2
        draw.text((x, y_pos), info_text, fill=(200, 200, 200))
    
    return img

def get_video_download_link(video_buffer, filename):
    """生成视频下载链接"""
    video_buffer.seek(0)
    b64 = base64.b64encode(video_buffer.read()).decode()
    href = f'<a href="data:video/mp4;base64,{b64}" download="{filename}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px; font-size: 16px;">📥 下载MP4视频文件</a>'
    return href

if uploaded_file is not None:
    try:
        # 读取Excel
        df = pd.read_excel(uploaded_file)
        
        # 检查必要列
        required_columns = ['英语', '中文', '音标']
        if all(col in df.columns for col in required_columns):
            st.success(f"✅ 文件验证成功！共找到 {len(df)} 条句子")
            
            # 显示预览
            st.subheader("📊 数据预览")
            st.dataframe(df.head(10), use_container_width=True)
            
            # 视频设置
            st.header("⚙️ 第二步：视频设置")
            
            col1, col2 = st.columns(2)
            
            with col1:
                video_title = st.text_input("视频标题", "旅游英语学习视频")
                fps = st.selectbox("帧率", [24, 30], index=0)
                duration_per_sentence = st.slider("每句显示时间(秒)", 3, 10, 5)
                
            with col2:
                resolution = st.selectbox("分辨率", ["720p", "1080p"])
                background_color = st.color_picker("背景颜色", "#000000")
                text_color = st.color_picker("文字颜色", "#FFFFFF")
            
            # 视频预览
            st.subheader("🎥 视频帧预览")
            if len(df) > 0:
                preview_frame = create_video_frame(
                    str(df.iloc[0]['英语']), 
                    str(df.iloc[0]['中文']), 
                    str(df.iloc[0]['音标']),
                    bg_color=background_color,
                    text_color=text_color
                )
                st.image(preview_frame, caption="第一句视频帧预览", use_column_width=True)
            
            # 生成按钮
            st.header("🎬 第三步：生成MP4视频")
            
            if st.button("🚀 开始生成视频", type="primary", use_container_width=True):
                # 创建进度区域
                progress_bar = st.progress(0)
                status_text = st.empty()
                time_estimate = st.empty()
                
                # 视频信息
                total_frames = len(df) * duration_per_sentence * fps + 2 * fps
                estimated_time = total_frames / fps
                
                st.info(f"""
                **视频规格：**
                - 总时长: {estimated_time:.1f}秒
                - 分辨率: {resolution}
                - 帧率: {fps}fps
                - 总帧数: {total_frames}帧
                - 文件格式: MP4 (H.264)
                """)
                
                # 生成视频
                try:
                    video_buffer = BytesIO()
                    progress_generator = generate_video_from_dataframe(
                        df, video_title, fps, duration_per_sentence
                    )
                    
                    # 执行生成过程
                    for progress in progress_generator:
                        progress_bar.progress(progress)
                        status_text.text(f"生成进度: {progress*100:.1f}%")
                        time_estimate.text(f"预计剩余时间: {(1-progress)*estimated_time/2:.1f}秒")
                    
                    # 完成效果
                    st.balloons()
                    st.success("🎉 MP4视频生成完成！")
                    
                    # 生成下载链接
                    filename = f"{video_title}.mp4"
                    download_link = get_video_download_link(video_buffer, filename)
                    
                    st.markdown(download_link, unsafe_allow_html=True)
                    
                    # 视频信息总结
                    st.subheader("📊 生成总结")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("视频时长", f"{estimated_time:.1f}秒")
                    with col2:
                        st.metric("句子数量", len(df))
                    with col3:
                        st.metric("分辨率", resolution)
                    with col4:
                        file_size = len(video_buffer.getvalue()) / (1024 * 1024)
                        st.metric("文件大小", f"{file_size:.1f}MB")
                    
                except Exception as e:
                    st.error(f"❌ 视频生成失败：{str(e)}")
                    st.info("如果遇到内存错误，请尝试减少句子数量或降低视频质量")
                    
        else:
            st.error("❌ Excel文件必须包含'英语','中文','音标'三列")
            st.write("**当前文件的列**:", list(df.columns))
            
    except Exception as e:
        st.error(f"❌ 文件读取失败：{str(e)}")

else:
    # 提供示例文件下载
    st.header("📝 示例文件")
    
    example_data = {
        '英语': [
            'Where is the gate?',
            'Window seat, please.',
            'How much does it cost?',
            'I would like to check in.',
            'Where can I find a taxi?'
        ],
        '中文': [
            '登机口在哪？',
            '请给我靠窗座位。',
            '这个多少钱？',
            '我想要办理入住。',
            '我在哪里可以找到出租车？'
        ],
        '音标': [
            '/weə ɪz ðə ɡeɪt/',
            '/ˈwɪndəʊ siːt pliːz/',
            '/haʊ mʌtʃ dʌz ɪt kɒst/',
            '/aɪ wʊd laɪk tə tʃek ɪn/',
            '/weə kæn aɪ faɪnd ə ˈtæksi/'
        ]
    }
    example_df = pd.DataFrame(example_data)
    
    # 显示示例
    st.write("**示例数据格式**:")
    st.dataframe(example_df, use_container_width=True)
    
    # 下载示例模板
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
with st.expander("📖 使用说明"):
    st.markdown("""
    ## 使用指南
    
    ### 视频生成说明
    1. **上传Excel文件**：必须包含英语、中文、音标三列
    2. **调整设置**：根据需求调整视频参数
    3. **生成视频**：点击按钮开始生成MP4文件
    4. **下载使用**：直接下载生成的视频文件
    
    ### 技术规格
    - 视频格式：MP4 (H.264编码)
    - 音频：静音视频（专注于文字学习）
    - 分辨率：720p 或 1080p
    - 帧率：24fps 或 30fps
    
    ### 性能提示
    - 句子数量建议：10-30句最佳
    - 生成时间：每句约2-3秒处理时间
    - 文件大小：与句子数量成正比
    """)

# 页脚
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎬 旅游英语视频生成器 • 🚂 Railway部署 • 🎥 直接输出MP4</p>
</div>
""", unsafe_allow_html=True)
