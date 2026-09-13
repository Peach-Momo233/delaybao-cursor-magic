#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/usr/local/share/delaybao-cursor-gtk3"
APP_COMMAND="/usr/local/bin/delaybao-cursor-gtk3"
DESKTOP_FILE="/usr/local/share/applications/io.github.delaybao.CursorMagicGtk3.desktop"
ICON_FILE="/usr/local/share/icons/hicolor/scalable/apps/io.github.delaybao.CursorMagicGtk3.svg"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
    echo "请使用 sudo 运行：sudo ./install.sh"
    exit 1
fi

required_files=(app.py converter.py style.css bow.svg hearts.svg io.github.delaybao.CursorMagicGtk3.desktop)
for file in "${required_files[@]}"; do
    if [[ ! -f "${SOURCE_DIR}/${file}" ]]; then
        echo "缺少必要文件：${file}"
        exit 1
    fi
done

echo "[1/4] 安装运行依赖……"
apt-get update
apt-get install -y python3 python3-gi python3-pil gir1.2-gtk-3.0 libgtk-3-0 libglib2.0-bin unrar

echo "[2/4] 复制程序文件……"
install -d -m 755 "${APP_DIR}"
install -m 644 "${SOURCE_DIR}/app.py" "${APP_DIR}/app.py"
install -m 644 "${SOURCE_DIR}/converter.py" "${APP_DIR}/converter.py"
install -m 644 "${SOURCE_DIR}/style.css" "${APP_DIR}/style.css"
install -m 644 "${SOURCE_DIR}/bow.svg" "${APP_DIR}/bow.svg"
install -m 644 "${SOURCE_DIR}/hearts.svg" "${APP_DIR}/hearts.svg"

echo "[3/4] 创建启动命令和应用菜单……"
install -d -m 755 /usr/local/bin /usr/local/share/applications
install -d -m 755 /usr/local/share/icons/hicolor/scalable/apps

launcher_tmp="$(mktemp)"
trap 'rm -f "${launcher_tmp}"' EXIT
printf '%s\n' '#!/bin/sh' \
    'exec python3 /usr/local/share/delaybao-cursor-gtk3/app.py "$@"' \
    > "${launcher_tmp}"
install -m 755 "${launcher_tmp}" "${APP_COMMAND}"
install -m 644 "${SOURCE_DIR}/io.github.delaybao.CursorMagicGtk3.desktop" "${DESKTOP_FILE}"
install -m 644 "${SOURCE_DIR}/bow.svg" "${ICON_FILE}"

echo "[4/4] 刷新应用菜单和图标……"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/local/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/local/share/icons/hicolor || true
fi

echo
echo "安装完成！"
echo "终端命令：delaybao-cursor-gtk3"
echo "应用菜单：delay宝指针大法"
