"""MIDI 分析对话框：展示 MIDI 文件的深度分析报告"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.midi_analyzer import analyze
from core.keymap_manager import midi_to_jianpu, midi_to_note_name
from utils.style import genshin_font, get_genshin_stylesheet


class AnalyzerDialog(QDialog):
    """MIDI 分析二级界面"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("MIDI 分析")
        self.setMinimumSize(720, 680)
        self.resize(780, 740)

        self._init_ui()
        self._apply_style()

        # 若主界面已导入 MIDI，直接分析它
        if self.main_window._current_file is not None:
            self._analyze_file(self.main_window._current_file)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("MIDI 深度分析")
        title.setFont(genshin_font(20, bold=True))
        title.setStyleSheet("color: #e9c46a; padding: 4px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 操作区：分析当前 / 选择文件
        action_row = QHBoxLayout()
        self.analyze_current_btn = QPushButton("分析已导入的 MIDI")
        self.analyze_current_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_current_btn.clicked.connect(self._on_analyze_current)
        action_row.addWidget(self.analyze_current_btn)

        self.pick_btn = QPushButton("选择其他 MIDI 文件…")
        self.pick_btn.setCursor(Qt.PointingHandCursor)
        self.pick_btn.clicked.connect(self._on_pick_file)
        action_row.addWidget(self.pick_btn)
        action_row.addStretch()

        self.file_label = QLabel("尚未分析")
        action_row.addWidget(self.file_label)
        layout.addLayout(action_row)

        # 概览区
        self.overview_box = QGroupBox("文件概览")
        overview_layout = QVBoxLayout(self.overview_box)
        self.overview_label = QLabel("点击上方按钮开始分析")
        self.overview_label.setWordWrap(True)
        overview_layout.addWidget(self.overview_label)
        layout.addWidget(self.overview_box)

        # 适配区
        self.adapt_box = QGroupBox("键位适配情况")
        adapt_layout = QVBoxLayout(self.adapt_box)
        self.adapt_label = QLabel("—")
        self.adapt_label.setWordWrap(True)
        adapt_layout.addWidget(self.adapt_label)
        layout.addWidget(self.adapt_box)

        # 音符分布表
        dist_box = QGroupBox("音符分布（次数 / MIDI 编号 / 音名 / 简谱 / 按键 / 适配方式）")
        dist_layout = QVBoxLayout(dist_box)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["次数", "MIDI", "音名", "简谱", "按键", "适配"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        dist_layout.addWidget(self.table)
        layout.addWidget(dist_box, stretch=1)

        close_btn = QPushButton("关闭")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

    def _on_analyze_current(self) -> None:
        if self.main_window._current_file is None:
            QMessageBox.information(self, "未导入", "请先在主界面导入 MIDI 文件")
            return
        self._analyze_file(self.main_window._current_file)

    def _on_pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 MIDI 文件", "", "MIDI 文件 (*.mid *.midi)"
        )
        if path:
            self._analyze_file(Path(path))

    def _analyze_file(self, path: Path) -> None:
        try:
            report = analyze(path, self.main_window.keymap_manager)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "分析失败", f"无法解析 MIDI 文件：\n{e}")
            return

        self.file_label.setText(path.name)
        self._show_report(report)

    def _show_report(self, report) -> None:
        # 概览
        self.overview_label.setText(
            f"文件：{report.file_name}    类型：{report.midi_type}    "
            f"轨道数：{report.track_count}    ticks/beat：{report.ticks_per_beat}\n"
            f"总时长：{report.length:.1f}s    音符总数：{report.total_notes}    "
            f"音域：{midi_to_note_name(report.note_min)}({report.note_min}) ~ "
            f"{midi_to_note_name(report.note_max)}({report.note_max})\n"
            f"音符时长：{report.duration_min:.2f}s ~ {report.duration_max:.2f}s"
            f"（平均 {report.duration_avg:.2f}s）    "
            f"< 50ms：{report.short_notes_50ms}    < 20ms：{report.short_notes_20ms}\n"
            f"音符间隔：{report.gap_min:.2f}s ~ {report.gap_max:.2f}s"
            f"（平均 {report.gap_avg:.2f}s）    密集间隔（< 30ms）：{report.dense_gaps} 次\n"
            f"和弦时刻：{report.chord_count} 个    最大同时音符数：{report.max_chord_size}"
        )

        # 适配统计
        stats = report.stats
        total = max(report.total_notes, 1)
        adapted = stats["shift"] + stats["near"]
        unplayable = stats["unmapped"]
        if adapted == 0 and unplayable == 0:
            adapt_text = "所有音符均可直接映射到琴键。"
        else:
            adapt_text = (
                f"直接映射：{stats['exact']} 个（{stats['exact'] * 100.0 / total:.1f}%）\n"
                f"八度移位：{stats['shift']} 个    黑键就近白键：{stats['near']} 个"
                f"    合计自动适配 {adapted} 个（{adapted * 100.0 / total:.1f}%）\n"
                f"无法演奏：{unplayable} 个（{unplayable * 100.0 / total:.1f}%）"
            )
            if report.unresolved_notes:
                names = "、".join(
                    f"{midi_to_jianpu(n)}({midi_to_note_name(n)})" for n, _ in report.unresolved_notes[:10]
                )
                more = " 等" if len(report.unresolved_notes) > 10 else ""
                adapt_text += f"\n无法演奏的音符：{names}{more}"
        self.adapt_label.setText(adapt_text)

        # 分布表
        self.table.setRowCount(len(report.distribution))
        for row, item in enumerate(report.distribution):
            values = [
                str(item.count),
                str(item.note),
                midi_to_note_name(item.note),
                midi_to_jianpu(item.note),
                item.key.upper() if item.key else "—",
                {"exact": "直接", "shift": "移位", "near": "就近", "unmapped": "无法演奏"}[item.mode],
            ]
            for col, text in enumerate(values):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignCenter)
                if item.mode == "unmapped":
                    cell.setForeground(Qt.red)
                self.table.setItem(row, col, cell)
        self.table.resizeColumnsToContents()

    def _apply_style(self) -> None:
        self.setStyleSheet(get_genshin_stylesheet())
