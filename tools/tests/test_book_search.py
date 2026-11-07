"""Tests for tools/book_search.py, using small synthetic books (no real book text)."""

from __future__ import annotations

from pathlib import Path

import pytest

from book_search import BookError, main, parse_chapter_number, parse_progress

XHTML = """<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head>
<body>{body}</body></html>"""


def progress(status: str, chapter: str = "", part: str = "", section: str = "") -> str:
    return (f"---\nstatus: {status}  # not started | reading | finished\n"
            f"chapter: {chapter}\npart: {part}\nsection: {section}\nupdated: 2026-11-08\n---\n\n"
            "# Reading progress\n\n- Status: this human line is ignored by the tool\n")


def make_book(book_dir: Path, title: str, files: list[tuple[str, str]], toc: list,
              progress_text: str) -> Path:
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

    def points(items: list) -> str:
        return "".join(
            f'<navPoint><navLabel><text>{label}</text></navLabel>'
            f'<content src="text/{src}"/>{points(children)}</navPoint>'
            for label, src, children in items)

    (html / "toc.ncx").write_text(f"""<?xml version='1.0' encoding='utf-8'?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<navMap>{points(toc)}</navMap></ncx>""", encoding="utf-8")
    (book_dir / "reading-progress.md").write_text(progress_text, encoding="utf-8")
    return book_dir


