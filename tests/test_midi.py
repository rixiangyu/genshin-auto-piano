"""核心模块单元测试"""
from __future__ import annotations

import tempfile
from pathlib import Path

import mido

from core.keymap_manager import KeymapManager
from core.midi_parser import MidiParser
from core.player import MidiPlayer


def make_test_midi(path: Path, notes: list[tuple[int, int, int, int]]) -> None:
    """生成测试 MIDI 文件
    notes: [(note, velocity, start_tick, duration_tick)]
    """
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    last_tick = 0
    events = []
    for note, velocity, start, duration in notes:
        events.append((start, mido.Message("note_on", note=note, velocity=velocity, time=0)))
        events.append((start + duration, mido.Message("note_off", note=note, velocity=0, time=0)))

    events.sort(key=lambda x: x[0])

    for tick, msg in events:
        msg.time = tick - last_tick
        track.append(msg)
        last_tick = tick

    mid.save(str(path))


def test_parse_single_note() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        midi_path = Path(tmp) / "test.mid"
        make_test_midi(midi_path, [(60, 80, 0, 480)])
        result = MidiParser.parse(midi_path)

        assert result.track_count == 1
        assert not result.is_multi_track
        assert len(result.events) == 1
        assert result.events[0].note == 60
        assert result.events[0].velocity == 80
        assert result.total_duration > 0


def test_parse_chord() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        midi_path = Path(tmp) / "chord.mid"
        make_test_midi(midi_path, [
            (60, 80, 0, 480),
            (64, 80, 0, 480),
            (67, 80, 0, 480),
        ])
        result = MidiParser.parse(midi_path)

        assert len(result.events) == 3
        assert MidiParser.detect_overlapping_notes(result.events)


def test_keymap_manager() -> None:
    km = KeymapManager()
    assert km.get_key(60) == "a"
    km.set_mapping(60, "k")
    assert km.get_key(60) == "k"
    km.remove_mapping(60)
    assert km.get_key(60) is None


def test_player_load_and_stop() -> None:
    km = KeymapManager()
    player = MidiPlayer(keymap_manager=km)

    with tempfile.TemporaryDirectory() as tmp:
        midi_path = Path(tmp) / "test.mid"
        make_test_midi(midi_path, [(60, 80, 0, 480)])
        result = MidiParser.parse(midi_path)
        player.load(result)
        assert len(player._note_groups) == 1
        player.stop()
