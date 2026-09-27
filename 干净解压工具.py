#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
干净解压工具 CleanUnarchiver
============================
一款面向 Windows 的纯净解压缩工具：
  - 无广告、无弹窗、无捆绑安装
  - 支持 zip / 7z / rar / tar / tar.gz / tar.bz2 / tar.xz / gz / bz2 / xz
  - 拖拽即解压，支持多文件批量、进度显示、加密压缩包密码
  - 内置“路径穿越”防护，解压更安全
  - 界面自适应：窗口放大时列表区变大，缩小时其余控件始终可见

运行方式：
  双击本文件，或
  python 干净解压工具.py [压缩包路径...]
  也可在资源管理器中右键 -> 打开方式 -> 选择本脚本。
"""

import os
import sys
import threading
import shutil
import subprocess
import tempfile
import zipfile
import tarfile
import gzip
import bz2
import lzma

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False

try:
    import py7zr
except Exception:
    py7zr = None

try:
    import rarfile
except Exception:
    rarfile = None

try:
    import pyzstd            # Zstandard（.zst / .tar.zst）
except Exception:
    pyzstd = None
try:
    import lz4.frame as lz4_frame   # LZ4（.lz4 / .tar.lz4）
except Exception:
    lz4_frame = None
try:
    import pyzipper         # WinZip AES 加密的 zip
except Exception:
    pyzipper = None


APP_TITLE = "干净解压工具 · CleanUnarchiver"
APP_NAME = "干净解压工具"
VERSION = "1.0.0"
COMPANY_NAME = "深圳市研融科技有限公司"

# 品牌色
BRAND_BLUE = "#1f6fed"
BRAND_DARK = "#143a8a"
BRAND_LIGHT = "#f5f7fa"
BRAND_TEXT = "#1f2d3d"
BRAND_MUTED = "#8a97a8"
BANNER_TOP = "#2f7bf0"
BANNER_BOTTOM = "#1a55c8"


def _resource_path(rel):
    """同时兼容源码运行与 PyInstaller 打包后的运行环境。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _gradient(canvas, top, bottom, width, height):
    """在 Canvas 上绘制自上而下的品牌渐变。"""
    steps = 64
    for i in range(steps):
        r = top[0] + (bottom[0] - top[0]) * i / steps
        g = top[1] + (bottom[1] - top[1]) * i / steps
        b = top[2] + (bottom[2] - top[2]) * i / steps
        color = "#%02x%02x%02x" % (int(r), int(g), int(b))
        y0 = int(height * i / steps)
        y1 = int(height * (i + 1) / steps)
        canvas.create_rectangle(0, y0, width, y1, fill=color, outline=color)
    canvas.update_idletasks()

# ---------------------------------------------------------------------------
# 压缩格式识别（先按扩展名，再按文件头 magic bytes 兜底）
# ---------------------------------------------------------------------------

def _magic(path, n):
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except Exception:
        return b""


def detect_archive(path):
    """返回 (格式名, 是否容器型)。容器型=内部有多个文件需保持目录结构。"""
    name = path.lower()
    ext = os.path.splitext(name)[1]

    # 先看扩展名
    if ext == ".zip" or name.endswith(".zipx"):
        return "zip", True
    if ext in (".7z",):
        return "7z", True
    if ext in (".rar", ".rev"):
        # RAR 是专有格式，必须用文件头核实，避免把“改名/伪装的非 RAR 文件”误当 RAR 处理
        if _magic(path, 4)[:4] == b"Rar!":
            return "rar", True
        # 扩展名是 .rar 但魔数不是 → 可能是被改名/伪装的其它格式。
        # 常见为“自定义前导头 + 内嵌 ZIP”的安装器/浏览器扩展包（如 Cr24 头），
        # zipfile 会从文件末尾的 EOCD 定位中央目录，天然能处理这类前导头。
        if zipfile.is_zipfile(path):
            return "zip", True
        # 仍不是 → 继续用下面的文件头识别（命中其他格式则返回，否则 None）
    if ext in (".tar",):
        return "tar", True
    if name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz",
                      ".tar.zst", ".tzst", ".tar.lz4", ".tlz4")):
        return "tar", True
    if ext == ".gz":
        return "gz", False
    if ext == ".bz2":
        return "bz2", False
    if ext == ".xz":
        return "xz", False
    if ext == ".zst":
        return "zst", False
    if ext == ".lz4":
        return "lz4", False
    if ext == ".cab":
        return "cab", True

    # 扩展名不可靠时用 magic bytes
    h = _magic(path, 6)
    if h[:4] == b"PK\x03\x04" or h[:4] == b"PK\x05\x06" or h[:4] == b"PK\x07\x08":
        return "zip", True
    if h[:6] == b"7z\xbc\xaf\x27\x1c":
        return "7z", True
    if h[:4] == b"Rar!":
        return "rar", True
    if h[:2] == b"\x1f\x8b":
        return "gz", False
    if h[:3] == b"BZh":
        return "bz2", False
    if h[:6] == b"\xfd7zXZ\x00":
        return "xz", False
    if h[:4] == b"\x28\xb5\x2f\xfd":      # Zstandard frame
        return "zst", False
    if h[:4] == b"\x04\x22\x4d\x18":      # LZ4 frame
        return "lz4", False
    if h[:4] == b"MSCF":                   # Microsoft CAB
        return "cab", True
    # tar 无固定头，靠 257 偏移的 ustar 判断
    if _magic(path, 262)[257:262] == b"ustar":
        return "tar", True

    return None, False


