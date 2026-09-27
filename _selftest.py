# -*- coding: utf-8 -*-
"""干净解压工具 —— 全面功能自测 v2
覆盖：格式识别、zip/7z/rar/tar/tar.gz/tar.bz2/tar.xz/gz/bz2/xz 解压、
真实加密 zip(ZipCrypto)/7z、路径穿越防护、批量解压、覆盖/跳过、错误密码。
"""
import os, sys, tempfile, shutil, zipfile, tarfile, gzip, bz2, lzma, struct, zlib, time
import importlib.util

BASE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("cu", os.path.join(BASE, "干净解压工具.py"))
cu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cu)
import py7zr

PASS = FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"PASS  {name}  {detail}")
    else:
        FAIL += 1; print(f"FAIL  {name}  {detail}")

def make_tree(root, subdirs=True):
    os.makedirs(root, exist_ok=True)
    open(os.path.join(root, "hello.txt"), "w", encoding="utf-8").write("你好，研融科技自测\n第二行")
    open(os.path.join(root, "data.bin"), "wb").write(bytes(range(256)))
    if subdirs:
        os.makedirs(os.path.join(root, "sub"), exist_ok=True)
        open(os.path.join(root, "sub", "inner.txt"), "w", encoding="utf-8").write("inner content")

# ---------- 真实 ZipCrypto 加密 zip 生成器（完全镜像 CPython zipfile 解密算法） ----------
def _crc_update(crc, ch):
    crc ^= ch
    for _ in range(8):
        crc = (crc >> 1) ^ 0xEDB88320 if crc & 1 else crc >> 1
    return crc & 0xFFFFFFFF
def _upd_keys(keys, ch):
    k0, k1, k2 = keys
    k0 = _crc_update(k0, ch)
    k1 = (k1 + (k0 & 0xFF)) & 0xFFFFFFFF
    k1 = (k1 * 134775813 + 1) & 0xFFFFFFFF
    k2 = _crc_update(k2, (k1 >> 24) & 0xFF)
    return (k0, k1, k2)
def _encrypt(data, keys):
    """ZipCrypto 加密：用『明文』字节更新密钥（匹配 CPython zipfile 解密）。"""
    out = bytearray()
    for p in data:
        k = keys[2] | 2
        c = p ^ ((k * (k ^ 1)) >> 8) & 0xFF
        keys = _upd_keys(keys, p)
        out.append(c)
    return bytes(out), keys

