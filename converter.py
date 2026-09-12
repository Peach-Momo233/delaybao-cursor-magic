"""Windows CUR/ANI to Xcursor converter used by delay宝指针大法.

The Xcursor writer and ANI parsing model follow the GPL-3.0 win2xcur project:
https://github.com/quantum5/win2xcur
"""

from __future__ import annotations

import io
import hashlib
import re
import shutil
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PIL import Image

MAX_ARCHIVE_SIZE = 150 * 1024 * 1024
MAX_FILES = 1000

ROLE_ALIASES = {
    "default": ("left_ptr", "openhand", "top_left_arrow"),
    "text": ("ibeam", "xterm"),
    "wait": ("watch",),
    "crosshair": ("cross",),
    "pointer": ("hand1", "hand2", "half-busy", "pointing_hand",
                "e29285e634086352946a0e7090d73106",
                "9d800788f1b08800ae810202380a0822"),
    "progress": ("left_ptr_watch", "08e8e1c95fe2fc01f976f1e063a24ccd",
                 "3ecb610c1bf2410f44200f48c40d3599"),
    "not-allowed": ("circle", "crossed_circle", "03b6e0fcb3499374a867c041f52298f0",
                    "pirate", "no-drop", "dnd-no-copy"),
    "pencil": ("draft",),
    "size_ver": ("split_v", "n-resize", "ns-resize", "row-resize", "s-resize",
                 "sb_v_double_arrow", "00008160000006810000408080010102",
                 "down-arrow", "bottom_side", "top_side"),
    "size_hor": ("e-resize", "ew-resize", "h_double_arrow", "left_side",
                 "right_side", "sb_h_double_arrow", "w-resize", "split_h",
                 "col-resize", "left-arrow", "right-arrow"),
    "size_fdiag": ("bottom_right_corner", "ul_angle", "lr_angle",
                   "top_left_corner", "sw-resize", "nw-resize", "nwse-resize",
                   "se-resize"),
    "size_bdiag": ("bottom_left_corner", "ur_angle", "ll_angle",
                   "top_right_corner", "ne-resize", "nesw-resize", "sw-resize"),
    "dnd-move": ("closedhand", "dnd-none", "fleur", "grabbing", "move",
                 "all-scroll", "size_all", "4498f0e0c1937ffe01fd06f973665830",
                 "9081237383d90e509aa00f00170e968f", "grab"),
    "help": ("5c6cd98b3f3ebcb1f9c7f1c204630408", "whats_this",
             "question_arrow", "left_ptr_help"),
    "up-arrow": ("link",),
}

ROLE_WORDS = {
    "default": ("普通", "正常", "标准", "normal", "default", "arrow"),
    "help": ("帮助", "help"),
    "wait": ("等待", "忙", "busy", "wait"),
    "crosshair": ("精准", "精确", "precision", "crosshair", "cross"),
    "pointer": ("链接", "link", "hand", "pointer"),
    "not-allowed": ("禁止", "不可用", "unavailable", "forbidden", "notallowed"),
    "size_ver": ("垂直", "vertical", "sizever"),
    "size_hor": ("水平", "horizontal", "sizehor"),
    "size_fdiag": ("对角线1", "diagonal1", "fdiag", "nwse"),
    "size_bdiag": ("对角线2", "diagonal2", "bdiag", "nesw"),
    "text": ("文本", "文字", "text", "ibeam"),
    "dnd-move": ("移动", "move", "sizeall"),
    "progress": ("后台", "工作", "working", "progress"),
    "pencil": ("手写", "handwriting", "pencil"),
    "up-arrow": ("备用", "alternate", "uparrow"),
}

FALLBACKS = {"progress": "wait", "pencil": "pointer", "up-arrow": "default"}
CURSOR_SIZES = tuple(range(16, 97, 4))


@dataclass
class CursorImage:
    image: Image.Image
    hotspot: Tuple[int, int]
    nominal: int


@dataclass
class CursorFrame:
    images: List[CursorImage]
    delay: float = 0.0


def _chunks(blob: bytes, start: int = 12):
    offset = start
    while offset + 8 <= len(blob):
        name, size = struct.unpack_from("<4sI", blob, offset)
        data = offset + 8
        yield name, blob[data:data + size]
        offset = data + size + (size & 1)