# ---------------------------------------------------------------------------
# 文件校验：检测文件真实格式，与扩展名比对，动态匹配解压工具
# ---------------------------------------------------------------------------

FORMAT_FULL = {
    "zip": "ZIP 压缩包", "7z": "7Z 压缩包", "rar": "RAR 压缩包", "tar": "TAR 归档",
    "gz": "GZIP 单文件", "bz2": "BZIP2 单文件", "xz": "XZ 单文件",
    "zst": "Zstandard 单文件", "lz4": "LZ4 单文件", "cab": "CAB 压缩包",
}


def _detect_real_format(path):
    """只看文件内容（magic bytes + 结构探测），返回真实格式名或 None。"""
    h = _magic(path, 6)
    if h[:6] == b"7z\xbc\xaf\x27\x1c":
        return "7z"
    if h[:4] == b"Rar!":
        return "rar"
    if h[:2] == b"\x1f\x8b":
        return "gz"
    if h[:3] == b"BZh":
        return "bz2"
    if h[:6] == b"\xfd7zXZ\x00":
        return "xz"
    if h[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        return "zip"
    if h[:4] == b"\x28\xb5\x2f\xfd":
        return "zst"
    if h[:4] == b"\x04\x22\x4d\x18":
        return "lz4"
    if h[:4] == b"MSCF":
        return "cab"
    if _magic(path, 262)[257:262] == b"ustar":
        return "tar"
    # 兜底：可能是“自定义前导头 + 内嵌 ZIP”（如 Cr24 头扩展包/安装器）
    if zipfile.is_zipfile(path):
        return "zip"
    return None


def _extension_claimed_format(path):
    """只看扩展名，返回扩展名声称的格式名或 None。"""
    name = path.lower()
    if name.endswith((".zip", ".zipx")):
        return "zip"
    if name.endswith(".7z"):
        return "7z"
    if name.endswith((".rar", ".rev")):
        return "rar"
    if name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz",
                      ".tar.zst", ".tzst", ".tar.lz4", ".tlz4", ".tar")):
        return "tar"
    if name.endswith(".gz"):
        return "gz"
    if name.endswith(".bz2"):
        return "bz2"
    if name.endswith(".xz"):
        return "xz"
    if name.endswith(".zst"):
        return "zst"
    if name.endswith(".lz4"):
        return "lz4"
    if name.endswith(".cab"):
        return "cab"
    return None


def _fmt_label(fmt):
    return FORMAT_FULL.get(fmt, (fmt or "未知").upper())


def verify_archive(path):
    """校验文件：检测真实格式并与扩展名比对，动态匹配解压工具。

    返回 dict：
      - real:        真实格式（内容检测），None 表示无法识别
      - claimed:     扩展名声称的格式，None 表示扩展名无对应格式
      - match:       'ok' | 'mismatch' | 'unrecognized' | 'no_ext'
      - note:        人类可读说明
      - extract_fmt: 建议使用的解压格式（按真实格式动态匹配解压工具）
    """
    real = _detect_real_format(path)
    claimed = _extension_claimed_format(path)

    if real is None:
        return {"real": None, "claimed": claimed, "match": "unrecognized",
                "note": "内容无法识别为任何已知压缩格式（可能是伪装文件、程序或损坏/未下载完整的数据）",
                "extract_fmt": None}
    if claimed is None:
        return {"real": real, "claimed": None, "match": "no_ext",
                "note": f"扩展名无对应格式，内容实际是 {_fmt_label(real)}（已按真实格式匹配解压工具）",
                "extract_fmt": real}
    if claimed == real:
        return {"real": real, "claimed": claimed, "match": "ok",
                "note": f"扩展名与内容一致：{_fmt_label(real)}",
                "extract_fmt": real}
    return {"real": real, "claimed": claimed, "match": "mismatch",
            "note": f"扩展名声称 {_fmt_label(claimed)}，但内容实际是 {_fmt_label(real)}"
                    f"（已按真实格式匹配解压工具）",
            "extract_fmt": real}


# ---------------------------------------------------------------------------
# 路径穿越防护：拒绝绝对路径与 ".." 逃逸，防止解压到目标目录之外
# ---------------------------------------------------------------------------

