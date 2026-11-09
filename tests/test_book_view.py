"""book-view: the pages and files it serves from a small library."""

from __future__ import annotations

import http.client
import threading
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlencode

import pytest

from book_companion.view.app import PALETTE_COOKIE, App
from book_companion.view.cli import main
from book_companion.view.layout import PALETTE_PATH
from book_companion.view.server import make_server
from book_companion.view.themes import DEFAULT_PALETTE, PALETTES
from book_companion.view.web import Request, Response

PNG = b"\x89PNG\r\n\x1a\nfake png"
SERIES = "/books/jane-doe/night-saga/"
MIRA = SERIES + "characters/mira-vale/"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def library(tmp_path: Path) -> Path:
    root = tmp_path / "library"
    series = root / "books" / "jane-doe" / "night-saga"
    write(series / "reading-progress.md",
          "---\nvolume: 1\nstatus: reading\nchapter: 12\nupdated: 2026-11-07\n---\n\n"
          "# Reading progress\n\n- Current: chapter 13\n")

    first = series / "volumes" / "01-first-night"
    write(first / "metadata.md", "# Book metadata\n\n- Title: First Night\n"
                                 "- Author(s): Jane Doe\n- Series: The Night Saga\n\n"
                                 "## Metadata notes\n\n- Title: not this one\n")
    write(first / "chapters.md", "# First Night — Chapter Notes\n")
    write(first / "book.txt", "SECRET TEXT")
    write(first / "book-html" / "OEBPS" / "c1.xhtml", "<p>SECRET</p>")
    (first / "source.epub").write_bytes(b"PK")
    second = series / "volumes" / "02-second-night"
    write(second / "metadata.md", "- Title: Second Night\n")
    write(second / "reference.md", "# Second Night — Reference\n\n"
                                   "| Name | Fate |\n|---|---|\n| Mira | lives |\n")

    mira = series / "characters" / "mira-vale"
    write(mira / "description.md",
          "# Mira Vale\n\n## Established details\n- Grey eyes <script>alert(1)</script>\n")
    (mira / "pics").mkdir()
    (mira / "pics" / "mira-portrait-v01.png").write_bytes(PNG)
    write(mira / "pics" / "mira-portrait-v01.prompt.md",
          "# Image prompt: Mira\n\n## Prompt\n> A woman with grey eyes.\n")
    write(mira / "pics" / "mira-portrait-v02.prompt.md", "# Image prompt: Mira, armored\n")
    tower = series / "locations" / "black-tower" / "pics"
    tower.mkdir(parents=True)
    (tower / "black-tower-v01.jpg").write_bytes(b"JPEG")

    standalone = root / "books" / "jane-doe" / "standalone" / "lone-star"
    write(standalone / "reading-progress.md", "---\nstatus: finished\n---\n")
    write(standalone / "metadata.md", "- Title: Lone Star\n- Author(s): Jane Doe\n")
    write(standalone / "chapters.md", "# Lone Star — Chapter Notes\n")
    write(standalone / "entities" / "characters" / "ash" / "description.md", "# Ash\n")
    return root


def respond(root: Path, url: str, cookie: str | None = None) -> Response:
    return App(root).handle(Request.parse("GET", url, cookie))


def post(root: Path, url: str, form: dict[str, str]) -> Response:
    return App(root).handle(Request.parse("POST", url, body=urlencode(form).encode()))


def get(root: Path, url: str, cookie: str | None = None) -> Response:
    response = respond(root, url, cookie)
    assert response.status == 200, url
    return response


def page(root: Path, url: str, cookie: str | None = None) -> str:
    response = get(root, url, cookie)
    assert response.content_type == "text/html; charset=utf-8"
    return response.body.decode("utf-8")


# Library pages


