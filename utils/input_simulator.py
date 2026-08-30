"""底层键盘输入模拟（模仿 BetterGenshinImpact 的 SendInput + SCANCODE 方案）

原神通过 RawInput/DirectInput 读取键盘，必须提供硬件扫描码；
且原神以管理员权限运行，普通权限进程的注入输入会被 UIPI 拦截，
因此本程序也必须以管理员身份运行。
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from typing import List

# ---------------- Win32 结构体定义（x64 上 INPUT 必须为 40 字节） ----------------


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("_union",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_union", _INPUT_UNION),
    ]


assert ctypes.sizeof(_INPUT) == 40, f"INPUT 结构体大小错误: {ctypes.sizeof(_INPUT)} (应为 40)"

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

_user32 = ctypes.windll.user32
_user32.SendInput.restype = wintypes.UINT
_user32.SendInput.argtypes = [
    wintypes.UINT,
    ctypes.POINTER(_INPUT),
    ctypes.c_int,
]

# ---------------- 美国 104 键标准布局：字符 -> (虚拟键码, 扫描码) ----------------
# 使用固定映射表而非 VkKeyScanA，避免中文输入法/非美式布局干扰
_KEY_TABLE = {
    "1": (0x31, 0x02), "2": (0x32, 0x03), "3": (0x33, 0x04), "4": (0x34, 0x05),
    "5": (0x35, 0x06), "6": (0x36, 0x07), "7": (0x37, 0x08), "8": (0x38, 0x09),
    "9": (0x39, 0x0A), "0": (0x30, 0x0B),
    "q": (0x51, 0x10), "w": (0x57, 0x11), "e": (0x45, 0x12), "r": (0x52, 0x13),
    "t": (0x54, 0x14), "y": (0x59, 0x15), "u": (0x55, 0x16), "i": (0x49, 0x17),
    "o": (0x4F, 0x18), "p": (0x50, 0x19),
    "a": (0x41, 0x1E), "s": (0x53, 0x1F), "d": (0x44, 0x20), "f": (0x46, 0x21),
    "g": (0x47, 0x22), "h": (0x48, 0x23), "j": (0x4A, 0x24), "k": (0x4B, 0x25),
    "l": (0x4C, 0x26),
    "z": (0x5A, 0x2C), "x": (0x58, 0x2D), "c": (0x43, 0x2E), "v": (0x56, 0x2F),
    "b": (0x42, 0x30), "n": (0x4E, 0x31), "m": (0x4D, 0x32),
}


def _lookup(key: str):
    """字符 -> (vk, scan_code)，找不到返回 None"""
    if len(key) != 1:
        return None
    return _KEY_TABLE.get(key.lower())


def _send(vk: int, scan_code: int, press: bool) -> None:
    """构造单个 INPUT 并发送（BGI 方式：SCANCODE + VK 一起填充，逐事件发送）"""
    inp = _INPUT()
    inp.type = INPUT_KEYBOARD
    inp._union.ki.wVk = vk
    inp._union.ki.wScan = scan_code
    inp._union.ki.dwFlags = (0 if press else KEYEVENTF_KEYUP) | KEYEVENTF_SCANCODE
    inp._union.ki.time = 0
    inp._union.ki.dwExtraInfo = None
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def send_key(key: str, press: bool) -> None:
    """模拟单个按键的按下或释放"""
    mapping = _lookup(key)
    if mapping is None:
        return
    _send(mapping[0], mapping[1], press)


def press_and_release(key: str, hold_seconds: float = 0.03) -> None:
    """按下并释放单个按键"""
    mapping = _lookup(key)
    if mapping is None:
        return
    _send(mapping[0], mapping[1], True)
    if hold_seconds > 0:
        time.sleep(hold_seconds)
    _send(mapping[0], mapping[1], False)


def press_keys(keys: List[str]) -> None:
    """同时按下多个按键（和弦）"""
    for key in keys:
        mapping = _lookup(key)
        if mapping is not None:
            _send(mapping[0], mapping[1], True)


def release_keys(keys: List[str]) -> None:
    """同时释放多个按键"""
    for key in keys:
        mapping = _lookup(key)
        if mapping is not None:
            _send(mapping[0], mapping[1], False)


def tap_keys(keys: List[str], hold_seconds: float = 0.03) -> None:
    """按下并保持一段时间后释放多个按键"""
    press_keys(keys)
    if hold_seconds > 0:
        time.sleep(hold_seconds)
    release_keys(keys)
