"""book-view: browse the library's notes and images in a web browser.

A small local web server renders each page when it is requested, so new images
and edited notes show up on reload. It serves only what the library scan found
(entity notes and pictures, book notes, series notes); never book text, EPUBs or
anything outside the library. Memory notes for books past the recorded reading
progress are hidden behind a click-through spoiler warning.

Modules: scan (what the library holds), pages and layout (HTML), themes (color
palettes), assets (static files), app (routing), web (request and response
types), server (http.server adapter), and this command line.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from book_companion.core.cli import utf8_streams
from book_companion.core.errors import BookError
from book_companion.view.app import App
from book_companion.view.server import HOST, make_server

DEFAULT_PORT = 8765


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
            server = make_server(App(root), args.port)
        except OSError as exc:
            raise BookError(f"Could not serve on port {args.port}: {exc.strerror or exc}. "
                            "Choose another with --port.") from exc
    except BookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    url = f"http://{HOST}:{server.server_port}/"
    print(f"Serving {root} at {url}  (Ctrl+C to stop)", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    with server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopped.")
    return 0
