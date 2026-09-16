#!/bin/bash
# move-download.sh — 每日凌晨将系统下载目录所有内容（含隐藏文件）归档到 ~/download-history/
# 不覆盖已存在的同名文件（mv -n）。由 crontab 每日 01:00 调用。
set -euo pipefail

mkdir -p "$HOME/download-history"

# 下载目录名随系统默认语言而异（英文 Downloads / 中文 "下载"），优先用 xdg-user-dir 探测
DOWNLOAD_DIR="$(xdg-user-dir DOWNLOAD 2>/dev/null || true)"
if [ -z "$DOWNLOAD_DIR" ] || [ ! -d "$DOWNLOAD_DIR" ]; then
    if [ -d "$HOME/Downloads" ]; then
        DOWNLOAD_DIR="$HOME/Downloads"
    elif [ -d "$HOME/下载" ]; then
        DOWNLOAD_DIR="$HOME/下载"
    else
        echo "未找到下载目录（Downloads / 下载 均不存在），本次跳过归档" >&2
        exit 0
    fi
fi

# dotglob 使 * 也匹配隐藏文件；nullglob 避免空目录时字面量 "*" 干扰
shopt -s dotglob nullglob

for item in "$DOWNLOAD_DIR/"*; do
    mv -n "$item" "$HOME/download-history/"
done
