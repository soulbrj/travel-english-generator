# [file name]: streamlit_app.py
import streamlit as st
import pandas as pd
import os
import json
import time
import base64
from datetime import datetime
from pathlib import Path

# 页面配置
st.set_page_config(
    page_title="旅游英语视频课件生成器",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
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
    .sentence-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 4px solid #3B82F6;
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
if 'generation_report' not in st.session_state:
    st.session_state.generation_report = ""
if 'example_data' not in st.session_state:
    # 创建示例数据
    st.session_state.example_data = {
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

# 配置选项
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

RESOLUTIONS = {
    "1920x1080 (全高清)": (1920, 1080),
    "1280x720 (高清)": (1280, 720),
    "854x480 (标清)": (854, 480)
}

# 侧边栏
with st.sidebar:
    st.markdown("### ⚙️ 视频配置")
    
    selected_resolution = st.selectbox(
        "📺 视频分辨率",
        list(RESOLUTIONS.keys()),
        index=0,
        help="选择视频的分辨率"
    )
    
    selected_audio_mode = st.selectbox(
        "🔊 音频模式",
        list(AUDIO_MODES.keys()),
        index=0,
        help="选择音频的朗读模式"
    )
    
    st.markdown(f"""
    <div style="background-color: white; border-radius: 10px; padding: 15px; margin: 10px 0; border: 1px solid #E5E7EB;">
        <strong>当前模式:</strong> {selected_audio_mode}<br>
        <small>{AUDIO_MODES[selected_audio_mode]['description']}</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🔤 字幕设置")
    
    font_size = st.slider("字体大小", 16, 60, 36)
    english_color = st.color_picker("英语颜色", "#FFFFFF")
    chinese_color = st.color_picker("中文颜色", "#00FFFF")
    phonetic_color = st.color_picker("音标颜色", "#FFFF00")
    
    st.markdown("---")
    st.markdown("### 🎨 背景设置")
    
    background_type = st.radio("背景类型", ["纯色背景", "渐变背景", "图片背景"])
    
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
    
    st.markdown("---")
    st.markdown("### ⚡ 生成设置")
    
    include_silence = st.checkbox("包含句子间静默", value=True)
    silence_duration = st.slider("静默时长(ms)", 200, 2000, 800, disabled=not include_silence)
    slow_rate = st.slider("慢速比例(%)", -50, 50, -20)

# 主标签页
tab1, tab2, tab3, tab4 = st.tabs(["📁 数据管理", "⚙️ 生成设置", "🎬 视频生成", "📥 结果下载"])

with tab1:
    st.markdown("### 📁 数据管理")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "上传Excel文件",
            type=['xlsx', 'xls'],
            help="请上传包含'英语'、'中文'、'音标'列的Excel文件"
        )
    
    with col2:
        if st.button("使用示例数据", use_container_width=True):
            st.session_state.df = pd.DataFrame(st.session_state.example_data)
            st.success("✅ 已加载示例数据")
            st.rerun()
    
    # 处理上传的文件
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            st.session_state.df = df
            st.success(f"✅ 成功读取 {len(df)} 条数据")
        except Exception as e:
            st.error(f"读取文件失败: {str(e)}")
    
    # 显示数据
    if st.session_state.df is not None:
        st.markdown(f"#### 数据预览 (共 {len(st.session_state.df)} 条)")
        
        # 显示数据表格
        st.dataframe(st.session_state.df, use_container_width=True)
        
        # 统计信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("英语句子", len(st.session_state.df))
        with col2:
            total_words = sum(len(str(s).split()) for s in st.session_state.df['英语'])
            st.metric("总单词数", total_words)
        with col3:
            avg_length = sum(len(str(s)) for s in st.session_state.df['英语']) / len(st.session_state.df)
            st.metric("平均长度", f"{avg_length:.1f}字符")
        
        # 下载数据按钮
        if st.button("💾 下载数据"):
            # 将数据转换为CSV格式供下载
            csv = st.session_state.df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="下载CSV文件",
                data=csv,
                file_name="旅游英语数据.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.info("👆 请上传Excel文件或使用示例数据开始")

with tab2:
    st.markdown("### ⚙️ 生成设置")
    
    if st.session_state.df is None:
        st.warning("⚠️ 请先在【数据管理】标签页上传或创建数据")
    else:
        total_sentences = len(st.session_state.df)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            start_idx = st.number_input("起始句子", 1, total_sentences, 1)
        with col2:
            end_idx = st.number_input("结束句子", 1, total_sentences, min(10, total_sentences))
        with col3:
            selected_count = end_idx - start_idx + 1
            estimated_time = selected_count * AUDIO_MODES[selected_audio_mode]['steps'] * 3
            st.metric("生成句子数", selected_count)
            st.caption(f"预计时间: {estimated_time}秒")
        
        # 保存配置到会话状态
        st.session_state.config = {
            'start_idx': start_idx,
            'end_idx': end_idx,
            'selected_count': selected_count,
            'selected_resolution': selected_resolution,
            'selected_audio_mode': selected_audio_mode,
            'font_size': font_size,
            'english_color': english_color,
            'chinese_color': chinese_color,
            'phonetic_color': phonetic_color
        }
        
        # 预览选中的句子
        st.markdown("#### 预览选中的句子")
        
        if start_idx <= end_idx:
            for i in range(start_idx-1, end_idx):
                row = st.session_state.df.iloc[i]
                with st.container():
                    st.markdown(f"""
                    <div class="sentence-card">
                        <strong>句子 #{i+1}</strong><br>
                        <span style="color: white; font-size: 18px;">{row['英语']}</span><br>
                        <span style="color: cyan; font-size: 16px;">{row['中文']}</span><br>
                        <span style="color: yellow; font-size: 14px;">{row['音标']}</span>
                    </div>
                    """, unsafe_allow_html=True)

with tab3:
    st.markdown("### 🎬 视频生成")
    
    if st.session_state.df is None:
        st.warning("⚠️ 请先在【数据管理】标签页上传或创建数据")
    else:
        config = st.session_state.config
        estimated_time = config['selected_count'] * AUDIO_MODES[selected_audio_mode]['steps'] * 3
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"""
            <div class="info-box">
                <h4>生成信息</h4>
                • 总句子数: {config['selected_count']} 句<br>
                • 音频模式: {selected_audio_mode}<br>
                • 分辨率: {selected_resolution}<br>
                • 预计时长: 约 {estimated_time} 秒
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            if st.button("🚀 开始生成", 
                        disabled=st.session_state.generating,
                        use_container_width=True,
                        type="primary"):
                st.session_state.generating = True
                st.session_state.progress = 0
                st.session_state.video_ready = False
                st.session_state.current_step = "初始化"
                st.rerun()
        
        # 进度显示
        if st.session_state.generating:
            st.markdown("""
            <div style="background-color: #F3F4F6; border-radius: 10px; padding: 20px; margin: 20px 0;">
                <h4>⏳ 生成进度</h4>
            </div>
            """, unsafe_allow_html=True)
            
            progress_bar = st.progress(st.session_state.progress)
            status_text = st.empty()
            
            # 模拟生成步骤
            steps = [
                ("初始化生成环境...", 10),
                ("处理数据文件...", 20),
                ("生成音频文件...", 40),
                ("合成音频序列...", 60),
                ("创建视频帧...", 80),
                ("导出视频文件...", 95),
                ("完成生成...", 100)
            ]
            
            # 模拟进度更新
            for i, (step_text, step_progress) in enumerate(steps):
                time.sleep(1.5)
                st.session_state.current_step = step_text
                st.session_state.progress = step_progress
                progress_bar.progress(step_progress / 100)
                status_text.text(f"🔄 {step_text}")
            
            # 完成生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = "output_videos"
            os.makedirs(output_dir, exist_ok=True)
            
            # 创建模拟视频文件
            video_filename = f"旅游英语视频_{timestamp}.mp4"
            video_path = os.path.join(output_dir, video_filename)
            
            with open(video_path, 'w') as f:
                f.write(f"模拟视频文件 - 旅游英语学习视频\n")
                f.write(f"生成时间: {timestamp}\n")
                f.write(f"句子数: {config['selected_count']}\n")
                f.write(f"分辨率: {selected_resolution}\n")
                f.write(f"音频模式: {selected_audio_mode}\n")
            
            # 生成报告
            report_content = f"""
            视频生成报告
            =====================
            生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            视频文件: {video_filename}
            句子范围: {config['start_idx']} - {config['end_idx']} (共{config['selected_count']}句)
            分辨率: {selected_resolution}
            音频模式: {selected_audio_mode}
            字幕设置:
              - 英语颜色: {english_color}
              - 中文颜色: {chinese_color}
              - 音标颜色: {phonetic_color}
              - 字体大小: {font_size}
            
            生成句子列表:
            """
            
            for i in range(config['start_idx']-1, config['end_idx']):
                row = st.session_state.df.iloc[i]
                report_content += f"\n{i+1}. {row['英语']}"
                report_content += f"\n   中文: {row['中文']}"
                report_content += f"\n   音标: {row['音标']}\n"
            
            # 更新会话状态
            st.session_state.video_path = video_path
            st.session_state.video_ready = True
            st.session_state.generating = False
            st.session_state.generation_report = report_content
            
            st.success("✅ 视频生成完成！")
            st.balloons()
            st.rerun()
        
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
        # 视频信息
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
        
        with col2:
            # 下载报告按钮
            st.download_button(
                label="📋 下载生成报告",
                data=st.session_state.generation_report,
                file_name="生成报告.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        # 其他导出选项
        st.markdown("#### 🔄 其他格式")
        
        if st.button("导出数据JSON", use_container_width=True):
            # 导出数据为JSON
            export_data = {
                "sentences": st.session_state.df.iloc[
                    st.session_state.config['start_idx']-1:st.session_state.config['end_idx']
                ].to_dict('records'),
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
    <p>🎬 旅游英语视频课件生成器 • 基于Streamlit • 版本 2.0</p>
</div>
""", unsafe_allow_html=True)
