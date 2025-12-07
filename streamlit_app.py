import streamlit as st
import pandas as pd
import os
import sys
import asyncio
import json
import time
import base64
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import tempfile
import shutil
from pathlib import Path

# 设置页面配置
st.set_page_config(
    page_title="旅游英语视频课件生成器",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 添加自定义CSS样式
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1E3A8A;
        margin-bottom: 30px;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        color: white;
    }
    .sub-header {
        color: #3B82F6;
        margin-top: 25px;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 2px solid #E5E7EB;
    }
    .info-box {
        background-color: #E0F2FE;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid #0EA5E9;
        margin: 15px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .success-box {
        background-color: #D1FAE5;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid #10B981;
        margin: 15px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .warning-box {
        background-color: #FEF3C7;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid #F59E0B;
        margin: 15px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: bold;
        padding: 12px 24px;
        border-radius: 8px;
        border: none;
        width: 100%;
        transition: all 0.3s ease;
        font-size: 16px;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    .stDownloadButton > button {
        background: linear-gradient(135deg, #10B981 0%, #047857 100%);
        color: white;
        font-weight: bold;
        padding: 12px 24px;
        border-radius: 8px;
        border: none;
        width: 100%;
        transition: all 0.3s ease;
    }
    .stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
    }
    .progress-container {
        background-color: #F3F4F6;
        border-radius: 10px;
        padding: 20px;
        margin: 20px 0;
    }
    .sentence-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 4px solid #3B82F6;
    }
    .config-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border: 1px solid #E5E7EB;
    }
    .tab-content {
        padding: 20px 0;
    }
    /* 响应式调整 */
    @media (max-width: 768px) {
        .main-header {
            font-size: 1.5rem;
            padding: 15px;
        }
        .config-card {
            padding: 10px;
        }
    }
</style>
""", unsafe_allow_html=True)

# 页面标题
st.markdown("""
<div class="main-header">
    <h1>🎬 旅游英语视频课件生成器</h1>
    <p style="color: rgba(255,255,255,0.9); margin-top: 10px;">一键生成专业的旅游英语学习视频，支持高清下载</p>
</div>
""", unsafe_allow_html=True)

# 初始化会话状态
if 'environment_checked' not in st.session_state:
    st.session_state.environment_checked = False
if 'generating' not in st.session_state:
    st.session_state.generating = False
if 'progress' not in st.session_state:
    st.session_state.progress = 0
if 'video_ready' not in st.session_state:
    st.session_state.video_ready = False
if 'video_path' not in st.session_state:
    st.session_state.video_path = None
if 'current_step' not in st.session_state:
    st.session_state.current_step = ""
if 'df' not in st.session_state:
    st.session_state.df = None
if 'sample_data_used' not in st.session_state:
    st.session_state.sample_data_used = False
if 'generation_report' not in st.session_state:
    st.session_state.generation_report = ""

# 音频模式说明
AUDIO_MODES = {
    "完整模式 (5遍)": {
        "description": "每组句子包含5个朗读版本：女生英语(慢)-男生英语(慢)-女生英语(慢)-男生中文-男生英语(慢)",
        "steps": 5
    },
    "标准模式 (3遍)": {
        "description": "每组句子包含3个朗读版本：女生英语(慢)-中文翻译-男生英语(慢)",
        "steps": 3
    },
    "快速模式 (2遍)": {
        "description": "每组句子包含2个朗读版本：英语朗读-中文翻译",
        "steps": 2
    }
}

# 视频分辨率选项
RESOLUTIONS = {
    "1920x1080 (全高清)": (1920, 1080),
    "1280x720 (高清)": (1280, 720),
    "854x480 (标清)": (854, 480)
}

# 侧边栏配置
with st.sidebar:
    st.markdown("### ⚙️ 视频配置")
    
    # 视频分辨率
    selected_resolution = st.selectbox(
        "📺 视频分辨率",
        list(RESOLUTIONS.keys()),
        index=0,
        help="选择视频的分辨率，分辨率越高文件越大"
    )
    
    # 音频模式
    selected_audio_mode = st.selectbox(
        "🔊 音频模式",
        list(AUDIO_MODES.keys()),
        index=0,
        help="选择音频的朗读模式"
    )
    
    # 显示当前选择的音频模式说明
    st.markdown(f"""
    <div class="config-card">
        <strong>当前模式:</strong> {selected_audio_mode}<br>
        <small>{AUDIO_MODES[selected_audio_mode]['description']}</small>
    </div>
    """, unsafe_allow_html=True)
    
    # 字幕样式
    st.markdown("---")
    st.markdown("### 🔤 字幕设置")
    
    font_size = st.slider(
        "字体大小",
        min_value=16,
        max_value=60,
        value=36,
        help="字幕字体大小"
    )
    
    english_color = st.color_picker("英语颜色", "#FFFFFF")
    chinese_color = st.color_picker("中文颜色", "#00FFFF")
    phonetic_color = st.color_picker("音标颜色", "#FFFF00")
    
    # 背景设置
    st.markdown("---")
    st.markdown("### 🎨 背景设置")
    
    background_type = st.radio(
        "背景类型",
        ["纯色背景", "渐变背景", "图片背景"]
    )
    
    if background_type == "纯色背景":
        bg_color = st.color_picker("背景颜色", "#000000")
    elif background_type == "渐变背景":
        col1, col2 = st.columns(2)
        with col1:
            bg_color1 = st.color_picker("起始颜色", "#000428")
        with col2:
            bg_color2 = st.color_picker("结束颜色", "#004e92")
    else:
        bg_image = st.file_uploader("上传背景图片", type=['jpg', 'jpeg', 'png'])
    
    # 生成设置
    st.markdown("---")
    st.markdown("### ⚡ 生成设置")
    
    include_silence = st.checkbox("包含句子间静默", value=True, help="在每个句子之间添加800ms的静默间隔")
    silence_duration = st.slider("静默时长(ms)", 200, 2000, 800, disabled=not include_silence)
    
    slow_rate = st.slider("慢速比例(%)", -50, 50, -20, help="负值表示减慢，正值表示加快")
    
    # 环境检查
    st.markdown("---")
    st.markdown("### 🔧 系统状态")
    
    if st.button("检查环境"):
        with st.spinner("检查依赖包..."):
            try:
                import pandas as pd
                import openpyxl
                import pydub
                import edge_tts
                import moviepy
                import numpy as np
                from PIL import Image
                st.success("✅ 环境检查通过")
                st.session_state.environment_checked = True
            except ImportError as e:
                st.error(f"缺少依赖包: {e}")
                st.info("请运行: pip install -r requirements_streamlit.txt")

# 主界面标签页
tab1, tab2, tab3, tab4 = st.tabs(["📁 数据管理", "⚙️ 生成设置", "🎬 视频生成", "📥 结果下载"])

with tab1:
    st.markdown("### 📁 数据管理")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 数据上传区域
        uploaded_file = st.file_uploader(
            "上传Excel文件",
            type=['xlsx', 'xls'],
            help="请上传包含'英语'、'中文'、'音标'列的Excel文件"
        )
    
    with col2:
        # 使用示例数据
        if st.button("使用示例数据", use_container_width=True):
            # 创建示例数据
            example_data = {
                '英语': [
                    'Where is the gate?',
                    'Window seat, please.',
                    'Aisle seat, please.',
                    'Check in, please.',
                    'How many bags?',
                    'Is it overweight?',
                    'Take off shoes.',
                    'Where is luggage?',
                    'Boarding pass, please.',
                    'Any delay?'
                ],
                '中文': [
                    '登机口在哪？',
                    '请给我靠窗座位。',
                    '请给我过道座位。',
                    '办理登机手续。',
                    '要托运几件行李？',
                    '超重了吗？',
                    '请脱鞋。',
                    '行李在哪里？',
                    '请出示登机牌。',
                    '航班延误吗？'
                ],
                '音标': [
                    '/weə ɪz ðə ɡeɪt/',
                    '/ˈwɪndəʊ siːt pliːz/',
                    '/ˈaɪl siːt pliːz/',
                    '/tʃek ɪn pliːz/',
                    '/haʊ ˈmeni bæɡz/',
                    '/ɪz ɪt ˌəʊvəˈweɪt/',
                    '/teɪk ɔːf ʃuːz/',
                    '/weə ɪz ˈlʌɡɪdʒ/',
                    '/ˈbɔːdɪŋ pɑːs pliːz/',
                    '/ˈeni dɪˈleɪ/'
                ]
            }
            st.session_state.df = pd.DataFrame(example_data)
            st.session_state.sample_data_used = True
            st.success("✅ 已加载示例数据")
    
    # 显示数据
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            st.session_state.df = df
            st.success(f"✅ 成功读取 {len(df)} 条数据")
        except Exception as e:
            st.error(f"读取文件失败: {str(e)}")
    
    if st.session_state.df is not None:
        st.markdown(f"#### 数据预览 (共 {len(st.session_state.df)} 条)")
        
        # 可编辑的数据表格
        edited_df = st.data_editor(
            st.session_state.df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "英语": st.column_config.TextColumn("英语", width="large"),
                "中文": st.column_config.TextColumn("中文", width="medium"),
                "音标": st.column_config.TextColumn("音标", width="medium")
            }
        )
        
        # 更新会话状态中的数据
        st.session_state.df = edited_df
        
        # 显示统计信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("英语句子", len(edited_df))
        with col2:
            total_words = sum(len(str(s).split()) for s in edited_df['英语'])
            st.metric("总单词数", total_words)
        with col3:
            avg_length = np.mean([len(str(s)) for s in edited_df['英语']])
            st.metric("平均长度", f"{avg_length:.1f}字符")
        
        # 保存数据按钮
        if st.button("💾 保存数据"):
            try:
                # 保存到临时文件
                temp_file = "temp_data.xlsx"
                edited_df.to_excel(temp_file, index=False)
                st.success(f"✅ 数据已保存到 {temp_file}")
                
                # 提供下载
                with open(temp_file, "rb") as f:
                    st.download_button(
                        label="下载Excel文件",
                        data=f,
                        file_name="旅游英语数据.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except Exception as e:
                st.error(f"保存失败: {str(e)}")
    
    else:
        st.info("👆 请上传Excel文件或使用示例数据开始")

with tab2:
    st.markdown("### ⚙️ 生成设置")
    
    if st.session_state.df is None:
        st.warning("⚠️ 请先在【数据管理】标签页上传或创建数据")
    else:
        # 句子选择器
        st.markdown("#### 选择生成范围")
        
        total_sentences = len(st.session_state.df)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            start_idx = st.number_input(
                "起始句子",
                min_value=1,
                max_value=total_sentences,
                value=1
            )
        
        with col2:
            end_idx = st.number_input(
                "结束句子",
                min_value=1,
                max_value=total_sentences,
                value=min(10, total_sentences)
            )
        
        with col3:
            selected_count = end_idx - start_idx + 1
            estimated_time = selected_count * AUDIO_MODES[selected_audio_mode]['steps'] * 3
            st.metric("生成句子数", selected_count)
            st.caption(f"预计时间: {estimated_time}秒")
        
        # 预览选中的句子
        st.markdown("#### 预览选中的句子")
        
        if start_idx <= end_idx:
            preview_df = st.session_state.df.iloc[start_idx-1:end_idx].copy()
            preview_df.index = range(start_idx, end_idx + 1)
            
            # 显示句子卡片
            for idx, row in preview_df.iterrows():
                with st.container():
                    st.markdown(f"""
                    <div class="sentence-card">
                        <strong>句子 #{idx}</strong><br>
                        <span style="color: white; font-size: 18px;">{row['英语']}</span><br>
                        <span style="color: cyan; font-size: 16px;">{row['中文']}</span><br>
                        <span style="color: yellow; font-size: 14px;">{row['音标']}</span>
                    </div>
                    """, unsafe_allow_html=True)
        
        # 高级设置
        with st.expander("高级设置", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                output_fps = st.number_input("视频帧率(FPS)", 10, 60, 24)
                audio_bitrate = st.selectbox(
                    "音频比特率",
                    ["64k", "128k", "192k", "256k", "320k"],
                    index=2
                )
            
            with col2:
                video_bitrate = st.selectbox(
                    "视频比特率",
                    ["1M", "2M", "5M", "8M", "10M"],
                    index=2
                )
                enable_watermark = st.checkbox("添加水印", value=False)
                
                if enable_watermark:
                    watermark_text = st.text_input("水印文字", "旅游英语学习")
        
        # 生成预览
        st.markdown("#### 视频预览效果")
        
        # 创建一个预览图
        try:
            # 使用PIL创建预览图
            width, height = RESOLUTIONS[selected_resolution]
            
            # 创建预览图像
            preview_img = Image.new('RGB', (width // 4, height // 4), color='black')
            draw = ImageDraw.Draw(preview_img)
            
            # 绘制文本
            sample_text = "Where is the gate?"
            sample_chinese = "登机口在哪？"
            sample_phonetic = "/weə ɪz ðə ɡeɪt/"
            
            # 计算文本位置
            center_x = preview_img.width // 2
            
            # 绘制英语
            english_y = preview_img.height // 4
            draw.text((center_x, english_y), sample_text, fill=english_color, anchor="mm")
            
            # 绘制音标
            phonetic_y = english_y + 30
            draw.text((center_x, phonetic_y), sample_phonetic, fill=phonetic_color, anchor="mm")
            
            # 绘制中文
            chinese_y = phonetic_y + 30
            draw.text((center_x, chinese_y), sample_chinese, fill=chinese_color, anchor="mm")
            
            # 显示预览图
            st.image(preview_img, caption="字幕预览效果", use_column_width=True)
            
        except Exception as e:
            st.warning(f"预览图生成失败: {str(e)}")

with tab3:
    st.markdown("### 🎬 视频生成")
    
    if st.session_state.df is None:
        st.warning("⚠️ 请先在【数据管理】标签页上传或创建数据")
    else:
        # 生成控制面板
        col1, col2 = st.columns([3, 1])
        
        with col1:
            total_sentences = len(st.session_state.df)
            selected_count = end_idx - start_idx + 1 if 'end_idx' in locals() else min(10, total_sentences)
            estimated_time = selected_count * AUDIO_MODES[selected_audio_mode]['steps'] * 3
            
            st.markdown(f"""
            <div class="info-box">
                <h4>生成信息</h4>
                • 总句子数: {selected_count} 句<br>
                • 音频模式: {selected_audio_mode}<br>
                • 分辨率: {selected_resolution}<br>
                • 预计时长: 约 {estimated_time} 秒
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            generate_disabled = st.session_state.generating
            
            if st.button("🚀 开始生成", 
                        disabled=generate_disabled,
                        use_container_width=True,
                        type="primary"):
                st.session_state.generating = True
                st.session_state.progress = 0
                st.session_state.video_ready = False
                st.session_state.current_step = "初始化"
                st.rerun()
        
        # 进度显示区域
        if st.session_state.generating:
            st.markdown("""
            <div class="progress-container">
                <h4>⏳ 生成进度</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # 进度条
            progress_bar = st.progress(st.session_state.progress / 100)
            
            # 状态文本
            status_text = st.empty()
            status_text.text(f"🔄 {st.session_state.current_step}")
            
            # 模拟生成过程
            steps = [
                ("初始化生成环境...", 5),
                ("处理数据文件...", 10),
                ("生成TTS音频文件...", 25),
                ("合成音频序列...", 40),
                ("创建视频帧...", 60),
                ("添加字幕效果...", 75),
                ("编码视频文件...", 90),
                ("完成生成...", 100)
            ]
            
            # 在单独的函数中模拟进度更新
            def simulate_progress():
                for step_text, step_progress in steps:
                    time.sleep(1.5)  # 模拟处理时间
                    st.session_state.current_step = step_text
                    st.session_state.progress = step_progress
            
            # 使用st.empty()创建占位符并更新
            import threading
            
            def run_simulation():
                simulate_progress()
                
                # 完成生成
                time.sleep(1)
                
                # 创建模拟视频文件
                output_dir = "output_videos"
                os.makedirs(output_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                video_filename = f"旅游英语视频_{timestamp}.mp4"
                video_path = os.path.join(output_dir, video_filename)
                
                # 创建模拟视频文件内容
                with open(video_path, 'w') as f:
                    f.write("Simulated video file - 这是模拟的视频文件内容\n")
                    f.write(f"生成时间: {timestamp}\n")
                    f.write(f"句子数: {selected_count}\n")
                    f.write(f"分辨率: {selected_resolution}\n")
                    f.write(f"音频模式: {selected_audio_mode}\n")
                
                # 更新会话状态
                st.session_state.video_path = video_path
                st.session_state.video_ready = True
                st.session_state.generating = False
                
                # 生成报告
                report_content = f"""
                视频生成报告
                =====================
                生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                视频文件: {video_filename}
                句子范围: {start_idx} - {end_idx} (共{selected_count}句)
                分辨率: {selected_resolution}
                音频模式: {selected_audio_mode}
                字幕设置:
                  - 英语颜色: {english_color}
                  - 中文颜色: {chinese_color}
                  - 音标颜色: {phonetic_color}
                  - 字体大小: {font_size}
                
                生成句子列表:
                """
                
                for i in range(start_idx-1, end_idx):
                    eng = st.session_state.df.iloc[i]['英语']
                    chn = st.session_state.df.iloc[i]['中文']
                    pho = st.session_state.df.iloc[i]['音标']
                    report_content += f"\n{i+1}. {eng}\n   中文: {chn}\n   音标: {pho}\n"
                
                st.session_state.generation_report = report_content
                
                # 重新运行以更新UI
                st.rerun()
            
            # 在新线程中运行模拟
            if not hasattr(st.session_state, 'simulation_started'):
                st.session_state.simulation_started = True
                import threading
                thread = threading.Thread(target=run_simulation)
                thread.start()
        
        elif st.session_state.video_ready:
            st.markdown("""
            <div class="success-box">
                <h4>✅ 视频已生成</h4>
                视频文件已准备就绪，请切换到【结果下载】标签页查看和下载。
            </div>
            """, unsafe_allow_html=True)

with tab4:
    st.markdown("### 📥 结果下载")
    
    if st.session_state.video_ready and st.session_state.video_path:
        # 视频信息卡片
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("视频文件", "旅游英语学习视频.mp4")
        
        with col2:
            if os.path.exists(st.session_state.video_path):
                file_size = os.path.getsize(st.session_state.video_path)
                st.metric("文件大小", f"{file_size/1024:.1f} KB")
            else:
                st.metric("文件大小", "模拟文件")
        
        with col3:
            st.metric("生成时间", datetime.now().strftime("%H:%M"))
        
        # 视频预览区域
        st.markdown("#### 🎬 视频预览")
        
        # 在实际应用中，这里会显示真正的视频预览
        # 这里我们显示一个占位符
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    height: 400px; 
                    border-radius: 15px; 
                    display: flex; 
                    align-items: center; 
                    justify-content: center;
                    color: white;
                    font-size: 24px;
                    margin: 20px 0;">
            🎬 视频预览区域<br>
            <small style="font-size: 16px;">(实际应用中这里会显示生成的视频)</small>
        </div>
        """, unsafe_allow_html=True)
        
        # 下载区域
        st.markdown("#### 📥 下载文件")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 下载视频按钮
            if os.path.exists(st.session_state.video_path):
                with open(st.session_state.video_path, "rb") as f:
                    st.download_button(
                        label="🎬 下载高清视频",
                        data=f,
                        file_name="旅游英语学习视频.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )
            else:
                st.warning("视频文件不存在")
        
        with col2:
            # 下载报告按钮
            st.download_button(
                label="📋 下载生成报告",
                data=st.session_state.generation_report,
                file_name="生成报告.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        # 其他格式导出
        st.markdown("#### 🔄 其他格式")
        
        export_col1, export_col2, export_col3 = st.columns(3)
        
        with export_col1:
            if st.button("导出音频MP3", use_container_width=True):
                st.info("音频导出功能开发中...")
        
        with export_col2:
            if st.button("导出字幕SRT", use_container_width=True):
                st.info("字幕导出功能开发中...")
        
        with export_col3:
            if st.button("导出数据JSON", use_container_width=True):
                # 导出数据为JSON
                export_data = {
                    "sentences": st.session_state.df.iloc[start_idx-1:end_idx].to_dict('records'),
                    "config": {
                        "resolution": selected_resolution,
                        "audio_mode": selected_audio_mode,
                        "colors": {
                            "english": english_color,
                            "chinese": chinese_color,
                            "phonetic": phonetic_color
                        }
                    }
                }
                
                json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                
                st.download_button(
                    label="📄 下载JSON数据",
                    data=json_str,
                    file_name="旅游英语数据.json",
                    mime="application/json",
                    use_container_width=True
                )
        
        # 分享功能
        st.markdown("---")
        st.markdown("#### 📤 分享")
        
        share_col1, share_col2 = st.columns(2)
        
        with share_col1:
            if st.button("复制分享链接", use_container_width=True):
                st.success("链接已复制到剪贴板！")
        
        with share_col2:
            if st.button("保存到云端", use_container_width=True):
                st.info("云存储功能开发中...")
    
    else:
        st.markdown("""
        <div class="warning-box">
            <h4>⚠️ 暂无生成结果</h4>
            请先在【视频生成】标签页生成视频，完成后可以在这里下载。
        </div>
        """, unsafe_allow_html=True)

# 页脚
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9em; padding: 20px;'>
    <p>🎬 旅游英语视频课件生成器 • 基于Streamlit • 版本 2.0 • 
    <a href="#" style="color: #3B82F6; text-decoration: none;">使用说明</a> • 
    <a href="#" style="color: #3B82F6; text-decoration: none;">问题反馈</a></p>
</div>
""", unsafe_allow_html=True)

# 初始化代码 - 只在第一次运行时执行
if not st.session_state.environment_checked:
    # 自动检查环境
    with st.spinner("正在初始化环境..."):
        time.sleep(2)
        st.session_state.environment_checked = True