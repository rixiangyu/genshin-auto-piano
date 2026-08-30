"""使用教程对话框"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from utils.style import genshin_font, get_genshin_stylesheet


class HelpDialog(QDialog):
    """使用教程弹窗"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("使用教程")
        self.setMinimumSize(560, 520)
        self.resize(620, 580)

        self._init_ui()
        self._apply_style()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("原神自动弹琴 - 使用教程")
        title.setFont(genshin_font(20, bold=True))
        title.setStyleSheet("color: #e9c46a; padding: 4px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        container = QWidget()
        content_layout = QVBoxLayout(container)
        content_layout.setSpacing(14)
        content_layout.setContentsMargins(8, 8, 8, 8)

        sections = [
            (
                "1. 导入 MIDI 文件",
                "点击主界面「导入 MIDI」按钮，选择你要演奏的 .mid 或 .midi 文件。"
                "程序会自动解析音符、计算时长，并在信息区显示轨道数、总时长、是否包含和弦。",
            ),
            (
                "2. 键位设置",
                "点击「键位设置」打开设置对话框。默认已加载原神 PC 端 21 键布局。\n"
                "你可以根据需要添加、删除或修改 MIDI 音符与键盘按键的对应关系。"
                "设置会自动保存到程序目录下的 resources/keymap.json。",
            ),
            (
                "3. 试听功能",
                "导入 MIDI 后，点击「试听」即可在不模拟按键的情况下预览整首曲子。"
                "试听时会播放提示音，并在进度条/当前音符区显示当前演奏位置，方便你核对键位映射是否正确。",
            ),
            (
                "4. 开始自动演奏",
                "确保原神窗口已经打开并处于焦点状态，然后回到本程序点击「播放」。"
                "程序会按 MIDI 的时间线自动模拟键盘按键。支持单音、和弦、连音。",
            ),
            (
                "5. 控制与暂停",
                "播放过程中，你可以：\n"
                "  • 点击主界面或悬浮窗的「暂停/继续」\n"
                "  • 按全局快捷键 F8 切换暂停/继续\n"
                "  • 按 ESC 或点击「停止」结束演奏\n"
                "悬浮窗可以拖动，方便你在游戏中随时控制。",
            ),
            (
                "6. 播放速度",
                "通过「播放速度」滑块可以调整演奏速度（0.25x ~ 2.0x）。"
                "速度调节对试听和实际演奏都生效。",
            ),
            (
                "7. MCP 智能体接入",
                "程序内嵌 MCP（Model Context Protocol）服务器，可被 OpenClaw、Claude Desktop 等 AI 客户端"
                "控制，实现对话式导入 MIDI、播放、暂停、调速。\n"
                "使用方法：\n"
                "  1. 点击主界面「MCP 协议」按钮打开设置界面，确认开关已启用\n"
                "  2. 在 AI 客户端的 MCP 配置中添加服务地址，例如：\n"
                '  {\n    "mcpServers": {\n      "genshin-piano": {\n        "type": "http",\n        "url": "http://127.0.0.1:8765/mcp"\n      }\n    }\n  }\n'
                "  3. 可用工具：import_midi / play / pause / resume / stop / toggle_preview / "
                "set_speed / get_status / show_floating\n"
                "详细教程见项目根目录的《MCP使用教程.md》。",
            ),
            (
                "8. 注意事项",
                "  • 如果原神以管理员权限运行，建议本程序也右键「以管理员身份运行」，否则按键可能无法输入到游戏。\n"
                "  • 导入多音轨 MIDI 时程序会提醒，并自动合并所有音轨。\n"
                "  • 程序仅模拟键盘操作，不修改游戏内存，理论上适用于任何窗口。\n"
                "  • MCP 控制接口仅监听本机回环地址（127.0.0.1），外部网络无法访问。",
            ),
        ]

        for header, body in sections:
            header_label = QLabel(header)
            header_label.setFont(genshin_font(13, bold=True))
            header_label.setStyleSheet("color: #f4d88c; margin-top: 6px;")
            content_layout.addWidget(header_label)

            body_label = QLabel(body)
            body_label.setWordWrap(True)
            body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            content_layout.addWidget(body_label)

        content_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        close_btn = QPushButton("我知道了")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

    def _apply_style(self) -> None:
        self.setStyleSheet(get_genshin_stylesheet())
