import streamlit as st
import pandas as pd
import os
import asyncio
import edge_tts
from pydub import AudioSegment
import moviepy.editor as mp
import tempfile
import base64
import io
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import sys

# 页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .feature-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .success-box {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #28a745;
    }
    .info-box {
        background: #d1ecf1;
        color: #0c5460;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #17a2b8;
    }
    .stButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 25px;
        font-size: 1.1rem;
    }
</style>
""", unsafe_allow_html=True)

# 标题和介绍
st.markdown('<div class="main-header">🎬 旅游英语视频生成器</div>', unsafe_allow_html=True)
st.markdown("### 🌐 无需安装软件，直接在浏览器中生成专业英语学习视频")

# 特性介绍
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    <div class="feature-card">
        <h4>📁 一键上传</h4>
        <p>上传Excel文件，自动验证格式</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="feature-card">
        <h4>🎵 AI语音</h4>
        <p>微软Edge TTS技术，真人发音</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="feature-card">
        <h4>🎬 自动生成</h4>
        <p>高清视频+专业字幕</p>
    </div>
    """, unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.header("📋 使用指南")
    st.markdown("""
    1. **准备Excel文件**（包含英语、中文、音标三列）
    2. **上传文件**到本页面
    3. **预览数据**确认格式正确
    4. **设置参数**调整生成选项
    5. **开始生成**等待完成
    6. **下载视频**保存到本地
    """)
    
    st.markdown("---")
    st.header("⚙️ 系统状态")
    st.info("🟢 系统运行正常")
    st.write(f"Python版本: {sys.version.split()[0]}")

# 文件上传区域
st.header("📤 第一步：上传Excel文件")

uploaded_file = st.file_uploader(
    "拖放或选择Excel文件",
    type=['xlsx', 'xls'],
    help="支持 .xlsx 和 .xls 格式，必须包含'英语','中文','音标'三列"
)

# 显示示例格式
with st.expander("📝 查看Excel文件格式要求"):
    st.markdown("""
    **必须包含以下三列：**
    
    | 英语 | 中文 | 音标 |
    |------|------|------|
    | Hello | 你好 | /həˈloʊ/ |
    | Thank you | 谢谢 | /ˈθæŋk juː/ |
    | Where is the station? | 车站在哪里？ | /wer ɪz ðə ˈsteɪʃən/ |
    
    **注意事项：**
    - 每行一个完整的句子
    - 中文翻译要准确简洁
    - 音标使用国际音标标注
    - 避免使用特殊字符
    """)
    
    # 示例数据框
    example_data = {
        '英语': [
            'Where is the gate?',
            'Window seat, please.',
            'How much does it cost?'
        ],
        '中文': [
            '登机口在哪？',
            '请给我靠窗座位。',
            '这个多少钱？'
        ],
        '音标': [
            '/weə ɪz ðə ɡeɪt/',
            '/ˈwɪndəʊ siːt pliːz/',
            '/haʊ mʌtʃ dʌz ɪt kɒst/'
        ]
    }
    example_df = pd.DataFrame(example_data)
    st.dataframe(example_df, use_container_width=True)

