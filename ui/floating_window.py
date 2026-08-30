"""悬浮窗界面"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from core.player import PlayerState
from utils.style import get_genshin_stylesheet


class FloatingWindow(QWidget):
    """置顶悬浮窗，用于随时控制播放"""

    toggle_clicked = Signal()
    stop_clicked = Signal()
    hide_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("控制")
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(280, 60)

        self._drag_pos = None
        self._dragging = False

        self._init_ui()
        self._apply_style()
        self.update_state(PlayerState.STOPPED)

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.drag_btn = QPushButton("≡")
        self.drag_btn.setObjectName("drag_btn")
        self.drag_btn.setFixedSize(24, 24)
        self.drag_btn.setCursor(Qt.OpenHandCursor)
        self.drag_btn.setToolTip("拖动悬浮窗")

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("status_label")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedWidth(50)

        self.toggle_btn = QPushButton("播放")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_clicked.emit)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)

        self.hide_btn = QPushButton("×")
        self.hide_btn.setObjectName("hide_btn")
        self.hide_btn.setFixedSize(24, 24)
        self.hide_btn.setCursor(Qt.PointingHandCursor)
        self.hide_btn.setToolTip("隐藏悬浮窗")
        self.hide_btn.clicked.connect(self.hide_clicked.emit)

        layout.addWidget(self.drag_btn)
        layout.addWidget(self.status_label)
        layout.addWidget(self.toggle_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.hide_btn)

        # 仅拖动柄需要拦截鼠标事件，其他按钮保持默认点击行为
        self.drag_btn.installEventFilter(self)

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 35, 59, 245);
                border-radius: 12px;
                border: 1px solid #b8860b;
            }
            QLabel#status_label {
                color: #f4d88c;
                font-family: "Microsoft YaHei UI";
                font-size: 11px;
                background-color: transparent;
                border: none;
            }
            QPushButton {
                background-color: #2d365c;
                color: #e9c46a;
                border: 1px solid #b8860b;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #b8860b;
                color: #1a1f35;
            }
            QPushButton:pressed {
                background-color: #8f6a08;
            }
            QPushButton:disabled {
                background-color: #3c466e;
                color: #6e789c;
                border-color: #4a5580;
            }
            QPushButton#drag_btn {
                background-color: #4a5580;
                color: #f4f1e0;
                border-radius: 12px;
                font-size: 16px;
                padding: 0px;
            }
            QPushButton#drag_btn:hover {
                background-color: #b8860b;
                color: #1a1f35;
            }
            QPushButton#hide_btn {
                background-color: transparent;
                color: #a8b0d0;
                border: 1px solid transparent;
                border-radius: 12px;
                font-size: 16px;
                padding: 0px;
            }
            QPushButton#hide_btn:hover {
                background-color: #4a5580;
                color: #f4f1e0;
            }
        """)

    def update_state(self, state: PlayerState) -> None:
        if state == PlayerState.PLAYING:
            self.status_label.setText("播放中")
            self.toggle_btn.setText("暂停")
            self.stop_btn.setEnabled(True)
        elif state == PlayerState.PAUSED:
            self.status_label.setText("已暂停")
            self.toggle_btn.setText("继续")
            self.stop_btn.setEnabled(True)
        else:
            self.status_label.setText("就绪")
            self.toggle_btn.setText("播放")
            self.stop_btn.setEnabled(False)

    def eventFilter(self, watched, event):
        if watched is self.drag_btn and isinstance(event, QMouseEvent):
            etype = event.type()

            if etype == QMouseEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._dragging = True
                self._drag_pos = event.globalPosition().toPoint()
                self.drag_btn.setCursor(Qt.ClosedHandCursor)
                self.grabMouse()
                event.accept()
                return True

            #  grabbed 后移动/释放会进入窗口级事件，这里兜底防止按钮自身响应
            if self._dragging:
                event.accept()
                return True

        return super().eventFilter(watched, event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and self._drag_pos is not None:
            current = event.globalPosition().toPoint()
            delta = current - self._drag_pos
            self._drag_pos = current
            self.move(self.x() + delta.x(), self.y() + delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self._drag_pos = None
            self.releaseMouse()
            self.drag_btn.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # 窗口空白区域（如有）也可拖动
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint()
            self.grabMouse()
            event.accept()
