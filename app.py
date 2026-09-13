#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from converter import install_theme, remove_theme

APP_DIR = Path(__file__).resolve().parent
STATE_DIR = Path.home() / ".config" / "delaybao-cursor"
STATE_FILE = STATE_DIR / "state.json"


def add_class(widget, *names):
    context = widget.get_style_context()
    for name in names:
        context.add_class(name)


def setting_get(key, fallback):
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", key],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True
        ).stdout.strip()
        return result.strip("'")
    except Exception:
        return fallback


def setting_set(key, value):
    subprocess.run(
        ["gsettings", "set", "org.gnome.desktop.interface", key, value],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(data):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class DelaybaoWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        Gtk.ApplicationWindow.__init__(self, application=app)
        self.set_title("delay宝指针大法")
        self.set_default_size(720, 640)
        self.set_resizable(False)
        self.source = None  # type: Optional[Path]
        self.state = load_state()
        self.slider_timer = 0
        self._build_ui()
        self._refresh_state()
        self.show_all()

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        add_class(root, "app-root")
        self.add(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        add_class(header, "macaron-header")
        bow = Gtk.Image.new_from_file(str(APP_DIR / "bow.svg"))
        add_class(bow, "bow-icon")
        header.pack_start(bow, False, False, 0)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="delay宝指针大法", xalign=0)
        add_class(title, "app-title")
        subtitle = Gtk.Label(label="把喜欢的光标，变成 Linux 的小糖果", xalign=0)
        add_class(subtitle, "app-subtitle")
        title_box.pack_start(title, False, False, 0)
        title_box.pack_start(subtitle, False, False, 0)
        header.pack_start(title_box, False, False, 0)
        self.theme_badge = Gtk.Label()
        add_class(self.theme_badge, "theme-badge")
        header.pack_end(self.theme_badge, False, False, 0)
        root.pack_start(header, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        add_class(body, "pink-body")
        body.set_margin_start(38)
        body.set_margin_end(38)
        body.set_margin_top(24)
        body.set_margin_bottom(22)
        root.pack_start(body, True, True, 0)

        self.drop = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        add_class(self.drop, "drop-card")
        self.drop.set_size_request(-1, 175)
        drop_title = Gtk.Label(label="把鼠标皮肤拖放到这里")
        add_class(drop_title, "drop-title")
        drop_hint = Gtk.Label(label="支持 ZIP / RAR / INF / ANI / CUR")
        add_class(drop_hint, "drop-hint")
        self.file_label = Gtk.Label(label="也可以点击下方按钮选择文件")
        self.file_label.set_ellipsize(3)
        add_class(self.file_label, "file-label")
        choose = Gtk.Button(label="选择皮肤文件")
        add_class(choose, "blue-button")
        choose.set_halign(Gtk.Align.CENTER)
        choose.connect("clicked", self._choose_file)
        self.drop.pack_start(drop_title, True, False, 0)
        self.drop.pack_start(drop_hint, False, False, 0)
        self.drop.pack_start(self.file_label, False, False, 0)
        self.drop.pack_start(choose, False, False, 0)
        body.pack_start(self.drop, False, False, 0)

        self.drop.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drop.drag_dest_add_uri_targets()
        self.drop.connect("drag-motion", self._drag_motion)
        self.drop.connect("drag-leave", self._drag_leave)
        self.drop.connect("drag-data-received", self._drag_received)

        size_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        add_class(size_card, "size-card")
        size_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        size_title = Gtk.Label(label="光标大小", xalign=0)
        add_class(size_title, "section-title")
        self.size_value = Gtk.Label()
        add_class(self.size_value, "size-badge")
        size_row.pack_start(size_title, True, True, 0)
        size_row.pack_end(self.size_value, False, False, 0)
        size_card.pack_start(size_row, False, False, 0)
        current_size = int(setting_get("cursor-size", "48"))
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 16, 96, 1)
        self.scale.set_value(current_size)
        self.scale.set_draw_value(False)
        for mark in (24, 32, 48, 64, 80, 96):
            self.scale.add_mark(mark, Gtk.PositionType.BOTTOM, str(mark))
        self.scale.connect("value-changed", self._size_changed)
        size_card.pack_start(self.scale, False, False, 0)
        body.pack_start(size_card, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("等待选择皮肤")
        add_class(self.progress, "candy-progress")
        body.pack_start(self.progress, False, False, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.install_button = Gtk.Button(label="转换并安装")
        add_class(self.install_button, "primary-button")
        self.install_button.set_sensitive(False)
        self.install_button.connect("clicked", self._install)
        reset = Gtk.Button(label="恢复默认")
        add_class(reset, "blue-button")
        reset.connect("clicked", self._restore)
        self.uninstall_button = Gtk.Button(label="一键卸载")
        add_class(self.uninstall_button, "danger-button")
        self.uninstall_button.connect("clicked", self._uninstall)
        history = Gtk.Button(label="历史安装")
        add_class(history, "history-button")
        history.connect("clicked", self._show_history)
        for button in (self.install_button, reset, self.uninstall_button, history):
            actions.pack_start(button, True, True, 0)
        body.pack_start(actions, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.status = Gtk.Label(label="准备好了", xalign=0)
        self.status.set_line_wrap(True)
        add_class(self.status, "status-label")
        hearts = Gtk.Image.new_from_file(str(APP_DIR / "hearts.svg"))
        add_class(hearts, "pixel-hearts")
        footer.pack_start(self.status, True, True, 0)
        footer.pack_end(hearts, False, False, 0)
        body.pack_start(footer, False, False, 0)

    def _choose_file(self, _button):
        dialog = Gtk.FileChooserDialog(
            title="选择鼠标皮肤", parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            "取消", Gtk.ResponseType.CANCEL,
            "选择", Gtk.ResponseType.OK
        )
        file_filter = Gtk.FileFilter()
        file_filter.set_name("鼠标皮肤（ZIP、RAR、INF、ANI、CUR）")
        for pattern in ("*.zip", "*.ZIP", "*.rar", "*.RAR", "*.inf", "*.INF",
                        "*.ani", "*.ANI", "*.cur", "*.CUR"):
            file_filter.add_pattern(pattern)
        dialog.add_filter(file_filter)
        if dialog.run() == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
            if filename:
                self._select(Path(filename))
        dialog.destroy()

    def _drag_motion(self, *_args):
        add_class(self.drop, "drag-active")
        return True

    def _drag_leave(self, *_args):
        self.drop.get_style_context().remove_class("drag-active")

    def _drag_received(self, widget, context, x, y, selection, info, time):
        self.drop.get_style_context().remove_class("drag-active")
        uris = selection.get_uris() or []
        if uris:
            parsed = urlparse(uris[0])
            if parsed.scheme == "file":
                self._select(Path(unquote(parsed.path)))
                Gtk.drag_finish(context, True, False, time)
                return
        Gtk.drag_finish(context, False, False, time)

    def _select(self, path):
        if path.suffix.lower() not in (".zip", ".rar", ".inf", ".ani", ".cur"):
            self._message("不支持这个格式，请选择 ZIP、RAR、INF、ANI 或 CUR", True)
            return
        self.source = path
        self.file_label.set_text("已选择：{}".format(path.name))
        self.install_button.set_sensitive(True)
        self.progress.set_fraction(0)
        self.progress.set_text("等待转换")
        self._message("文件已就位，点击“转换并安装”吧")

    def _size_changed(self, scale):
        value = int(scale.get_value())
        self.size_value.set_text(str(value))
        if self.slider_timer:
            GLib.source_remove(self.slider_timer)
        self.slider_timer = GLib.timeout_add(120, self._apply_size, value)

    def _apply_size(self, value):
        self.slider_timer = 0
        try:
            current_theme = setting_get("cursor-theme", "Yaru")
            setting_set("cursor-size", str(value))
            if current_theme != "Yaru":
                setting_set("cursor-theme", "Yaru")
                setting_set("cursor-theme", current_theme)
            self.status.set_text("光标大小已调整为 {}".format(value))
        except Exception as exc:
            self._message("调整失败：{}".format(exc), True)
        return False

    def _install(self, _button):
        if not self.source:
            return
        self._busy(True)
        source = self.source

        def progress(value, message):
            GLib.idle_add(self._set_progress, value, message)

        def worker():
            try:
                theme_id, path, roles = install_theme(source, progress)
                setting_set("cursor-theme", "Yaru")
                setting_set("cursor-theme", theme_id)
                self.state["last_theme"] = theme_id
                self.state.setdefault("themes", {})[theme_id] = {
                    "display_name": source.stem,
                    "source": str(source),
                    "path": str(path),
                }
                save_state(self.state)
                GLib.idle_add(self._installed, len(roles))
            except Exception as exc:
                GLib.idle_add(self._failed, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _set_progress(self, value, message):
        self.progress.set_fraction(value)
        self.progress.set_text(message)
        return False

    def _installed(self, count):
        self._busy(False)
        self.progress.set_fraction(1)
        self.progress.set_text("转换、安装、启用完成")
        self._message("甜甜完成！已识别并安装 {} 种光标角色".format(count))
        self._refresh_state()
        return False

    def _failed(self, message):
        self._busy(False)
        self.progress.set_fraction(0)
        self.progress.set_text("转换失败")
        self._message("没有成功：{}".format(message), True)
        return False

    def _restore(self, _button):
        try:
            setting_set("cursor-theme", "Yaru")
            setting_set("cursor-size", "24")
            self.scale.set_value(24)
            self._message("已恢复 Yaru 默认主题，大小为 24")
            self._refresh_state()
        except Exception as exc:
            self._message("恢复失败：{}".format(exc), True)

    def _uninstall(self, _button):
        theme_id = self.state.get("last_theme")
        if not theme_id:
            self._message("没有找到本程序安装的主题")
            return
        try:
            if setting_get("cursor-theme", "Yaru") == theme_id:
                setting_set("cursor-theme", "Yaru")
            removed = remove_theme(theme_id)
            self.state.get("themes", {}).pop(theme_id, None)
            self.state["last_theme"] = next(iter(self.state.get("themes", {})), "")
            save_state(self.state)
            self._message(
                "主题已卸载，当前已切回 Yaru" if removed else "主题文件已经不存在"
            )
            self._refresh_state()
        except Exception as exc:
            self._message("卸载失败：{}".format(exc), True)

    def _show_history(self, _button):
        window = Gtk.Window(title="历史安装", transient_for=self, modal=True)
        window.set_default_size(520, 400)
        window.set_resizable(False)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        add_class(outer, "history-window")
        outer.set_border_width(22)
        heading = Gtk.Label(label="以前安装过的鼠标皮肤", xalign=0)
        add_class(heading, "history-title")
        hint = Gtk.Label(
            label="点击名字即可切换；删除只移除这条记录，不会删除电脑里的皮肤文件。",
            xalign=0
        )
        hint.set_line_wrap(True)
        add_class(hint, "history-hint")
        outer.pack_start(heading, False, False, 0)
        outer.pack_start(hint, False, False, 0)
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        outer.pack_start(list_box, True, True, 0)
        close = Gtk.Button(label="关闭")
        add_class(close, "blue-button")
        close.set_halign(Gtk.Align.END)
        close.connect("clicked", lambda _button: window.close())
        outer.pack_end(close, False, False, 0)
        window.add(outer)

        def rebuild():
            for child in list_box.get_children():
                list_box.remove(child)
            themes = self.state.get("themes", {})
            if not themes:
                empty = Gtk.Label(label="还没有安装记录 O_o")
                add_class(empty, "history-empty")
                list_box.pack_start(empty, True, True, 0)
            else:
                current = setting_get("cursor-theme", "Yaru")
                for theme_id, record in themes.items():
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                    add_class(row, "history-row")
                    display_name = record.get("display_name")
                    if not display_name:
                        source = record.get("source", "")
                        display_name = Path(source).stem if source else theme_id
                    switch = Gtk.Button(label=display_name)
                    add_class(switch, "history-theme-button")
                    if current == theme_id:
                        add_class(switch, "active-theme")
                    switch.set_tooltip_text(record.get("path", theme_id))
                    switch.connect(
                        "clicked",
                        lambda _b, selected=theme_id:
                        self._switch_history(selected, window)
                    )
                    forget = Gtk.Button(label="删除记录")
                    add_class(forget, "forget-button")
                    forget.set_tooltip_text("只删除历史记录，不删除主题文件")
                    forget.connect(
                        "clicked",
                        lambda _b, selected=theme_id:
                        self._forget_history(selected, rebuild)
                    )
                    row.pack_start(switch, True, True, 0)
                    row.pack_end(forget, False, False, 0)
                    list_box.pack_start(row, False, False, 0)
            list_box.show_all()

        rebuild()
        window.show_all()

    def _switch_history(self, theme_id, history_window):
        record = self.state.get("themes", {}).get(theme_id, {})
        theme_path = Path(record.get(
            "path", str(Path.home() / ".icons" / theme_id)
        ))
        if not theme_path.is_dir():
            self._message("这个主题路径已经不存在，可用“删除记录”移除它", True)
            return
        try:
            setting_set("cursor-theme", theme_id)
            self.state["last_theme"] = theme_id
            save_state(self.state)
            self._message("已切换到：{}".format(
                record.get("display_name", theme_id)
            ))
            self._refresh_state()
            history_window.close()
        except Exception as exc:
            self._message("切换失败：{}".format(exc), True)

    def _forget_history(self, theme_id, rebuild):
        themes = self.state.get("themes", {})
        record = themes.pop(theme_id, None)
        if self.state.get("last_theme") == theme_id:
            self.state["last_theme"] = next(iter(themes), "")
        save_state(self.state)
        name = (record or {}).get("display_name", theme_id)
        self._message("已删除“{}”的记录，主题文件保持不变".format(name))
        self._refresh_state()
        rebuild()

    def _busy(self, busy):
        self.install_button.set_sensitive(not busy and self.source is not None)
        self.uninstall_button.set_sensitive(
            not busy and bool(self.state.get("last_theme"))
        )

    def _refresh_state(self):
        current = setting_get("cursor-theme", "Yaru")
        managed = current.startswith("Delaybao-")
        self.theme_badge.set_text("已启用" if managed else "当前：{}".format(current))
        self.uninstall_button.set_sensitive(bool(self.state.get("last_theme")))
        self.size_value.set_text(setting_get("cursor-size", "48"))

    def _message(self, text, error=False):
        self.status.set_text(text)
        context = self.status.get_style_context()
        if error:
            context.add_class("error")
        else:
            context.remove_class("error")


class DelaybaoApp(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(
            self, application_id="io.github.delaybao.CursorMagicGtk3"
        )

    def do_startup(self):
        Gtk.Application.do_startup(self)
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(str(APP_DIR / "style.css"))
        screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def do_activate(self):
        window = self.get_active_window()
        if not window:
            window = DelaybaoWindow(self)
        window.present()


if __name__ == "__main__":
    app = DelaybaoApp()
    raise SystemExit(app.run(sys.argv))
