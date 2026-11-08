"""The book-view application: which request gets which page, file or redirect.

The library is scanned afresh for every request, and only what the scan found
can be served (see scan.py), plus the viewer's own static files. The chosen
palette lives in a cookie, so it applies on every page and survives restarts.
"""

from __future__ import annotations

import mimetypes
from collections.abc import Callable
from pathlib import Path

from book_companion.view import assets, pages
from book_companion.view.layout import PALETTE_PATH, Page, document
from book_companion.view.scan import Library, link_path, scan
from book_companion.view.themes import find_palette, palette_or_default
from book_companion.view.web import (
    Request,
    Response,
    html_response,
    local_path,
    redirect,
    set_cookie,
)

PALETTE_COOKIE = "book-view-palette"
COOKIE_MAX_AGE = 10 * 365 * 24 * 3600

Route = Callable[[], Page | Response]


class App:
    def __init__(self, root: Path) -> None:
        self.root = root

    def handle(self, request: Request) -> Response:
        if request.method == "POST" and request.path == PALETTE_PATH:
            return self._choose_palette(request)
        if request.method != "GET":
            return self._error(request, 405, "This address only supports viewing.")
        if (asset := assets.load(request.path)) is not None:
            body, content_type = asset
            return Response(200, body, content_type)

        table = routes(scan(self.root))
        if (route := table.get(request.path)) is not None:
            result = route()
            return result if isinstance(result, Response) else self._render(request, result)
        if not request.path.endswith("/") and request.path + "/" in table:
            return redirect(request.path + "/", status=301)
        return self._error(request, 404, "Nothing in the library matches this address.")

    def internal_error(self, request: Request, error: Exception) -> Response:
        """The page for a request that failed; the server keeps running."""
        return self._error(request, 500, f"{type(error).__name__}: {error}")

    def _choose_palette(self, request: Request) -> Response:
        palette = find_palette(request.form.get("palette"))
        if palette is None:
            return self._error(request, 400, "Unknown palette.")
        return redirect(local_path(request.form.get("next")),
                        headers=(set_cookie(PALETTE_COOKIE, palette.key, COOKIE_MAX_AGE),))

    def _render(self, request: Request, page: Page, status: int = 200) -> Response:
        palette = palette_or_default(request.cookies.get(PALETTE_COOKIE))
        # After a POST, the picker returns to the home page rather than to the form's URL.
        path = request.path if request.method == "GET" else "/"
        return html_response(document(page, palette, path), status)

    def _error(self, request: Request, status: int, message: str) -> Response:
        return self._render(request, pages.error_page(status, message), status)


def routes(library: Library) -> dict[str, Route]:
    """Every library URL path the viewer answers, each with what renders it."""
    root = library.root
    table: dict[str, Route] = {"/": lambda: pages.index_page(library)}
    for series in library.series:
        table[link_path(root, series.path, directory=True)] = _bind(
            pages.series_page, library, series)
        if series.note is not None:
            table[link_path(root, series.note)] = _bind(
                pages.note_page, library, series, None, series.note)
        for volume in series.volumes:
            for note in volume.notes:
                table[link_path(root, note)] = _bind(
                    pages.note_page, library, series, volume, note)
        for entity in series.entities:
            table[link_path(root, entity.path, directory=True)] = _bind(
                pages.entity_page, library, series, entity)
            for image in entity.images:
                table[link_path(root, image.path)] = _bind(_file, image.path)
    return table


def _bind[**P](render: Callable[P, Page | Response], *args: P.args,
               **kwargs: P.kwargs) -> Route:
    """A route that calls `render` with these arguments, bound now (not when called)."""
    return lambda: render(*args, **kwargs)


def _file(path: Path) -> Response:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return Response(200, path.read_bytes(), content_type)
