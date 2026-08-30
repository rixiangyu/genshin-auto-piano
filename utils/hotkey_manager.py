"""全局快捷键管理"""
from __future__ import annotations

from typing import Callable, Optional

from pynput.keyboard import Key, Listener


class HotkeyManager:
    """监听全局快捷键"""

    def __init__(
        self,
        on_toggle: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
    ):
        self.on_toggle = on_toggle
        self.on_stop = on_stop
        self._listener: Optional[Listener] = None

        # 默认快捷键
        self._toggle_key = Key.f8
        self._stop_key = Key.esc

    def start(self) -> None:
        if self._listener is not None:
            return
        self._listener = Listener(on_press=self._on_press)
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key) -> None:
        if key == self._toggle_key and self.on_toggle:
            self.on_toggle()
        elif key == self._stop_key and self.on_stop:
            self.on_stop()
