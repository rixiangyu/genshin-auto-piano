"""启动自检模块测试"""
from __future__ import annotations

from utils.startup_check import run_startup_check


def test_startup_check_passes() -> None:
    report = run_startup_check()
    assert len(report.items) >= 3
    assert report.items[0].ok
    assert report.items[2].ok
