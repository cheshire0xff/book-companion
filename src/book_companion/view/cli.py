"""book-view: browse the library's notes and images in a web browser.

A small local web server renders each page when it is requested, so new images
and edited notes show up on reload. It serves only what the library scan found
(entity notes and pictures, book notes, series notes); never book text, EPUBs or
anything outside the library. Memory notes for books past the recorded reading
progress are hidden behind a click-through spoiler warning.
"""

from __future__ import annotations

import argparse
import mimetypes
import socketserver
import sys
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from book_companion.core.cli import utf8_streams
from book_companion.core.errors import BookError
from book_companion.view import pages
from book_companion.view.scan import Library, link_path, scan

DEFAULT_PORT = 8765


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str
    body: bytes
    location: str | None = None


def _html(text: str, status: int = 200) -> Response:
    return Response(status, "text/html; charset=utf-8", text.encode("utf-8"))


def _file(path: Path) -> Response:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return Response(200, content_type, path.read_bytes())


def _page(render: Callable[..., str], *args: object) -> Callable[[], Response]:
    return lambda: _html(render(*args))


def routes(library: Library) -> dict[str, Callable[[], Response]]:
    """Every URL path the viewer answers, each with the function that renders it."""
    root = library.root
    table = {"/": _page(pages.index_page, library)}
    for series in library.series:
        table[link_path(root, series.path, directory=True)] = _page(
            pages.series_page, library, series)
        if series.note is not None:
            table[link_path(root, series.note)] = _page(
                pages.note_page, library, series, None, series.note)
        for volume in series.volumes:
            for note in volume.notes:
                table[link_path(root, note)] = _page(
                    pages.note_page, library, series, volume, note)
        for entity in series.entities:
            table[link_path(root, entity.path, directory=True)] = _page(
                pages.entity_page, library, series, entity)
            for image in entity.images:
                table[link_path(root, image.path)] = partial(_file, image.path)
    return table


def respond(root: Path, url: str) -> Response:
    """The response for one GET request; the library is scanned afresh each time."""
    path = unquote(urlsplit(url).path)
    table = routes(scan(root))
    if (route := table.get(path)) is not None:
        return route()
    if not path.endswith("/") and path + "/" in table:
        return Response(301, "text/plain; charset=utf-8", b"", location=quote(path + "/"))
    return _html(pages.error_page(404, "Nothing in the library matches this address."), 404)


class _Server(ThreadingHTTPServer):
    # On Windows, SO_REUSEADDR would let a second server take a port already in use.
    allow_reuse_address = sys.platform != "win32"

    def server_bind(self) -> None:
        # HTTPServer.server_bind looks up the host's FQDN, which can stall for seconds.
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


def make_server(root: Path, port: int) -> ThreadingHTTPServer:
    """A server for the library on 127.0.0.1 (port 0 picks a free port)."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (the name http.server calls)
            try:
                response = respond(root, self.path)
            except Exception as exc:  # show the problem in the browser, keep serving
                message = f"{type(exc).__name__}: {exc}"
                response = _html(pages.error_page(500, message), 500)
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.send_header("Cache-Control", "no-cache")
            if response.location is not None:
                self.send_header("Location", response.location)
            self.end_headers()
            try:
                self.wfile.write(response.body)
            except ConnectionError:
                pass  # the browser went away (e.g. navigated during a large image)

        def log_message(self, format: str, *args: Any) -> None:
            pass  # keep the terminal quiet; errors are shown in the browser

    return _Server(("127.0.0.1", port), Handler)


def _port(value: str) -> int:
    if not value.isdigit() or not 0 <= int(value) <= 65535:
        raise argparse.ArgumentTypeError(f"expected a port number 0-65535, got {value!r}")
    return int(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="book-view",
        description="Browse the library's entity notes, images and book notes in your web "
                    "browser. Pages are served on this computer only (127.0.0.1) and reflect "
                    "the files on each reload. Press Ctrl+C to stop.")
    parser.add_argument("library", type=Path, nargs="?", default=Path("."),
                        help="the library folder, the one that holds books/ "
                             "(default: the current folder)")
    parser.add_argument("--port", type=_port, default=DEFAULT_PORT,
                        help=f"port to serve on (default: {DEFAULT_PORT}; 0 picks a free one)")
    parser.add_argument("--no-browser", action="store_true",
                        help="only print the address; don't open a browser")
    return parser


def main(argv: list[str] | None = None) -> int:
    utf8_streams()
    args = build_parser().parse_args(argv)
    root = args.library.resolve()
    try:
        if not (root / "books").is_dir():
            raise BookError(f"{root} has no books/ folder. Run book-view in your library "
                            "folder, or pass the library's path.")
        try:
            server = make_server(root, args.port)
        except OSError as exc:
            raise BookError(f"Could not serve on port {args.port}: {exc.strerror or exc}. "
                            "Choose another with --port.") from exc
    except BookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Serving {root} at {url}  (Ctrl+C to stop)", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    with server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopped.")
    return 0