def parse_cur(blob: bytes) -> CursorFrame:
    if len(blob) < 6:
        raise ValueError("CUR 文件过短")
    reserved, kind, count = struct.unpack_from("<HHH", blob)
    if reserved != 0 or kind not in (1, 2) or count < 1:
        raise ValueError("不是有效的 CUR/ICO 文件")
    entries = []
    for index in range(count):
        off = 6 + index * 16
        if off + 16 > len(blob):
            break
        width, height, _, _, hx, hy, size, data_off = struct.unpack_from(
            "<BBBBHHII", blob, off
        )
        entries.append((width or 256, height or 256, hx, hy, size, data_off))
    images = []
    pil = Image.open(io.BytesIO(blob))
    ico = getattr(pil, "ico", None)
    for width, height, hx, hy, size, data_off in entries:
        try:
            if ico is not None:
                frame = ico.getimage((width, height)).convert("RGBA")
            else:
                frame = Image.open(io.BytesIO(blob[data_off:data_off + size])).convert("RGBA")
        except Exception:
            frame = pil.copy().convert("RGBA")
        images.append(CursorImage(frame, (min(hx, frame.width - 1),
                                          min(hy, frame.height - 1)), width))
    if not images:
        images.append(CursorImage(pil.convert("RGBA"), (0, 0), pil.width))
    return CursorFrame(images)


def parse_ani(blob: bytes) -> List[CursorFrame]:
    if blob[:4] != b"RIFF" or blob[8:12] != b"ACON":
        raise ValueError("不是有效的 ANI 文件")
    header = None
    order = None
    rates = None
    icons = []
    for name, data in _chunks(blob):
        if name == b"anih" and len(data) >= 36:
            header = struct.unpack_from("<9I", data)
        elif name == b"seq ":
            order = list(struct.iter_unpack("<I", data))
            order = [item[0] for item in order]
        elif name == b"rate":
            rates = [item[0] for item in struct.iter_unpack("<I", data)]
        elif name == b"LIST" and data[:4] == b"fram":
            for inner_name, inner in _chunks(b"RIFF\0\0\0\0FAKE" + data[4:]):
                if inner_name == b"icon":
                    icons.append(parse_cur(inner))
    if not header or not icons:
        raise ValueError("ANI 中没有可用帧")
    _, frame_count, step_count, _, _, _, _, default_rate, _ = header
    order = order or list(range(min(frame_count, len(icons))))
    rates = rates or [default_rate] * max(step_count, len(order))
    frames = []
    for index, rate in zip(order, rates):
        if index >= len(icons):
            continue
        base = icons[index]
        frames.append(CursorFrame(base.images, max(rate, 1) / 60.0))
    return frames or icons


def parse_cursor(path: Path) -> List[CursorFrame]:
    blob = path.read_bytes()
    return parse_ani(blob) if path.suffix.lower() == ".ani" else [parse_cur(blob)]


