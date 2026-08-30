"""Windows 11 视觉效果工具"""
from __future__ import annotations

import ctypes
import platform
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget


# DWM 属性常量（Windows 11）
DWMWA_USE_HOST_BACKDROP_BRUSH = 17
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_MICA_EFFECT = 1029  # 旧版 Windows 11 使用
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36

# 系统背景类型
DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2      # Mica
DWMSBT_TRANSIENTWINDOW = 3 # Acrylic
DWMSBT_TABBEDWINDOW = 4


def is_windows_11() -> bool:
    """判断当前系统是否为 Windows 11"""
    if platform.system() != "Windows":
        return False
    try:
        version = platform.version()
        major, minor, build = map(int, version.split(".")[:3])
        return major == 10 and build >= 22000
    except Exception:
        return False


def _get_window_handle(widget: QWidget) -> Optional[int]:
    """获取 QWidget 的 Win32 窗口句柄"""
    try:
        return int(widget.winId())
    except Exception:
        return None


def enable_backdrop(widget: QWidget, backdrop_type: int = DWMSBT_MAINWINDOW, dark_mode: bool = False) -> bool:
    """
    为窗口启用 Windows 11 背景效果（Mica / Acrylic）
    :param widget: 目标窗口
    :param backdrop_type: DWMSBT_MAINWINDOW(Mica) / DWMSBT_TRANSIENTWINDOW(Acrylic)
    :param dark_mode: 是否使用深色模式
    :return: 是否成功
    """
    if not is_windows_11():
        return False

    hwnd = _get_window_handle(widget)
    if hwnd is None:
        return False

    try:
        dwmapi = ctypes.windll.dwmapi

        # 设置沉浸式深色/浅色模式，失败也不影响后续设置
        try:
            dark_value = ctypes.c_int(1 if dark_mode else 0)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(dark_value),
                ctypes.sizeof(dark_value),
            )
        except Exception:
            pass

        # 设置背景材料
        try:
            value = ctypes.c_int(backdrop_type)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
            return True
        except Exception:
            return False
    except Exception:
        return False


def enable_mica(widget: QWidget) -> bool:
    """启用 Mica 效果"""
    return enable_backdrop(widget, DWMSBT_MAINWINDOW)


def enable_acrylic(widget: QWidget) -> bool:
    """启用 Acrylic 效果"""
    return enable_backdrop(widget, DWMSBT_TRANSIENTWINDOW)


def apply_win11_glass(widget: QWidget, effect: str = "mica", dark_mode: bool = False) -> None:
    """
    为窗口应用玻璃效果。
    由于 PySide6 + PyInstaller 环境下 DWM Mica/Acrylic 调用不稳定，
    实际效果改用 Qt 自带半透明背景实现，由调用方自行设置样式表。
    :param effect: 保留参数，已无实际作用
    :param dark_mode: 保留参数，已无实际作用
    """
    # 不再调用 DWM，也不再修改窗口属性，避免破坏调用方样式
    pass


# 延迟导入 Qt 常量，避免循环导入问题
from PySide6.QtCore import Qt  # noqa: E402
