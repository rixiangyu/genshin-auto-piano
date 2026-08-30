"""键位映射管理模块"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Optional


# ---------------- 简谱转换工具 ----------------
# 简谱以 C 大调为准：C=1(do) D=2(re) E=3(mi) F=4(fa) G=5(sol) A=6(la) B=7(si)
_STEP_SEMITONES = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11}
_SHARP_STEPS = ["1", "#1", "2", "#2", "3", "4", "#4", "5", "#5", "6", "#6", "7"]
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_JIANPU_RE = re.compile(r"^(?P<octave>倍*[高中低]音)?(?P<accidental>[#b♭♯]?)(?P<step>[1-7])$")


def midi_to_jianpu(note: int) -> str:
    """MIDI 音符编号转简谱名称（C 大调），如 60 -> 中音1、61 -> 中音#1、72 -> 高音1"""
    if not 0 <= note <= 127:
        raise ValueError("MIDI 音符编号必须在 0-127 之间")
    octave_offset = note // 12 - 5  # MIDI 60 = C4 = 简谱中音区
    step_name = _SHARP_STEPS[note % 12]
    if octave_offset == 0:
        octave_name = "中音"
    elif octave_offset > 0:
        octave_name = "倍" * (octave_offset - 1) + "高音"
    else:
        octave_name = "倍" * (-octave_offset - 1) + "低音"
    return f"{octave_name}{step_name}"


def midi_to_note_name(note: int) -> str:
    """MIDI 音符编号转音名，如 60 -> C4"""
    return f"{_NOTE_NAMES[note % 12]}{note // 12 - 1}"


def jianpu_to_midi(text: str) -> Optional[int]:
    """解析简谱文本为 MIDI 音符编号。

    支持的写法：高音1 / 低音#5 / 倍高音1 / #4（默认中音）/ 3（默认中音3）/ 60（MIDI 编号）。
    无法识别时返回 None。
    """
    if not text:
        return None
    s = text.strip().replace(" ", "")
    if not s:
        return None

    # 纯数字：单个 1-7 视为简谱中音，其余按 MIDI 编号处理
    if s.isdigit():
        if len(s) == 1 and 1 <= int(s) <= 7:
            return 60 + _STEP_SEMITONES[int(s)]
        value = int(s)
        return value if 0 <= value <= 127 else None

    match = _JIANPU_RE.match(s)
    if not match:
        return None

    octave_text = match.group("octave") or ""
    if not octave_text or octave_text == "中音":
        octave_offset = 0
    else:
        times = octave_text.count("倍")
        octave_offset = (times + 1) * (1 if octave_text.endswith("高音") else -1)

    semitone = _STEP_SEMITONES[int(match.group("step"))]
    accidental = match.group("accidental")
    if accidental in ("#", "♯"):
        semitone += 1
    elif accidental in ("b", "♭"):
        semitone -= 1

    midi = 60 + octave_offset * 12 + semitone
    return midi if 0 <= midi <= 127 else None


# 原神 PC 端默认键盘琴键参考布局（基于 21 键）
DEFAULT_GENSHIN_KEYMAP: Dict[int, str] = {
    # 低音区
    48: "z", 50: "x", 52: "c", 53: "v", 55: "b", 57: "n", 59: "m",
    # 中音区
    60: "a", 62: "s", 64: "d", 65: "f", 67: "g", 69: "h", 71: "j",
    # 高音区
    72: "q", 74: "w", 76: "e", 77: "r", 79: "t", 81: "y", 83: "u",
}


class KeymapManager:
    """管理 MIDI 音符到键盘按键的映射"""

    def __init__(self, save_path: Optional[str | Path] = None):
        self._keymap: Dict[int, str] = {}
        self._save_path = Path(save_path) if save_path else None
        # 是否对超出键位音域的音符启用自动适配（八度移位 / 黑键就近白键）
        self.auto_adapt: bool = True
        self.load_default()
        if self._save_path and self._save_path.exists():
            self.load_from_file(self._save_path)

    @property
    def keymap(self) -> Dict[int, str]:
        return self._keymap.copy()

    def load_default(self) -> None:
        """加载原神默认键位"""
        self._keymap = dict(DEFAULT_GENSHIN_KEYMAP)

    def load_from_file(self, path: str | Path) -> None:
        """从 JSON 文件加载自定义键位"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._keymap = {int(k): v for k, v in data.items()}

    def save_to_file(self, path: Optional[str | Path] = None) -> None:
        """保存当前键位到 JSON 文件"""
        target = Path(path) if path else self._save_path
        if not target:
            raise ValueError("未指定保存路径")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self._keymap, f, ensure_ascii=False, indent=2)

    def set_mapping(self, note: int, key: str) -> None:
        """设置单个音符对应的按键"""
        if not key or len(key) != 1:
            raise ValueError("按键必须是单个字符")
        self._keymap[note] = key.lower()

    def remove_mapping(self, note: int) -> None:
        """删除某个音符的映射"""
        self._keymap.pop(note, None)

    def get_key(self, note: int) -> Optional[str]:
        """获取音符对应的按键，未映射返回 None"""
        return self._keymap.get(note)

    def resolve_key(self, note: int, auto_adapt: Optional[bool] = None) -> tuple[Optional[str], str]:
        """自适应解析按键，返回 (按键, 适配方式)。

        适配顺序：
        1. exact   —— 键位表中的直接映射
        2. shift   —— 八度移位：超出键位音域的音符整体升/降八度（需启用适配）
        3. near    —— 黑键就近：键位表只有白键时，黑键映射到相邻白键（需启用适配）
        4. unmapped —— 无法适配（返回 None）

        auto_adapt 为 None 时使用 self.auto_adapt 当前设置；False 时只做直接映射。
        """
        if auto_adapt is None:
            auto_adapt = self.auto_adapt

        key = self._keymap.get(note)
        if key:
            return key, "exact"
        if not auto_adapt or not self._keymap:
            return None, "unmapped"

        lo, hi = min(self._keymap), max(self._keymap)
        if hi - lo < 12:
            # 键位跨度不足一个八度，不做移位（避免死循环），仅就近白键
            n = note
        else:
            n = note
            while n < lo:
                n += 12
            while n > hi:
                n -= 12

        if lo <= n <= hi:
            if n != note:
                key = self._keymap.get(n)
                if key:
                    return key, "shift"
            # 黑键（半音）就近映射到相邻白键
            if n % 12 in (1, 3, 6, 8, 10):
                for cand in (n - 1, n + 1):
                    if cand in self._keymap:
                        return self._keymap[cand], "near"
        return None, "unmapped"

    def resolve_stats(self, notes, auto_adapt: Optional[bool] = None) -> Dict[str, int]:
        """统计一组音符的适配情况，返回 {exact/shift/near/unmapped: 数量}

        auto_adapt 为 None 时使用当前设置；False 时统计纯直接映射的结果。
        """
        stats: Dict[str, int] = {"exact": 0, "shift": 0, "near": 0, "unmapped": 0}
        for note in notes:
            _, mode = self.resolve_key(note, auto_adapt=auto_adapt)
            stats[mode] += 1
        return stats

    def clear(self) -> None:
        """清空所有映射"""
        self._keymap.clear()

    def has_mapping(self, note: int) -> bool:
        return note in self._keymap
