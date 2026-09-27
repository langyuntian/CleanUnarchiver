# -*- coding: utf-8 -*-
"""构造最小 RAR4(store) 测试归档，支持切换 CRC16 多项式。"""
import struct, zlib, os, sys

def crc16_rar(data):
    """RAR 头部 CRC16 = CRC32（0xEDB88320）的低 16 位。"""
    return zlib.crc32(data) & 0xFFFF

def build():
    sig = b"Rar!\x1a\x07\x00"
    # MAIN HEAD
    mbody = b"\x00" * 6
    m_head = bytes([0x73]) + struct.pack("<H", 0x0000) + struct.pack("<H", 13) + mbody
    m_crc = struct.pack("<H", crc16_rar(m_head))
    # FILE HEAD
    name = "hello_rar.txt"
    data = "你好，RAR 测试内容".encode("utf-8")
    nb = name.encode("utf-8")
    fbody = (struct.pack("<I", len(data)) + struct.pack("<I", len(data)) +
             bytes([0]) + struct.pack("<I", zlib.crc32(data) & 0xFFFFFFFF) +
             struct.pack("<I", 0) + bytes([29]) + bytes([0x30]) +
             struct.pack("<H", len(nb)) + struct.pack("<I", 0x20) + nb)
    f_head = bytes([0x74]) + struct.pack("<H", 0x8000) + struct.pack("<H", 7 + len(fbody)) + fbody
    f_crc = struct.pack("<H", crc16_rar(f_head))
    return sig + m_crc + m_head + sig + f_crc + f_head + data

with open("test_sample.rar", "wb") as f:
    f.write(build())
print("generated", os.path.getsize("test_sample.rar"))
