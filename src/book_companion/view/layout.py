"""The frame every page shares: document head, breadcrumbs and the palette picker.

Pages (pages.py) only describe their content as a `Page`; this module turns a
page into a full HTML document for the palette the viewer has chosen.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from book_companion.view import assets
from book_companion.view.themes import PALETTES, Palette

PALETTE_PATH = "/palette"  # the picker posts here (fields: palette, next)


@dataclass(frozen=True)
class Crumb:
    label: str
    url: str | None = None  # percent-encoded; None for the current page


@dataclass(frozen=True)
class Page:
    title: str
    crumbs: tuple[Crumb, ...]
    body: str  # HTML


def document(page: Page, palette: Palette, path: str) -> str:
    """The HTML document for a page; `path` is where the picker returns to."""
    return f"""<!doctype html>
<html lang="en" data-palette="{escape(palette.key)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(page.title)}</title>
<link rel="icon" href="{assets.url("icon.svg")}" type="image/svg+xml">
<link rel="stylesheet" href="{assets.url("style.css")}">
<style>
{palette.css()}
</style>
</head>
<body>
<main>
<header class="top">{_crumbs(page.crumbs)}{_picker(palette, path)}</header>
{page.body}
</main>
</body>
</html>
"""


def _crumbs(crumbs: tuple[Crumb, ...]) -> str:
    trail = " › ".join(
        f'<a href="{escape(crumb.url)}">{escape(crumb.label)}</a>' if crumb.url
        else escape(crumb.label)
        for crumb in crumbs)
    return f'<nav class="crumbs">{trail}</nav>'


def _picker(current: Palette, path: str) -> str:
    """A quiet text menu (a <details> disclosure, no script) listing the palettes."""
    options = "".join(
        f'<button type="submit" name="palette" value="{escape(palette.key)}" '
        f'aria-pressed="{"true" if palette.key == current.key else "false"}">'
        f"{escape(palette.name)}</button>"
        for palette in PALETTES)
    return (f'<details class="palette-menu"><summary>Palette: {escape(current.name)}</summary>'
            f'<form method="post" action="{PALETTE_PATH}" aria-label="Color palette">'
            f'<input type="hidden" name="next" value="{escape(path)}">{options}</form></details>')
