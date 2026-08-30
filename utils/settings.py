"""程序设置读写（resources/settings.json）"""
from __future__ import annotations

import json
from typing import Any, Dict

from utils.paths import ensure_resource_dir

DEFAULT_SETTINGS: Dict[str, Any] = {
    "mcp_enabled": True,
}


def load_settings() -> Dict[str, Any]:
    """读取设置；不存在或损坏时返回默认值"""
    path = ensure_resource_dir() / "settings.json"
    settings = dict(DEFAULT_SETTINGS)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                settings.update(data)
        except Exception:
            pass
    return settings


def save_settings(settings: Dict[str, Any]) -> bool:
    """保存设置，返回是否成功"""
    path = ensure_resource_dir() / "settings.json"
    try:
        path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False
