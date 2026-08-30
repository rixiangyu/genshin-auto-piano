"""键位设置对话框"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.keymap_manager import (
    DEFAULT_GENSHIN_KEYMAP,
    KeymapManager,
    jianpu_to_midi,
    midi_to_jianpu,
    midi_to_note_name,
)
from utils.style import genshin_font, get_genshin_stylesheet


class KeymapSettingsDialog(QDialog):
    """键位设置界面"""

    def __init__(self, keymap_manager: KeymapManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("键位设置")
        self.setMinimumSize(500, 450)
        self.resize(550, 500)

        self.keymap_manager = keymap_manager
        self._temp_keymap = keymap_manager.keymap

        self._init_ui()
        self._apply_style()
        self._refresh_table()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 说明
        hint = QLabel(
            "编辑简谱音符与键盘按键的对应关系（C 大调：1=do、2=re、3=mi、4=fa、5=sol、6=la、7=si，"
            "「高音/低音」表示升降一个八度）。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["简谱音符", "键盘按键", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setColumnWidth(2, 80)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

        # 添加新映射
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("音符："))
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("如：高音1、低音#5、中音3 或 MIDI 编号")
        self.note_input.setMaxLength(8)
        add_layout.addWidget(self.note_input)

        add_layout.addWidget(QLabel("按键："))
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("如：a")
        self.key_input.setMaxLength(1)
        add_layout.addWidget(self.key_input)

        self.add_btn = QPushButton("添加")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_mapping)
        add_layout.addWidget(self.add_btn)
        layout.addLayout(add_layout)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.default_btn = QPushButton("恢复默认")
        self.default_btn.setCursor(Qt.PointingHandCursor)
        self.default_btn.clicked.connect(self._reset_default)

        self.save_btn = QPushButton("保存")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.default_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _apply_style(self) -> None:
        self.setStyleSheet(get_genshin_stylesheet())

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        for note in sorted(self._temp_keymap.keys()):
            self._add_table_row(note, self._temp_keymap[note])

    def _add_table_row(self, note: int, key: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        note_item = QTableWidgetItem(midi_to_jianpu(note))
        note_item.setTextAlignment(Qt.AlignCenter)
        note_item.setToolTip(f"MIDI {note} · {midi_to_note_name(note)}")
        self.table.setItem(row, 0, note_item)

        key_item = QTableWidgetItem(key.upper())
        key_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 1, key_item)

        delete_btn = QPushButton("删除")
        delete_btn.setProperty("note", note)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(self._delete_mapping)
        self.table.setCellWidget(row, 2, delete_btn)

    def _add_mapping(self) -> None:
        note_text = self.note_input.text().strip()
        key_text = self.key_input.text().strip()

        if not note_text or not key_text:
            QMessageBox.warning(self, "输入不完整", "请输入音符和按键")
            return

        note = jianpu_to_midi(note_text)
        if note is None:
            QMessageBox.warning(
                self,
                "输入错误",
                "无法识别的音符。\n请输入简谱（如：低音1、中音#1、高音1、倍高音2）或 MIDI 编号（0-127）。",
            )
            return

        if len(key_text) != 1:
            QMessageBox.warning(self, "输入错误", "按键必须是单个字符")
            return

        self._temp_keymap[note] = key_text.lower()
        self.note_input.clear()
        self.key_input.clear()
        self._refresh_table()

    def _delete_mapping(self) -> None:
        btn = self.sender()
        if not isinstance(btn, QPushButton):
            return
        note = btn.property("note")
        if note is not None:
            self._temp_keymap.pop(note, None)
            self._refresh_table()

    def _reset_default(self) -> None:
        reply = QMessageBox.question(
            self,
            "恢复默认",
            "确定要恢复为原神默认键位吗？当前自定义的键位将丢失。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._temp_keymap = dict(DEFAULT_GENSHIN_KEYMAP)
            self._refresh_table()

    def _save(self) -> None:
        self.keymap_manager._keymap = self._temp_keymap
        try:
            self.keymap_manager.save_to_file()
            QMessageBox.information(self, "保存成功", "键位设置已保存")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存键位：\n{e}")
