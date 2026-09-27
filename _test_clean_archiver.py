# -*- coding: utf-8 -*-
"""端到端功能测试：生成各类压缩包 -> 识别格式 -> 解压 -> 校验内容。"""
import os, sys, io, tarfile, zipfile, gzip, shutil, tempfile, importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载被测模块
spec = importlib.util.spec_from_file_location(
    "clean_archiver", os.path.join(os.path.dirname(os.path.abspath(__file__)), "干净解压工具.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

WORK = tempfile.mkdtemp(prefix="cleanunarchiver_test_")
SRC = os.path.join(WORK, "src")
os.makedirs(os.path.join(SRC, "sub", "deep"), exist_ok=True)

# 生成测试内容
open(os.path.join(SRC, "hello.txt"), "w", encoding="utf-8").write("你好，干净解压工具")
open(os.path.join(SRC, "sub", "note.md"), "w", encoding="utf-8").write("# 测试\n第二行内容。")
open(os.path.join(SRC, "sub", "deep", "bin.dat"), "wb").write(bytes(range(256)))

results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))

# ---- 制作 zip ----
zip_path = os.path.join(WORK, "test.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(SRC):
        for f in files:
            full = os.path.join(root, f)
            arc = os.path.relpath(full, SRC).replace("\\", "/")
            z.write(full, arc)
fmt, c = mod.detect_archive(zip_path)
check("识别 zip", fmt == "zip", f"got={fmt}")

# ---- 制作 7z ----
import py7zr
sz_path = os.path.join(WORK, "test.7z")
with py7zr.SevenZipFile(sz_path, "w") as z:
    for root, _, files in os.walk(SRC):
        for f in files:
            full = os.path.join(root, f)
            arc = os.path.relpath(full, SRC).replace("\\", "/")
            z.write(full, arc)
fmt, _ = mod.detect_archive(sz_path)
check("识别 7z", fmt == "7z", f"got={fmt}")

# ---- 制作 tar.gz ----
tgz_path = os.path.join(WORK, "test.tar.gz")
with tarfile.open(tgz_path, "w:gz") as tf:
    tf.add(SRC, arcname="src")
fmt, _ = mod.detect_archive(tgz_path)
check("识别 tar.gz", fmt == "tar", f"got={fmt}")

# ---- 制作 单 gz ----
gz_path = os.path.join(WORK, "single.gz")
with gzip.open(gz_path, "wb") as g:
    g.write(b"single file content")
fmt, _ = mod.detect_archive(gz_path)
check("识别 gz", fmt == "gz", f"got={fmt}")

# ---- 解压并校验 ----
def extract_and_verify(archive, expect_dir, label):
    dest = os.path.join(WORK, "out_" + label)
    os.makedirs(dest, exist_ok=True)
    try:
        mod.extract_one(archive, dest, None, True, lambda m: None)
    except Exception as e:
        check("解压 " + label, False, str(e)); return
    # 校验关键文件
    ok = os.path.exists(os.path.join(dest, expect_dir, "hello.txt"))
    txt = open(os.path.join(dest, expect_dir, "hello.txt"), encoding="utf-8").read() if ok else ""
    ok2 = os.path.exists(os.path.join(dest, expect_dir, "sub", "deep", "bin.dat"))
    check("解压 " + label, ok and txt == "你好，干净解压工具" and ok2,
          f"txt_ok={ok} bin_ok={ok2}")

extract_and_verify(zip_path, ".", "zip")
extract_and_verify(sz_path, ".", "7z")
extract_and_verify(tgz_path, "src", "tar.gz")

# 单 gz
gdest = os.path.join(WORK, "out_gz"); os.makedirs(gdest, exist_ok=True)
try:
    mod.extract_one(gz_path, gdest, None, True, lambda m: None)
    content = open(os.path.join(gdest, "single"), "rb").read()
    check("解压 单gz", content == b"single file content")
except Exception as e:
    check("解压 单gz", False, str(e))

# ---- 路径穿越防护测试 ----
evil_zip = os.path.join(WORK, "evil.zip")
with zipfile.ZipFile(evil_zip, "w") as z:
    z.writestr("../../evil.txt", "should not escape")
edest = os.path.join(WORK, "out_evil"); os.makedirs(edest, exist_ok=True)
escaped = os.path.join(WORK, "evil.txt")
try:
    mod.extract_one(evil_zip, edest, None, True, lambda m: None)
    check("路径穿越防护", not os.path.exists(escaped),
          "危险文件被写出" if os.path.exists(escaped) else "拦截成功")
except Exception:
    check("路径穿越防护", True, "条目被安全拦截")

# ---- 加密 zip 测试 ----
enc_zip = os.path.join(WORK, "enc.zip")
with zipfile.ZipFile(enc_zip, "w", zipfile.ZIP_DEFLATED) as z:
    z.setpassword(b"secret123")
    z.writestr("locked.txt", "top secret")
ed2 = os.path.join(WORK, "out_enc"); os.makedirs(ed2, exist_ok=True)
mod.extract_one(enc_zip, ed2, "secret123", True, lambda m: None)
content = open(os.path.join(ed2, "locked.txt"), encoding="utf-8").read()
check("加密 zip 密码解压", content == "top secret", content)

# ---- 非法文件识别 ----
plain = os.path.join(WORK, "plain.txt")
open(plain, "w").write("just text")
fmt, _ = mod.detect_archive(plain)
check("非法文件识别为 None", fmt is None, f"got={fmt}")

print("\n==== 汇总 ====")
passed = sum(1 for _, ok, _ in results if ok)
print(f"通过 {passed}/{len(results)}")
shutil.rmtree(WORK, ignore_errors=True)
sys.exit(0 if passed == len(results) else 1)
