"""主窗口界面"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.style import genshin_font, get_genshin_stylesheet

from core.control_server import ControlServer
from core.keymap_manager import KeymapManager, midi_to_jianpu
from core.midi_parser import MidiParser, MidiParseResult
from core.player import MidiPlayer, PlaybackProgress, PlayerState
from core.preview_player import MidiPreviewPlayer, PreviewEvent, PreviewState
from ui.analyzer_dialog import AnalyzerDialog
from ui.floating_window import FloatingWindow
from ui.help_dialog import HelpDialog
from ui.mcp_dialog import McpSettingsDialog
from ui.settings_dialog import KeymapSettingsDialog
from utils.hotkey_manager import HotkeyManager
from utils.paths import ensure_resource_dir
from utils.settings import load_settings, save_settings
from utils.startup_check import run_startup_check


def _format_stats(stats: dict) -> str:
    """把音符适配统计格式化为日志文案"""
    parts = [f"直接映射 {stats['exact']}"]
    if stats["shift"]:
        parts.append(f"八度移位 {stats['shift']}")
    if stats["near"]:
        parts.append(f"黑键就近 {stats['near']}")
    if stats["unmapped"]:
        parts.append(f"无法演奏 {stats['unmapped']}")
    return " · ".join(parts)


class MainWindow(QMainWindow):
    """Windows 11 风格主窗口"""

    progress_signal = Signal(PlaybackProgress)
    state_signal = Signal(PlayerState)
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("原神自动弹琴")
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)

        self._current_file: Optional[Path] = None
        self._parsed: Optional[MidiParseResult] = None
        self._settings = load_settings()

        self.keymap_manager = KeymapManager(save_path=ensure_resource_dir() / "keymap.json")
        self.player = MidiPlayer(
            keymap_manager=self.keymap_manager,
            speed=1.0,
            on_progress=self._on_progress_callback,
            on_finished=self._on_finished_callback,
            on_state_changed=self._on_state_changed_callback,
        )
        self.preview_player = MidiPreviewPlayer(
            speed=1.0,
            on_event=self._on_preview_event_callback,
            on_finished=self._on_preview_finished_callback,
            on_state_changed=self._on_preview_state_changed_callback,
        )

        self.hotkey_manager = HotkeyManager(
            on_toggle=self._toggle_playback,
            on_stop=self._stop_playback,
        )

        # 不设置父窗口，避免主窗口最小化时悬浮窗被一起最小化
        self.floating_window = FloatingWindow()
        self.floating_window.toggle_clicked.connect(self._toggle_playback)
        self.floating_window.stop_clicked.connect(self._stop_playback)
        self.floating_window.hide_clicked.connect(self._hide_floating_window)

        self.progress_signal.connect(self._update_progress_ui)
        self.state_signal.connect(self._update_state_ui)
        self.log_signal.connect(self._append_log)

        self._init_ui()
        self._apply_genshin_style()
        self._run_startup_check()
        self.hotkey_manager.start()

        # 本地控制服务器（供 MCP 等 AI 客户端接入），受设置开关控制
        self._last_progress_time = 0.0
        self.control_server = None
        if bool(self._settings.get("mcp_enabled", True)):
            self._start_control_server()

    def _start_control_server(self) -> bool:
        """启动本地控制服务器（MCP），返回是否成功"""
        if self.control_server is not None:
            return True
        server = ControlServer(self._handle_control_action)
        port = server.start()
        if port:
            self.control_server = server
            self._append_log(f"MCP 控制接口已启动（http://127.0.0.1:{port}/mcp）")
            return True
        self._append_log("MCP 控制接口启动失败：端口 8765-8785 均被占用")
        return False

    def _stop_control_server(self) -> None:
        """停止本地控制服务器（MCP）"""
        if self.control_server is None:
            return
        self.control_server.shutdown()
        self.control_server = None
        self._append_log("MCP 控制接口已停止")

    def set_mcp_enabled(self, enabled: bool) -> bool:
        """切换 MCP 开关（持久化并即时生效），返回是否成功"""
        self._settings["mcp_enabled"] = enabled
        save_settings(self._settings)
        if enabled:
            return self._start_control_server()
        self._stop_control_server()
        return True

    # ---------------- MCP / 外部控制接口（在 GUI 线程执行） ----------------

    def _handle_control_action(self, action: str, params: dict):
        handlers = {
            "get_status": lambda: self._ctl_get_status(),
            "import_midi": lambda: self._ctl_import_midi(
                str(params.get("path", "")), params.get("auto_adapt")
            ),
            "play": lambda: self._ctl_play(),
            "pause": lambda: self.player.pause() or "已暂停",
            "resume": lambda: self._ctl_resume(),
            "stop": lambda: self._ctl_stop(),
            "toggle_preview": lambda: self._ctl_toggle_preview(),
            "set_speed": lambda: self._ctl_set_speed(float(params.get("speed", 1.0))),
            "show_floating": lambda: self._ctl_show_floating(bool(params.get("show", True))),
        }
        handler = handlers.get(action)
        if handler is None:
            raise ValueError(f"未知操作：{action}")
        return handler()

    def _ctl_get_status(self) -> dict:
        state_map = {PlayerState.STOPPED: "stopped", PlayerState.PLAYING: "playing", PlayerState.PAUSED: "paused"}
        preview_map = {
            PreviewState.STOPPED: "stopped", PreviewState.PLAYING: "playing", PreviewState.PAUSED: "paused",
        }
        return {
            "file": str(self._current_file) if self._current_file else None,
            "note_count": len(self._parsed.events) if self._parsed else 0,
            "duration": round(self._parsed.total_duration, 2) if self._parsed else 0.0,
            "track_count": self._parsed.track_count if self._parsed else 0,
            "keymap_stats": (
                self.keymap_manager.resolve_stats([ev.note for ev in self._parsed.events])
                if self._parsed else None
            ),
            "auto_adapt": self.keymap_manager.auto_adapt,
            "player_state": state_map.get(self.player.state, "stopped"),
            "preview_state": preview_map.get(self.preview_player.state, "stopped"),
            "progress": round(self._last_progress_time, 2),
            "speed": round(self.player.speed, 2),
            "floating_visible": self.floating_window.isVisible(),
            "mcp_enabled": self.control_server is not None,
            "mcp_port": self.control_server.port if self.control_server else None,
        }

    def _ctl_import_midi(self, path: str, auto_adapt: Optional[bool] = None) -> str:
        if not path:
            raise ValueError("缺少 path 参数")
        file = Path(path)
        if not file.is_file():
            raise FileNotFoundError(f"文件不存在：{path}")

        parsed = MidiParser.parse(file)
        self._current_file = file
        self._parsed = parsed
        self.file_path_edit.setText(str(file))
        self.track_label.setText(f"轨道数：{parsed.track_count}")
        self.duration_label.setText(f"总时长：{parsed.total_duration:.1f}s")
        has_chords = MidiParser.detect_overlapping_notes(parsed.events)
        self.chord_label.setText(f"包含和弦：{'是' if has_chords else '否'}")
        self._last_progress_time = 0.0
        self.progress_bar.setValue(0)

        # 音域适配：MCP 调用不弹窗（避免阻塞请求），默认启用适配，可用 auto_adapt 参数覆盖
        events = parsed.events
        raw = self.keymap_manager.resolve_stats([ev.note for ev in events], auto_adapt=False)
        if raw["unmapped"] > 0:
            self.keymap_manager.auto_adapt = True if auto_adapt is None else bool(auto_adapt)
        else:
            self.keymap_manager.auto_adapt = True

        self.player.load(parsed)
        stats = self.keymap_manager.resolve_stats([ev.note for ev in events])
        self._append_log(
            f"已导入：{file.name}，共 {len(events)} 个音符（{_format_stats(stats)}）"
        )
        if stats["unmapped"]:
            self._append_log(f"提示：{stats['unmapped']} 个音符无法适配任何琴键，将被跳过")
        self._refresh_adapt_label()

        msg = f"已导入 {file.name}：{len(events)} 个音符，{parsed.track_count} 轨道，时长 {parsed.total_duration:.1f}s"
        if raw["unmapped"] > 0:
            unplayable = stats["unmapped"] if self.keymap_manager.auto_adapt else stats["shift"] + stats["near"] + stats["unmapped"]
            msg += (
                f"；{'已启用' if self.keymap_manager.auto_adapt else '未启用'}音域适配，"
                f"不适配音符 {unplayable} 个（{unplayable * 100.0 / len(events):.1f}%）"
            )
        return msg

    def _ctl_play(self) -> str:
        if self._parsed is None:
            raise RuntimeError("尚未导入 MIDI 文件，请先调用 import_midi")
        self.preview_player.stop()
        self.player.play()
        return "开始播放"

    def _ctl_resume(self) -> str:
        if self.player.state != PlayerState.PAUSED:
            raise RuntimeError("当前不是暂停状态，无法继续")
        self.player.play()
        return "继续播放"

    def _ctl_stop(self) -> str:
        self.player.stop()
        self.preview_player.stop()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("00.0 / 00.0 s")
        self.current_notes_label.setText("当前音符：无")
        self._last_progress_time = 0.0
        return "已停止"

    def _ctl_toggle_preview(self) -> str:
        if self._parsed is None:
            raise RuntimeError("尚未导入 MIDI 文件，请先调用 import_midi")
        if self.preview_player.state == PreviewState.PLAYING:
            self.preview_player.pause()
            return "试听已暂停"
        if self.preview_player.state == PreviewState.PAUSED:
            self.preview_player.play()
            return "试听已继续"
        self.player.stop()
        self.preview_player.load(self._parsed)
        self.preview_player.play()
        return "开始试听"

    def _ctl_set_speed(self, speed: float) -> str:
        if not 0.1 <= speed <= 5.0:
            raise ValueError("speed 需在 0.1 ~ 5.0 之间")
        self.player.speed = speed
        self.preview_player.speed = speed
        self.speed_slider.setValue(int(speed * 100))
        return f"速度已设置为 {speed:.2f}x"

    def _ctl_show_floating(self, show: bool) -> str:
        if show:
            self.floating_window.show()
            self.floating_window.raise_()
            self.float_btn.setText("隐藏悬浮窗")
            return "悬浮窗已显示"
        self.floating_window.hide()
        self.float_btn.setText("显示悬浮窗")
        return "悬浮窗已隐藏"

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title = QLabel("原神自动弹琴")
        title.setFont(genshin_font(24, bold=True))
        title.setStyleSheet("color: #e9c46a; padding: 8px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 文件导入区域
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("请选择 MIDI 文件...")
        self.file_path_edit.setReadOnly(True)
        self.import_btn = QPushButton("导入 MIDI")
        self.import_btn.setCursor(Qt.PointingHandCursor)
        self.import_btn.clicked.connect(self._import_midi)
        file_layout.addWidget(self.file_path_edit, stretch=1)
        file_layout.addWidget(self.import_btn)
        layout.addLayout(file_layout)

        # 信息显示
        info_layout = QHBoxLayout()
        self.track_label = QLabel("轨道数：未导入")
        self.duration_label = QLabel("总时长：0.0s")
        self.chord_label = QLabel("包含和弦：否")
        self.adapt_label = QLabel("不适配音符：未导入")
        info_layout.addWidget(self.track_label)
        info_layout.addWidget(self.duration_label)
        info_layout.addWidget(self.chord_label)
        info_layout.addWidget(self.adapt_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 控制区
        control_layout = QHBoxLayout()
        self.play_btn = QPushButton("播放")
        self.pause_btn = QPushButton("暂停")
        self.stop_btn = QPushButton("停止")
        self.preview_btn = QPushButton("试听")
        self.float_btn = QPushButton("显示悬浮窗")
        self.settings_btn = QPushButton("键位设置")
        self.mcp_btn = QPushButton("MCP 协议")
        self.analyzer_btn = QPushButton("MIDI 分析")
        self.help_btn = QPushButton("使用教程")
        for btn in (self.play_btn, self.pause_btn, self.stop_btn, self.preview_btn, self.float_btn, self.settings_btn, self.mcp_btn, self.analyzer_btn, self.help_btn):
            btn.setCursor(Qt.PointingHandCursor)
            control_layout.addWidget(btn)

        self.play_btn.clicked.connect(self._start_playback)
        self.pause_btn.clicked.connect(self._pause_playback)
        self.preview_btn.clicked.connect(self._toggle_preview)
        self.stop_btn.clicked.connect(self._stop_playback)
        self.float_btn.clicked.connect(self._show_floating_window)
        self.settings_btn.clicked.connect(self._open_settings)
        self.mcp_btn.clicked.connect(self._open_mcp_settings)
        self.analyzer_btn.clicked.connect(self._open_analyzer)
        self.help_btn.clicked.connect(self._open_help)
        control_layout.addStretch()
        layout.addLayout(control_layout)

        # 速度滑块
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("播放速度："))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(25, 200)
        self.speed_slider.setValue(100)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        self.speed_label = QLabel("1.0x")
        speed_layout.addWidget(self.speed_slider, stretch=1)
        speed_layout.addWidget(self.speed_label)
        layout.addLayout(speed_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("00.0 / 00.0 s")
        layout.addWidget(self.progress_bar)

        # 当前音符
        self.current_notes_label = QLabel("当前音符：无")
        self.current_notes_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.current_notes_label)

        # 日志区
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("运行日志...")
        layout.addWidget(self.log_edit, stretch=1)

        # 快捷键提示
        hint = QLabel("快捷键：F8 播放/暂停  |  ESC 停止")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

    def _apply_genshin_style(self) -> None:
        """为主窗口应用原神风格样式（与全局主题保持一致并增强主窗口细节）。"""
        self.setStyleSheet(get_genshin_stylesheet())

    def _ask_adaptation(self) -> None:
        """当有音符无法直接映射到琴键时，询问用户是否启用自动适配"""
        events = self._parsed.events if self._parsed else []
        if not events:
            return
        total = len(events)
        # 先按「仅直接映射」统计：unmapped 即无法直接演奏的数量
        raw = self.keymap_manager.resolve_stats([ev.note for ev in events], auto_adapt=False)
        if raw["unmapped"] == 0:
            self.keymap_manager.auto_adapt = True
            return

        adapted = self.keymap_manager.resolve_stats([ev.note for ev in events], auto_adapt=True)
        raw_pct = raw["unmapped"] * 100.0 / total
        msg = (
            f"检测到 {raw['unmapped']} 个音符（占 {raw_pct:.1f}%）无法直接映射到琴键。\n\n"
            f"启用「自动适配」后：\n"
            f"  · {adapted['shift']} 个音符将八度移位到琴键音域\n"
            f"  · {adapted['near']} 个黑键将就近映射到相邻白键\n"
            f"  · 仍有 {adapted['unmapped']} 个音符无法演奏\n\n"
            f"是否对这首歌曲启用自动适配？\n"
            f"（选「否」将直接跳过所有无法直接映射的音符）"
        )
        reply = QMessageBox.question(
            self,
            "音域适配",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        self.keymap_manager.auto_adapt = reply == QMessageBox.Yes

    def _refresh_adapt_label(self) -> None:
        """刷新主界面「不适配音符」标签（数量与占比）"""
        events = self._parsed.events if self._parsed else []
        if not events:
            self.adapt_label.setText("不适配音符：未导入")
            self.adapt_label.setStyleSheet("")
            return
        total = len(events)
        # raw：仅直接映射的统计（non_exact = 无法直接映射的数量）
        raw = self.keymap_manager.resolve_stats([ev.note for ev in events], auto_adapt=False)
        non_exact = raw["unmapped"]
        if non_exact == 0:
            self.adapt_label.setText("不适配音符：0 个（0.0%）")
            unplayable = 0
        elif self.keymap_manager.auto_adapt:
            stats = self.keymap_manager.resolve_stats([ev.note for ev in events])
            adapted_count = stats["shift"] + stats["near"]
            self.adapt_label.setText(
                f"不适配音符：{stats['unmapped']} 个（{stats['unmapped'] * 100.0 / total:.1f}%），"
                f"已自动适配 {adapted_count} 个"
            )
            unplayable = stats["unmapped"]
        else:
            self.adapt_label.setText(
                f"不适配音符：{non_exact} 个（{non_exact * 100.0 / total:.1f}%），未启用适配"
            )
            unplayable = non_exact
        # 有音符无法演奏时红色高亮提醒
        if unplayable > 0:
            self.adapt_label.setStyleSheet("color: #d13438; font-weight: bold;")
        else:
            self.adapt_label.setStyleSheet("")

    def _import_midi(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 MIDI 文件",
            "",
            "MIDI 文件 (*.mid *.midi)",
        )
        if not path:
            return

        self._current_file = Path(path)
        self.file_path_edit.setText(str(self._current_file))

        try:
            self._parsed = MidiParser.parse(self._current_file)
        except Exception as e:
            QMessageBox.critical(self, "解析失败", f"无法解析 MIDI 文件：\n{e}")
            return

        self.track_label.setText(f"轨道数：{self._parsed.track_count}")
        self.duration_label.setText(f"总时长：{self._parsed.total_duration:.1f}s")
        has_chords = MidiParser.detect_overlapping_notes(self._parsed.events)
        self.chord_label.setText(f"包含和弦：{'是' if has_chords else '否'}")

        if self._parsed.is_multi_track:
            QMessageBox.information(
                self,
                "多音轨提醒",
                "检测到该 MIDI 文件包含多个音轨，程序将合并所有音轨进行播放。",
            )

        # 有音符无法直接映射时询问是否启用自动适配
        self._ask_adaptation()

        self.player.load(self._parsed)
        stats = self.keymap_manager.resolve_stats([ev.note for ev in self._parsed.events])
        adapt_desc = "已启用适配" if self.keymap_manager.auto_adapt else "未启用适配"
        self._append_log(
            f"已导入：{self._current_file.name}，共 {len(self._parsed.events)} 个音符"
            f"（{_format_stats(stats)}，{adapt_desc}）"
        )
        if stats["unmapped"]:
            self._append_log(f"提示：{stats['unmapped']} 个音符无法适配任何琴键，将被跳过")
        self._refresh_adapt_label()

    def _start_playback(self) -> None:
        if self._parsed is None:
            QMessageBox.warning(self, "未导入", "请先导入 MIDI 文件")
            return
        self.preview_player.stop()
        self.player.play()

    def _pause_playback(self) -> None:
        self.player.pause()

    def _stop_playback(self) -> None:
        self.player.stop()
        self.preview_player.stop()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("00.0 / 00.0 s")
        self.current_notes_label.setText("当前音符：无")

    def _toggle_playback(self) -> None:
        if self._parsed is None:
            return
        if self.preview_player.state in (PreviewState.PLAYING, PreviewState.PAUSED):
            self.preview_player.stop()
        if self.player.state == PlayerState.STOPPED:
            self.player.play()
        else:
            self.player.toggle_pause()

    def _toggle_preview(self) -> None:
        if self._parsed is None:
            QMessageBox.warning(self, "未导入", "请先导入 MIDI 文件")
            return
        if self.preview_player.state == PreviewState.PLAYING:
            self.preview_player.pause()
        elif self.preview_player.state == PreviewState.PAUSED:
            self.preview_player.play()
        else:
            self.player.stop()
            self.preview_player.load(self._parsed)
            self.preview_player.play()

    def _stop_preview(self) -> None:
        self.preview_player.stop()

    def _on_preview_event_callback(self, event: PreviewEvent) -> None:
        self.progress_signal.emit(
            PlaybackProgress(
                current_time=event.current_time,
                total_time=event.total_time,
                current_notes=[midi_to_jianpu(ev.note) for ev in event.notes],
            )
        )

    def _on_preview_finished_callback(self) -> None:
        self.log_signal.emit("试听结束")

    def _on_preview_state_changed_callback(self, state: PreviewState) -> None:
        if state == PreviewState.PLAYING:
            self.preview_btn.setText("暂停试听")
            self.play_btn.setEnabled(False)
            self.log_signal.emit("开始试听")
        elif state == PreviewState.PAUSED:
            self.preview_btn.setText("继续试听")
            self.play_btn.setEnabled(False)
            self.log_signal.emit("试听已暂停")
        else:
            self.preview_btn.setText("试听")
            self.play_btn.setEnabled(True)
            self.log_signal.emit("试听已停止")

    def _show_floating_window(self) -> None:
        if self.floating_window.isVisible():
            self.floating_window.hide()
            self.float_btn.setText("显示悬浮窗")
        else:
            self.floating_window.show()
            self.floating_window.raise_()
            self.floating_window.activateWindow()
            self.float_btn.setText("隐藏悬浮窗")

    def _hide_floating_window(self) -> None:
        self.floating_window.hide()
        self.float_btn.setText("显示悬浮窗")

    def _run_startup_check(self) -> None:
        report = run_startup_check()
        for detail in report.details:
            self._append_log(detail)
        if not report.ok:
            QMessageBox.warning(
                self,
                "启动检查异常",
                "程序启动检查发现问题，部分功能可能受限。\n详情请查看日志区。",
            )

    def _open_settings(self) -> None:
        dialog = KeymapSettingsDialog(self.keymap_manager, self)
        dialog.exec()
        # 键位可能已修改，重新统计不适配音符
        if self._parsed is not None:
            self._refresh_adapt_label()

    def _open_mcp_settings(self) -> None:
        dialog = McpSettingsDialog(self, self)
        dialog.exec()

    def _open_analyzer(self) -> None:
        dialog = AnalyzerDialog(self, self)
        dialog.exec()

    def _open_help(self) -> None:
        dialog = HelpDialog(self)
        dialog.exec()

    def _on_speed_changed(self, value: int) -> None:
        speed = value / 100.0
        self.speed_label.setText(f"{speed:.1f}x")
        self.player.speed = speed
        self.preview_player.speed = speed

    def _on_progress_callback(self, progress: PlaybackProgress) -> None:
        self.progress_signal.emit(progress)

    def _on_finished_callback(self) -> None:
        self.log_signal.emit("播放结束")

    def _on_state_changed_callback(self, state: PlayerState) -> None:
        self.state_signal.emit(state)

    def _update_progress_ui(self, progress: PlaybackProgress) -> None:
        self._last_progress_time = progress.current_time
        if progress.total_time > 0:
            ratio = progress.current_time / progress.total_time
            self.progress_bar.setValue(int(ratio * 1000))
            self.progress_bar.setFormat(
                f"{progress.current_time:.1f} / {progress.total_time:.1f} s"
            )
        notes_text = ", ".join(progress.current_notes) if progress.current_notes else "无"
        self.current_notes_label.setText(f"当前音符：{notes_text}")

    def _update_state_ui(self, state: PlayerState) -> None:
        self.floating_window.update_state(state)
        if state == PlayerState.PLAYING:
            self.play_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.log_signal.emit("开始播放")
        elif state == PlayerState.PAUSED:
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.log_signal.emit("已暂停")
        else:
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.log_signal.emit("已停止")

    def _append_log(self, message: str) -> None:
        self.log_edit.append(message)

    def changeEvent(self, event):
        # 主窗口最小化/还原时，保持悬浮窗可见，不跟随最小化
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                self.floating_window.setWindowState(Qt.WindowNoState)
                self.floating_window.show()
        super().changeEvent(event)

    def closeEvent(self, event):
        if self.control_server is not None:
            self.control_server.shutdown()
        self.player.stop()
        self.preview_player.stop()
        self.hotkey_manager.stop()
        self.floating_window.close()
        event.accept()
