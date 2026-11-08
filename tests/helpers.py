"""Synthetic Calibre-like books for the tests (no real book text)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

type Toc = list[tuple[str, str, Toc]]  # (label, src, children)
Builder = Callable[..., str]  # fixture: writes a book or series, returns its path
Capture = pytest.CaptureFixture[str]

XHTML = """<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head>
<body>{body}</body></html>"""


def progress(status: str, chapter: str = "", part: str = "", section: str = "",
             book: str = "") -> str:
    return (f"---\nbook: {book}\nstatus: {status}  # not started | reading | finished\n"
            f"chapter: {chapter}\npart: {part}\nsection: {section}\nupdated: 2026-11-08\n---\n\n"
            "# Reading progress\n\n- Status: this human line is ignored by the tool\n")


def make_book(book_dir: Path, title: str, files: list[tuple[str, str]], toc: Toc,
              progress_text: str | None = None) -> Path:
    """Write a Calibre-like book directory.

    files: (filename, body html) in spine order. toc: nested (label, src, children).
    """
    html = book_dir / "book-html"
    (html / "text").mkdir(parents=True)
    for name, body in files:
        (html / "text" / name).write_text(XHTML.format(body=body), encoding="utf-8")
    manifest = "\n".join(
        f'<item id="f{i}" href="text/{name}" media-type="application/xhtml+xml"/>'
        for i, (name, _) in enumerate(files))
    spine = "\n".join(f'<itemref idref="f{i}"/>' for i in range(len(files)))
    (html / "content.opf").write_text(f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title></metadata>
<manifest>{manifest}
<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest>
<spine toc="ncx">{spine}</spine></package>""", encoding="utf-8")

    def points(items: Toc) -> str:
        return "".join(
            f'<navPoint><navLabel><text>{label}</text></navLabel>'
            f'<content src="text/{src}"/>{points(children)}</navPoint>'
            for label, src, children in items)

    (html / "toc.ncx").write_text(f"""<?xml version='1.0' encoding='utf-8'?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<navMap>{points(toc)}</navMap></ncx>""", encoding="utf-8")
    if progress_text is not None:
        (book_dir / "reading-progress.md").write_text(progress_text, encoding="utf-8")
    return book_dir


# Sections: 1 Contents, 2 Ch1, 3 Ch2, 4 Interlude (nested in Ch2), 5 Ch3, 6 Ch4, 7 Ch5
FLAT_TOC: Toc = [
    ("Contents", "contents.xhtml", []),
    ("Chapter 1: Arrival", "c1.xhtml", []),
    ("Chapter 2: The Garden", "c2.xhtml", [("Interlude", "c2.xhtml#s2", [])]),
    ("Chapter 3: The Secret Betrayal", "c3.xhtml", []),
    ("Chapter 4: Aftermath", "c4.xhtml", []),
    ("Chapter 5: Ending", "c5.xhtml", []),
]
FLAT_FILES = [
    ("contents.xhtml", "".join(f"<p>{label}</p>" for label, _, _ in FLAT_TOC[1:])
     + "<p>Interlude</p>"),
    ("c1.xhtml", "<h1>Chapter 1</h1><p>Anaïs arrives at the gate.</p>"),
    ("c2.xhtml", "<h1>Chapter 2</h1><p>Valka’s tattoo is <i>very</i> fine.</p>"
                 '<p id="s2">Interlude text about the moon.</p>'),
    ("c2b.xhtml", "<p>Continuation of chapter two.</p>"),
    ("c3.xhtml", "<h1>Chapter 3</h1><p>Gilliam plans something.</p>"),
    ("c4.xhtml", "<p>Quiet days.</p>"),
    ("c5.xhtml", "<p>The final scene.</p>"),
]

PARTS_TOC: Toc = [
    ("Book One: Beginnings", "b1.xhtml", [
        ("Chapter One: Dawn", "b1c1.xhtml", []),
        ("Chapter Two: Noon", "b1c2.xhtml", []),
    ]),
    ("Book Two: Endings", "b2.xhtml", [
        ("Chapter One: Dusk", "b2c1.xhtml", []),
        ("Chapter Two: Midnight", "b2c2.xhtml", []),
    ]),
]
PARTS_FILES = [
    ("b1.xhtml", "<h1>Book One</h1><p>part one page</p>"),
    ("b1c1.xhtml", "<p>alpha</p>"),
    ("b1c2.xhtml", "<p>beta</p>"),
    ("b2.xhtml", "<h1>Book Two</h1><p>part two page</p>"),
    ("b2c1.xhtml", "<p>gamma</p>"),
    ("b2c2.xhtml", "<p>delta</p>"),
]


@pytest.fixture
def flat(tmp_path: Path) -> Builder:
    """A standalone book with its own reading-progress.md."""
    def build(text: str = progress("reading", chapter="2")) -> str:
        return str(make_book(tmp_path / "standalone" / "flat", "Flat Book", FLAT_FILES,
                             FLAT_TOC, text))
    return build


@pytest.fixture
def parts(tmp_path: Path) -> Builder:
    """A standalone book whose chapter numbering restarts in each part."""
    def build(text: str) -> str:
        return str(make_book(tmp_path / "standalone" / "parts", "Parts Book", PARTS_FILES,
                             PARTS_TOC, text))
    return build


@pytest.fixture
def series(tmp_path: Path) -> Builder:
    """Book 1 = the flat book, book 2 = the parts book, one series-level progress file."""
    def build(text: str) -> str:
        root = tmp_path / "series"
        if not (root / "books").exists():
            make_book(root / "books" / "01-flat", "Flat Book", FLAT_FILES, FLAT_TOC)
            make_book(root / "books" / "02-parts", "Parts Book", PARTS_FILES, PARTS_TOC)
        (root / "reading-progress.md").write_text(text, encoding="utf-8")
        return str(root)
    return build
