"""路径工具"""
from __future__ import annotations

import sys
from pathlib import Path


def get_app_dir() -> Path:
    """获取程序所在目录（兼容 PyInstaller 打包）。用于存放可写配置。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def get_bundle_dir() -> Path:
    """获取打包资源根目录。源码运行时与 get_app_dir() 一致。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass)
    return get_app_dir()


def get_resource_dir() -> Path:
    """获取可写资源目录（用于 keymap.json、settings.json 等）"""
    return get_app_dir() / "resources"


def get_bundle_resource_dir() -> Path:
    """获取打包资源目录（用于字体等只读资源）"""
    return get_bundle_dir() / "resources"


def ensure_resource_dir() -> Path:
    """确保可写资源目录存在"""
    resource_dir = get_resource_dir()
    resource_dir.mkdir(parents=True, exist_ok=True)
    return resource_dir
