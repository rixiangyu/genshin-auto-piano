"""播放器核心模块"""
from __future__ import annotations

import heapq
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from threading import Event, Thread
from typing import Callable, Dict, List, Optional, Tuple

from core.keymap_manager import KeymapManager, midi_to_jianpu
from core.midi_parser import MidiParseResult, NoteEvent
from utils.input_simulator import press_keys, release_keys


class PlayerState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


@dataclass
class PlaybackProgress:
    current_time: float
    total_time: float
    current_notes: List[str]


# 按键释放的最小保持时间（秒）：确保原神 RawInput 能识别按下/释放
MIN_HOLD = 0.03
# 释放与下一次按下之间预留的间隙（秒）：保证游戏检测到按键状态变化
RELEASE_GAP = 0.03


class MidiPlayer:
    """MIDI 播放器：按时间线模拟键盘按键

    支持的音乐表现：
    - 长按持续音：按键按住 MIDI 音符的实际时长（原神琴按住持续发声）
    - 断奏/连奏：音符时长短则短按，长则长按，自然还原
    - 和弦：同一时刻的音符同时按下
    - 同键重复：前一个音先释放再按下，避免游戏漏音
    - 音域适配：超范围音符八度移位、黑键就近白键（见 KeymapManager.resolve_key）
    """

    def __init__(
        self,
        keymap_manager: KeymapManager,
        speed: float = 1.0,
        on_progress: Optional[Callable[[PlaybackProgress], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
        on_state_changed: Optional[Callable[[PlayerState], None]] = None,
    ):
        self.keymap = keymap_manager
        self.speed = max(0.1, speed)
        self._state = PlayerState.STOPPED
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._pause_event = Event()
        self._pause_event.set()  # 默认不暂停

        self._on_progress = on_progress
        self._on_finished = on_finished
        self._on_state_changed = on_state_changed

        self._parsed: Optional[MidiParseResult] = None
        self._note_groups: List[tuple[float, List[NoteEvent]]] = []
        self._total_time = 0.0
        # 播放期状态：key -> (释放时间, 序号)，用于校验 heap 条目是否仍有效
        self._held_keys: Dict[str, Tuple[float, int]] = {}
        self._release_heap: List[Tuple[float, int, str]] = []
        self._release_seq = 0

    @property
    def state(self) -> PlayerState:
        return self._state

    def _set_state(self, state: PlayerState) -> None:
        self._state = state
        if self._on_state_changed:
            self._on_state_changed(state)

    def load(self, parsed: MidiParseResult) -> None:
        """加载解析后的 MIDI 数据"""
        self.stop()
        self._parsed = parsed
        self._total_time = parsed.total_duration

        # 将相同开始时间的音符分组，构成和弦
        groups = defaultdict(list)
        for ev in parsed.events:
            groups[round(ev.start_time, 5)].append(ev)

        self._note_groups = sorted(groups.items(), key=lambda x: x[0])

    def play(self) -> None:
        """开始或继续播放"""
        if self._state == PlayerState.PLAYING:
            return
        if self._state == PlayerState.PAUSED:
            self._pause_event.set()
            self._set_state(PlayerState.PLAYING)
            return
        if not self._note_groups:
            return

        self._stop_event.clear()
        self._pause_event.set()
        self._set_state(PlayerState.PLAYING)

        self._thread = Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        """暂停播放"""
        if self._state == PlayerState.PLAYING:
            self._pause_event.clear()
            self._set_state(PlayerState.PAUSED)

    def toggle_pause(self) -> None:
        """切换暂停/继续"""
        if self._state == PlayerState.PLAYING:
            self.pause()
        elif self._state == PlayerState.PAUSED:
            self.play()

    def stop(self) -> None:
        """停止播放"""
        self._stop_event.set()
        self._pause_event.set()
        self._set_state(PlayerState.STOPPED)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        # 兜底：确保没有任何按键被卡在按下状态
        self._release_all()

    # ---------------- 播放期间按键管理 ----------------

    def _schedule_release(self, key: str, midi_time: float) -> None:
        """登记按键的释放时间（MIDI 时间域）"""
        heapq.heappush(self._release_heap, (midi_time, self._release_seq, key))
        self._held_keys[key] = (midi_time, self._release_seq)
        self._release_seq += 1

    def _release_key(self, key: str) -> None:
        """立即释放按键"""
        self._held_keys.pop(key, None)
        release_keys([key])

    def _pop_due_releases(self, start: float, t0: float) -> None:
        """释放所有到期的按键（把 MIDI 时间换算为墙钟时间）"""
        now = time.perf_counter()
        while self._release_heap:
            when, seq, key = self._release_heap[0]
            release_abs = start + (when - t0) / self.speed
            if release_abs > now:
                break
            heapq.heappop(self._release_heap)
            # 仅当该条目仍是此键当前的有效释放计划时才释放
            # （同键重复时旧条目已失效，避免误释放新音）
            if self._held_keys.get(key) == (when, seq):
                self._release_key(key)

    def _release_all(self) -> None:
        """释放全部按下的按键并清空状态"""
        if self._held_keys:
            release_keys(list(self._held_keys.keys()))
            self._held_keys.clear()
        self._release_heap.clear()

    def _next_release_abs(self, start: float, t0: float) -> Optional[float]:
        """最近一次释放事件对应的墙钟时间"""
        if not self._release_heap:
            return None
        when = self._release_heap[0][0]
        return start + (when - t0) / self.speed

    # ---------------- 主播放循环 ----------------

    def _playback_loop(self) -> None:
        if not self._note_groups:
            return

        self._release_all()
        start_time = time.perf_counter()
        first_group_time = self._note_groups[0][0]
        t0 = first_group_time

        for group_time, notes in self._note_groups:
            if self._stop_event.is_set():
                break

            # 等待到该组音符的播放时间（期间处理到期释放）
            target = start_time + (group_time - t0) / self.speed
            while True:
                if self._stop_event.is_set():
                    break
                self._pop_due_releases(start_time, t0)
                now = time.perf_counter()
                if now >= target:
                    break
                next_release = self._next_release_abs(start_time, t0)
                deadline = target if next_release is None else min(target, next_release)
                if not self._pause_event.is_set():
                    # 暂停时冻结时间轴，恢复后继续
                    pause_start = time.perf_counter()
                    self._pause_event.wait()
                    paused_duration = time.perf_counter() - pause_start
                    start_time += paused_duration
                    target += paused_duration
                    deadline += paused_duration
                sleep = deadline - time.perf_counter()
                if sleep > 0:
                    time.sleep(min(sleep, 0.002))

            if self._stop_event.is_set():
                break

            # 到点后处理已到期释放，再按下本组音符
            self._pop_due_releases(start_time, t0)

            press_plan: List[Tuple[str, float]] = []
            for ev in notes:
                key, _mode = self.keymap.resolve_key(ev.note)
                if not key:
                    continue
                if key in self._held_keys:
                    # 同键重复：先释放旧音再按新音，确保游戏识别到两次独立按键
                    self._release_key(key)
                press_plan.append((key, ev.duration))

            if press_plan:
                press_keys([k for k, _ in press_plan])
                # 按住实际时长（扣除释放间隙）；MIN_HOLD/RELEASE_GAP 以墙钟时间为基准，
                # 换算回 MIDI 时间域时需乘以 speed，保证加速播放时游戏仍能识别按键
                for key, duration in press_plan:
                    hold = max(MIN_HOLD * self.speed, duration - RELEASE_GAP * self.speed)
                    self._schedule_release(key, group_time + hold)

            # 进度回调（音符用简谱显示）
            if self._on_progress:
                progress = PlaybackProgress(
                    current_time=group_time,
                    total_time=self._total_time,
                    current_notes=[midi_to_jianpu(ev.note) for ev in notes],
                )
                self._on_progress(progress)

        # 等待尾音全部释放
        while self._release_heap and not self._stop_event.is_set():
            next_release = self._next_release_abs(start_time, t0)
            if next_release is None:
                break
            while time.perf_counter() < next_release:
                if self._stop_event.is_set():
                    break
                if not self._pause_event.is_set():
                    pause_start = time.perf_counter()
                    self._pause_event.wait()
                    paused_duration = time.perf_counter() - pause_start
                    start_time += paused_duration
                    next_release += paused_duration
                time.sleep(0.002)
            self._pop_due_releases(start_time, t0)

        self._release_all()

        if self._on_finished and not self._stop_event.is_set():
            self._on_finished()
        self._set_state(PlayerState.STOPPED)