def safe_member_name(member):
    """清洗压缩包内部成员名，返回一个相对安全路径（posix 风格）。
    返回 None 表示危险（含 .. 逃逸）；返回 '' 表示根目录条目（如 '.'），应映射到目标根。"""
    name = member.replace("\\", "/")
    parts = []
    for p in name.split("/"):
        if p in ("", "."):
            continue
        if p == "..":
            return None  # 危险：拒绝整个条目
        # 去掉盘符
        if len(p) == 2 and p[1] == ":":
            continue
        parts.append(p)
    return "/".join(parts)


def safe_extract_path(base_dir, member_name):
    """把内部名映射到安全的目标路径；若逃逸则抛异常。"""
    safe = safe_member_name(member_name)
    if safe is None:
        raise ValueError(f"发现不安全的路径条目，已跳过：{member_name!r}")
    if safe == "":
        # 根目录条目（'.' / 空）：映射到目标根，不做任何写入
        return os.path.abspath(base_dir), ""
    dest = os.path.join(base_dir, safe)
    base = os.path.abspath(base_dir)
    if not os.path.abspath(dest).startswith(base + os.sep):
        raise ValueError(f"路径越界，已跳过：{member_name!r}")
    return dest, safe


# ---------------------------------------------------------------------------
# 各类解压实现（统一产出进度信息文本便于显示）
# ---------------------------------------------------------------------------

def extract_zip(path, dest_dir, password, overwrite, log):
    # WinZip AES 加密（压缩方法 0x63 / 0x9901）走 pyzipper 分支
    try:
        with zipfile.ZipFile(path, "r") as _probe:
            aes = any(zi.compress_type in (0x9901, 0x63) for zi in _probe.infolist())
    except Exception:
        aes = False
    if aes:
        _extract_zip_aes(path, dest_dir, password, overwrite, log)
        return
    with zipfile.ZipFile(path, "r") as zf:
        infos = zf.infolist()
        total = len(infos)
        for i, zi in enumerate(infos, 1):
            target, safe = safe_extract_path(dest_dir, zi.filename)
            if zi.is_dir():
                os.makedirs(target, exist_ok=True)
                log(f"[{i}/{total}] 目录  {safe}")
                continue
            if not overwrite and os.path.exists(target):
                log(f"[{i}/{total}] 跳过（已存在）  {safe}")
                continue
            os.makedirs(os.path.dirname(target) or dest_dir, exist_ok=True)
            with zf.open(zi, pwd=password.encode() if password else None) as src, \
                 open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            log(f"[{i}/{total}] 解压  {safe}")


def _extract_zip_aes(path, dest_dir, password, overwrite, log):
    if pyzipper is None:
        raise RuntimeError(
            "该 zip 使用 WinZip AES 加密，需要 pyzipper 库支持，但当前环境中未安装。")
    with pyzipper.AESZipFile(path, "r") as zf:
        if password:
            zf.setpassword(password.encode())
        infos = zf.infolist()
        total = len(infos)
        for i, zi in enumerate(infos, 1):
            target, safe = safe_extract_path(dest_dir, zi.filename)
            if zi.is_dir():
                os.makedirs(target, exist_ok=True)
                log(f"[{i}/{total}] 目录  {safe}")
                continue
            if not overwrite and os.path.exists(target):
                log(f"[{i}/{total}] 跳过（已存在）  {safe}")
                continue
            os.makedirs(os.path.dirname(target) or dest_dir, exist_ok=True)
            with zf.open(zi) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            log(f"[{i}/{total}] 解压  {safe}")


def extract_7z(path, dest_dir, password, overwrite, log):
    if py7zr is None:
        raise RuntimeError("未安装 py7zr，无法解压 7z。请运行：python -m pip install py7zr")
    with py7zr.SevenZipFile(path, mode="r", password=password or None) as z:
        all_names = z.getnames()
        total = len(all_names)
        # 一次调用提取全部安全目标（py7zr 对同一句柄多次 extract 会触发 CRC 校验失败）
        targets = []
        for name in all_names:
            safe = safe_member_name(name)
            if not safe:
                log(f"[跳过] 不安全/空路径条目  {name}")
                continue
            if not overwrite and os.path.exists(os.path.join(dest_dir, safe)):
                log(f"[跳过] 已存在  {safe}")
                continue
            targets.append(name)
        if targets:
            z.extract(path=dest_dir, targets=targets)
        for i, name in enumerate(all_names, 1):
            safe = safe_member_name(name)
            if safe:
                log(f"[{i}/{total}] 解压  {safe}")


def _configure_rar_tool():
    """优先使用随软件内置的 UnRAR 工具（开箱即用，无需用户安装）；否则回退到系统已有工具。"""
    if rarfile is None:
        return
    bundled = _resource_path("UnRAR.exe")
    if os.path.exists(bundled):
        rarfile.UNRAR_TOOL = bundled


def _rar_tool_available():
    """兼容不同 rarfile 版本地检测 unrar/7z 是否可用。"""
    if rarfile is None:
        return False
    try:
        # 新版本 rarfile
        if hasattr(rarfile, "is_tool_available"):
            return bool(rarfile.is_tool_available())
        # 旧版本 rarfile（如 4.5）：通过 tool_setup 探测
        rarfile.tool_setup()
        return bool(getattr(rarfile, "UNRAR_TOOL", None))
    except Exception:
        return False


