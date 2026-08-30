"""MCP 设置对话框：控制 MCP 服务的开关与查看接入配置"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.style import genshin_font, get_genshin_stylesheet


class McpSettingsDialog(QDialog):
    """MCP 协议设置二级界面"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("MCP 协议设置")
        self.setMinimumSize(620, 640)
        self.resize(680, 700)

        self._init_ui()
        self._apply_style()
        self._refresh_status()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("MCP 智能体接入")
        title.setFont(genshin_font(20, bold=True))
        title.setStyleSheet("color: #e9c46a; padding: 4px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        intro = QLabel(
            "启用后，OpenClaw、Claude Desktop 等 AI 客户端可以通过本机接口控制本程序，"
            "实现对话式导入 MIDI、播放、暂停、调速等操作。\n"
            "接口仅监听本机回环地址（127.0.0.1），外部网络无法访问。"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # 开关区
        switch_box = QGroupBox("服务开关")
        switch_layout = QVBoxLayout(switch_box)

        self.enable_check = QCheckBox("启用 MCP 控制（允许本机 AI 客户端接入）")
        enabled = bool(self.main_window._settings.get("mcp_enabled", True))
        self.enable_check.setChecked(enabled)
        self.enable_check.toggled.connect(self._on_toggled)
        switch_layout.addWidget(self.enable_check)

        status_row = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.status_label, stretch=1)
        switch_layout.addLayout(status_row)
        layout.addWidget(switch_box)

        # 配置说明区
        config_box = QGroupBox("OpenClaw / MCP 客户端配置")
        config_layout = QVBoxLayout(config_box)

        config_hint = QLabel(
            "在 OpenClaw 的 MCP 配置文件中加入以下内容"
            "（端口以状态栏显示的实际端口为准，默认 8765）："
        )
        config_hint.setWordWrap(True)
        config_layout.addWidget(config_hint)

        self.config_edit = QTextEdit()
        self.config_edit.setReadOnly(True)
        self.config_edit.setMaximumHeight(140)
        config_layout.addWidget(self.config_edit)
        layout.addWidget(config_box)

        # 工具说明区
        tools_box = QGroupBox("可用工具（AI 可调用的功能）")
        tools_layout = QVBoxLayout(tools_box)
        tools_text = QLabel(
            "  • import_midi(path)  导入 MIDI 文件\n"
            "  • play / pause / resume / stop  播放控制\n"
            "  • toggle_preview  切换试听\n"
            "  • set_speed(speed)  调整播放速度（0.1~5.0）\n"
            "  • get_status  查询当前状态与进度\n"
            "  • show_floating(show)  显示/隐藏悬浮窗"
        )
        tools_layout.addWidget(tools_text)
        layout.addWidget(tools_box)

        # Skill 说明区
        skill_box = QGroupBox("Skill 文件（可选，推荐）")
        skill_layout = QVBoxLayout(skill_box)
        skill_text = QLabel(
            "项目目录 skills/genshin-piano/ 下提供了现成的 Skill 文件，"
            "将其复制到 OpenClaw 的 skills 目录"
            "（通常为 C:\\Users\\<用户名>\\.openclaw\\skills\\）后，"
            "AI 即可直接理解如何操作本程序。\n"
            "详细说明见项目根目录的《MCP使用教程.md》。"
        )
        skill_text.setWordWrap(True)
        skill_layout.addWidget(skill_text)
        layout.addWidget(skill_box)

        layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

    def _on_toggled(self, checked: bool) -> None:
        ok = self.main_window.set_mcp_enabled(checked)
        self._refresh_status()
        if checked and not ok:
            self.enable_check.blockSignals(True)
            self.enable_check.setChecked(False)
            self.enable_check.blockSignals(False)

    def _refresh_status(self) -> None:
        server = self.main_window.control_server
        enabled = bool(self.main_window._settings.get("mcp_enabled", True))
        if enabled and server is not None and server.port:
            self.status_label.setText(
                f"状态：运行中    地址：http://127.0.0.1:{server.port}/mcp"
            )
            self.config_edit.setPlainText(
                '{\n'
                '  "mcpServers": {\n'
                '    "genshin-piano": {\n'
                '      "type": "http",\n'
                f'      "url": "http://127.0.0.1:{server.port}/mcp"\n'
                '    }\n'
                '  }\n'
                '}'
            )
        else:
            self.status_label.setText("状态：已停止（AI 客户端无法接入）")
            self.config_edit.setPlainText("（请先启用 MCP 控制）")

    def _apply_style(self) -> None:
        self.setStyleSheet(get_genshin_stylesheet())
