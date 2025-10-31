# 旅行英语视频生成器 (Streamlit)

功能：
- 上传 Excel（列名：英语、中文、音标）
- 文字显示：英语（上）、音标（中）、中文（下），可调字号与颜色
- 支持背景图或纯色背景
- 多音色 TTS（edge-tts），可选择音色与语速
- 生成带音频视频并支持下载

## 本地运行
1. 克隆或下载本项目
2. 创建虚拟环境并激活（推荐）
3. 安装依赖：
pip install -r requirements.txt
4. 若需安装系统 ffmpeg（本地）：
- Windows: 下载并安装 ffmpeg，添加到 PATH
- macOS: `brew install ffmpeg`
- Ubuntu: `sudo apt-get install ffmpeg`
5. 运行：
streamlit run streamlit_app.py
6. 打开浏览器访问 http://localhost:8501
## 部署
- 可部署到 Railway / Streamlit Cloud 等，确保平台允许联网（edge-tts 需要联网）并安装 ffmpeg。
- Railway 示例已包含 `railway.json` 与 `packages.txt`（包含 ffmpeg）。

## 注意
- edge-tts 需要联网访问微软服务以生成音频。
- 生成高分辨率视频、大数量行时可能占用较多内存，建议先用少量行测试。