def _premultiply_bgra(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA")
    out = bytearray()
    for r, g, b, a in rgba.getdata():
        out.extend((b * a // 255, g * a // 255, r * a // 255, a))
    return bytes(out)


def to_xcursor(frames: List[CursorFrame]) -> bytes:
    chunk_type = 0xFFFD0002
    chunks = []
    for frame in frames:
        for target_size in CURSOR_SIZES:
            cursor = min(
                frame.images,
                key=lambda item: abs(item.nominal - target_size),
            )
            ratio = target_size / max(cursor.nominal, 1)
            width = max(1, round(cursor.image.width * ratio))
            height = max(1, round(cursor.image.height * ratio))
            resampling = getattr(Image, "Resampling", Image)
            image = cursor.image.resize((width, height), resampling.LANCZOS)
            hx = min(width - 1, max(0, round(cursor.hotspot[0] * ratio)))
            hy = min(height - 1, max(0, round(cursor.hotspot[1] * ratio)))
            image_header = struct.pack(
                "<9I", 36, chunk_type, target_size, 1, image.width,
                image.height, hx, hy, int(frame.delay * 1000)
            )
            chunks.append((chunk_type, target_size,
                           image_header + _premultiply_bgra(image)))
    header = struct.pack("<4sIII", b"Xcur", 16, 0x00010000, len(chunks))
    offset = 16 + 12 * len(chunks)
    toc = []
    for kind, subtype, chunk in chunks:
        toc.append(struct.pack("<III", kind, subtype, offset))
        offset += len(chunk)
    return header + b"".join(toc) + b"".join(item[2] for item in chunks)


def safe_name(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    suffix = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return (f"Delaybao-{clean}-{suffix}")[:60] if clean else f"Delaybao-Cursor-{suffix}"


def role_for(path: Path) -> Optional[str]:
    name = re.sub(r"[\s_.-]+", "", path.stem).lower()
    for role, words in ROLE_WORDS.items():
        if any(word.replace("-", "") in name for word in words):
            return role
    return None


def extract_input(source: Path, destination: Path) -> List[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES:
                raise ValueError("压缩包文件数量过多")
            if sum(item.file_size for item in infos) > MAX_ARCHIVE_SIZE:
                raise ValueError("压缩包解压后超过 150 MB")
            for info in infos:
                member_name = info.filename
                if not (info.flag_bits & 0x800):
                    try:
                        member_name = member_name.encode("cp437").decode("gbk")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        pass
                raw_parts = Path(member_name.replace("\\", "/")).parts
                if info.is_dir() or ".." in raw_parts or Path(member_name).is_absolute():
                    continue
                if Path(member_name).suffix.lower() not in (".ani", ".cur", ".inf"):
                    continue
                target = destination / Path(member_name).name
                with archive.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    elif suffix in (".ani", ".cur"):
        shutil.copy2(source, destination / source.name)
    elif suffix == ".inf":
        for item in source.parent.iterdir():
            if item.suffix.lower() in (".ani", ".cur"):
                shutil.copy2(item, destination / item.name)
    else:
        raise ValueError("请选择 ZIP、INF、ANI 或 CUR 文件")
    return sorted((*destination.glob("*.ani"), *destination.glob("*.cur")))


def install_theme(
    source: Path,
    progress: Optional[Callable[[float, str], None]] = None,
) -> Tuple[str, Path, Dict[str, str]]:
    notify = progress or (lambda _fraction, _message: None)
    if not source.exists():
        raise FileNotFoundError(source)
    theme_id = safe_name(source.stem)
    # ~/.icons is understood by both older Xcursor/GNOME releases (including
    # Ubuntu 20.04) and current desktops.
    install_root = Path.home() / ".icons"
    final = install_root / theme_id
    with tempfile.TemporaryDirectory(prefix="delaybao-") as work:
        workdir = Path(work)
        inputs = extract_input(source, workdir / "input")
        if not inputs:
            raise ValueError("没有找到可转换的 ANI/CUR 文件")
        output = workdir / theme_id
        cursors = output / "cursors"
        cursors.mkdir(parents=True)
        roles: Dict[str, str] = {}
        for index, path in enumerate(inputs, 1):
            role = role_for(path)
            if not role or role in roles:
                continue
            notify(index / (len(inputs) + 2), f"正在转换：{path.name}")
            (cursors / role).write_bytes(to_xcursor(parse_cursor(path)))
            roles[role] = path.name
        if "default" not in roles:
            raise ValueError("没有识别到普通/默认指针")
        for role, fallback in FALLBACKS.items():
            if role not in roles and (cursors / fallback).exists():
                shutil.copy2(cursors / fallback, cursors / role)
                roles[role] = f"回退到 {fallback}"
        for role, aliases in ROLE_ALIASES.items():
            target = cursors / role
            if not target.exists():
                continue
            for alias in aliases:
                link = cursors / alias
                if not link.exists():
                    link.symlink_to(role)
        (output / "index.theme").write_text(
            "[Icon Theme]\n"
            f"Name={source.stem}\n"
            "Comment=由 delay宝指针大法转换的 Xcursor 主题\n"
            "Inherits=Yaru\n",
            encoding="utf-8",
        )
        notify(0.9, "正在安装主题…")
        install_root.mkdir(parents=True, exist_ok=True)
        if final.exists():
            shutil.rmtree(final)
        shutil.copytree(output, final, symlinks=True)
    notify(1.0, "安装完成")
    return theme_id, final, roles


def remove_theme(theme_id: str) -> bool:
    if not theme_id.startswith("Delaybao-"):
        raise ValueError("拒绝删除非本程序管理的主题")
    removed = False
    for root in (
        Path.home() / ".icons",
        Path.home() / ".local" / "share" / "icons",
    ):
        path = root / theme_id
        if path.is_dir():
            shutil.rmtree(path)
            removed = True
    return removed