def extract_rar(path, dest_dir, password, overwrite, log):
    if rarfile is None:
        raise RuntimeError("未安装 rarfile，无法解压 rar。请运行：python -m pip install rarfile")
    _configure_rar_tool()
    if not _rar_tool_available():
        raise RuntimeError(
            "解压 rar 需要 unrar 或 7-Zip 工具，但系统中未找到。\n"
            "RAR 为专有格式，无法纯 Python 解压。请安装免费开源的 7-Zip：https://www.7-zip.org/"
        )
    try:
        rf = rarfile.RarFile(path)
    except Exception:
        raise RuntimeError(
            "不是有效的 RAR 压缩包（文件扩展名为 .rar，但内容并不是 RAR）。\n"
            "该文件可能是被改名/伪装的其它程序（如安装程序、自解压文件），\n"
            "也可能是损坏或未下载完整的文件。请确认文件来源。"
        ) from None
    infos = rf.infolist()
    total = len(infos)
    for i, info in enumerate(infos, 1):
        target, safe = safe_extract_path(dest_dir, info.filename)
        if info.isdir():
            os.makedirs(target, exist_ok=True)
            log(f"[{i}/{total}] 目录  {safe}")
            continue
        if not overwrite and os.path.exists(target):
            log(f"[{i}/{total}] 跳过（已存在）  {safe}")
            continue
        os.makedirs(os.path.dirname(target) or dest_dir, exist_ok=True)
        with rf.open(info, pwd=password or None) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)
        log(f"[{i}/{total}] 解压  {safe}")


def extract_tar(path, dest_dir, password, overwrite, log):
    low = path.lower()
    if low.endswith((".tar.zst", ".tzst")):
        if pyzstd is None:
            raise RuntimeError("解压 .tar.zst 需要 pyzstd 库，但当前环境中未安装。")
        ctx = tarfile.open(fileobj=pyzstd.ZstdFile(path, "r"), mode="r:")
    elif low.endswith((".tar.lz4", ".tlz4")):
        if lz4_frame is None:
            raise RuntimeError("解压 .tar.lz4 需要 lz4 库，但当前环境中未安装。")
        ctx = tarfile.open(fileobj=lz4_frame.open(path, "rb"), mode="r:")
    else:
        ctx = tarfile.open(path, "r:*")
    with ctx as tf:
        members = tf.getmembers()
        total = len(members)
        for i, mi in enumerate(members, 1):
            target, safe = safe_extract_path(dest_dir, mi.name)
            if mi.isdir():
                os.makedirs(target, exist_ok=True)
                log(f"[{i}/{total}] 目录  {safe}")
                continue
            if not overwrite and os.path.exists(target):
                log(f"[{i}/{total}] 跳过（已存在）  {safe}")
                continue
            os.makedirs(os.path.dirname(target) or dest_dir, exist_ok=True)
            src = tf.extractfile(mi)
            if src is None:
                log(f"[{i}/{total}] 跳过（特殊文件）  {safe}")
                continue
            with src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            log(f"[{i}/{total}] 解压  {safe}")


def extract_single(path, dest_dir, format_, overwrite, log):
    """单文件压缩（gz/bz2/xz/zst/lz4）。目标文件名去掉压缩扩展名。"""
    name = os.path.basename(path)
    out_name = name
    for ext in (".tar.gz", ".tgz", ".tar.zst", ".tzst", ".tar.lz4", ".tlz4",
                ".tar.bz2", ".tbz2", ".tar.xz", ".txz",
                ".gz", ".bz2", ".xz", ".zst", ".lz4"):
        if name.lower().endswith(ext):
            out_name = name[: -len(ext)]
            break
    if not out_name or out_name == name:
        out_name = name + ".out"
    target = os.path.join(dest_dir, out_name)
    if overwrite or not os.path.exists(target):
        if format_ == "zst":
            if pyzstd is None:
                raise RuntimeError("解压 .zst 需要 pyzstd 库，但当前环境中未安装。")
            src = pyzstd.ZstdFile(path, "r")
        elif format_ == "lz4":
            if lz4_frame is None:
                raise RuntimeError("解压 .lz4 需要 lz4 库，但当前环境中未安装。")
            src = lz4_frame.open(path, "rb")
        else:
            opener = {"gz": gzip.open, "bz2": bz2.open, "xz": lzma.open}
            src = opener[format_](path, "rb")
        with src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)
        log(f"解压  {name}  ->  {out_name}")
    else:
        log(f"跳过（已存在）  {out_name}")