def make_encrypted_zip(path, name, payload, password):
    """构造一个 ZipCrypto 加密（store）的单文件 zip，可被 Python zipfile 解密。"""
    keys = (0x12345678, 0x23456789, 0x34567890)
    for ch in password:
        keys = _upd_keys(keys, ch)
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    # DOS 时间（固定 2026-01-02 03:04:05，避免负值）
    dos_date = ((2026 - 1980) << 9) | (1 << 5) | 2
    dos_time = (3 << 11) | (4 << 5) | (5 // 2)
    # 12 字节加密头：字节0-1=CRC 高16位，字节11=CRC 最高字节（zipfile 无描述符时用它校验密码）
    hdr12 = bytes([(crc >> 24) & 0xFF, (crc >> 16) & 0xFF]) + os.urandom(9) + bytes([(crc >> 24) & 0xFF])
    enc_hdr, keys = _encrypt(hdr12, keys)
    enc_data, _ = _encrypt(payload, keys)
    nameb = name.encode()
    comp_size = 12 + len(payload)
    flags = 0x0001  # encrypted
    # local header
    lh = struct.pack("<IHHHHHIIIHH", 0x04034b50, 20, flags, 0, dos_time, dos_date,
                     crc, comp_size, len(payload), len(nameb), 0)
    lh += nameb + enc_hdr + enc_data
    offset = 0
    # central header
    chh = struct.pack("<IHHHHHHIIIHHHHHII", 0x02014b50, 20, 20, flags, 0, dos_time,
                      dos_date, crc, comp_size, len(payload), len(nameb), 0, 0, 0, 0, 0x20, offset)
    chh += nameb
    cd = chh
    eocd = struct.pack("<IHHHHIIH", 0x06054b50, 0, 0, 1, 1, len(cd), offset + len(lh), 0)
    with open(path, "wb") as f:
        f.write(lh + cd + eocd)

# ---------- 准备样本 ----------
W = tempfile.mkdtemp(prefix="cu_selftest_")
SRC = os.path.join(W, "src"); make_tree(SRC)
ARCH = os.path.join(W, "arch"); os.makedirs(ARCH)

p = os.path.join(ARCH, "test.zip")
with zipfile.ZipFile(p, "w") as z:
    for root, _, files in os.walk(SRC):
        for fn in files:
            fp = os.path.join(root, fn); z.write(fp, os.path.relpath(fp, SRC))
# 真实加密 zip
pz = os.path.join(ARCH, "enc.zip")
make_encrypted_zip(pz, "secret.txt", "这是加密内容 TOP SECRET".encode("utf-8"), b"secret123")
# 7z
p7 = os.path.join(ARCH, "test.7z")
with py7zr.SevenZipFile(p7, "w") as z: z.writeall(SRC, arcname=".")
# 加密 7z
pe7 = os.path.join(ARCH, "enc.7z")
with py7zr.SevenZipFile(pe7, "w", password="pwd456") as z: z.writeall(SRC, arcname=".")
# tar / tar.gz / tar.bz2 / tar.xz
for ext, mode in (("tar", "w"), ("tar.gz", "w:gz"), ("tar.bz2", "w:bz2"), ("tar.xz", "w:xz")):
    with tarfile.open(os.path.join(ARCH, "test." + ext), mode) as t:
        t.add(SRC, arcname=".")
# 单 gz / bz2 / xz
data = "单文件压缩测试 single file".encode("utf-8")
for ext, opener in (("gz", gzip.open), ("bz2", bz2.open), ("xz", lzma.open)):
    with opener(os.path.join(ARCH, "plain.txt." + ext), "wb") as f: f.write(data)

def crc16_rar(d): return zlib.crc32(d) & 0xFFFF
def build_rar(path):
    sig = b"Rar!\x1a\x07\x00"
    m_head = bytes([0x73]) + struct.pack("<H", 0) + struct.pack("<H", 13) + b"\x00" * 6
    m_crc = struct.pack("<H", crc16_rar(m_head))
    def fh(name, dd):
        nb = name.encode()
        body = (struct.pack("<I", len(dd)) + struct.pack("<I", len(dd)) + bytes([0]) +
                struct.pack("<I", zlib.crc32(dd) & 0xFFFFFFFF) + struct.pack("<I", 0) +
                bytes([29]) + bytes([0x30]) + struct.pack("<H", len(nb)) +
                struct.pack("<I", 0x20) + nb)
        h = bytes([0x74]) + struct.pack("<H", 0x8000) + struct.pack("<H", 7 + len(body)) + body
        return sig + struct.pack("<H", crc16_rar(h)) + h + dd
    with open(path, "wb") as f:
        f.write(sig + m_crc + m_head)
        f.write(fh("hello_rar.txt", "RAR 解压测试内容".encode()))
        f.write(fh("sub/inner.bin", bytes(range(32))))
prar = os.path.join(ARCH, "test.rar"); build_rar(prar)

p_evil_zip = os.path.join(ARCH, "evil.zip")
with zipfile.ZipFile(p_evil_zip, "w") as z:
    z.writestr("../../evil.txt", "escape"); z.writestr("/abs_evil.txt", "abs")
bad = os.path.join(ARCH, "bad.txt"); open(bad, "w").write("not an archive")

OUT = os.path.join(W, "out")

# ---------- 1. 格式识别 ----------
for nm, arc in (("zip", p), ("7z", p7), ("rar", prar), ("tar", os.path.join(ARCH, "test.tar")),
                ("tar.gz", os.path.join(ARCH, "test.tar.gz")),
                ("tar.bz2", os.path.join(ARCH, "test.tar.bz2")),
                ("tar.xz", os.path.join(ARCH, "test.tar.xz")),
                ("gz", os.path.join(ARCH, "plain.txt.gz")),
                ("bz2", os.path.join(ARCH, "plain.txt.bz2")),
                ("xz", os.path.join(ARCH, "plain.txt.xz"))):
    check(f"识别 {nm}", cu.detect_archive(arc)[0] == ("tar" if nm.startswith("tar") else nm.split(" ")[0] if nm in ("zip","7z","rar") else nm.split(".")[0]))
check("非法文件识别为 None", cu.detect_archive(bad)[0] is None)

# ---------- 2. 解压 ----------
def walk_files(d):
    return sorted(os.path.relpath(os.path.join(r, f), d).replace("\\", "/")
                  for r, _, fs in os.walk(d) for f in fs)

def find_by_name(d, name):
    for root, _, files in os.walk(d):
        if name in files:
            return os.path.join(root, name)
    return None

for nm, arc in (("zip", p), ("7z", p7), ("tar", os.path.join(ARCH, "test.tar")),
                ("tar.gz", os.path.join(ARCH, "test.tar.gz")),
                ("tar.bz2", os.path.join(ARCH, "test.tar.bz2")),
                ("tar.xz", os.path.join(ARCH, "test.tar.xz"))):
    d = tempfile.mkdtemp(prefix="o_")
    logs, logf = [], list.append if False else (lambda *a: None)
    def logf2(m, *a): logs.append(m)
    cu.extract_one(arc, d, "", True, logf2)
    hello = find_by_name(d, "hello.txt")
    inner = find_by_name(d, "inner.txt")
    ok = hello and "研融科技" in open(hello, encoding="utf-8").read() and inner is not None
    check(f"解压 {nm}", ok, f"文件数={len(walk_files(d))}")

for ext in ("gz", "bz2", "xz"):
    d = tempfile.mkdtemp(prefix="o_")
    cu.extract_one(os.path.join(ARCH, "plain.txt." + ext), d, "", True, lambda *a: None)
    out = os.path.join(d, "plain.txt")
    check(f"解压单{ext}", os.path.isfile(out) and open(out, "rb").read() == data)

# ---------- 3. RAR（内置 UnRAR） ----------
d = tempfile.mkdtemp(prefix="rar_")
logs = []
cu.extract_rar(prar, d, None, True, logs.append)
h = find_by_name(d, "hello_rar.txt")
check("解压 RAR(内置UnRAR)", h and "RAR 解压测试" in open(h, encoding="utf-8").read(),
      f"文件={walk_files(d)}")

# ---------- 4. 加密解压 ----------
d = tempfile.mkdtemp(prefix="e_")
cu.extract_one(pz, d, "secret123", True, lambda *a: None)
check("加密 zip 正确密码解压", os.path.isfile(os.path.join(d, "secret.txt"))
      and "TOP SECRET" in open(os.path.join(d, "secret.txt"), encoding="utf-8").read())
try:
    d2 = tempfile.mkdtemp(prefix="e_")
    cu.extract_one(pz, d2, "wrongpw", True, lambda *a: None)
    check("加密 zip 错误密码被拒绝", False)
except Exception:
    check("加密 zip 错误密码被拒绝", True)
d3 = tempfile.mkdtemp(prefix="e_")
cu.extract_one(pe7, d3, "pwd456", True, lambda *a: None)
check("加密 7z 正确密码解压", find_by_name(d3, "hello.txt") is not None)
try:
    d4 = tempfile.mkdtemp(prefix="e_")
    cu.extract_one(pe7, d4, "wrongpw", True, lambda *a: None)
    check("加密 7z 错误密码被拒绝", False)
except Exception:
    check("加密 7z 错误密码被拒绝", True)

# ---------- 5. 路径穿越防护 ----------
d5 = tempfile.mkdtemp(prefix="x_")
blocked = False
try:
    cu.extract_one(p_evil_zip, d5, "", True, lambda *a: None)
    blocked = not any(os.path.exists(x) for x in (os.path.join(d5, "..", "..", "evil.txt"),
                                                  os.path.abspath("/abs_evil.txt")))
except Exception:
    blocked = True
check("路径穿越被拦截", blocked)

# ---------- 6. 批量 ----------
bd = tempfile.mkdtemp(prefix="b_")
count = sum(1 for f in (p, p7, prar) if (lambda ff: (cu.extract_one(ff, bd, "", True, lambda *a: None), True)[1])(f))
check("批量解压 3 个文件", count == 3)

# ---------- 7. 覆盖/跳过 ----------
d6 = tempfile.mkdtemp(prefix="ov_")
os.makedirs(os.path.join(d6, "sub"), exist_ok=True)
open(os.path.join(d6, "hello.txt"), "w", encoding="utf-8").write("OLD")
cu.extract_one(p, d6, "", False, lambda *a: None)
check("不覆盖时保留旧文件", find_by_name(d6, "hello.txt") and "OLD" in open(find_by_name(d6, "hello.txt"), encoding="utf-8").read())
cu.extract_one(p, d6, "", True, lambda *a: None)
check("覆盖时更新文件", find_by_name(d6, "hello.txt") and "研融科技" in open(find_by_name(d6, "hello.txt"), encoding="utf-8").read())

# ---------- 8. 伪装 .rar（自定义前导头 + 内嵌 ZIP，如 Cr24 头安装器/扩展包） ----------
cr24 = os.path.join(ARCH, "fake_cr24.rar")
with zipfile.ZipFile(cr24, "w") as z:
    z.writestr("inner/a.txt", "inside a")
    z.writestr("b.bin", b"\x01\x02\x03")
with open(cr24, "rb") as f: zbody = f.read()
with open(cr24, "wb") as f:
    f.write(b"Cr24" + b"\x00" * 1322)   # 伪装前导头（魔数非 RAR，也非 ZIP 起始）
    f.write(zbody)
check("伪装 .rar(Cr24头)识别为 zip", cu.detect_archive(cr24)[0] == "zip")
d7 = tempfile.mkdtemp(prefix="cr_")
cu.extract_one(cr24, d7, "", True, lambda *a: None)
check("伪装 .rar(Cr24头)解压",
      os.path.isfile(os.path.join(d7, "inner", "a.txt"))
      and open(os.path.join(d7, "inner", "a.txt"), encoding="utf-8").read() == "inside a")

# ---------- 9. 文件校验（真实格式 vs 扩展名） ----------
vr = cu.verify_archive(p)
check("校验: 正常 zip 一致", vr["match"] == "ok" and vr["real"] == "zip")
vr2 = cu.verify_archive(prar)
check("校验: 正常 rar 一致", vr2["match"] == "ok" and vr2["real"] == "rar")
vr3 = cu.verify_archive(cr24)
check("校验: 伪装 .rar(Cr24头) 识别为不一致且按zip", 
      vr3["match"] == "mismatch" and vr3["real"] == "zip" and vr3["extract_fmt"] == "zip")
vr4 = cu.verify_archive(bad)
check("校验: 非压缩文件 无法识别", vr4["match"] == "unrecognized" and vr4["real"] is None)
# 无扩展名但内容是 zip → 按真实格式识别
noext = os.path.join(ARCH, "noext")
import shutil as _sh; _sh.copy(p, noext)
vr5 = cu.verify_archive(noext)
check("校验: 无扩展名按真实zip识别", vr5["match"] == "no_ext" and vr5["real"] == "zip")

# ---------- 10. 新增格式：zst / lz4 / tar.zst / tar.lz4 / cab / AES-zip ----------
import pyzstd, lz4.frame, pyzipper, subprocess as _sp
_ns_data = open(os.path.join(SRC, "hello.txt"), "rb").read()
p_zst = os.path.join(ARCH, "hello.txt.zst")
open(p_zst, "wb").write(pyzstd.compress(_ns_data))
p_lz4 = os.path.join(ARCH, "hello.txt.lz4")
open(p_lz4, "wb").write(lz4.frame.compress(_ns_data))
def _tar_build(tmp):
    with tarfile.open(tmp, "w") as _t: _t.add(SRC, arcname=".")
_tz = os.path.join(ARCH, "z.tmp"); _tar_build(_tz)
p_tz = os.path.join(ARCH, "test.tar.zst")
open(p_tz, "wb").write(pyzstd.compress(open(_tz, "rb").read()))
_tl = os.path.join(ARCH, "l.tmp"); _tar_build(_tl)
p_tl = os.path.join(ARCH, "test.tar.lz4")
open(p_tl, "wb").write(lz4.frame.compress(open(_tl, "rb").read()))
p_aes = os.path.join(ARCH, "aes.zip")
with pyzipper.AESZipFile(p_aes, "w", compression=pyzipper.ZIP_DEFLATED,
                         encryption=pyzipper.WZ_AES) as _z:
    _z.setpassword(b"aespass"); _z.writestr("secret.txt", "AES加密 SECRET".encode())

d8 = tempfile.mkdtemp(prefix="n_")
cu.extract_one(p_zst, d8, "", True, lambda *a: None)
check("解压 单zst", os.path.isfile(os.path.join(d8, "hello.txt"))
      and "研融科技" in open(os.path.join(d8, "hello.txt"), encoding="utf-8").read())
d9 = tempfile.mkdtemp(prefix="n_")
cu.extract_one(p_lz4, d9, "", True, lambda *a: None)
check("解压 单lz4", os.path.isfile(os.path.join(d9, "hello.txt"))
      and "研融科技" in open(os.path.join(d9, "hello.txt"), encoding="utf-8").read())
d10 = tempfile.mkdtemp(prefix="n_")
cu.extract_one(p_tz, d10, "", True, lambda *a: None)
check("解压 tar.zst", find_by_name(d10, "hello.txt") is not None and find_by_name(d10, "data.bin") is not None)
d11 = tempfile.mkdtemp(prefix="n_")
cu.extract_one(p_tl, d11, "", True, lambda *a: None)
check("解压 tar.lz4", find_by_name(d11, "hello.txt") is not None and find_by_name(d11, "data.bin") is not None)
d12 = tempfile.mkdtemp(prefix="n_")
cu.extract_one(p_aes, d12, "aespass", True, lambda *a: None)
check("解压 AES-zip 正确密码", find_by_name(d12, "secret.txt") is not None
      and "SECRET" in open(find_by_name(d12, "secret.txt"), encoding="utf-8").read())
try:
    d13 = tempfile.mkdtemp(prefix="n_")
    cu.extract_one(p_aes, d13, "wrong", True, lambda *a: None)
    check("AES-zip 错误密码被拒绝", False)
except Exception:
    check("AES-zip 错误密码被拒绝", True)
_cb = os.path.join(W, "cabmake"); os.makedirs(os.path.join(_cb, "sub"), exist_ok=True)
open(os.path.join(_cb, "a.txt"), "w", encoding="utf-8").write("CAB 内容测试\n第二行")
open(os.path.join(_cb, "sub", "b.bin"), "wb").write(bytes(range(64)))
open(os.path.join(_cb, "make.ddf"), "w").write(
    '.OPTION EXPLICIT\n.Set DiskDirectory1=%s\n.Set CabinetNameTemplate=test.cab\n.Set MaxDiskSize=0\n"a.txt"\n"sub\\b.bin"\n' % _cb)
_sp.run(["makecab.exe", "/F", os.path.join(_cb, "make.ddf")], cwd=_cb, capture_output=True)
p_cab = os.path.join(_cb, "test.cab")
if os.path.isfile(p_cab):
    d14 = tempfile.mkdtemp(prefix="n_")
    cu.extract_one(p_cab, d14, "", True, lambda *a: None)
    check("解压 CAB", find_by_name(d14, "a.txt") is not None
          and "CAB 内容" in open(find_by_name(d14, "a.txt"), encoding="utf-8").read())
else:
    check("解压 CAB", False, "makecab 未生成 cab")
check("校验: zst/lz4/cab 识别一致",
      cu.verify_archive(p_zst)["real"] == "zst" and cu.verify_archive(p_lz4)["real"] == "lz4"
      and cu.verify_archive(p_cab)["real"] == "cab")

print(f"\n==== 汇总 ====")
print(f"通过 {PASS}/{PASS+FAIL}")
shutil.rmtree(W, ignore_errors=True)
sys.exit(1 if FAIL else 0)
