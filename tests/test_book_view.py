"""book-view: the pages and files it serves from a small library."""

from __future__ import annotations

import threading
import urllib.request
from pathlib import Path
from urllib.parse import quote

import pytest

from book_companion.view.cli import Response, main, make_server, respond

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
          "---\nbook: 1\nstatus: reading\nchapter: 12\nupdated: 2026-11-07\n---\n\n"
          "# Reading progress\n\n- Current: chapter 13\n")

    first = series / "books" / "01-first-night"
    write(first / "metadata.md", "# Book metadata\n\n- Title: First Night\n"
                                 "- Author(s): Jane Doe\n- Series: The Night Saga\n\n"
                                 "## Metadata notes\n\n- Title: not this one\n")
    write(first / "chapters.md", "# First Night — Chapter Notes\n")
    write(first / "book.txt", "SECRET TEXT")
    write(first / "book-html" / "OEBPS" / "c1.xhtml", "<p>SECRET</p>")
    (first / "source.epub").write_bytes(b"PK")
    second = series / "books" / "02-second-night"
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


def get(root: Path, url: str) -> Response:
    response = respond(root, url)
    assert response.status == 200, url
    return response


def page(root: Path, url: str) -> str:
    response = get(root, url)
    assert response.content_type == "text/html; charset=utf-8"
    return response.body.decode("utf-8")


def test_index_lists_series_and_standalone_books(library: Path) -> None:
    html = page(library, "/")
    assert "The Night Saga" in html and "Jane Doe" in html
    assert "Book 1 · read through chapter 12 · updated 2026-11-07" in html
    assert "Lone Star" in html and "finished" in html
    assert f'href="{SERIES}"' in html


def test_series_page_links_books_entities_and_marks_spoilers(library: Path) -> None:
    html = page(library, SERIES)
    assert "Book 1: First Night" in html and "Book 2: Second Night" in html
    assert f'href="{MIRA}"' in html and "Mira Vale" in html
    assert "Black Tower" in html and "no description" in html  # pics only, name from slug
    assert "Current: chapter 13" in html  # the notes below the front matter
    # Book 1 is still being read, so its chapter notes are a spoiler; so is book 2's reference.
    assert html.count('class="pill past"') == 2
    assert f'<a class="pill" href="{SERIES}books/01-first-night/metadata.md">' in html


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
    reference = page(library, SERIES + "books/02-second-night/reference.md")
    assert '<details class="spoiler">' in reference and "Book 2 is past" in reference
    assert "<table>" in reference
    chapters = page(library, SERIES + "books/01-first-night/chapters.md")
    assert '<details class="spoiler">' in chapters
    metadata = page(library, SERIES + "books/01-first-night/metadata.md")
    assert '<details class="spoiler">' not in metadata and "First Night" in metadata
    finished = page(library, "/books/jane-doe/standalone/lone-star/chapters.md")
    assert '<details class="spoiler">' not in finished and "Lone Star — Chapter Notes" in finished


def test_broken_progress_shows_an_error_and_hides_every_memory_note(library: Path) -> None:
    write(library / "books" / "jane-doe" / "night-saga" / "reading-progress.md",
          "---\nbook: one\nstatus: reading\n---\n")
    html = page(library, SERIES)
    assert "Could not read the reading progress" in html
    assert html.count('class="pill past"') == 2
    assert '<details class="spoiler">' in page(library, SERIES + "books/01-first-night/chapters.md")


@pytest.mark.parametrize("url", [
    SERIES + "books/01-first-night/book.txt",
    SERIES + "books/01-first-night/source.epub",
    SERIES + "books/01-first-night/book-html/OEBPS/c1.xhtml",
    SERIES + "reading-progress.md",
    MIRA + "description.md",
    MIRA + "pics/mira-portrait-v01.prompt.md",
    "/../library/books/",
    "/books/jane-doe/night-saga/%2e%2e/%2e%2e/%2e%2e/",
    "/C:/Windows/win.ini",
    "/nope",
])
def test_only_discovered_pages_and_images_are_served(library: Path, url: str) -> None:
    assert respond(library, url).status == 404


def test_folder_without_trailing_slash_redirects(library: Path) -> None:
    response = respond(library, SERIES.rstrip("/"))
    assert (response.status, response.location) == (301, SERIES)


def test_non_ascii_names_round_trip(library: Path) -> None:
    write(library / "books" / "jane-doe" / "night-saga" / "characters" / "zoë" / "description.md",
          "# Zoë\n")
    link = quote(SERIES + "characters/zoë/")
    assert f'href="{link}"' in page(library, SERIES)
    assert "<h1>Zoë</h1>" in page(library, link)


def test_server_serves_pages(library: Path) -> None:
    server = make_server(library, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/"
        with urllib.request.urlopen(url, timeout=10) as reply:
            assert reply.status == 200
            assert "The Night Saga" in reply.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_main_rejects_a_folder_without_books(tmp_path: Path,
                                             capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path), "--no-browser"]) == 2
    assert "has no books/ folder" in capsys.readouterr().err
