"""The local HTTP server: adapts http.server requests to the application."""

from __future__ import annotations

import socketserver
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from book_companion.view.app import App
from book_companion.view.web import Request, Response

HOST = "127.0.0.1"  # this computer only
MAX_BODY = 16 * 1024  # forms are tiny; refuse anything larger


class _Server(ThreadingHTTPServer):
    # On Windows, SO_REUSEADDR would let a second server take a port already in use.
    allow_reuse_address = sys.platform != "win32"

    def server_bind(self) -> None:
        # HTTPServer.server_bind looks up the host's FQDN, which can stall for seconds.
        socketserver.TCPServer.server_bind(self)
        self.server_name = HOST
        self.server_port = self.server_address[1]


def make_server(app: App, port: int) -> ThreadingHTTPServer:
    """A server for the application on 127.0.0.1 (port 0 picks a free port)."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (the name http.server calls)
            self._dispatch()

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch()

        def _dispatch(self) -> None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._send(Response(400, b"Bad Content-Length"))
                return
            if not 0 <= length <= MAX_BODY:
                self._send(Response(413, b"Request body too large"))
                return
            body = self.rfile.read(length) if length else b""
            request = Request.parse(self.command, self.path, self.headers.get("Cookie"), body)
            try:
                response = app.handle(request)
            except Exception as exc:  # show the problem in the browser, keep serving
                response = app.internal_error(request, exc)
            self._send(response)

        def _send(self, response: Response) -> None:
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.send_header("Cache-Control", "no-cache")
            for name, value in response.headers:
                self.send_header(name, value)
            self.end_headers()
            try:
                self.wfile.write(response.body)
            except ConnectionError:
                pass  # the browser went away (e.g. navigated during a large image)

        def log_message(self, format: str, *args: Any) -> None:
            pass  # keep the terminal quiet; errors are shown in the browser

    return _Server((HOST, port), Handler)
