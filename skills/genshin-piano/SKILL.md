---
name: genshin-piano
description: 控制本机运行的「原神自动弹琴」程序：导入 MIDI 文件、开始/暂停/停止自动演奏、切换试听、调整播放速度、查询播放状态、显示或隐藏悬浮窗。当用户想自动弹琴、播放 MIDI 曲子、控制弹琴进度或速度时使用本技能。
---

# 原神自动弹琴控制

控制本机运行的「原神自动弹琴」桌面程序（模拟键盘在原神等游戏中自动演奏 MIDI）。

## 前提检查

主程序必须已启动且 MCP 开关已启用。先调用 `get_status` 确认在线：

- 如果已配置 `genshin-piano` MCP 服务器，直接调用其 `get_status` 工具
- 否则用命令行探测（端口 8765，占用时依次为 8766~8785）：
  `curl.exe http://127.0.0.1:8765/ping`
- 全部无响应时，告知用户：「请先启动『原神自动弹琴』主程序，并在主界面『MCP 协议』中确认开关已启用」

## 调用方式

优先使用 MCP 工具（若 `genshin-piano` 服务器已连接）；未连接 MCP 时，直接 HTTP 调用：

```
POST http://127.0.0.1:8765/action
Content-Type: application/json
{"action": "<动作名>", "params": { ... }}
```

## 可用动作

| 动作 | 参数 | 说明 |
|---|---|---|
| `get_status` | 无 | 查询当前文件、播放状态、进度、速度 |
| `import_midi` | `path`: MIDI 绝对路径；`auto_adapt`（可选，默认 true）: 是否启用音域自动适配 | 导入 MIDI（播放前必须先导入）。部分音符超出琴键音域时默认自动适配（八度移位/黑键就近），返回值含不适配音符数量与占比 |
| `play` | 无 | 开始模拟键盘播放 |
| `pause` | 无 | 暂停 |
| `resume` | 无 | 继续播放 |
| `stop` | 无 | 停止并归零 |
| `toggle_preview` | 无 | 切换试听（不模拟按键，仅提示音） |
| `set_speed` | `speed`: 0.1~5.0 | 调整速度，1.0 为原速 |
| `show_floating` | `show`: true/false | 显示/隐藏悬浮窗 |

## 典型流程

1. **播放一首曲子**：`import_midi`(path) → `play`
2. **用户问进度**：`get_status`，读 `progress` / `duration` / `player_state` 字段
3. **用户说太快了**：`set_speed`(speed=0.8)
4. **先听听效果再上游戏**：`import_midi` → `toggle_preview`，满意后 `stop` → `play`

## 注意事项

- 播放（`play`）会真实模拟键盘按键，确保用户已在目标窗口（如原神弹琴界面）
- 返回 JSON 中 `ok: false` 时，`error` 字段是失败原因，原样转述给用户
- 不要连续快速调用 `play`/`stop`，状态切换以 `get_status` 结果为准
