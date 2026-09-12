#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "请使用 sudo 运行：sudo ./uninstall.sh"
    exit 1
fi

echo "正在卸载 delay宝指针大法……"
rm -f /usr/local/bin/delaybao-cursor-gtk3
rm -f /usr/local/share/applications/io.github.delaybao.CursorMagicGtk3.desktop
rm -f /usr/local/share/icons/hicolor/scalable/apps/io.github.delaybao.CursorMagicGtk3.svg
rm -rf /usr/local/share/delaybao-cursor-gtk3

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/local/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/local/share/icons/hicolor || true
fi

echo "程序已卸载。"
echo "用户安装的光标主题和历史记录已保留。"
