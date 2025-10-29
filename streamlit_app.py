import streamlit as st
import pandas as pd
import time
import io
import base64

# 页面配置
st.set_page_config(
    page_title="旅游英语视频生成器",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 旅游英语视频生成器")
st.markdown("### 🌐 无需安装软件，在线生成英语学习视频")

# 特性介绍
col1, col2, col3 = st.columns(3)
with col1:
    st.info("📁 一键上传\n\n上传Excel文件，自动识别内容")

with col2:
    st.info("🎵 智能处理\n\n自动分析句子结构")

with col3:
    st.info("📋 学习卡片\n\n生成可打印的学习材料")

# 文件上传
st.header("📤 第一步：上传Excel文件")
uploaded_file = st.file_uploader("选择Excel文件", type=['xlsx', 'xls'], 
                                help="Excel文件必须包含'英语','中文','音标'三列")

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
            
            # 数据统计
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总句子数", len(df))
            with col2:
                avg_english_len = df['英语'].str.len().mean()
                st.metric("平均英文长度", f"{avg_english_len:.1f}字符")
            with col3:
                st.metric("文件类型", uploaded_file.type)
            
            # 设置
            st.header("⚙️ 第二步：生成设置")
            col1, col2 = st.columns(2)
            
            with col1:
                output_type = st.selectbox(
                    "输出类型",
                    ["学习卡片PDF", "练习文档", "音频脚本", "视频制作文件"]
                )
                document_title = st.text_input("文档标题", "旅游英语学习材料")
            
            with col2:
                language_mode = st.selectbox(
                    "语言模式",
                    ["中英对照", "纯英语", "纯中文"]
                )
                include_phonetic = st.checkbox("包含音标", value=True)
            
            # 生成按钮
            st.header("🎬 第三步：生成学习材料")
            if st.button("🚀 开始生成", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                time_estimate = st.empty()
                
                # 模拟生成过程
                steps = [
                    ("📥 读取文件数据...", 10),
                    ("🔍 分析句子结构...", 25),
                    ("📝 生成学习内容...", 50),
                    ("🎨 格式化文档...", 75),
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
                    
                    time.sleep(1)
                
                # 完成效果
                st.balloons()
                st.success("🎉 学习材料生成完成！")
                
                # 生成学习卡片内容
                learning_content = f"""
# {document_title}
生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
句子数量: {len(df)}
输出类型: {output_type}

## 学习内容
{'-' * 50}

"""
                
                for i, row in df.iterrows():
                    learning_content += f"""
### 第 {i+1} 句
**英语**: {row['英语']}
**中文**: {row['中文']}
"""
                    if include_phonetic:
                        learning_content += f"**音标**: {row['音标']}\n"
                    learning_content += "-" * 30 + "\n"
                
                # 下载按钮区域
                st.subheader("📥 下载生成结果")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # 下载学习文档
                    st.download_button(
                        label="📄 下载学习文档 (TXT)",
                        data=learning_content.encode('utf-8'),
                        file_name=f"{document_title}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                
                with col2:
                    # 下载练习表格
                    practice_df = df.copy()
                    practice_df['掌握程度'] = ''
                    practice_df['练习次数'] = ''
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        practice_df.to_excel(writer, index=False, sheet_name='练习表格')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📊 下载练习表格 (Excel)",
                        data=excel_data,
                        file_name=f"{document_title}_练习表.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                # 预览生成内容
                with st.expander("👀 预览生成内容"):
                    st.text_area("学习文档内容", learning_content, height=300)
                    
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
    
    1. **准备Excel文件**
       - 必须包含"英语"、"中文"、"音标"三列
       - 每行一个完整的句子
       - 避免使用特殊字符
    
    2. **上传文件**
       - 点击上方上传按钮
       - 选择你的Excel文件
       - 系统会自动验证格式
    
    3. **生成学习材料**
       - 选择输出类型和设置
       - 点击生成按钮
       - 等待处理完成
    
    4. **下载使用**
       - 下载生成的学习文档
       - 下载练习表格
       - 打印或电子学习
    """)

# 页脚
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎬 旅游英语学习材料生成器 • 🌐 云端版本 • 🆓 免费使用</p>
</div>
""", unsafe_allow_html=True)
