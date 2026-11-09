"""Tests for the book-search command, using small synthetic books (no real book text)."""

from __future__ import annotations

from pathlib import Path

import pytest

from book_companion.core.errors import BookError
from book_companion.core.labels import parse_chapter_number
from book_companion.core.progress import Status, parse_progress
from book_companion.search.cli import main
from helpers import FLAT_FILES, FLAT_TOC, Builder, Capture, make_book, progress


def run(capsys: Capture, *argv: str) -> tuple[int, str, str]:
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
def test_parse_chapter_number(label: str, expected: int | None) -> None:
    assert parse_chapter_number(label) == expected


# -- progress front matter ----------------------------------------------------

def test_progress_front_matter_is_read(tmp_path: Path) -> None:
    path = tmp_path / "reading-progress.md"
    path.write_text(progress("reading", chapter="5", part="2", book="3"), encoding="utf-8")
    result = parse_progress(path)
    assert result.status is Status.READING
    assert (result.book, result.chapter, result.part, result.section) == (3, 5, 2, None)


@pytest.mark.parametrize("text, message", [
    ("# Reading progress\n- Status: reading\n", "front-matter"),
    ("---\nstatus: reading\nchapter: 5\n", "not closed"),
    ("---\nstatus: reading\nchpter: 5\n---\n", "chpter: unknown field"),
    ("---\nstatus: reading\nchapter: five\n---\n", "whole number"),
    ("---\nstatus: halfway\n---\n", "status: Input should be .not started."),
    ("---\nstatus: reading\nchapter: 5\nsection: 3\n---\n", "not both"),
    ("---\nstatus: reading\npart: 2\n---\n", "together with chapter"),
    ("---\nstatus: reading\nstatus: finished\n---\n", "set twice"),
    ("---\nstatus: reading\nupdated: yesterday\n---\n", "YYYY-MM-DD"),
    ("---\nbook: two\nstatus: reading\n---\n", "whole number"),
])
def test_progress_front_matter_is_strict(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "reading-progress.md"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(BookError, match=message):
        parse_progress(path)


def test_invalid_progress_blocks_search(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat("---\nstatus: reading\nchapter: 2b\n---\n"), "gate")
    assert code == 2 and "whole number" in err


# -- boundary in one book -----------------------------------------------------

def test_search_stops_at_boundary_and_skips_contents_page(flat: Builder, capsys: Capture) -> None:
    code, out, _ = run(capsys, "search", flat(), "betrayal")
    assert code == 0 and "No matches" in out  # only in chapter 3's title and the contents page


def test_nested_section_and_unlisted_file_belong_to_finished_chapter(
        flat: Builder, capsys: Capture) -> None:
    book = flat()
    assert "moon" in run(capsys, "search", book, "moon")[1]
    assert "Continuation" in run(capsys, "search", book, "continuation")[1]


def test_narrowing_needs_no_permission(flat: Builder, capsys: Capture) -> None:
    book = flat()
    code, out, _ = run(capsys, "search", book, "Anais", "--chapter", "1")
    assert code == 0 and "**Anaïs**" in out
    assert "No matches" in run(capsys, "search", book, "tattoo", "--chapter", "1")[1]


def test_going_past_progress_needs_permission(flat: Builder, capsys: Capture) -> None:
    book = flat()
    code, _, err = run(capsys, "search", book, "Gilliam", "--chapter", "3")
    assert code == 2 and "--allow-spoilers" in err
    code, _, err = run(capsys, "search", book, "Gilliam", "--all")
    assert code == 2 and "--allow-spoilers" in err
    out = run(capsys, "search", book, "Gilliam", "--chapter", "3", "--allow-spoilers")[1]
    assert "**Gilliam**" in out


def test_not_started_refuses(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(progress("not started")), "gate")
    assert code == 2 and "nothing completed" in err


def test_reading_without_completed_chapter_refuses(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(progress("reading")), "gate")
    assert code == 2 and "nothing completed" in err


def test_finished_searches_whole_book(flat: Builder, capsys: Capture) -> None:
    assert "**final**" in run(capsys, "search", flat(progress("finished")), "final")[1]


def test_section_progress(flat: Builder, capsys: Capture) -> None:
    book = flat(progress("reading", section="2"))  # section 2 = chapter 1
    assert "**gate**" in run(capsys, "search", book, "gate")[1]
    assert "No matches" in run(capsys, "search", book, "moon")[1]


def test_book_flag_is_rejected_for_a_single_book(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(), "gate", "--book", "1")
    assert code == 2 and "only for series" in err


# -- folding and output -------------------------------------------------------

def test_accents_and_curly_quotes_are_folded(flat: Builder, capsys: Capture) -> None:
    book = flat()
    assert "**Anaïs**" in run(capsys, "search", book, "anais")[1]
    assert "**Valka’s**" in run(capsys, "search", book, "Valka's")[1]


def test_inline_markup_does_not_split_paragraphs(flat: Builder, capsys: Capture) -> None:
    assert "**is very fine**" in run(capsys, "search", flat(), "is very fine")[1]


def test_word_and_regex_options(flat: Builder, capsys: Capture) -> None:
    book = flat()
    assert "No matches" in run(capsys, "search", book, "Val", "--word")[1]
    assert "**Valka" in run(capsys, "search", book, r"Val\w+", "--regex")[1]


def test_results_name_the_section(flat: Builder, capsys: Capture) -> None:
    assert "Chapter 1: Arrival  (section 2)" in run(capsys, "search", flat(), "gate")[1]


# -- read / chapters / check --------------------------------------------------

def test_read_includes_nested_sections_and_refuses_later_chapters(
        flat: Builder, capsys: Capture) -> None:
    book = flat()
    out = run(capsys, "read", book, "--chapter", "2")[1]
    assert "tattoo" in out and "moon" in out and "Continuation" in out
    code, _, err = run(capsys, "read", book, "--chapter", "3")
    assert code == 2 and "--allow-spoilers" in err
    assert "Gilliam" in run(capsys, "read", book, "--chapter", "3", "--allow-spoilers")[1]


def test_read_by_section_and_paragraph_range(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "read", flat(), "--section", "3", "--from", "2", "--to", "2")[1]
    assert "tattoo" in out and "CHAPTER" not in out.upper().split("##")[0]
    assert "moon" not in out  # a paragraph range reads only that section


def test_chapters_hides_later_sections(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "chapters", flat())[1]
    assert "Chapter 2: The Garden" in out
    assert "Betrayal" not in out and "3 later sections hidden" in out


def test_check_prints_no_titles(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "check", flat())[1]
    assert "Result: OK" in out and "reading: through chapter 2" in out
    assert "Betrayal" not in out and "Garden" not in out


# -- parts with restarting chapter numbers ------------------------------------

def test_part_aware_progress(parts: Builder, capsys: Capture) -> None:
    book = parts(progress("reading", chapter="1", part="2"))
    assert "**gamma**" in run(capsys, "search", book, "gamma")[1]
    assert "No matches" in run(capsys, "search", book, "delta")[1]


def test_chapter_without_part_is_ambiguous(parts: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", parts(progress("reading", chapter="1")), "alpha")
    assert code == 2 and "parts 1, 2" in err


def test_finishing_a_part_page_does_not_include_its_chapters(
        parts: Builder, capsys: Capture) -> None:
    book = parts(progress("reading", section="4"))  # section 4 = the "Book Two" part page
    out = run(capsys, "search", book, "part two page")[1]
    assert "**part two page**" in out
    assert "No matches" in run(capsys, "search", book, "gamma")[1]


def test_part_flag_for_narrowing_and_read(parts: Builder, capsys: Capture) -> None:
    book = parts(progress("reading", chapter="2", part="2"))
    assert "**alpha**" in run(capsys, "search", book, "alpha", "--chapter", "1", "--part", "1")[1]
    assert "gamma" in run(capsys, "read", book, "--chapter", "1", "--part", "2")[1]


def test_part_requires_chapter(parts: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", parts(progress("finished")), "alpha", "--part", "1")
    assert code == 2 and "together with --chapter" in err


def test_check_reports_restarting_numbering(parts: Builder, capsys: Capture) -> None:
    out = run(capsys, "check", parts(progress("not started")))[1]
    assert "restarts in each part" in out
    assert "Duplicate chapter numbers:    none" in out


# -- series directories -------------------------------------------------------

def test_series_story_point_reads_earlier_books_in_full(series: Builder, capsys: Capture) -> None:
    root = series(progress("reading", chapter="1", part="1", book="2"))
    out = run(capsys, "search", root, "final|alpha|beta", "--regex")[1]
    assert "earlier book: whole book" in out
    assert "Flat Book · Chapter 5: Ending  (book 1, section 7)" in out
    assert "**alpha**" in out and "**beta**" not in out


def test_series_later_books_are_excluded(series: Builder, capsys: Capture) -> None:
    root = series(progress("reading", chapter="2", book="1"))
    out = run(capsys, "search", root, "moon|alpha", "--regex")[1]
    assert "**moon**" in out and "**alpha**" not in out
    assert "later book: not read yet" in out


def test_series_narrowing_excludes_later_books(series: Builder, capsys: Capture) -> None:
    root = series(progress("finished", book="2"))
    out = run(capsys, "search", root, "gate|final|alpha", "--regex", "--book", "1",
              "--chapter", "1")[1]
    assert "**gate**" in out and "**final**" not in out and "**alpha**" not in out
    assert "after the requested story point" in out


def test_series_story_point_past_progress_needs_permission(
        series: Builder, capsys: Capture) -> None:
    root = series(progress("reading", chapter="1", part="1", book="2"))
    code, _, err = run(capsys, "search", root, "delta", "--book", "2")
    assert code == 2 and "Book 2: Parts Book" in err
    out = run(capsys, "search", root, "delta", "--book", "2", "--allow-spoilers")[1]
    assert "**delta**" in out


def test_series_chapter_needs_book(series: Builder, capsys: Capture) -> None:
    root = series(progress("not started", book="2"))
    code, _, err = run(capsys, "search", root, "gate", "--chapter", "1")
    assert code == 2 and "--book" in err
    code, _, err = run(capsys, "read", root, "--chapter", "1")
    assert code == 2 and "--book" in err
    assert "gate" in run(capsys, "read", root, "--book", "1", "--chapter", "1")[1]


def test_series_progress_needs_book(series: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", series(progress("reading", chapter="2")), "gate")
    assert code == 2 and "set 'book'" in err


def test_series_progress_book_may_be_one_past_the_imported_books(
        series: Builder, capsys: Capture) -> None:
    out = run(capsys, "search", series(progress("reading", chapter="3", book="3")), "delta")[1]
    assert "**delta**" in out  # books 1 and 2 count as read; book 3 isn't imported yet
    code, _, err = run(capsys, "search", series(progress("reading", book="9")), "delta")
    assert code == 2 and "past the imported books" in err


def test_standalone_progress_rejects_book(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(progress("reading", chapter="2", book="1")), "gate")
    assert code == 2 and "only used in a series" in err


def test_book_directory_inside_series_uses_series_progress(
        series: Builder, capsys: Capture) -> None:
    root = Path(series(progress("reading", chapter="1", part="2", book="2")))
    book = str(root / "books" / "02-parts")
    out = run(capsys, "search", book, "gamma|delta|final", "--regex")[1]
    assert "**gamma**" in out and "**delta**" not in out and "**final**" not in out
    assert "alpha" in run(capsys, "read", book, "--chapter", "1", "--part", "1")[1]
    code, _, err = run(capsys, "read", book, "--book", "1", "--chapter", "1")
    assert code == 2 and "book 2 only" in err


@pytest.mark.parametrize("cwd, target", [("books", "02-parts"), ("books/02-parts", ".")])
def test_relative_book_path_still_finds_the_series(
        series: Builder, capsys: Capture, monkeypatch: pytest.MonkeyPatch,
        cwd: str, target: str) -> None:
    root = Path(series(progress("reading", chapter="1", part="2", book="2")))
    monkeypatch.chdir(root / cwd)
    out = run(capsys, "search", target, "gamma|delta", "--regex")[1]
    assert "**gamma**" in out and "**delta**" not in out


def test_series_check_reports_each_book(series: Builder, capsys: Capture) -> None:
    out = run(capsys, "check", series(progress("not started", book="2")))[1]
    assert "book 2, not started" in out
    assert "## Book 1" in out and "earlier book: whole book" in out
    assert "## Book 2" in out and "nothing completed yet" in out


def test_series_check_reports_invalid_progress(series: Builder, capsys: Capture) -> None:
    out = run(capsys, "check", series("---\nstatus: reading\nchpter: 2\n---\n"))[1]
    assert "Reading progress: ERROR" in out and "chpter: unknown field" in out


def test_series_rejects_book_folder_without_volume_prefix(tmp_path: Path, capsys: Capture) -> None:
    make_book(tmp_path / "series" / "books" / "flat", "Flat Book", FLAT_FILES, FLAT_TOC)
    (tmp_path / "series" / "reading-progress.md").write_text(
        progress("finished", book="1"), encoding="utf-8")
    code, _, err = run(capsys, "check", str(tmp_path / "series"))
    assert code == 2 and "volume prefix" in err


# -- start points, output budget and continuation -----------------------------

def test_start_chapter_skips_earlier_chapters(flat: Builder, capsys: Capture) -> None:
    book = flat(progress("finished"))
    out = run(capsys, "search", book, "gate|Gilliam", "--regex", "--start-chapter", "3")[1]
    assert "starting at: section 5" in out
    assert "**Gilliam**" in out and "**gate**" not in out


def test_start_and_end_make_a_range(flat: Builder, capsys: Capture) -> None:
    book = flat(progress("finished"))
    out = run(capsys, "search", book, "tattoo|Gilliam|Quiet|final", "--regex",
              "--start-chapter", "2", "--chapter", "3")[1]
    assert "**tattoo**" in out and "**Gilliam**" in out
    assert "**Quiet**" not in out and "**final**" not in out


def test_start_after_end_is_an_error(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(), "gate", "--start-chapter", "4")
    assert code == 2 and "after the end" in err


def test_start_never_widens_past_progress(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(), "Gilliam", "--start-chapter", "3")
    assert code == 2 and "after the end" in err  # chapter 3 is past progress (chapter 2)


def test_series_start_needs_start_book(series: Builder, capsys: Capture) -> None:
    root = series(progress("finished", book="2"))
    code, _, err = run(capsys, "search", root, "gamma", "--start-chapter", "1")
    assert code == 2 and "--start-book" in err
    out = run(capsys, "search", root, "gate|gamma", "--regex", "--start-book", "2")[1]
    assert "**gamma**" in out and "**gate**" not in out


def test_chapters_listing_honours_start(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "chapters", flat(progress("finished")), "--start-chapter", "4")[1]
    assert "Chapter 4: Aftermath" in out and "Chapter 2: The Garden" not in out


def test_output_budget_prints_continuation_that_resumes(flat: Builder, capsys: Capture) -> None:
    book = flat(progress("finished"))
    out = run(capsys, "search", book, "a", "--max-chars", "1")[1]  # one hit per page
    assert "Output limit reached" in out and "Remaining matches by section" in out
    flags = out.split("Continue: rerun with  ")[1].split("  (")[0].split()
    assert flags[0] == "--start-section"
    resumed = run(capsys, "search", book, "a", "--max-chars", "1", *flags)[1]
    first_hit = [line for line in resumed.splitlines() if line.startswith("  ¶")][0]
    assert first_hit not in out  # the next page starts with a hit not shown before


def test_capture_groups_limit_highlighting(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "search", flat(), r"(Valka).{0,40}(fine)", "--regex")[1]
    assert "**Valka**" in out and "**fine**" in out and "**Valka’s tattoo" not in out


def test_word_applies_to_regex_ends(flat: Builder, capsys: Capture) -> None:
    book = flat()
    assert "No matches" in run(capsys, "search", book, "Val|gat", "--regex", "--word")[1]
    assert "**gate**" in run(capsys, "search", book, "Valka|gate", "--regex", "--word")[1]


# -- read paging ----------------------------------------------------------------

def _continuation(out: str) -> list[str]:
    return out.split("rerun read with  ")[1].strip().split()


def test_read_pages_through_a_chapter_with_nested_sections(flat: Builder, capsys: Capture) -> None:
    book = flat()  # chapter 2 = sections 3 (two paragraphs) and 4 (the nested interlude)
    seen: list[str] = []
    out = run(capsys, "read", book, "--chapter", "2", "--max-chars", "1")[1]
    for _ in range(10):
        seen += [line for line in out.splitlines() if line.startswith("¶")]
        if "Output limit reached" not in out:
            break
        out = run(capsys, "read", book, *_continuation(out), "--max-chars", "1")[1]
    text = " ".join(seen)
    assert "tattoo" in text and "moon" in text and "Continuation" in text
    assert len(seen) == len(set(seen))  # nothing repeated, nothing skipped


def test_read_paging_with_a_paragraph_range(flat: Builder, capsys: Capture) -> None:
    book = flat()
    out = run(capsys, "read", book, "--section", "3", "--from", "1", "--to", "2",
              "--max-chars", "1")[1]
    flags = _continuation(out)
    assert flags[-4:] == ["--from", "2", "--to", "2"]
    assert "tattoo" in run(capsys, "read", book, *flags)[1]


def test_read_start_section_must_be_inside_the_target(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "read", flat(), "--chapter", "1", "--start-section", "4")
    assert code == 2 and "--start-section must be within" in err


def test_read_range_and_resume_flags_do_not_mix(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "read", flat(), "--chapter", "2", "--from", "1",
                       "--start-paragraph", "2")
    assert code == 2 and "not both" in err


# -- reading on through a later point -------------------------------------------

def test_read_through_a_later_chapter(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "read", flat(progress("finished")), "--chapter", "1",
              "--through-chapter", "4")[1]
    for text in ("gate", "tattoo", "moon", "Continuation", "Gilliam", "Quiet"):
        assert text in out
    assert "final scene" not in out


def test_read_through_stops_at_reading_progress(flat: Builder, capsys: Capture) -> None:
    book = flat()  # progress: chapter 2
    out = run(capsys, "read", book, "--chapter", "1", "--through-chapter", "4")[1]
    assert "moon" in out and "Gilliam" not in out
    assert "beyond the reading progress" in out
    out = run(capsys, "read", book, "--chapter", "1", "--through-chapter", "4",
              "--allow-spoilers")[1]
    assert "Gilliam" in out and "Quiet" in out


def test_read_pages_through_a_whole_book(flat: Builder, capsys: Capture) -> None:
    book = flat(progress("finished"))
    seen: list[str] = []
    out = run(capsys, "read", book, "--chapter", "1", "--through-section", "7",
              "--max-chars", "1")[1]
    for _ in range(20):
        seen += [line for line in out.splitlines() if line.startswith("¶")]
        if "Output limit reached" not in out:
            break
        assert "--through-section 7" in out
        out = run(capsys, "read", book, *_continuation(out), "--max-chars", "1")[1]
    text = " ".join(seen)
    assert "gate" in text and "moon" in text and "final scene" in text
    assert len(seen) == len(set(seen))  # nothing repeated, nothing skipped


def test_read_through_a_chapter_in_a_later_part(parts: Builder, capsys: Capture) -> None:
    book = parts(progress("finished"))
    out = run(capsys, "read", book, "--chapter", "2", "--part", "1",
              "--through-chapter", "1", "--through-part", "2")[1]
    assert "beta" in out and "part two page" in out and "gamma" in out
    assert "alpha" not in out and "delta" not in out
    code, _, err = run(capsys, "read", book, "--chapter", "1", "--part", "1",
                       "--through-part", "2")
    assert code == 2 and "together with --through-chapter" in err


def test_read_through_must_follow_what_is_read(flat: Builder, capsys: Capture) -> None:
    book = flat(progress("finished"))
    code, _, err = run(capsys, "read", book, "--chapter", "3", "--through-chapter", "1")
    assert code == 2 and "must not come before" in err
    code, _, err = run(capsys, "read", book, "--section", "3", "--from", "1",
                       "--through-chapter", "4")
    assert code == 2 and "leave out" in err
