"""MIDI 试听模块"""
from __future__ import annotations

import io
import math
import struct
import time
import wave
import winsound
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from threading import Event, Thread
from typing import Callable, List, Optional

from core.midi_parser import MidiParseResult, NoteEvent


class PreviewState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


@dataclass
class PreviewEvent:
    """试听事件"""
    current_time: float
    total_time: float
    notes: List[NoteEvent]


def midi_note_to_freq(note: int) -> int:
    """MIDI 音符转频率（Hz）"""
    return int(440.0 * (2.0 ** ((note - 69) / 12.0)))


def generate_tone_buffer(
    frequencies: List[int],
    duration_ms: int,
    sample_rate: int = 16000,
    stop_event: Optional[Event] = None,
) -> Optional[bytes]:
    """生成正弦波 WAV 数据，支持多频率混合（和弦）"""
    if not frequencies:
        return b""

    num_samples = int(sample_rate * duration_ms / 1000)
    # 避免和弦音量过大导致削波，振幅按频率数量均分
    amplitude = 32767 // len(frequencies)

    samples = []
    for i in range(num_samples):
        # 每 1000 个采样检查一次停止信号，让长时间生成可被中断
        if i % 1000 == 0 and stop_event is not None and stop_event.is_set():
            return None
        t = i / sample_rate
        value = 0.0
        for freq in frequencies:
            value += math.sin(2.0 * math.pi * freq * t)
        # 归一化到 [-1, 1]，再映射到 16-bit 采样
        value = max(-1.0, min(1.0, value / len(frequencies)))
        samples.append(int(value * amplitude))

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<" + "h" * len(samples), *samples))

    return buf.getvalue()


class MidiPreviewPlayer:
    """MIDI 试听播放器：不模拟按键，仅提供视觉/听觉预览"""

    def __init__(
        self,
        speed: float = 1.0,
        on_event: Optional[Callable[[PreviewEvent], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
        on_state_changed: Optional[Callable[[PreviewState], None]] = None,
    ):
        self.speed = max(0.1, speed)
        self._state = PreviewState.STOPPED
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._pause_event = Event()
        self._pause_event.set()

        self._on_event = on_event
        self._on_finished = on_finished
        self._on_state_changed = on_state_changed

        self._note_groups: List[tuple[float, List[NoteEvent]]] = []
        self._total_time = 0.0

    @property
    def state(self) -> PreviewState:
        return self._state

    def _set_state(self, state: PreviewState) -> None:
        self._state = state
        if self._on_state_changed:
            self._on_state_changed(state)

    def load(self, parsed: MidiParseResult) -> None:
        """加载解析后的 MIDI 数据"""
        self.stop()
        self._total_time = parsed.total_duration

        groups = defaultdict(list)
        for ev in parsed.events:
            groups[round(ev.start_time, 5)].append(ev)
        self._note_groups = sorted(groups.items(), key=lambda x: x[0])

    def play(self) -> None:
        if self._state == PreviewState.PLAYING:
            return
        if self._state == PreviewState.PAUSED:
            self._pause_event.set()
            self._set_state(PreviewState.PLAYING)
            return
        if not self._note_groups:
            return

        self._stop_event.clear()
        self._pause_event.set()
        self._set_state(PreviewState.PLAYING)

        self._thread = Thread(target=self._preview_loop, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        if self._state == PreviewState.PLAYING:
            self._pause_event.clear()
            self._set_state(PreviewState.PAUSED)
            # 立即停止当前正在播放的声音
            winsound.PlaySound(None, winsound.SND_PURGE)

    def toggle_pause(self) -> None:
        if self._state == PreviewState.PLAYING:
            self.pause()
        elif self._state == PreviewState.PAUSED:
            self.play()

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        self._set_state(PreviewState.STOPPED)
        winsound.PlaySound(None, winsound.SND_PURGE)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.3)
        self._thread = None

    def _wait_while_paused(self) -> float:
        """如果处于暂停状态则等待，返回本次暂停持续时长"""
        if not self._pause_event.is_set():
            pause_start = time.perf_counter()
            self._pause_event.wait()
            return time.perf_counter() - pause_start
        return 0.0

    def _preview_loop(self) -> None:
        if not self._note_groups:
            return

        start_time = time.perf_counter()
        first_group_time = self._note_groups[0][0]

        for group_time, notes in self._note_groups:
            if self._stop_event.is_set():
                break

            target = start_time + (group_time - first_group_time) / self.speed

            # 等待到达播放时间点
            while time.perf_counter() < target:
                if self._stop_event.is_set():
                    break
                paused = self._wait_while_paused()
                if paused > 0:
                    start_time += paused
                    target += paused
                time.sleep(0.001)

            if self._stop_event.is_set():
                break

            # 到达时间点后再次检查暂停/停止
            paused = self._wait_while_paused()
            if paused > 0:
                start_time += paused
            if self._stop_event.is_set():
                break

            # 按该组和弦音符的实际时长发声，最短 80ms、最长 500ms
            duration_s = max((ev.duration for ev in notes), default=0.0)
            duration_ms = int(max(80.0, min(duration_s * 1000.0, 500.0)))

            frequencies = []
            for ev in notes:
                freq = midi_note_to_freq(ev.note)
                # 限制在 winsound 可接受范围 37-32767 Hz
                freq = max(37, min(freq, 32767))
                frequencies.append(freq)

            if frequencies and duration_ms > 0:
                buffer = generate_tone_buffer(
                    frequencies, duration_ms, stop_event=self._stop_event
                )
                if buffer:
                    Thread(
                        target=lambda b=buffer: winsound.PlaySound(b, winsound.SND_MEMORY),
                        daemon=True,
                    ).start()

            if self._on_event:
                self._on_event(
                    PreviewEvent(
                        current_time=group_time,
                        total_time=self._total_time,
                        notes=notes,
                    )
                )

        if self._on_finished and not self._stop_event.is_set():
            self._on_finished()
        self._set_state(PreviewState.STOPPED)