def test_index_lists_series_and_standalone_books(library: Path) -> None:
    html = page(library, "/")
    assert "The Night Saga" in html and "Jane Doe" in html
    assert "Volume 1 · read through chapter 12 · updated 2026-11-07" in html
    assert "Lone Star" in html and "finished" in html
    assert f'href="{SERIES}"' in html


def test_series_page_links_books_entities_and_marks_spoilers(library: Path) -> None:
    html = page(library, SERIES)
    assert "Volume 1: First Night" in html and "Volume 2: Second Night" in html
    assert f'href="{MIRA}"' in html and "Mira Vale" in html
    assert "Black Tower" in html and "no description" in html  # pics only, name from slug
    assert "Current: chapter 13" in html  # the notes below the front matter
    # Book 1 is still being read, so its chapter notes are a spoiler; so is book 2's reference.
    assert html.count('class="pill past"') == 2
    assert f'<a class="pill" href="{SERIES}volumes/01-first-night/metadata.md">' in html


def test_entity_page_shows_images_prompts_and_description(library: Path) -> None:
    html = page(library, MIRA)
    assert html.count("Mira Vale</h1>") == 1  # the description's own title is dropped
    assert f'<img src="{MIRA}pics/mira-portrait-v01.png"' in html
    assert "A woman with grey eyes." in html  # the image's prompt sidecar
    assert "Prompts waiting for an image" in html and "Mira, armored" in html
    assert "&lt;script&gt;" in html and "<script>" not in html


def test_images_are_served_with_their_type(library: Path) -> None:
    png = get(library, MIRA + "pics/mira-portrait-v01.png")
    assert (png.content_type, png.body) == ("image/png", PNG)
    jpeg = get(library, SERIES + "locations/black-tower/pics/black-tower-v01.jpg")
    assert jpeg.content_type == "image/jpeg"


def test_notes_past_progress_are_behind_a_warning(library: Path) -> None:
    reference = page(library, SERIES + "volumes/02-second-night/reference.md")
    assert '<details class="spoiler">' in reference and "Volume 2 is past" in reference
    assert "<table>" in reference
    chapters = page(library, SERIES + "volumes/01-first-night/chapters.md")
    assert '<details class="spoiler">' in chapters
    metadata = page(library, SERIES + "volumes/01-first-night/metadata.md")
    assert '<details class="spoiler">' not in metadata and "First Night" in metadata
    finished = page(library, "/books/jane-doe/standalone/lone-star/chapters.md")
    assert '<details class="spoiler">' not in finished and "Lone Star — Chapter Notes" in finished


def test_broken_progress_shows_an_error_and_hides_every_memory_note(library: Path) -> None:
    write(library / "books" / "jane-doe" / "night-saga" / "reading-progress.md",
          "---\nvolume: one\nstatus: reading\n---\n")
    html = page(library, SERIES)
    assert "Could not read the reading progress" in html
    assert html.count('class="pill past"') == 2
    chapters = page(library, SERIES + "volumes/01-first-night/chapters.md")
    assert '<details class="spoiler">' in chapters


@pytest.mark.parametrize("url", [
    SERIES + "volumes/01-first-night/book.txt",
    SERIES + "volumes/01-first-night/source.epub",
    SERIES + "volumes/01-first-night/book-html/OEBPS/c1.xhtml",
    SERIES + "reading-progress.md",
    MIRA + "description.md",
    MIRA + "pics/mira-portrait-v01.prompt.md",
    "/../library/books/",
    "/books/jane-doe/night-saga/%2e%2e/%2e%2e/%2e%2e/",
    "/C:/Windows/win.ini",
    "/static/../app.py",
    "/static/%2e%2e/app.py",
    "/static/missing.css",
    "/nope",
])
def test_only_discovered_pages_and_files_are_served(library: Path, url: str) -> None:
    assert respond(library, url).status == 404


def test_folder_without_trailing_slash_redirects(library: Path) -> None:
    response = respond(library, SERIES.rstrip("/"))
    assert (response.status, response.header("Location")) == (301, SERIES)