def extract_cab(path, dest_dir, password, overwrite, log):
    """解压 Microsoft CAB。使用 Windows 自带的 expand.exe（零额外依赖）。
    注意：CAB 内嵌目录会被 expand 拍平，按文件名解到目标目录。"""
    exe = shutil.which("expand") or "expand.exe"
    os.makedirs(dest_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="cab_")
    try:
        r = subprocess.run([exe, path, "-F:*", tmp], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(
                "CAB 解压失败：" + (r.stderr.strip() or r.stdout.strip() or "expand 工具返回错误"))
        files = [f for f in os.listdir(tmp)
                 if os.path.isfile(os.path.join(tmp, f))]
        for i, f in enumerate(files, 1):
            target = os.path.join(dest_dir, f)
            if not overwrite and os.path.exists(target):
                log(f"[{i}/{len(files)}] 跳过（已存在）  {f}")
                continue
            shutil.move(os.path.join(tmp, f), target)
            log(f"[{i}/{len(files)}] 解压  {f}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log("提示：CAB 内嵌套目录已按文件名平铺到目标目录")


EXTRACTORS = {
    "zip": extract_zip,
    "7z": extract_7z,
    "rar": extract_rar,
    "tar": extract_tar,
    "gz": extract_single,
    "bz2": extract_single,
    "xz": extract_single,
    "zst": extract_single,
    "lz4": extract_single,
    "cab": extract_cab,
}


def extract_one(path, dest_dir, password, overwrite, log):
    fmt, container = detect_archive(path)
    if fmt is None:
        raise ValueError("无法识别的压缩格式：" + os.path.basename(path))
    # 单文件压缩若实为 tar.* 容器，交给 tar 处理
    if not container and path.lower().endswith(
            (".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz",
             ".tar.zst", ".tzst", ".tar.lz4", ".tlz4")):
        fmt = "tar"
    if fmt in ("gz", "bz2", "xz", "zst", "lz4"):
        extract_single(path, dest_dir, fmt, overwrite, log)
        return
    extractor = EXTRACTORS.get(fmt)
    if extractor is None:
        raise ValueError("暂不支持该格式：" + os.path.basename(path))
    extractor(path, dest_dir, password, overwrite, log)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class CleanUnarchiverApp:
    def __init__(self, root):
        self.root = root
        root.title(f"{APP_TITLE} - {COMPANY_NAME}")
        root.geometry("900x680")
        # 最小尺寸：保证所有固定控件（设置/按钮/进度/日志/底栏）与最小列表区同时可见
        root.minsize(720, 640)
        try:
            ico = _resource_path("app_icon.ico")
            if os.path.exists(ico):
                root.iconbitmap(ico)
        except Exception:
            pass

        self.files = []          # 待处理压缩包列表
        self.busy = False

        self._build_style()
        self._build_ui()

        for arg in sys.argv[1:]:
            self.add_file(arg)

    # ---------------- 样式 ----------------
    def _build_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        base = BRAND_LIGHT
        self.root.configure(bg=base)
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 11, "bold"),
                        background=BRAND_BLUE, foreground="white", padding=(20, 9))
        style.map("Accent.TButton", background=[("active", "#1e55c8"), ("disabled", "#9db6e8")])
        style.configure("TLabelframe", background=base, bordercolor="#d7deea")
        style.configure("TLabelframe.Label", background=base, font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TLabel", background=base, font=("Microsoft YaHei UI", 10))
        style.configure("Treeview", rowheight=26, font=("Microsoft YaHei UI", 10))
        style.configure("TProgressbar", troughcolor="#e6ebf4", background=BRAND_BLUE,
                        borderwidth=0, thickness=10)

    # ---------------- UI 搭建 ----------------
    def _draw_banner(self, banner):
        banner.delete("all")
        w = banner.winfo_width()
        _gradient(banner, (0x2f, 0x7b, 0xf0), (0x1a, 0x55, 0xc8), max(w, 1), 84)
        banner.create_text(28, 22, anchor="w", text=APP_NAME,
                           fill="white", font=("Microsoft YaHei UI", 20, "bold"))
        banner.create_text(28, 58, anchor="w", text="无广告 · 无弹窗 · 无捆绑安装 · 全本地运行",
                           fill="#dce7ff", font=("Microsoft YaHei UI", 9))
        banner.create_text(max(w - 28, 0), 26, anchor="e", text=COMPANY_NAME,
                           fill="white", font=("Microsoft YaHei UI", 10, "bold"))
        banner.create_text(max(w - 28, 0), 58, anchor="e", text=f"V{VERSION}",
                           fill="#dce7ff", font=("Microsoft YaHei UI", 9))

    def _build_ui(self):
        base = BRAND_LIGHT
        root = self.root

        # ---- 主布局：grid + 行权重，实现真正的自适应 ----
        # 列：整窗铺满
        root.columnconfigure(0, weight=1)
        # 行：列表行(1)可伸缩，其余行固定高度
        root.rowconfigure(1, weight=1, minsize=150)   # 待解压文件区：放大/收缩都只影响它
        root.rowconfigure(6, minsize=30)              # 底部品牌栏

        # 顶部品牌渐变横幅（宽度自适应）
        banner = tk.Canvas(root, height=84, highlightthickness=0, bd=0)
        banner.grid(row=0, column=0, sticky="ew")
        banner.bind("<Configure>", lambda e: self._draw_banner(banner))
        self._draw_banner(banner)

        # 待解压文件区（grid 权重行：窗口高时变大，窗口矮时收缩，其余控件始终可见）
        self.list_frame = ttk.LabelFrame(root, text=" 待解压文件 ")
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=6)

        self.drop_hint = tk.Label(self.list_frame,
                                  text="将压缩包拖到此处，或点击下方“添加文件”\n\n支持 zip / 7z / rar / tar / gz / bz2 / xz",
                                  bg="#ffffff", fg=BRAND_MUTED,
                                  font=("Microsoft YaHei UI", 11), justify="center")
        self.drop_hint.pack(fill="both", expand=True, pady=20)

        self.tree = ttk.Treeview(self.list_frame, columns=("name", "size", "fmt"),
                                 show="headings", selectmode="extended")
        self.tree.heading("name", text="文件名")
        self.tree.heading("size", text="大小")
        self.tree.heading("fmt", text="格式")
        self.tree.column("name", width=330, minwidth=120, anchor="w")
        self.tree.column("size", width=110, minwidth=80, anchor="e")
        self.tree.column("fmt", width=70, minwidth=60, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self._last_tree_w = 0
        self.tree.bind("<Configure>", self._resize_tree)   # 窗口拉伸时按比例缩放列宽

        if DND_AVAILABLE:
            for w in (self.list_frame, self.drop_hint, self.tree):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)

        # 解压设置
        opts = ttk.LabelFrame(root, text=" 解压设置 ")
        opts.grid(row=2, column=0, sticky="ew", padx=14, pady=4)
        opts.columnconfigure(1, weight=1)   # “解压到”输入框所在列可拉伸

        tk.Label(opts, text="解压到：", bg=base).grid(row=0, column=0, sticky="e",
                padx=(12, 4), pady=(9, 4))
        self.dest_var = tk.StringVar(value="源文件所在目录")
        self.dest_entry = tk.Entry(opts, textvariable=self.dest_var,
                                   font=("Microsoft YaHei UI", 10))
        self.dest_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=(9, 4))
        ttk.Button(opts, text="选择目录…", command=self._choose_dest).grid(
                row=0, column=2, padx=(4, 12), pady=(9, 4))

        self.overwrite_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opts, text="覆盖同名文件", variable=self.overwrite_var, bg=base,
                       font=("Microsoft YaHei UI", 10)).grid(
                row=1, column=0, columnspan=2, sticky="w", padx=(12, 4), pady=(2, 9))
        tk.Label(opts, text="  密码（加密压缩包）：", bg=base).grid(
                row=1, column=2, sticky="e", padx=(8, 4), pady=(2, 9))
        self.pwd_var = tk.StringVar()
        tk.Entry(opts, textvariable=self.pwd_var, width=16, show="•",
                 font=("Microsoft YaHei UI", 10)).grid(
                row=1, column=3, sticky="e", padx=(0, 12), pady=(2, 9))

        # 按钮栏
        btns = tk.Frame(root, bg=base)
        btns.grid(row=3, column=0, sticky="ew", padx=14, pady=6)
        ttk.Button(btns, text="添加文件…", command=self._choose_files).pack(side="left")
        ttk.Button(btns, text="校验文件", command=self._verify_files).pack(side="left", padx=8)
        ttk.Button(btns, text="移除选中", command=self._remove_selected).pack(side="left", padx=8)
        ttk.Button(btns, text="清空列表", command=self._clear_all).pack(side="left")
        self.extract_btn = ttk.Button(btns, text="开始解压", style="Accent.TButton",
                                      command=self._start_extract)
        self.extract_btn.pack(side="right")

        # 进度
        prog = tk.Frame(root, bg=base)
        prog.grid(row=4, column=0, sticky="ew", padx=14, pady=(2, 4))
        self.prog_var = tk.DoubleVar(value=0)
        self.prog_label = tk.Label(prog, text="就绪", bg=base, fg=BRAND_MUTED,
                                   font=("Microsoft YaHei UI", 9), anchor="w")
        self.prog_label.pack(fill="x")
        self.progress = ttk.Progressbar(prog, variable=self.prog_var, maximum=100)
        self.progress.pack(fill="x")

        # 日志
        logf = ttk.LabelFrame(root, text=" 解压日志 ")
        logf.grid(row=5, column=0, sticky="ew", padx=14, pady=(2, 6))
        self.log_box = tk.Text(logf, height=5, wrap="none", font=("Consolas", 9),
                               bg="#ffffff", fg="#3c4b5a", relief="flat",
                               state="disabled")
        sb = ttk.Scrollbar(logf, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_box.pack(side="left", fill="both", expand=True)

        # 底部品牌栏
        footer = tk.Frame(root, bg="#eef2f8")
        footer.grid(row=6, column=0, sticky="ew")
        tk.Label(footer, text=f"{COMPANY_NAME} · 版权所有",
                 bg="#eef2f8", fg=BRAND_MUTED, font=("Microsoft YaHei UI", 9)).pack(side="left", padx=14, pady=6)
        tk.Label(footer, text=f"软件著作权及知识产权归 {COMPANY_NAME} 所有",
                 bg="#eef2f8", fg=BRAND_MUTED, font=("Microsoft YaHei UI", 9)).pack(side="right", padx=14, pady=6)

    # ---------------- 自适应：列表列宽随窗口缩放 ----------------
    def _resize_tree(self, event):
        w = event.width
        if w < 300 or abs(w - self._last_tree_w) < 8:
            return
        self._last_tree_w = w
        self.tree.column("name", width=int(w * 0.62))
        self.tree.column("size", width=int(w * 0.23))
        self.tree.column("fmt", width=int(w * 0.15))

    # ---------------- 文件管理 ----------------
    def _on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        for p in paths:
            self.add_file(p)

    def add_file(self, path):
        path = os.path.normpath(path)
        if not os.path.isfile(path):
            return
        fmt, _ = detect_archive(path)
        if fmt is None:
            self._log(f"忽略非压缩文件：{os.path.basename(path)}", error=True)
            if os.path.splitext(path)[1].lower() in (".rar", ".rev"):
                msg = ("扩展名是 .rar，但内容并不是 RAR 压缩包。\n"
                       "可能是被改名/伪装的其它程序（如安装程序、自解压文件），\n"
                       "也可能是损坏或未下载完整的文件。")
            else:
                msg = "这不是支持的压缩格式：\n" + os.path.basename(path)
            messagebox.showwarning("提示", msg)
            return
        if os.path.normpath(path) in self.files:
            return
        self.files.append(os.path.normpath(path))
        size = os.path.getsize(path)
        self.tree.insert("", "end", values=(os.path.basename(path), self._human(size), fmt.upper()))
        self._toggle_hint()

    def _toggle_hint(self):
        if self.files:
            self.drop_hint.pack_forget()
            self.tree.pack(fill="both", expand=True)
        else:
            self.tree.pack_forget()
            self.drop_hint.pack(fill="both", expand=True, pady=20)

    def _remove_selected(self):
        sel = self.tree.selection()
        for item in sel:
            idx = self.tree.index(item)
            self.tree.delete(item)
            del self.files[idx]
        self._toggle_hint()

    def _clear_all(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.files.clear()
        self._toggle_hint()

    def _verify_files(self):
        """校验列表内所有文件的真实格式，与扩展名比对，并展示结果窗口。"""
        if not self.files:
            messagebox.showinfo("提示", "请先添加要校验的压缩包。")
            return
        win = tk.Toplevel(self.root)
        win.title(f"文件校验 - {APP_NAME}")
        win.geometry("780x430")
        win.configure(bg=BRAND_LIGHT)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="文件格式校验：检测内容真实格式，与扩展名比对，动态匹配解压工具",
                 bg=BRAND_LIGHT, fg=BRAND_TEXT, font=("Microsoft YaHei UI", 10)).pack(
                anchor="w", padx=14, pady=(12, 4))

        cols = ("name", "claimed", "real", "match", "note")
        tv = ttk.Treeview(win, columns=cols, show="headings")
        heads = {"name": "文件名", "claimed": "扩展名声称", "real": "内容真实格式",
                 "match": "是否一致", "note": "说明"}
        widths = {"name": 150, "claimed": 88, "real": 100, "match": 74, "note": 320}
        for c in cols:
            tv.heading(c, text=heads[c])
            tv.column(c, width=widths[c], anchor="w" if c != "match" else "center")
        vsb = ttk.Scrollbar(win, command=tv.yview)
        tv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=6)

        match_colors = {"ok": ("一致", "#1e8e3e"), "mismatch": ("不一致", "#e67e22"),
                        "unrecognized": ("无法识别", "#c0392b"), "no_ext": ("无扩展名", "#8e44ad")}
        for tag, (_label, color) in match_colors.items():
            tv.tag_configure(tag, foreground=color)

        for f in self.files:
            try:
                r = verify_archive(f)
            except Exception as e:
                r = {"match": "unrecognized", "claimed": None, "real": None,
                     "note": f"读取/校验失败：{e}", "extract_fmt": None}
            label, _ = match_colors.get(r["match"], ("未知", BRAND_MUTED))
            claimed = _fmt_label(r["claimed"]) if r["claimed"] else "—"
            real = _fmt_label(r["real"]) if r["real"] else "—"
            tv.insert("", "end", tags=(r["match"],),
                      values=(os.path.basename(f), claimed, real, label, r["note"]))

        bar = tk.Frame(win, bg=BRAND_LIGHT)
        bar.pack(fill="x", padx=14, pady=(0, 10))
        tk.Button(bar, text="关闭", command=win.destroy, bg="#eef2f8",
                  font=("Microsoft YaHei UI", 10)).pack(side="right")

    def _choose_files(self):
        paths = filedialog.askopenfilenames(title="选择压缩包",
                                            filetypes=[("压缩文件", "*.zip *.7z *.rar *.tar *.gz *.bz2 *.xz"),
                                                       ("所有文件", "*.*")])
        for p in paths:
            self.add_file(p)

    def _choose_dest(self):
        d = filedialog.askdirectory(title="选择解压目标目录")
        if d:
            self.dest_var.set(d)

    # ---------------- 解压执行 ----------------
    def _start_extract(self):
        if self.busy:
            return
        if not self.files:
            messagebox.showinfo("提示", "请先添加要解压的压缩包。")
            return
        self.busy = True
        self.extract_btn.state(["disabled"])
        self._set_progress(0)
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        password = self.pwd_var.get().strip()
        overwrite = self.overwrite_var.get()
        total = len(self.files)
        try:
            for idx, f in enumerate(self.files, 1):
                self._safe_log(f"====== 开始解压：{os.path.basename(f)} （{idx}/{total}）")
                if self.dest_var.get() == "源文件所在目录":
                    dest = os.path.dirname(f) or os.getcwd()
                else:
                    dest = self.dest_var.get()
                os.makedirs(dest, exist_ok=True)
                extract_one(f, dest, password, overwrite, self._safe_log)
                self._set_progress(idx * 100.0 / total)
                self._safe_log(f"====== 完成：{os.path.basename(f)}", ok=True)
            self._safe_log("\n全部解压完成。", ok=True)
            self.root.after(0, lambda: messagebox.showinfo("完成", "所有压缩包已解压完成！"))
        except Exception as e:
            self._safe_log(f"\n解压出错：{e}", error=True)
            self.root.after(0, lambda: messagebox.showerror("出错", str(e)))
        finally:
            self.root.after(0, self._done)

    def _done(self):
        self.busy = False
        self.extract_btn.state(["!disabled"])
        self._set_progress(100)

    # ---------------- 日志 / 进度（线程安全） ----------------
    def _log(self, msg, error=False, ok=False):
        self.log_box.configure(state="normal")
        color = "#c0392b" if error else ("#1e8e3e" if ok else "#3c4b5a")
        self.log_box.insert("end", msg + "\n", (color,))
        self.log_box.tag_config(color, foreground=color)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _safe_log(self, msg, error=False, ok=False):
        self.root.after(0, self._log, msg, error, ok)

    def _set_progress(self, val):
        self.root.after(0, lambda: (self.prog_var.set(val),
                                    self.prog_label.config(text=f"进度：{int(val)}%")))

    @staticmethod
    def _human(n):
        n = float(n)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"


