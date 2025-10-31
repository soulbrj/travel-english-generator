# 🎬 旅游英语视频生成器

基于Streamlit的在线英语学习视频生成工具，无需安装任何软件，直接在浏览器中使用。

## 🌐 在线访问
https://your-app-name.streamlit.app/

## ✨ 功能特性
- 📁 一键上传Excel文件
- 🎵 AI智能语音合成
- 🎬 自动生成高清视频
- 📝 专业字幕显示
- 🌐 完全在线使用
- 🎨 自定义背景与文字样式
- 🎞️ 支持多种视频分辨率

## 📋 使用要求
Excel文件必须包含以下三列：
- 英语
- 中文  
- 音标

## 🔧 本地部署
1. 克隆仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 安装ffmpeg（必要组件）
4. 启动应用：`streamlit run streamlit_app.py`

## ⚠️ 注意事项
- 单个Excel文件大小限制为10MB
- 确保系统安装了中文字体以正常显示中文
- 音频功能需要ffmpeg支持