def test_non_ascii_names_round_trip(library: Path) -> None:
    write(library / "books" / "jane-doe" / "night-saga" / "characters" / "zoë" / "description.md",
          "# Zoë\n")
    link = quote(SERIES + "characters/zoë/")
    assert f'href="{link}"' in page(library, SERIES)
    assert "<h1>Zoë</h1>" in page(library, link)


def test_other_methods_are_refused(library: Path) -> None:
    assert post(library, SERIES, {}).status == 405


# Static files and palettes


def test_stylesheet_and_icon_are_served(library: Path) -> None:
    css = get(library, "/static/style.css")
    assert css.content_type == "text/css; charset=utf-8" and b"var(--bg)" in css.body
    assert get(library, "/static/icon.svg").content_type == "image/svg+xml"
    html = page(library, "/")
    assert '<link rel="stylesheet" href="/static/style.css">' in html


def test_pages_use_the_default_palette_without_a_cookie(library: Path) -> None:
    html = page(library, SERIES).replace("&amp;", "&")
    default = next(p for p in PALETTES if p.key == DEFAULT_PALETTE)
    assert f'data-palette="{DEFAULT_PALETTE}"' in html
    assert f"<summary>Palette: {default.name}</summary>" in html
    for palette in PALETTES:  # the menu offers every palette, marking the current one
        pressed = "true" if palette is default else "false"
        assert (f'value="{palette.key}" aria-pressed="{pressed}">{palette.name}</button>'
                in html)
    assert f'<input type="hidden" name="next" value="{SERIES}">' in html


def test_choosing_a_palette_sets_a_cookie_and_returns_to_the_page(library: Path) -> None:
    response = post(library, PALETTE_PATH, {"palette": "midnight", "next": MIRA})
    assert (response.status, response.header("Location")) == (303, MIRA)
    cookie = response.header("Set-Cookie") or ""
    assert cookie.startswith(f"{PALETTE_COOKIE}=midnight;") and "Path=/" in cookie
    midnight = next(p for p in PALETTES if p.key == "midnight")
    html = page(library, MIRA, cookie=f"{PALETTE_COOKIE}=midnight")
    assert 'data-palette="midnight"' in html and midnight.dark.accent in html


@pytest.mark.parametrize("target", ["//evil.example/", "https://evil.example/", "\\\\evil", ""])
def test_the_palette_picker_only_returns_to_this_site(library: Path, target: str) -> None:
    response = post(library, PALETTE_PATH, {"palette": "velvet", "next": target})
    assert response.header("Location") == "/"


def test_unknown_palettes_are_refused_or_ignored(library: Path) -> None:
    assert post(library, PALETTE_PATH, {"palette": "neon"}).status == 400
    html = page(library, "/", cookie=f"{PALETTE_COOKIE}=neon")
    assert f'data-palette="{DEFAULT_PALETTE}"' in html


# The server and the command


@pytest.fixture
def server(library: Path) -> Iterator[ThreadingHTTPServer]:
    server = make_server(App(library), 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def test_server_serves_pages(server: ThreadingHTTPServer) -> None:
    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=10) as reply:
        assert reply.status == 200
        assert "The Night Saga" in reply.read().decode("utf-8")


def test_server_accepts_the_palette_form(server: ThreadingHTTPServer) -> None:
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    try:
        connection.request("POST", PALETTE_PATH, urlencode({"palette": "graphite", "next": "/"}),
                           {"Content-Type": "application/x-www-form-urlencoded"})
        reply = connection.getresponse()
        assert reply.status == 303
        assert (reply.getheader("Set-Cookie") or "").startswith(f"{PALETTE_COOKIE}=graphite;")
    finally:
        connection.close()


def test_main_rejects_a_folder_without_books(tmp_path: Path,
                                             capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path), "--no-browser"]) == 2
    assert "has no books/ folder" in capsys.readouterr().err
