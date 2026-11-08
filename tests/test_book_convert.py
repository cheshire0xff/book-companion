"""book-convert, run against a fake ebook-convert so Calibre is not needed."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from book_companion.convert import cli
from book_companion.convert.cli import convert, find_converter, main
from book_companion.core.errors import BookError

# Called as: python fake.py <mode> <source> <destination>, like ebook-convert <source> <dest>.
FAKE = """\
import pathlib, sys
mode, _source, dest = sys.argv[1:4]
dest = pathlib.Path(dest)
if mode == "fail":
    print("conversion log line", flush=True)
    print("boom: broken epub", file=sys.stderr)
    sys.exit(3)
if dest.suffix == ".txt":
    dest.write_text("" if mode == "empty-text" else "Chapter 1\\n", encoding="utf-8")
elif mode == "no-html":
    dest.mkdir()
    (dest / "style.css").write_text("p {}", encoding="utf-8")
elif mode != "no-dir":
    (dest / "OEBPS").mkdir(parents=True)
    (dest / "OEBPS" / "c1.xhtml").write_text("<p>new</p>", encoding="utf-8")
"""


def fake(tmp_path: Path, mode: str = "ok") -> list[str]:
    script = tmp_path / "fake_ebook_convert.py"
    script.write_text(FAKE, encoding="utf-8")
    return [sys.executable, str(script), mode]


@pytest.fixture
def book(tmp_path: Path) -> Path:
    directory = tmp_path / "book"
    directory.mkdir()
    (directory / "source.epub").write_bytes(b"PK fake epub")
    return directory


def leftovers(book: Path) -> list[str]:
    return [path.name for path in book.iterdir() if path.name.startswith("book-html-")]


def test_converts_to_text_and_html(tmp_path: Path, book: Path) -> None:
    text, html = convert(book / "source.epub", book / "book.txt", force=False,
                         converter=fake(tmp_path))
    assert text == book / "book.txt" and text.read_text(encoding="utf-8") == "Chapter 1\n"
    assert html == book / "book-html"
    assert (html / "OEBPS" / "c1.xhtml").read_text(encoding="utf-8") == "<p>new</p>"
    assert leftovers(book) == []


def test_relative_paths_are_resolved(tmp_path: Path, book: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(book)
    text, html = convert(Path("source.epub"), Path("book.txt"), force=False,
                         converter=fake(tmp_path))
    assert text.is_absolute() and html == book / "book-html"


@pytest.mark.parametrize("existing", ["book.txt", "book-html"])
def test_refuses_to_replace_without_force(tmp_path: Path, book: Path, existing: str) -> None:
    (book / "book-html").mkdir() if existing == "book-html" else (book / existing).write_text("x")
    with pytest.raises(BookError, match="already exists. Use --force"):
        convert(book / "source.epub", book / "book.txt", force=False, converter=fake(tmp_path))
    if existing == "book-html":
        assert not (book / "book.txt").exists()  # checked before anything is converted


def test_force_replaces_text_and_html(tmp_path: Path, book: Path) -> None:
    (book / "book.txt").write_text("old", encoding="utf-8")
    (book / "book-html").mkdir()
    (book / "book-html" / "stale.xhtml").write_text("<p>old</p>", encoding="utf-8")
    convert(book / "source.epub", book / "book.txt", force=True, converter=fake(tmp_path))
    assert (book / "book.txt").read_text(encoding="utf-8") == "Chapter 1\n"
    assert not (book / "book-html" / "stale.xhtml").exists()
    assert (book / "book-html" / "OEBPS" / "c1.xhtml").is_file()


@pytest.mark.parametrize("source, output, message", [
    ("missing.epub", "book.txt", "Input file not found"),
    (".", "book.txt", "Input path is a directory"),
    ("notes.txt", "book.txt", "must have an .epub extension"),
    ("source.epub", "book.md", "must have a .txt extension"),
    ("source.epub", "nowhere/book.txt", "Output directory does not exist"),
    ("source.epub", "folder.txt", "Output path is a directory"),
])
def test_rejects_bad_paths(tmp_path: Path, book: Path, source: str, output: str,
                           message: str) -> None:
    (book / "notes.txt").write_text("x", encoding="utf-8")
    (book / "folder.txt").mkdir()
    with pytest.raises(BookError, match=message):
        convert(book / source, book / output, force=False, converter=fake(tmp_path))


def test_html_path_that_is_a_file_is_refused_even_with_force(tmp_path: Path,
                                                             book: Path) -> None:
    (book / "book-html").write_text("x", encoding="utf-8")
    with pytest.raises(BookError, match="exists as a file"):
        convert(book / "source.epub", book / "book.txt", force=True, converter=fake(tmp_path))


def test_converter_failure_reports_exit_code_and_output(tmp_path: Path, book: Path) -> None:
    with pytest.raises(BookError, match="exit code 3") as caught:
        convert(book / "source.epub", book / "book.txt", force=False,
                converter=fake(tmp_path, "fail"))
    assert "boom: broken epub" in str(caught.value)
    assert "conversion log line" in str(caught.value)


def test_missing_converter_program_is_a_book_error(book: Path) -> None:
    with pytest.raises(BookError, match="Could not run"):
        convert(book / "source.epub", book / "book.txt", force=False,
                converter=[str(book / "no-such-program")])


def test_empty_text_is_an_error(tmp_path: Path, book: Path) -> None:
    with pytest.raises(BookError, match="empty output file"):
        convert(book / "source.epub", book / "book.txt", force=False,
                converter=fake(tmp_path, "empty-text"))


@pytest.mark.parametrize("mode, message", [
    ("no-html", "no non-empty HTML files"),
    ("no-dir", "without creating a directory"),
])
def test_failed_html_conversion_keeps_the_existing_html(tmp_path: Path, book: Path,
                                                        mode: str, message: str) -> None:
    (book / "book-html").mkdir()
    (book / "book-html" / "kept.xhtml").write_text("<p>kept</p>", encoding="utf-8")
    with pytest.raises(BookError, match=message):
        convert(book / "source.epub", book / "book.txt", force=True,
                converter=fake(tmp_path, mode))
    assert (book / "book-html" / "kept.xhtml").is_file()
    assert leftovers(book) == []


def test_find_converter_prefers_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: f"/bin/{name}")
    assert find_converter() == ["/bin/ebook-convert"]


def test_find_converter_falls_back_to_install_locations(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    installed = tmp_path / "Calibre2" / "ebook-convert.exe"
    installed.parent.mkdir()
    installed.write_bytes(b"")
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    assert find_converter() == [str(installed)]


def test_find_converter_explains_how_to_install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(cli, "install_locations", lambda: [])
    with pytest.raises(BookError, match="Install Calibre"):
        find_converter()


def test_main_prints_paths(tmp_path: Path, book: Path, monkeypatch: pytest.MonkeyPatch,
                           capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "find_converter", lambda: fake(tmp_path))
    code = main([str(book / "source.epub"), str(book / "book.txt")])
    out = capsys.readouterr().out.splitlines()
    assert code == 0 and out == [str(book / "book.txt"), str(book / "book-html")]


def test_main_reports_errors_without_traceback(tmp_path: Path, book: Path,
                                               monkeypatch: pytest.MonkeyPatch,
                                               capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "find_converter", lambda: fake(tmp_path))
    (book / "book.txt").write_text("x", encoding="utf-8")
    code = main([str(book / "source.epub"), str(book / "book.txt")])
    assert code == 2 and capsys.readouterr().err.startswith("error: Output file already exists")
