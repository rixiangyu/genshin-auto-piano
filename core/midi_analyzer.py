"""MIDI 深度分析模块

分析 MIDI 文件的音符分布、时长、间隔、和弦、音域，
以及与当前键位映射的适配情况（直接映射/八度移位/黑键就近/无法演奏）。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mido

from core.keymap_manager import KeymapManager, midi_to_jianpu, midi_to_note_name


@dataclass
class NoteDistribution:
    """单个音符的统计"""
    note: int
    count: int
    mode: str  # exact / shift / near / unmapped
    key: Optional[str]  # 适配后的按键（可能为 None）


@dataclass
class AnalyzerReport:
    """MIDI 分析报告"""
    file_name: str
    midi_type: int
    track_count: int
    ticks_per_beat: int
    length: float  # 秒
    total_notes: int
    note_min: int
    note_max: int
    duration_min: float
    duration_avg: float
    duration_max: float
    short_notes_50ms: int  # < 50ms 音符数
    short_notes_20ms: int  # < 20ms 音符数
    gap_min: float
    gap_avg: float
    gap_max: float
    dense_gaps: int  # 相邻两组音符间隔 < 30ms 的次数
    chord_count: int  # 和弦时刻数
    max_chord_size: int  # 最大同时音符数
    chord_sizes: Dict[int, int]  # 和弦大小分布
    distribution: List[NoteDistribution] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)  # exact/shift/near/unmapped
    unresolved_notes: List[Tuple[int, int]] = field(default_factory=list)  # (note, count) 无法演奏


def analyze(path: Path | str, keymap: KeymapManager) -> AnalyzerReport:
    """分析 MIDI 文件并生成报告（分析时始终启用适配以展示完整适配效果）"""
    path = Path(path)
    mid = mido.MidiFile(path)

    all_notes = []  # (start_sec, note, velocity, duration_sec)
    for track in mid.tracks:
        abs_ticks = 0
        active = {}  # note -> (start_tick, velocity)
        for msg in track:
            abs_ticks += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                active[msg.note] = (abs_ticks, msg.velocity)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                if msg.note in active:
                    start_tick, vel = active.pop(msg.note)
                    dur = mido.tick2second(abs_ticks - start_tick, mid.ticks_per_beat, 500000)
                    start = mido.tick2second(start_tick, mid.ticks_per_beat, 500000)
                    all_notes.append((start, msg.note, vel, dur))
    all_notes.sort(key=lambda x: x[0])

    notes = [n[1] for n in all_notes]
    counter = Counter(notes)

    # 时长统计
    durs = [n[3] for n in all_notes] or [0.0]

    # 间隔统计
    gaps = []
    prev_end = None
    for start, note, vel, dur in all_notes:
        if prev_end is not None and start > prev_end:
            gaps.append(start - prev_end)
        prev_end = max(prev_end or 0, start + dur)

    # 和弦检测（同一时刻多个音符）
    groups: Dict[float, List[int]] = {}
    for start, note, vel, dur in all_notes:
        groups.setdefault(round(start, 3), []).append(note)
    chords = {t: ns for t, ns in groups.items() if len(ns) > 1}
    chord_sizes = Counter(len(ns) for ns in chords.values())

    # 相邻两组间隔 < 30ms
    starts = sorted(groups.keys())
    dense = sum(1 for i in range(1, len(starts)) if starts[i] - starts[i - 1] < 0.03)

    # 适配统计（启用适配）
    stats = keymap.resolve_stats(notes)
    distribution = []
    unresolved = []
    for note in sorted(counter):
        key, mode = keymap.resolve_key(note)
        distribution.append(NoteDistribution(note=note, count=counter[note], mode=mode, key=key))
        if mode == "unmapped":
            unresolved.append((note, counter[note]))

    return AnalyzerReport(
        file_name=path.name,
        midi_type=mid.type,
        track_count=len(mid.tracks),
        ticks_per_beat=mid.ticks_per_beat,
        length=mid.length,
        total_notes=len(all_notes),
        note_min=min(notes) if notes else 0,
        note_max=max(notes) if notes else 0,
        duration_min=min(durs),
        duration_avg=sum(durs) / len(durs),
        duration_max=max(durs),
        short_notes_50ms=sum(1 for d in durs if d < 0.05),
        short_notes_20ms=sum(1 for d in durs if d < 0.02),
        gap_min=min(gaps) if gaps else 0.0,
        gap_avg=sum(gaps) / len(gaps) if gaps else 0.0,
        gap_max=max(gaps) if gaps else 0.0,
        dense_gaps=dense,
        chord_count=len(chords),
        max_chord_size=max(chord_sizes) if chord_sizes else 0,
        chord_sizes=dict(sorted(chord_sizes.items())),
        distribution=distribution,
        stats=stats,
        unresolved_notes=unresolved,
    )


def distribution_row_text(item: NoteDistribution) -> str:
    """音符分布行文本"""
    mode_text = {"exact": "直接", "shift": "移位", "near": "就近", "unmapped": "无法演奏"}[item.mode]
    key_text = item.key.upper() if item.key else "—"
    return (
        f"{item.count:5d} 次   {item.note:3d}   {midi_to_note_name(item.note):4s}   "
        f"{midi_to_jianpu(item.note):8s} {key_text:4s}  {mode_text}"
    )
