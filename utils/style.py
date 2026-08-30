"""原神风格主题与字体工具"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtGui import QFontDatabase

from utils.paths import get_bundle_resource_dir


# ---------------- 调色板 ----------------
# 深蓝紫底 + 金色点缀，营造原神 UI 氛围
_BG_DARK = "#1a1f35"
_BG_PANEL = "#232a47"
_BG_INPUT = "#2d365c"
_BG_HOVER = "#3c4a75"
_BORDER = "#4a5580"
_TEXT_PRIMARY = "#f4f1e0"
_TEXT_SECONDARY = "#a8b0d0"
_ACCENT_GOLD = "#e9c46a"
_ACCENT_GOLD_HOVER = "#f4d88c"
_ACCENT_AMBER = "#b8860b"
_ACCENT_AMBER_DARK = "#8f6a08"
_SUCCESS = "#7cb342"
_ERROR = "#e06c75"

# 字体文件路径（优先使用项目 resources/fonts 下的字体）
_FONT_FILENAME = "GenshinStyle.ttf"
_FONT_FALLBACK = ["Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", "sans-serif"]

_genshin_font_family: str | None = None


def _get_font_dir() -> Path:
    """字体所在目录。兼容源码运行和 PyInstaller 打包。"""
    return get_bundle_resource_dir() / "fonts"


def load_genshin_font() -> str:
    """加载原神风格字体，返回字体族名。失败时返回系统回退字体。"""
    global _genshin_font_family
    if _genshin_font_family is not None:
        return _genshin_font_family

    font_path = _get_font_dir() / _FONT_FILENAME
    family = _FONT_FALLBACK[0]
    if font_path.is_file():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                family = families[0]
    _genshin_font_family = family
    return family


def genshin_font(point_size: int, bold: bool = False) -> QFont:
    """获取统一的游戏风格字体对象。"""
    font = QFont(load_genshin_font(), point_size)
    if bold:
        font.setWeight(QFont.Bold)
    font.setStyleStrategy(QFont.PreferAntialias)
    return font


def get_genshin_stylesheet() -> str:
    """返回原神风格的 Qt 样式表字符串。"""
    return f"""
        QMainWindow {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {_BG_DARK}, stop:1 {_BG_PANEL});
        }}
        QDialog {{
            background-color: {_BG_PANEL};
        }}
        QWidget {{
            background-color: transparent;
        }}
        QLabel {{
            color: {_TEXT_PRIMARY};
            font-family: "{load_genshin_font()}";
            background-color: transparent;
        }}
        QPushButton {{
            background-color: {_BG_INPUT};
            color: {_ACCENT_GOLD};
            border: 1px solid {_ACCENT_AMBER};
            border-radius: 8px;
            padding: 8px 20px;
            font-size: 14px;
            font-family: "{load_genshin_font()}";
        }}
        QPushButton:hover {{
            background-color: {_ACCENT_AMBER};
            color: {_BG_DARK};
            border-color: {_ACCENT_GOLD_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {_ACCENT_AMBER_DARK};
            color: {_TEXT_PRIMARY};
        }}
        QPushButton:disabled {{
            background-color: #3c466e;
            color: #6e789c;
            border-color: {_BORDER};
        }}
        QPushButton#drag_btn {{
            background-color: {_BORDER};
            color: {_TEXT_PRIMARY};
            border-radius: 12px;
            font-size: 16px;
            padding: 0px;
        }}
        QPushButton#drag_btn:hover {{
            background-color: {_ACCENT_AMBER};
            color: {_BG_DARK};
        }}
        QPushButton#hide_btn {{
            background-color: transparent;
            color: {_TEXT_SECONDARY};
            border: 1px solid transparent;
            border-radius: 12px;
            font-size: 16px;
            padding: 0px;
        }}
        QPushButton#hide_btn:hover {{
            background-color: {_BORDER};
            color: {_TEXT_PRIMARY};
        }}
        QLineEdit, QTextEdit {{
            border: 1px solid {_BORDER};
            border-radius: 6px;
            padding: 6px;
            background-color: {_BG_INPUT};
            color: {_TEXT_PRIMARY};
            font-family: "{load_genshin_font()}";
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border: 1px solid {_ACCENT_GOLD};
        }}
        QSlider::groove:horizontal {{
            height: 4px;
            background: {_BORDER};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 18px;
            height: 18px;
            margin: -7px 0;
            background: {_ACCENT_GOLD};
            border-radius: 9px;
            border: 1px solid {_ACCENT_AMBER};
        }}
        QSlider::sub-page:horizontal {{
            background: {_ACCENT_AMBER};
            border-radius: 2px;
        }}
        QProgressBar {{
            border: 1px solid {_BORDER};
            border-radius: 6px;
            text-align: center;
            background-color: {_BG_INPUT};
            color: {_TEXT_PRIMARY};
            font-family: "{load_genshin_font()}";
        }}
        QProgressBar::chunk {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {_ACCENT_AMBER}, stop:1 {_ACCENT_GOLD});
            border-radius: 6px;
        }}
        QGroupBox {{
            border: 1px solid {_BORDER};
            border-radius: 8px;
            margin-top: 12px;
            padding: 12px;
            color: {_ACCENT_GOLD};
            font-weight: bold;
            font-family: "{load_genshin_font()}";
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
        }}
        QCheckBox {{
            color: {_TEXT_PRIMARY};
            font-family: "{load_genshin_font()}";
            font-size: 14px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {_BORDER};
            border-radius: 4px;
            background-color: {_BG_INPUT};
        }}
        QCheckBox::indicator:checked {{
            background-color: {_ACCENT_AMBER};
            border-color: {_ACCENT_GOLD};
        }}
        QTableWidget {{
            border: 1px solid {_BORDER};
            border-radius: 6px;
            background-color: {_BG_INPUT};
            gridline-color: {_BORDER};
            color: {_TEXT_PRIMARY};
            font-family: "{load_genshin_font()}";
        }}
        QTableWidget::item {{
            padding: 4px;
        }}
        QHeaderView::section {{
            background-color: {_BG_HOVER};
            color: {_ACCENT_GOLD};
            border: 1px solid {_BORDER};
            padding: 6px;
            font-family: "{load_genshin_font()}";
        }}
        QScrollArea {{
            border: 1px solid {_BORDER};
            border-radius: 8px;
            background-color: {_BG_INPUT};
        }}
        QMessageBox {{
            background-color: {_BG_PANEL};
        }}
        QMessageBox QLabel {{
            color: {_TEXT_PRIMARY};
        }}
        QMessageBox QPushButton {{
            min-width: 70px;
        }}
        QFileDialog {{
            background-color: {_BG_PANEL};
        }}
    """


def apply_genshin_theme(app) -> None:
    """为整个 QApplication 应用原神主题与字体。"""
    font_family = load_genshin_font()
    app.setFont(QFont(font_family, 10))
    app.setStyleSheet(get_genshin_stylesheet())
