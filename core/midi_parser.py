"""MIDI 解析模块"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import mido


@dataclass
class NoteEvent:
    """单个音符事件"""
    note: int          # MIDI 音符号（0-127）
    velocity: int      # 力度
    start_time: float  # 起始时间（秒）
    duration: float    # 持续时长（秒）


@dataclass
class MidiParseResult:
    """MIDI 解析结果"""
    events: List[NoteEvent]
    track_count: int
    is_multi_track: bool
    ticks_per_beat: int
    total_duration: float
    tempo_changes: List[Tuple[float, int]]  # (时间, 微秒/拍)


class MidiParser:
    """解析 MIDI 文件，提取可播放的音符事件"""

    @staticmethod
    def parse(file_path: str | Path) -> MidiParseResult:
        midi = mido.MidiFile(str(file_path))
        track_count = len(midi.tracks)

        # 合并所有音轨的事件，按绝对 tick 排序
        raw_events: List[Tuple[int, mido.Message]] = []
        note_tracks = 0
        for track in midi.tracks:
            abs_tick = 0
            has_notes = False
            for msg in track:
                abs_tick += msg.time
                # 只保留 note_on / note_off 以及 set_tempo
                if msg.type in ("note_on", "note_off") or msg.type == "set_tempo":
                    raw_events.append((abs_tick, msg))
                    if msg.type == "note_on" and msg.velocity > 0:
                        has_notes = True
            if has_notes:
                note_tracks += 1

        is_multi_track = note_tracks > 1
        raw_events.sort(key=lambda x: x[0])

        ticks_per_beat = midi.ticks_per_beat
        tempo = 500000  # 默认 120 BPM
        tempo_changes: List[Tuple[float, int]] = [(0.0, tempo)]

        # 计算 tick -> 秒的映射
        def tick_to_second(tick: int) -> float:
            t = 0.0
            cur_tempo = 500000
            last_tick = 0
            for tc_tick, tc_msg in sorted(
                (e for e in raw_events if e[1].type == "set_tempo"),
                key=lambda x: x[0],
            ):
                if tc_tick > tick:
                    break
                t += (tc_tick - last_tick) * cur_tempo / ticks_per_beat / 1_000_000
                cur_tempo = tc_msg.tempo
                last_tick = tc_tick
            t += (tick - last_tick) * cur_tempo / ticks_per_beat / 1_000_000
            return t

        # 提取音符事件
        active_notes: dict[int, Tuple[int, int]] = {}  # note -> (start_tick, velocity)
        note_events: List[NoteEvent] = []

        for abs_tick, msg in raw_events:
            if msg.type == "set_tempo":
                current_time = tick_to_second(abs_tick)
                tempo = msg.tempo
                tempo_changes.append((current_time, tempo))
                continue

            if msg.type != "note_on" and msg.type != "note_off":
                continue

            # 兼容 velocity=0 的 note_on 作为 note_off
            is_note_off = msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0)

            if msg.type == "note_on" and msg.velocity > 0:
                active_notes[msg.note] = (abs_tick, msg.velocity)
            elif is_note_off and msg.note in active_notes:
                start_tick, velocity = active_notes.pop(msg.note)
                start_time = tick_to_second(start_tick)
                end_time = tick_to_second(abs_tick)
                duration = max(0.0, end_time - start_time)
                note_events.append(
                    NoteEvent(
                        note=msg.note,
                        velocity=velocity,
                        start_time=start_time,
                        duration=duration,
                    )
                )

        if not note_events:
            total_duration = 0.0
        else:
            last = max(note_events, key=lambda e: e.start_time + e.duration)
            total_duration = last.start_time + last.duration

        # 按开始时间排序
        note_events.sort(key=lambda e: e.start_time)

        return MidiParseResult(
            events=note_events,
            track_count=track_count,
            is_multi_track=is_multi_track,
            ticks_per_beat=ticks_per_beat,
            total_duration=total_duration,
            tempo_changes=tempo_changes,
        )

    @staticmethod
    def detect_overlapping_notes(events: List[NoteEvent]) -> bool:
        """检测是否存在和弦（同一时刻多个音符）"""
        from collections import defaultdict
        groups = defaultdict(list)
        for ev in events:
            groups[round(ev.start_time, 4)].append(ev)
        return any(len(g) > 1 for g in groups.values())
