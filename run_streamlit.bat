@echo off
chcp 65001 >nul
cls

echo ========================================
echo   旅游英语视频课件生成器 - Web版
echo ========================================
echo.

echo 步骤1: 检查Python环境...
python --version
if errorlevel 1 (
    echo.
    echo ❌ 未找到Python，请从 https://python.org 下载安装
    echo.
    pause
    exit /b 1
)

echo.
echo 步骤2: 检查依赖包...
pip install --upgrade pip
if errorlevel 1 (
    echo ❌ 无法升级pip，继续安装依赖...
)

echo.
echo 步骤3: 安装项目依赖...
pip install -r requirements_streamlit.txt
if errorlevel 1 (
    echo.
    echo ⚠️ 部分依赖安装失败，尝试手动安装...
    echo.
    pip install streamlit pandas openpyxl
    pip install pillow numpy
)

echo.
echo 步骤4: 创建输出目录...
if not exist "output_videos" mkdir output_videos

echo.
echo 步骤5: 启动Web应用...
echo.
echo ╔══════════════════════════════════════════╗
echo ║                                          ║
echo ║  应用将在浏览器中自动打开                ║
echo ║  访问地址: http://localhost:8501        ║
echo ║                                          ║
echo ║  按 Ctrl+C 停止服务                     ║
echo ║                                          ║
echo ╚══════════════════════════════════════════╝
echo.

rem 使用streamlit默认端口8501
streamlit run streamlit_app.py --server.port 8501 --server.headless false

pause