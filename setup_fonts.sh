#!/bin/bash
echo "正在安装中文字体..."

# 更新包列表并安装中文字体
apt-get update
apt-get install -y fonts-noto-cjk fonts-wqy-microhei fonts-wqy-zenhei

# 刷新字体缓存
fc-cache -fv

echo "字体安装完成！"