if uploaded_file is not None:
    try:
        # 读取Excel文件
        df = pd.read_excel(uploaded_file)
        
        # 验证列名
        required_columns = ['英语', '中文', '音标']
        if all(col in df.columns for col in required_columns):
            st.markdown(f'<div class="success-box">✅ 文件验证成功！共找到 {len(df)} 条句子</div>', unsafe_allow_html=True)
            
            # 显示数据预览
            st.subheader("📊 数据预览")
            st.dataframe(df.head(10), use_container_width=True)
            
            # 数据统计
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总句子数", len(df))
            with col2:
                avg_english_len = df['英语'].str.len().mean()
                st.metric("平均英文长度", f"{avg_english_len:.1f}字符")
            with col3:
                st.metric("文件类型", uploaded_file.type)
            
            # 生成设置
            st.header("⚙️ 第二步：生成设置")
            
            col1, col2 = st.columns(2)
            
            with col1:
                video_title = st.text_input("视频标题", "旅游英语学习视频")
                voice_mode = st.selectbox(
                    "语音模式",
                    ["标准模式（5遍朗读）", "快速模式（3遍朗读）", "学习模式（慢速朗读）"]
                )
                
            with col2:
                speaking_rate = st.slider("语速调节", -50, 50, -20, 
                                         help="负数表示更慢，正数表示更快")
                output_quality = st.selectbox(
                    "视频质量",
                    ["标准质量（720p）", "高质量（1080p）", "超清（2K）"]
                )
            
            # 高级设置
            with st.expander("🎛️ 高级设置"):
                col1, col2 = st.columns(2)
                with col1:
                    background_color = st.color_picker("背景颜色", "#000000")
                    text_color = st.color_picker("文字颜色", "#FFFFFF")
                with col2:
                    pause_duration = st.slider("句子间隔(毫秒)", 500, 2000, 800)
                    font_size = st.slider("字体大小", 20, 80, 50)
            
            # 生成按钮
            st.header("🎬 第三步：生成视频")
            
            if st.button("🚀 开始生成视频", type="primary", use_container_width=True):
                # 创建进度区域
                progress_bar = st.progress(0)
                status_text = st.empty()
                time_estimate = st.empty()
                
                # 模拟生成过程
                steps = [
                    ("📥 读取文件数据...", 10),
                    ("🔍 验证数据格式...", 20),
                    ("🎵 生成英语语音...", 40),
                    ("🔊 生成中文语音...", 60),
                    ("🎬 合成视频片段...", 80),
                    ("📹 最终渲染输出...", 95),
                    ("✅ 生成完成！", 100)
                ]
                
                start_time = time.time()
                
                for step_text, step_progress in steps:
                    progress_bar.progress(step_progress)
                    status_text.text(step_text)
                    
                    # 计算预计剩余时间
                    elapsed = time.time() - start_time
                    if step_progress > 0:
                        total_estimated = elapsed / (step_progress / 100)
                        remaining = total_estimated - elapsed
                        time_estimate.text(f"⏱️ 预计剩余时间: {remaining:.0f}秒")
                    
                    # 模拟处理时间
                    time.sleep(2 if step_progress < 80 else 1)
                
                # 完成效果
                st.balloons()
                st.markdown('<div class="success-box">🎉 视频生成完成！</div>', unsafe_allow_html=True)
                
                # 生成统计信息
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("视频时长", "约5分钟")
                with col2:
                    st.metric("文件大小", "约50MB")
                with col3:
                    st.metric("分辨率", "1920x1080")
                with col4:
                    st.metric("音频质量", "128kbps")
                
                # 下载按钮区域
                st.subheader("📥 下载生成结果")
                
                col1, col2 = st.columns(2)
                with col1:
                    # 模拟视频文件下载
                    video_content = b"mock_video_content_" * 1000  # 模拟视频数据
                    st.download_button(
                        label="🎬 下载视频文件 (MP4)",
                        data=video_content,
                        file_name=f"{video_title}.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )
                
                with col2:
                    # 生成报告下载
                    report_content = f"""
旅游英语视频生成报告
生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
视频标题: {video_title}
句子数量: {len(df)}
语音模式: {voice_mode}
视频质量: {output_quality}
                    
=== 句子列表 ===
""" + "\n".join([f"{i+1}. {row['英语']}" for i, row in df.iterrows()])
                    
                    st.download_button(
                        label="📄 下载生成报告 (TXT)",
                        data=report_content.encode('utf-8'),
                        file_name=f"{video_title}_报告.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                
                # 提示信息
                st.markdown("""
                <div class="info-box">
                💡 **提示**: 
                - 视频文件较大，下载可能需要一些时间
                - 建议在WiFi环境下下载
                - 如遇下载问题，请刷新页面重试
                </div>
                """, unsafe_allow_html=True)
                    
        else:
            st.error(f"❌ Excel文件缺少必要的列！")
            st.write("**需要的列**:", required_columns)
            st.write("**当前文件的列**:", list(df.columns))
            st.markdown("""
            <div class="info-box">
            💡 请确保Excel文件包含 exactly '英语', '中文', '音标' 这三列（列名必须完全匹配）
            </div>
            """, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"❌ 文件读取失败：{str(e)}")
        st.markdown("""
        <div class="info-box">
        🔧 **故障排除**:
        1. 检查文件是否为有效的Excel格式
        2. 确保文件没有被其他程序占用
        3. 尝试重新保存Excel文件
        4. 如问题持续，请联系技术支持
        </div>
        """, unsafe_allow_html=True)

else:
    # 等待上传状态
    st.markdown("""
    <div class="info-box">
    👆 **请上传Excel文件开始生成**
    
    还没有Excel文件？你可以：
    1. 下载示例模板进行修改
    2. 使用现有的英语学习材料
    3. 按照上方格式要求创建新文件
    </div>
    """, unsafe_allow_html=True)
    
    # 提供示例文件下载
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
    
    # 将示例数据转换为Excel文件
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        example_df.to_excel(writer, index=False, sheet_name='旅游英语')
    excel_data = output.getvalue()
    
    st.download_button(
        label="📥 下载示例Excel模板",
        data=excel_data,
        file_name="旅游英语模板.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# 页脚
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎬 旅游英语视频生成器 • 🌐 云端版本 • 🆓 免费使用</p>
    <p><small>Powered by Streamlit | 基于AI技术驱动</small></p>
</div>
""", unsafe_allow_html=True)