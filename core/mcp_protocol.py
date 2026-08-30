"""MCP（Model Context Protocol）协议逻辑

主程序内嵌 MCP 服务器（Streamable HTTP 传输），OpenClaw 等 AI 客户端
可通过 http://127.0.0.1:8765/mcp 直接连接，无需独立 EXE。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

SERVER_NAME = "genshin-auto-piano-mcp"
SERVER_VERSION = "1.1.0"
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")

Dispatch = Callable[[str, Dict[str, Any]], Tuple[bool, Any]]

# ---------------- 工具定义（MCP tools） ----------------

TOOLS = [
    {
        "name": "get_status",
        "description": "获取主程序当前状态：已导入的 MIDI 文件、音符数、时长、播放状态、进度、速度、悬浮窗可见性。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "import_midi",
        "description": (
            "导入 MIDI 文件到主程序（绝对路径，.mid/.midi）。导入成功后才能播放或试听。"
            "若部分音符超出琴键音域，默认自动启用适配（八度移位/黑键就近白键），"
            "返回值会给出不适配音符数量与占比；可通过 auto_adapt=false 关闭适配。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "MIDI 文件绝对路径"},
                "auto_adapt": {"type": "boolean", "description": "是否启用音域自动适配（默认 true）"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "play",
        "description": "开始模拟键盘播放已导入的 MIDI（需先 import_midi）。播放前会自动停止试听。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "pause",
        "description": "暂停正在进行的播放或试听。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "resume",
        "description": "继续已暂停的播放。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "stop",
        "description": "停止播放和试听，进度归零。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "toggle_preview",
        "description": "切换试听（不模拟按键，仅用提示音预览 MIDI）。再次调用可暂停/继续。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "set_speed",
        "description": "设置播放速度，1.0 为原速，0.5 为慢速，2.0 为两倍速（范围 0.1~5.0）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "speed": {"type": "number", "description": "播放速度倍率"},
            },
            "required": ["speed"],
        },
    },
    {
        "name": "show_floating",
        "description": "显示或隐藏置顶控制悬浮窗。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "show": {"type": "boolean", "description": "true 显示，false 隐藏"},
            },
            "required": ["show"],
        },
    },
]

# ---------------- 工具调用 → 主程序 action 映射 ----------------


def _tool_result(ok: bool, result: Any) -> dict:
    """构造 MCP CallToolResult"""
    if isinstance(result, (dict, list)):
        text = _dumps(result)
    else:
        text = str(result)
    return {
        "content": [{"type": "text", "text": text}],
        "isError": not ok,
    }


def _dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2)


def _handle_tool_call(params: dict, dispatch: Dispatch) -> dict:
    name = params.get("name", "")
    arguments = params.get("arguments") or {}

    if name == "set_speed":
        try:
            speed = float(arguments.get("speed"))
        except (TypeError, ValueError):
            return _tool_result(False, "speed 必须是数字")
        ok, result = dispatch("set_speed", {"speed": speed})
        return _tool_result(ok, result)

    if name == "import_midi":
        path = str(arguments.get("path", ""))
        auto_adapt = arguments.get("auto_adapt")
        if auto_adapt is not None and not isinstance(auto_adapt, bool):
            return _tool_result(False, "auto_adapt 必须是布尔值")
        ok, result = dispatch("import_midi", {"path": path, "auto_adapt": auto_adapt})
        return _tool_result(ok, result)

    mapping = {
        "get_status": ("get_status", {}),
        "play": ("play", {}),
        "pause": ("pause", {}),
        "resume": ("resume", {}),
        "stop": ("stop", {}),
        "toggle_preview": ("toggle_preview", {}),
        "show_floating": ("show_floating", {"show": bool(arguments.get("show", True))}),
    }
    if name not in mapping:
        return _tool_result(False, f"未知工具：{name}")

    action, fixed = mapping[name]
    ok, result = dispatch(action, fixed)
    return _tool_result(ok, result)


# ---------------- JSON-RPC 消息处理 ----------------


def handle_message(msg: dict, dispatch: Dispatch) -> Optional[dict]:
    """处理单条 JSON-RPC 消息；通知返回 None"""
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        version = params.get("protocolVersion", "")
        if version not in SUPPORTED_PROTOCOL_VERSIONS:
            version = "2025-06-18"
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        try:
            result = _handle_tool_call(params, dispatch)
        except Exception as e:  # noqa: BLE001
            result = _tool_result(False, f"工具执行异常：{e}")
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return None


def process_body(parsed: Any, dispatch: Dispatch) -> Tuple[int, Any]:
    """处理 HTTP POST 请求体（单个对象或批量数组），返回 (HTTP 状态码, 响应体)"""
    import json

    if isinstance(parsed, list):
        responses = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            resp = handle_message(item, dispatch)
            if resp is not None:
                responses.append(resp)
        if responses:
            return 200, responses
        return 202, {}

    if not isinstance(parsed, dict):
        return 400, {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Invalid Request"},
        }

    resp = handle_message(parsed, dispatch)
    if resp is None:  # 纯通知
        return 202, {}
    return 200, resp
