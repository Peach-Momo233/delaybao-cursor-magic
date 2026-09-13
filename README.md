# delay宝指针大法

一个带图形界面的 Windows 鼠标指针转换工具，可将 .ani、.cur
或包含这些文件的 ZIP、RAR 转换为 Linux Xcursor 主题。

适用于 Ubuntu 20.04-26.04 等提供 GTK3 的 Linux 系统。

## 软件截图

### 主界面

<img src="主界面.png" alt="delay宝指针大法主界面" width="700">

### 历史安装

<img src="历史记录.png" alt="历史安装窗口" width="520">

## 功能

- 拖放 ZIP、RAR、INF、ANI、CUR 文件
- 一键转换、安装并启用光标主题
- 调整光标大小
- 保存历史安装记录并快速切换
- 恢复 Yaru 默认主题
- 一键卸载程序安装的主题

## 从 GitHub 安装

    git clone https://github.com/Peach-Momo233/delaybao-cursor-magic.git
    cd delaybao-cursor-magic
    sudo ./install.sh

安装后在应用菜单中搜索“delay宝指针大法”，或运行：

    delaybao-cursor-gtk3

## 使用方法

1. 把鼠标皮肤拖入窗口，或点击“选择皮肤文件”。
2. 点击“转换并安装”。
3. 等待进度条完成，新主题会自动启用。
4. 使用滑杆调整光标大小。

“历史安装”可以切换以前安装过的皮肤。“删除记录”只删除历史按钮，
不会删除主题文件。

## 安装 DEB

也可以下载 Release 页面中的 .deb 文件并双击安装，或运行：

    sudo apt install ./delay宝指针大法_1.0.5_ubuntu_gtk3_all.deb

## 卸载

如果通过 GitHub 源码安装：

    cd delaybao-cursor-magic
    sudo ./uninstall.sh

如果通过 DEB 安装：

    sudo apt remove delaybao-cursor-magic-gtk3

卸载程序不会删除用户已经安装的光标主题和历史记录。

## 许可证

本项目采用 GPL-3.0-or-later。

光标转换逻辑参考并改编自：

- https://github.com/quantum5/win2xcur
- https://github.com/Hello-lingu/win2xcur
