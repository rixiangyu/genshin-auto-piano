# 原神自动弹琴 — MCP 使用教程

本程序内嵌 MCP（Model Context Protocol）服务器，可被 OpenClaw、Claude Desktop 等 AI 客户端控制，实现**对话式**导入 MIDI、播放、暂停、调速等操作。无需任何额外的 EXE 文件。

---

## 一、前提条件

1. 主程序「原神自动弹琴.exe」已启动并保持运行
2. MCP 开关已启用（默认启用）
3. 接口仅监听本机回环地址 `127.0.0.1`，外部网络无法访问，安全无需担心

## 二、开启 / 关闭 MCP

1. 在主界面点击 **「MCP 协议」** 按钮
2. 进入 MCP 设置界面后：
   - 勾选/取消 **「启用 MCP 控制」** 即可开关，立即生效并自动保存
   - 界面上会显示当前状态和实际端口（默认 `8765`，若被占用会依次尝试 8766~8785）
   - 界面还提供可直接复制的 OpenClaw 配置 JSON

开关状态保存在 `resources/settings.json`（字段 `mcp_enabled`），下次启动自动恢复。

## 三、接入 OpenClaw

### 方式 1：配置 MCP 服务器（推荐）

在 OpenClaw 的 MCP 配置（通常是 `~/.openclaw/openclaw.json` 或设置界面的 MCP 页面）中加入：

```json
{
  "mcpServers": {
    "genshin-piano": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

> 端口以 MCP 设置界面显示的实际端口为准。

配置后重启 OpenClaw，即可通过对话调用工具，例如：

- 「用原神弹琴程序播放 D:\曲库\卡农.mid」
- 「暂停弹琴」
- 「速度调到 0.8」
- 「现在弹到哪了？」

### 方式 2：安装 Skill 文件（可选，配合方式 1）

项目目录 `skills/genshin-piano/` 提供了现成的 Skill 文件。将其整个文件夹复制到 OpenClaw 的 skills 目录（通常为 `C:\Users\<用户名>\.openclaw\skills\`），OpenClaw 即可自动理解何时、如何操作本程序。

## 四、可用工具（9 个）

| 工具 | 参数 | 说明 |
|---|---|---|
| `import_midi` | `path`（绝对路径）、`auto_adapt`（可选，默认 true） | 导入 MIDI 文件，导入后才能播放/试听。若部分音符超出琴键音域，默认自动适配（八度移位/黑键就近），返回不适配音符数量与占比；`auto_adapt: false` 可关闭适配 |
| `play` | — | 开始模拟键盘播放（自动停止试听） |
| `pause` | — | 暂停播放或试听 |
| `resume` | — | 继续已暂停的播放 |
| `stop` | — | 停止播放和试听，进度归零 |
| `toggle_preview` | — | 切换试听（不模拟按键，仅提示音预览） |
| `set_speed` | `speed`（0.1~5.0） | 调整播放速度，1.0 为原速 |
| `get_status` | — | 查询文件、状态、进度、速度、适配统计、MCP 信息 |
| `show_floating` | `show`（true/false） | 显示/隐藏悬浮窗 |

> 提示：在主程序界面手动导入 MIDI 时，若有音符无法直接映射到琴键，会弹出「音域适配」对话框询问是否启用自动适配；主界面信息栏会显示不适配音符的数量与占比。MCP 导入不弹窗，默认启用适配。

## 五、直接 HTTP API（备用）

不配置 MCP 也可以直接调用简单 HTTP 接口：

### 探测服务是否在线

```
GET http://127.0.0.1:8765/ping
```

### 执行操作

```
POST http://127.0.0.1:8765/action
Content-Type: application/json

{"action": "import_midi", "params": {"path": "D:\\曲库\\卡农.mid"}}
```

支持的 `action`：`import_midi` / `play` / `pause` / `resume` / `stop` / `toggle_preview` / `set_speed` / `get_status` / `show_floating`

### curl 示例（PowerShell）

```powershell
# 导入
curl.exe -X POST http://127.0.0.1:8765/action -H "Content-Type: application/json" -d '{\"action\":\"import_midi\",\"params\":{\"path\":\"D:\\曲库\\卡农.mid\"}}'

# 播放
curl.exe -X POST http://127.0.0.1:8765/action -H "Content-Type: application/json" -d '{\"action\":\"play\",\"params\":{}}'

# 查询状态
curl.exe -X POST http://127.0.0.1:8765/action -H "Content-Type: application/json" -d '{\"action\":\"get_status\",\"params\":{}}'
```

### MCP 端点（JSON-RPC 2.0）

```
POST http://127.0.0.1:8765/mcp
Content-Type: application/json

{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
```

支持方法：`initialize` / `ping` / `tools/list` / `tools/call`。

## 六、故障排除

| 问题 | 解决方法 |
|---|---|
| AI 客户端连接失败 | 确认主程序已运行、MCP 开关已启用；检查端口是否一致 |
| 端口不是 8765 | 8765 被占用时自动切换，以 MCP 设置界面显示为准 |
| 工具调用返回错误 | 看返回文本，例如"尚未导入 MIDI 文件"表示需要先调用 `import_midi` |
| 播放无按键输出 | 与 MCP 无关，参考主程序《使用教程》第 8 节（管理员权限） |

## 七、安全说明

- 接口仅绑定 `127.0.0.1`，局域网/互联网均无法访问
- 不需要任何密钥或账户
- 关闭 MCP 开关后，所有外部接口立即失效
