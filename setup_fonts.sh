#!/bin/bash
echo "正在安装中文字体..."

# 创建字体目录
mkdir -p ~/.local/share/fonts

# 安装 Noto Sans CJK (支持中文、日文、韩文)
apt-get update
apt-get install -y fonts-noto-cjk

# 安装其他可能需要的字体
apt-get install -y fonts-wqy-microhei fonts-wqy-zenhei

# 刷新字体缓存
fc-cache -fv

echo "字体安装完成！"
