"""内嵌控制服务器：监听 127.0.0.1，为 MCP 服务器等外部程序提供本地控制 API

安全设计：
- 仅绑定回环地址 127.0.0.1，外部网络无法访问
- 所有 GUI 操作通过 Qt 信号派发到主线程执行，线程安全
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

import core.mcp_protocol as mcp_protocol

PORT_RANGE = range(8765, 8786)


class _Invoker(QObject):
    """把回调派发到 GUI 线程执行（信号跨线程自动为队列连接）"""

    _sig = Signal(object)

    def __init__(self):
        super().__init__()
        self._sig.connect(self._run)

    @staticmethod
    def _run(fn: Callable[[], None]) -> None:
        fn()

    def post(self, fn: Callable[[], None]) -> None:
        self._sig.emit(fn)


class ControlServer:
    """主程序内嵌的本地控制 API"""

    def __init__(self, action_handler: Callable[[str, Dict[str, Any]], Any]):
        """
        :param action_handler: 在 GUI 线程执行的处理器 (action, params) -> result
        """
        self._handler = action_handler
        self._invoker = _Invoker()
        self._server: Optional[ThreadingHTTPServer] = None
        self._port: Optional[int] = None
        self._lock = threading.Lock()

    @property
    def port(self) -> Optional[int]:
        return self._port

    def start(self) -> Optional[int]:
        """启动服务器，返回实际端口；失败返回 None"""
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, code: int, payload: dict) -> None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):  # noqa: N802
                if self.path == "/ping":
                    self._send_json(200, {"ok": True, "service": "genshin-piano"})
                elif self.path == "/mcp":
                    # Streamable HTTP：无状态服务器不支持 GET（SSE 流）
                    self._send_json(
                        405,
                        {"jsonrpc": "2.0", "id": None,
                         "error": {"code": -32000, "message": "SSE not supported"}},
                    )
                else:
                    self._send_json(404, {"ok": False, "error": "not found"})

            def do_POST(self):  # noqa: N802
                if self.path == "/mcp":
                    self._handle_mcp()
                    return
                if self.path != "/action":
                    self._send_json(404, {"ok": False, "error": "not found"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                except Exception:
                    self._send_json(400, {"ok": False, "error": "请求体不是合法 JSON"})
                    return

                action = body.get("action", "")
                params = body.get("params", {}) or {}
                if not isinstance(action, str) or not action:
                    self._send_json(400, {"ok": False, "error": "缺少 action 字段"})
                    return

                ok, result = outer._dispatch(action, params)
                if ok:
                    self._send_json(200, {"ok": True, "result": result})
                else:
                    self._send_json(200, {"ok": False, "error": str(result)})

            def do_DELETE(self):  # noqa: N802
                # Streamable HTTP 会话终止；无状态实现直接确认
                if self.path == "/mcp":
                    self._send_json(200, {})
                else:
                    self._send_json(404, {"ok": False, "error": "not found"})

            def _handle_mcp(self) -> None:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(length)
                    parsed = json.loads(raw.decode("utf-8")) if raw else None
                except Exception:
                    self._send_json(
                        400,
                        {"jsonrpc": "2.0", "id": None,
                         "error": {"code": -32700, "message": "Parse error"}},
                    )
                    return
                if parsed is None:
                    self._send_json(
                        400,
                        {"jsonrpc": "2.0", "id": None,
                         "error": {"code": -32700, "message": "Parse error"}},
                    )
                    return

                try:
                    status, payload = mcp_protocol.process_body(parsed, outer._dispatch)
                except Exception as e:  # noqa: BLE001
                    status, payload = 200, {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32603, "message": f"Internal error: {e}"},
                    }
                self._send_json(status, payload)

            def log_message(self, *args):  # 静默访问日志
                pass

        for port in PORT_RANGE:
            try:
                server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
                server.daemon_threads = True
                break
            except OSError:
                continue
        else:
            return None

        self._server = server
        self._port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return self._port

    def _dispatch(self, action: str, params: Dict[str, Any]) -> Tuple[bool, Any]:
        """在 GUI 线程执行 action，返回 (成功?, 结果或错误信息)"""
        box: Dict[str, Any] = {}
        done = threading.Event()

        def task():
            try:
                box["result"] = self._handler(action, params)
            except Exception as e:  # noqa: BLE001
                box["error"] = str(e) or type(e).__name__
            finally:
                done.set()

        self._invoker.post(task)
        if not done.wait(timeout=15):
            return False, "等待主程序响应超时"
        if "error" in box:
            return False, box["error"]
        return True, box["result"]

    def shutdown(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            threading.Thread(target=server.shutdown, daemon=True).start()
