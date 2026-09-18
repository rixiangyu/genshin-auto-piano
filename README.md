##该应用由AI进行开发，我使用了Trae作为工具


# 原神自动弹琴（Genshin Auto Piano）

自动化弹奏《原神》风物之诗琴的 Windows 桌面工具。导入任意 MIDI 文件，程序自动将音符转换为琴键并模拟键盘演奏，支持长音还原、和弦、变速播放与 AI（MCP 协议）控制。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

## 功能特性

- **MIDI 导入与解析**：多轨合并、变速曲（tempo change）精确换算、音符时长还原、和弦检测
- **音域自动适配**：MIDI 音域超出原神 21 键范围时，自动八度移位 + 黑键就近白键，导入时弹窗询问是否启用，主界面实时显示不适配音符数量与占比
- **长音还原**：按键按住实际音符时长（而非固定点按），长音持续、断奏短促
- **试听预览**：不弹键盘、扬声器合成音预览整首曲子
- **MIDI 深度分析**：音符分布、时长/间隔统计、和弦构成、适配明细表格
- **播放控制**：播放/暂停/停止、0.25x~2.0x 变速、进度与当前音符（简谱）显示
- **悬浮窗 + 全局热键**：游戏内免切窗口控制（F8 播放/暂停，ESC 停止）
- **键位自定义**：简谱 ↔ 按键可视编辑，持久化保存
- **MCP 协议服务**：内嵌标准 MCP 服务器（`http://127.0.0.1:8765/mcp`），OpenClaw 等 AI 客户端可远程控制播放

## 下载使用

从 [Releases](../../releases) 页面下载 `原神自动弹琴.exe`（单文件，约 47MB，内置全部依赖，无需安装 Python）。

1. 将 EXE 放到任意**可写**文件夹（如桌面），双击运行
2. 允许 UAC 管理员授权（模拟键盘必需；若原神以管理员运行，本程序也必须管理员权限，否则按键无效）
3. 导入 MIDI 文件 → 若提示音域不适配，按需选择是否自动适配
4. 打开原神进入弹琴界面 → 点击「播放」（或按 F8）

> Windows SmartScreen 可能提示"未知发布者"，点"更多信息 → 仍要运行"即可。

## 从源码运行

```bash
git clone https://github.com/jiuchun2026/genshin-auto-piano.git
cd genshin-auto-piano
pip install -r requirements.txt   # PySide6, mido, pynput
python main.py                    # 需管理员权限
```

## MCP 协议接入（AI 客户端）

程序运行后自动在 `http://127.0.0.1:8765/mcp`（端口冲突时顺延至 8785）提供 MCP 服务，支持 9 个工具：

`get_status` / `import_midi`（`path`, `auto_adapt`）/ `play` / `pause` / `resume` / `stop` / `toggle_preview` / `set_speed`（0.1~5.0）/ `show_floating`

接入配置（OpenClaw / Claude 等 MCP 客户端）：

```json
{
  "mcpServers": {
    "genshin-piano": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

示例对话："导入 D:\music\花之舞.mid 并开始播放" → AI 自动调用 `import_midi` + `play`。

## 项目结构

```
├── main.py               程序入口
├── core/                 核心层（无 UI 依赖，可独立测试）
│   ├── midi_parser.py      MIDI 解析：多轨合并 / tempo map / 音符配对
│   ├── keymap_manager.py   键位映射：简谱互转 / 四级适配算法
│   ├── player.py           播放引擎：最小堆释放调度 / 暂停时间轴冻结
│   ├── preview_player.py   试听：正弦波合成
│   ├── midi_analyzer.py    深度分析报告
│   ├── control_server.py   内嵌 HTTP 服务器（Qt 信号派发回主线程）
│   └── mcp_protocol.py     MCP / JSON-RPC 2.0 协议
├── ui/                   界面层（PySide6）
├── utils/                锥盘模拟（Win32 SendInput+扫描码）/ 热键 / 路径 / 自检
└── tests/                单元测试
```

详细架构说明见 [代码结构详解.md](代码结构详解.md)。

## 技术要点

- **键盘模拟**：ctypes 直调 Win32 `SendInput`，携带 `KEYEVENTF_SCANCODE` 硬件扫描码（原神 RawInput 只认扫描码），固定美式映射表规避输入法干扰
- **零漂移播放**：`perf_counter` 高精度计时 + 2ms 粒度等待，解析层预计算全部时间数据，播放线程只做查表与定时
- **释放堆 + 序号校验**：同一按键快速重复时旧释放计划自动失效，杜绝误释放与卡键
- **线程模型**：GUI 主线程 / 播放线程 / HTTP 线程池严格隔离，跨线程一律经 Qt 信号队列

## 常见问题

| 问题 | 解决 |
|---|---|
| 游戏里没反应 | 确认程序与原神都以管理员运行 |
| 按键错乱 | 输入法切到英文模式；检查键位设置 |
| 部分音符不响 | 该音符超音域且未启用适配，导入时选"启用自动适配" |
| MCP 连不上 | 主界面「MCP 协议」确认开关已开；端口显示在日志区 |

## 免责声明

本工具仅模拟键盘输入，供个人娱乐与学习用途。使用产生的任何账号风险由使用者自行承担。

## License

MIT