# Sections: 1 Contents, 2 Ch1, 3 Ch2, 4 Interlude (nested in Ch2), 5 Ch3, 6 Ch4, 7 Ch5
FLAT_TOC = [
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

PARTS_TOC = [
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
def flat(tmp_path: Path):
    def build(text: str = progress("reading", chapter="2")) -> str:
        return str(make_book(tmp_path / "01-flat", "Flat Book", FLAT_FILES, FLAT_TOC, text))
    return build


@pytest.fixture
def parts(tmp_path: Path):
    def build(text: str) -> str:
        return str(make_book(tmp_path / "01-parts", "Parts Book", PARTS_FILES, PARTS_TOC, text))
    return build


@pytest.fixture
def series(tmp_path: Path):
    """Book 1 = the flat book, book 2 = the parts book, in one series directory."""
    def build(first: str, second: str) -> str:
        root = tmp_path / "series"
        make_book(root / "books" / "01-flat", "Flat Book", FLAT_FILES, FLAT_TOC, first)
        make_book(root / "books" / "02-parts", "Parts Book", PARTS_FILES, PARTS_TOC, second)
        return str(root)
    return build


def run(capsys, *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# -- table-of-contents label parsing ------------------------------------------

@pytest.mark.parametrize("label, expected", [
    ("Chapter 12: The Doctor", 12),
    ("CHAPTER 7", 7),
    ("Chapter Twelve: Title", 12),
    ("Chapter Twenty-Two", 22),
    ("Chapter One Hundred and Five", 105),
    ("Chapter XIV", 14),
    ("12. A Title", 12),
    ("Chapter In Which Things Happen", None),
    ("Prologue", None),
    ("Book One: Beginnings", None),
])
def test_parse_chapter_number(label, expected):
    assert parse_chapter_number(label) == expected


# -- progress front matter ----------------------------------------------------

def test_progress_front_matter_is_read(tmp_path):
    path = tmp_path / "reading-progress.md"
    path.write_text(progress("reading", chapter="5", part="2"), encoding="utf-8")
    result = parse_progress(path)
    assert (result.status, result.chapter, result.part, result.section) == ("reading", 5, 2, None)


@pytest.mark.parametrize("text, message", [
    ("# Reading progress\n- Status: reading\n", "front-matter"),
    ("---\nstatus: reading\nchapter: 5\n", "not closed"),
    ("---\nstatus: reading\nchpter: 5\n---\n", "unknown key"),
    ("---\nstatus: reading\nchapter: five\n---\n", "whole number"),
    ("---\nstatus: halfway\n---\n", "status must be"),
    ("---\nstatus: reading\nchapter: 5\nsection: 3\n---\n", "not both"),
    ("---\nstatus: reading\npart: 2\n---\n", "together with chapter"),
    ("---\nstatus: reading\nstatus: finished\n---\n", "set twice"),
    ("---\nstatus: reading\nupdated: yesterday\n---\n", "YYYY-MM-DD"),
])
def test_progress_front_matter_is_strict(tmp_path, text, message):
    path = tmp_path / "reading-progress.md"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(BookError, match=message):
        parse_progress(path)


def test_invalid_progress_blocks_search(flat, capsys):
    code, _, err = run(capsys, "search", flat("---\nstatus: reading\nchapter: 2b\n---\n"), "gate")
    assert code == 2 and "whole number" in err


# -- boundary in one book -----------------------------------------------------

def test_search_stops_at_boundary_and_skips_contents_page(flat, capsys):
    code, out, _ = run(capsys, "search", flat(), "betrayal")
    assert code == 0 and "No matches" in out  # only in chapter 3's title and the contents page


def test_nested_section_and_unlisted_file_belong_to_finished_chapter(flat, capsys):
    book = flat()
    assert "moon" in run(capsys, "search", book, "moon")[1]
    assert "Continuation" in run(capsys, "search", book, "continuation")[1]


def test_narrowing_needs_no_permission(flat, capsys):
    book = flat()
    code, out, _ = run(capsys, "search", book, "Anais", "--chapter", "1")
    assert code == 0 and "**Anaïs**" in out
    assert "No matches" in run(capsys, "search", book, "tattoo", "--chapter", "1")[1]


def test_going_past_progress_needs_permission(flat, capsys):
    book = flat()
    code, _, err = run(capsys, "search", book, "Gilliam", "--chapter", "3")
    assert code == 2 and "--allow-spoilers" in err
    code, _, err = run(capsys, "search", book, "Gilliam", "--all")
    assert code == 2 and "--allow-spoilers" in err
    out = run(capsys, "search", book, "Gilliam", "--chapter", "3", "--allow-spoilers")[1]
    assert "**Gilliam**" in out


def test_not_started_refuses(flat, capsys):
    code, _, err = run(capsys, "search", flat(progress("not started")), "gate")
    assert code == 2 and "nothing completed" in err


def test_reading_without_completed_chapter_refuses(flat, capsys):
    code, _, err = run(capsys, "search", flat(progress("reading")), "gate")
    assert code == 2 and "nothing completed" in err


def test_finished_searches_whole_book(flat, capsys):
    assert "**final**" in run(capsys, "search", flat(progress("finished")), "final")[1]


def test_section_progress(flat, capsys):
    book = flat(progress("reading", section="2"))  # section 2 = chapter 1
    assert "**gate**" in run(capsys, "search", book, "gate")[1]
    assert "No matches" in run(capsys, "search", book, "moon")[1]


def test_book_flag_is_rejected_for_a_single_book(flat, capsys):
    code, _, err = run(capsys, "search", flat(), "gate", "--book", "1")
    assert code == 2 and "only for series" in err


# -- folding and output -------------------------------------------------------

def test_accents_and_curly_quotes_are_folded(flat, capsys):
    book = flat()
    assert "**Anaïs**" in run(capsys, "search", book, "anais")[1]
    assert "**Valka’s**" in run(capsys, "search", book, "Valka's")[1]


def test_inline_markup_does_not_split_paragraphs(flat, capsys):
    assert "**is very fine**" in run(capsys, "search", flat(), "is very fine")[1]


def test_word_and_regex_options(flat, capsys):
    book = flat()
    assert "No matches" in run(capsys, "search", book, "Val", "--word")[1]
    assert "**Valka" in run(capsys, "search", book, r"Val\w+", "--regex")[1]


def test_results_name_the_section(flat, capsys):
    assert "Chapter 1: Arrival  (section 2)" in run(capsys, "search", flat(), "gate")[1]


# -- read / chapters / check --------------------------------------------------

def test_read_includes_nested_sections_and_refuses_later_chapters(flat, capsys):
    book = flat()
    out = run(capsys, "read", book, "--chapter", "2")[1]
    assert "tattoo" in out and "moon" in out and "Continuation" in out
    code, _, err = run(capsys, "read", book, "--chapter", "3")
    assert code == 2 and "--allow-spoilers" in err
    assert "Gilliam" in run(capsys, "read", book, "--chapter", "3", "--allow-spoilers")[1]


def test_read_by_section_and_paragraph_range(flat, capsys):
    out = run(capsys, "read", flat(), "--section", "3", "--from", "2", "--to", "2")[1]
    assert "tattoo" in out and "CHAPTER" not in out.upper().split("##")[0]
    assert "moon" not in out  # a paragraph range reads only that section


def test_chapters_hides_later_sections(flat, capsys):
    out = run(capsys, "chapters", flat())[1]
    assert "Chapter 2: The Garden" in out
    assert "Betrayal" not in out and "3 later sections hidden" in out


def test_check_prints_no_titles(flat, capsys):
    out = run(capsys, "check", flat())[1]
    assert "Result: OK" in out and "reading: through chapter 2" in out
    assert "Betrayal" not in out and "Garden" not in out


# -- parts with restarting chapter numbers ------------------------------------

def test_part_aware_progress(parts, capsys):
    book = parts(progress("reading", chapter="1", part="2"))
    assert "**gamma**" in run(capsys, "search", book, "gamma")[1]
    assert "No matches" in run(capsys, "search", book, "delta")[1]


def test_chapter_without_part_is_ambiguous(parts, capsys):
    code, _, err = run(capsys, "search", parts(progress("reading", chapter="1")), "alpha")
    assert code == 2 and "parts 1, 2" in err


def test_finishing_a_part_page_does_not_include_its_chapters(parts, capsys):
    book = parts(progress("reading", section="4"))  # section 4 = the "Book Two" part page
    out = run(capsys, "search", book, "part two page")[1]
    assert "**part two page**" in out
    assert "No matches" in run(capsys, "search", book, "gamma")[1]


def test_part_flag_for_narrowing_and_read(parts, capsys):
    book = parts(progress("reading", chapter="2", part="2"))
    assert "**alpha**" in run(capsys, "search", book, "alpha", "--chapter", "1", "--part", "1")[1]
    assert "gamma" in run(capsys, "read", book, "--chapter", "1", "--part", "2")[1]


def test_part_requires_chapter(parts, capsys):
    code, _, err = run(capsys, "search", parts(progress("finished")), "alpha", "--part", "1")
    assert code == 2 and "together with --chapter" in err


def test_check_reports_restarting_numbering(parts, capsys):
    out = run(capsys, "check", parts(progress("not started")))[1]
    assert "restarts in each part" in out
    assert "Duplicate chapter numbers:    none" in out


# -- series directories -------------------------------------------------------

def test_series_search_uses_each_books_progress(series, capsys):
    root = series(progress("finished"), progress("reading", chapter="1", part="1"))
    out = run(capsys, "search", root, "final|alpha|beta", "--regex")[1]
    assert "Flat Book · Chapter 5: Ending  (book 1, section 7)" in out
    assert "**alpha**" in out and "**beta**" not in out


def test_series_story_point_excludes_later_books(series, capsys):
    root = series(progress("finished"), progress("finished"))
    out = run(capsys, "search", root, "gate|final|alpha", "--regex", "--book", "1",
              "--chapter", "1")[1]
    assert "**gate**" in out and "**final**" not in out and "**alpha**" not in out
    assert "after the requested story point" in out


def test_series_story_point_past_progress_needs_permission(series, capsys):
    root = series(progress("finished"), progress("reading", chapter="1", part="1"))
    code, _, err = run(capsys, "search", root, "delta", "--book", "2")
    assert code == 2 and "Book 2: Parts Book" in err
    out = run(capsys, "search", root, "delta", "--book", "2", "--allow-spoilers")[1]
    assert "**delta**" in out


def test_series_chapter_needs_book(series, capsys):
    root = series(progress("finished"), progress("not started"))
    code, _, err = run(capsys, "search", root, "gate", "--chapter", "1")
    assert code == 2 and "--book" in err
    code, _, err = run(capsys, "read", root, "--chapter", "1")
    assert code == 2 and "--book" in err
    assert "gate" in run(capsys, "read", root, "--book", "1", "--chapter", "1")[1]


def test_series_notes_unfinished_earlier_book(series, capsys):
    root = series(progress("reading", chapter="2"), progress("reading", chapter="1", part="1"))
    out = run(capsys, "search", root, "alpha")[1]
    assert "Book 1: Flat Book is not marked finished" in out


def test_series_check_reports_each_book(series, capsys):
    out = run(capsys, "check", series(progress("finished"), progress("not started")))[1]
    assert "## Book 1" in out and "## Book 2" in out and "finished: whole book" in out


def test_series_rejects_book_folder_without_volume_prefix(tmp_path, capsys):
    make_book(tmp_path / "series" / "books" / "flat", "Flat Book", FLAT_FILES, FLAT_TOC,
              progress("finished"))
    code, _, err = run(capsys, "check", str(tmp_path / "series"))
    assert code == 2 and "volume prefix" in err
