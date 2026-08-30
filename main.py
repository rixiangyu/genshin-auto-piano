"""原神自动弹琴 - 程序入口"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from utils.style import apply_genshin_theme


def main():
    # 启用高 DPI 缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("原神自动弹琴")
    app.setStyle("Fusion")

    # 应用原神风格主题与字体
    apply_genshin_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
