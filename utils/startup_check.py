"""启动自检模块"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List

from core.keymap_manager import KeymapManager
from utils.paths import ensure_resource_dir, get_resource_dir


@dataclass
class CheckResult:
    """单项检查结果"""
    name: str
    ok: bool
    message: str
    auto_fixed: bool = False


@dataclass
class StartupReport:
    """启动自检报告"""
    ok: bool
    items: List[CheckResult] = field(default_factory=list)
    details: List[str] = field(default_factory=list)

    def add(self, item: CheckResult) -> None:
        self.items.append(item)
        if not item.ok:
            self.ok = False
        status = "通过" if item.ok else "失败"
        fix_info = "（已自动修复）" if item.auto_fixed else ""
        self.details.append(f"[{status}] {item.name}: {item.message}{fix_info}")


def check_resources_directory() -> CheckResult:
    """检查资源目录是否存在"""
    try:
        path = ensure_resource_dir()
        return CheckResult(
            name="资源目录",
            ok=True,
            message=f"资源目录已就绪：{path}",
            auto_fixed=True,
        )
    except Exception as e:
        return CheckResult(
            name="资源目录",
            ok=False,
            message=f"无法创建资源目录：{e}",
        )


def check_keymap_file() -> CheckResult:
    """检查键位配置文件"""
    keymap_path = get_resource_dir() / "keymap.json"

    # 文件存在但损坏
    if keymap_path.exists():
        try:
            with open(keymap_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("配置文件格式不正确")
            # 空配置则恢复默认
            if not data:
                raise ValueError("键位配置为空")
            return CheckResult(
                name="键位配置",
                ok=True,
                message=f"已加载 {len(data)} 条键位映射",
            )
        except Exception as e:
            try:
                KeymapManager(save_path=keymap_path).load_default()
                KeymapManager(save_path=keymap_path).save_to_file()
                return CheckResult(
                    name="键位配置",
                    ok=True,
                    message=f"配置文件损坏或无效（{e}），已恢复默认",
                    auto_fixed=True,
                )
            except Exception as save_err:
                return CheckResult(
                    name="键位配置",
                    ok=False,
                    message=f"配置文件损坏且无法恢复：{save_err}",
                )

    # 文件不存在，创建默认
    try:
        manager = KeymapManager(save_path=keymap_path)
        manager.save_to_file()
        return CheckResult(
            name="键位配置",
            ok=True,
            message="键位配置文件不存在，已创建默认配置",
            auto_fixed=True,
        )
    except Exception as e:
        return CheckResult(
            name="键位配置",
            ok=False,
            message=f"无法创建默认键位配置：{e}",
        )


def check_write_permission() -> CheckResult:
    """检查程序目录是否有写入权限"""
    test_file = get_resource_dir() / ".write_test"
    try:
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return CheckResult(
            name="写入权限",
            ok=True,
            message="程序目录可写入",
        )
    except Exception as e:
        return CheckResult(
            name="写入权限",
            ok=False,
            message=f"程序目录无法写入，键位设置可能无法保存：{e}",
        )


def run_startup_check() -> StartupReport:
    """运行完整的启动自检"""
    report = StartupReport(ok=True)
    report.add(check_resources_directory())
    report.add(check_keymap_file())
    report.add(check_write_permission())
    return report
