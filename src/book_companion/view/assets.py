"""The viewer's own files (stylesheet, icon), shipped in the package's static/ folder.

They are read on each request, so an edited stylesheet shows up on reload. Only
files that are in static/ can be served, by name; there is no path to traverse.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import PurePosixPath

PREFIX = "/static/"

# Explicit types: on Windows, mimetypes reads the registry, which can be wrong.
CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".js": "text/javascript; charset=utf-8",
    ".png": "image/png",
}


def url(name: str) -> str:
    return PREFIX + name


def load(path: str) -> tuple[bytes, str] | None:
    """The content and type of the asset at this URL path, if there is one."""
    if not path.startswith(PREFIX):
        return None
    name = path.removeprefix(PREFIX)
    content_type = CONTENT_TYPES.get(PurePosixPath(name).suffix)
    if content_type is None:
        return None
    for entry in files("book_companion.view").joinpath("static").iterdir():
        if entry.name == name and entry.is_file():
            return entry.read_bytes(), content_type
    return None
