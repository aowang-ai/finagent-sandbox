"""stdlib HTTP server wrapping AmaHttpShim at POST /trading_action/."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from adapters.ama.adapter import AmaHttpShim
from adapters.base import AgentAdapter


class AmaHttpServer:
    def __init__(self, agent: AgentAdapter, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.shim = AmaHttpShim(agent)
        self.host = host
        self.port = port
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.calls = 0
        self.last_error: str | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/trading_action/"

    def start(self) -> str:
        shim = self.shim
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
                return

            def _send(self, code: int, payload: dict[str, Any]) -> None:
                blob = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(blob)))
                self.end_headers()
                self.wfile.write(blob)

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path in {"/", "/health", "/healthz"}:
                    self._send(200, {"ok": True, "calls": server.calls})
                    return
                self._send(404, {"error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path.rstrip("/") != "/trading_action":
                    self._send(404, {"error": "not found"})
                    return
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                    if not isinstance(payload, dict):
                        raise ValueError("body must be an object")
                    result = shim.handle(payload)
                    server.calls += 1
                    self._send(200, result)
                except Exception as exc:  # noqa: BLE001
                    server.last_error = str(exc)
                    self._send(500, {"error": str(exc), "recommended_action": "HOLD", "reasoning": "server error"})

        try:
            self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        except OSError as exc:
            # Bind is glue, not protocol. Port 8765 is often taken by other workspace servers.
            if getattr(exc, "errno", None) not in {98, 48} and "Address already in use" not in str(exc):
                raise
            self._httpd = ThreadingHTTPServer((self.host, 0), Handler)
            self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