def _cli_extract(args):
    """右键菜单触发的静默解压（不显示主界面）：
      --extract-here  解压到压缩包所在目录
      --extract-into  解压到压缩包同名的子文件夹
    返回进程退出码（0=全部成功，1=有失败）。"""
    mode = "--extract-into" if "--extract-into" in args else "--extract-here"
    paths = [a for a in args if not a.startswith("-")]
    results = []
    for p in paths:
        p = os.path.normpath(p)
        if not os.path.isfile(p):
            results.append((os.path.basename(p), False, "文件不存在或无法访问"))
            continue
        if mode == "--extract-into":
            base = os.path.basename(p)
            stem = base
            for ext in (".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz",
                        ".tar.zst", ".tzst", ".tar.lz4", ".tlz4",
                        ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2",
                        ".xz", ".zst", ".lz4", ".cab"):
                if base.lower().endswith(ext):
                    stem = base[: -len(ext)]
                    break
            dest = os.path.join(os.path.dirname(p) or os.getcwd(), stem)
        else:
            dest = os.path.dirname(p) or os.getcwd()
        try:
            os.makedirs(dest, exist_ok=True)
            logs = []
            extract_one(p, dest, None, False, logs.append)
            results.append((os.path.basename(p), True, dest))
        except Exception as e:
            results.append((os.path.basename(p), False, str(e)))

    root = tk.Tk()
    root.withdraw()
    if all(r[1] for r in results):
        if len(results) == 1:
            messagebox.showinfo("干净解压工具",
                                f"已解压：{os.path.basename(paths[0])}\n\n到：{results[0][2]}")
        else:
            messagebox.showinfo("干净解压工具", f"已成功解压 {len(results)} 个文件。")
    else:
        msgs = [f"{r[0]}：{r[2]}" for r in results if not r[1]]
        messagebox.showerror("干净解压工具 - 解压出错",
                             "以下文件未能解压：\n" + "\n".join(msgs[:5]))
    root.destroy()
    return 0 if all(r[1] for r in results) else 1


def main():
    args = sys.argv[1:]
    # 右键菜单静默解压模式（不显示主界面）
    if any(a in ("--extract-here", "--extract-into") for a in args):
        sys.exit(_cli_extract(args))
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = CleanUnarchiverApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
