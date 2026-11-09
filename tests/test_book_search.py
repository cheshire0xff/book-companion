"""Tests for the book-search command, using small synthetic books (no real book text)."""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest

from book_companion.core.cli import shell_quote
from book_companion.core.errors import BookError
from book_companion.core.labels import parse_chapter_number
from book_companion.core.progress import Status, parse_progress
from book_companion.search.cli import main
from helpers import FLAT_FILES, FLAT_TOC, Builder, Capture, make_book, progress


def run(capsys: Capture, *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def next_page(out: str) -> list[str]:
    """The arguments of the printed next-page command, without the program name."""
    command = shlex.split(out.split("Next page:  ")[1].splitlines()[0])
    assert command[0] == "book-search"
    return command[1:]


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
    path.write_text(progress("reading", chapter="5", part="2", volume="3"), encoding="utf-8")
    result = parse_progress(path)
    assert result.status is Status.READING
    assert (result.volume, result.chapter, result.part, result.section) == (3, 5, 2, None)


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
    ("---\nvolume: two\nstatus: reading\n---\n", "whole number"),
    ("---\nbook: 2\nstatus: reading\n---\n", "'book:' is now 'volume:'"),
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
    assert "reading progress: through chapter 2" in out


def test_nested_section_and_unlisted_file_belong_to_finished_chapter(
        flat: Builder, capsys: Capture) -> None:
    book = flat()
    assert "moon" in run(capsys, "search", book, "moon")[1]
    assert "Continuation" in run(capsys, "search", book, "continuation")[1]


def test_narrowing_needs_no_permission(flat: Builder, capsys: Capture) -> None:
    book = flat()
    code, out, _ = run(capsys, "search", book, "Anais", "--to", "chapter 1")
    assert code == 0 and "**Anaïs**" in out and "range: through chapter 1" in out
    assert "No matches" in run(capsys, "search", book, "tattoo", "--to", "ch1")[1]


def test_going_past_progress_needs_permission(flat: Builder, capsys: Capture) -> None:
    book = flat()
    code, _, err = run(capsys, "search", book, "Gilliam", "--to", "chapter 3")
    assert code == 2 and "--allow-spoilers" in err and "through chapter 2" in err
    code, _, err = run(capsys, "search", book, "Gilliam", "--all")
    assert code == 2 and "--allow-spoilers" in err
    out = run(capsys, "search", book, "Gilliam", "--to", "chapter 3", "--allow-spoilers")[1]
    assert "**Gilliam**" in out


def test_not_started_refuses(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(progress("not started")), "gate")
    assert code == 2 and "Nothing is completed yet" in err


def test_reading_without_completed_chapter_refuses(flat: Builder, capsys: Capture) -> None:
    book = flat(progress("reading"))
    code, _, err = run(capsys, "search", book, "gate")
    assert code == 2 and "Nothing is completed yet" in err
    code, _, err = run(capsys, "search", book, "gate", "--to", "chapter 1")
    assert code == 2 and "--allow-spoilers" in err


def test_finished_searches_whole_book(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "search", flat(progress("finished")), "final")[1]
    assert "**final**" in out and "range: whole book" in out


def test_section_progress(flat: Builder, capsys: Capture) -> None:
    book = flat(progress("reading", section="2"))  # section 2 = chapter 1
    assert "**gate**" in run(capsys, "search", book, "gate")[1]
    assert "No matches" in run(capsys, "search", book, "moon")[1]


def test_a_standalone_book_has_no_volumes(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(), "gate", "--to", "volume 1 chapter 1")
    assert code == 2 and "leave out the volume" in err


def test_places_must_be_written_in_full_or_short_form(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(), "gate", "--to", "Chapter 1")
    assert code == 2 and '"v2 pt1 ch3 p6"' in err


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


def test_results_name_the_place(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "search", flat(), "gate|moon", "--regex")[1]
    assert "Chapter 1: Arrival  (chapter 1, section 2)" in out
    assert "Interlude  (section 4)" in out


# -- read / chapters / check --------------------------------------------------

def test_read_includes_nested_sections_and_refuses_later_chapters(
        flat: Builder, capsys: Capture) -> None:
    book = flat()
    out = run(capsys, "read", book, "chapter 2")[1]
    assert "tattoo" in out and "moon" in out and "Continuation" in out
    assert "reading progress ends here" not in out  # a place, not a read up to the progress
    code, _, err = run(capsys, "read", book, "chapter 3")
    assert code == 2 and "--allow-spoilers" in err
    assert "Gilliam" in run(capsys, "read", book, "ch3", "--allow-spoilers")[1]


def test_read_a_paragraph_range(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "read", flat(), "--from", "section 3 paragraph 2",
              "--to", "section 3 paragraph 2")[1]
    assert "tattoo" in out and "¶1" not in out
    assert "moon" not in out  # a --to paragraph stops inside that section


def test_read_a_place_from_a_paragraph_reads_to_its_end(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "read", flat(progress("finished")), "chapter 2 paragraph 2")[1]
    assert "tattoo" in out and "moon" in out and "¶1  Chapter 2" not in out
    assert "Gilliam" not in out


def test_read_from_a_paragraph_on_through_later_chapters(
        flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "read", flat(progress("finished")), "--from", "chapter 2 paragraph 2",
              "--to", "chapter 3")[1]
    assert "tattoo" in out and "moon" in out and "Gilliam" in out
    assert "¶1  Chapter 2" not in out and "Quiet" not in out


def test_read_needs_a_place_or_a_range(flat: Builder, capsys: Capture) -> None:
    book = flat()
    code, _, err = run(capsys, "read", book)
    assert code == 2 and "Say what to read" in err
    code, _, err = run(capsys, "read", book, "chapter 1", "--from", "chapter 2")
    assert code == 2 and "not both" in err


def test_chapters_hides_later_sections(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "chapters", flat())[1]
    assert "Chapter 2: The Garden" in out
    assert "Betrayal" not in out and "3 later sections hidden" in out


def test_check_prints_no_titles(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "check", flat())[1]
    assert "Result: OK" in out and "Reading progress:             through chapter 2" in out
    assert "Betrayal" not in out and "Garden" not in out


# -- parts with restarting chapter numbers ------------------------------------

def test_part_aware_progress(parts: Builder, capsys: Capture) -> None:
    book = parts(progress("reading", chapter="1", part="2"))
    out = run(capsys, "search", book, "gamma")[1]
    assert "**gamma**" in out and "through part 2 chapter 1" in out
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


def test_part_in_places_for_narrowing_and_read(parts: Builder, capsys: Capture) -> None:
    book = parts(progress("reading", chapter="2", part="2"))
    out = run(capsys, "search", book, "alpha|beta", "--regex", "--to", "part 1 chapter 1")[1]
    assert "**alpha**" in out and "**beta**" not in out
    assert "gamma" in run(capsys, "read", book, "pt2 ch1")[1]
    code, _, err = run(capsys, "read", book, "chapter 1")
    assert code == 2 and "restarts in each part" in err


def test_part_goes_with_a_chapter(parts: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", parts(progress("finished")), "alpha", "--to", "part 1")
    assert code == 2 and "a part goes with a chapter" in err


def test_check_reports_restarting_numbering(parts: Builder, capsys: Capture) -> None:
    out = run(capsys, "check", parts(progress("not started")))[1]
    assert "restarts in each part" in out
    assert "Duplicate chapter numbers:    none" in out


# -- series directories -------------------------------------------------------

def test_series_story_point_reads_earlier_volumes_in_full(
        series: Builder, capsys: Capture) -> None:
    root = series(progress("reading", chapter="1", part="1", volume="2"))
    out = run(capsys, "search", root, "final|alpha|beta", "--regex")[1]
    assert "reading progress: through volume 2 part 1 chapter 1" in out
    assert "Volume 1: Flat Book: whole volume" in out
    assert "Volume 2: Parts Book: through part 1 chapter 1" in out
    assert "Flat Book · Chapter 5: Ending  (volume 1 chapter 5, section 7)" in out
    assert "**alpha**" in out and "**beta**" not in out


def test_series_later_volumes_are_excluded(series: Builder, capsys: Capture) -> None:
    root = series(progress("reading", chapter="2", volume="1"))
    out = run(capsys, "search", root, "moon|alpha", "--regex")[1]
    assert "**moon**" in out and "**alpha**" not in out
    assert "Volume 2: Parts Book: excluded" in out


def test_series_narrowing_excludes_later_volumes(series: Builder, capsys: Capture) -> None:
    root = series(progress("finished", volume="2"))
    out = run(capsys, "search", root, "gate|final|alpha", "--regex",
              "--to", "volume 1 chapter 1")[1]
    assert "**gate**" in out and "**final**" not in out and "**alpha**" not in out
    assert "Volume 2: Parts Book: excluded" in out


def test_series_place_past_progress_needs_permission(series: Builder, capsys: Capture) -> None:
    root = series(progress("reading", chapter="1", part="1", volume="2"))
    code, _, err = run(capsys, "search", root, "delta", "--to", "volume 2")
    assert code == 2 and "through volume 2 part 1 chapter 1" in err
    out = run(capsys, "search", root, "delta", "--to", "v2", "--allow-spoilers")[1]
    assert "**delta**" in out


def test_from_a_volume_leaves_out_the_earlier_ones(series: Builder, capsys: Capture) -> None:
    root = series(progress("reading", chapter="1", part="1", volume="2"))
    out = run(capsys, "search", root, "gate|alpha", "--regex", "--from", "volume 2")[1]
    assert "**alpha**" in out and "**gate**" not in out
    assert "Volume 1: Flat Book: excluded" in out


def test_series_places_name_their_volume(series: Builder, capsys: Capture) -> None:
    root = series(progress("not started", volume="2"))
    code, _, err = run(capsys, "search", root, "gate", "--to", "chapter 1")
    assert code == 2 and 'e.g. "volume 1 chapter 1"' in err
    code, _, err = run(capsys, "read", root, "chapter 1")
    assert code == 2 and 'e.g. "volume 1 chapter 1"' in err
    assert "gate" in run(capsys, "read", root, "volume 1 chapter 1")[1]


def test_to_without_a_volume_is_in_the_volume_of_from(series: Builder, capsys: Capture) -> None:
    root = series(progress("finished", volume="2"))
    out = run(capsys, "search", root, "tattoo|Gilliam|Quiet", "--regex",
              "--from", "volume 1 chapter 2", "--to", "chapter 3")[1]
    assert "**tattoo**" in out and "**Gilliam**" in out and "**Quiet**" not in out


def test_series_progress_needs_book(series: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", series(progress("reading", chapter="2")), "gate")
    assert code == 2 and "set 'volume'" in err


def test_series_progress_book_may_be_one_past_the_imported_volumes(
        series: Builder, capsys: Capture) -> None:
    out = run(capsys, "search", series(progress("reading", chapter="3", volume="3")), "delta")[1]
    assert "**delta**" in out  # volumes 1 and 2 count as read; volume 3 isn't imported yet
    code, _, err = run(capsys, "search", series(progress("reading", volume="9")), "delta")
    assert code == 2 and "past the imported volumes" in err


def test_standalone_progress_rejects_book(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(progress("reading", chapter="2", volume="1")), "gate")
    assert code == 2 and "only used in a series" in err


def test_volume_directory_inside_series_uses_series_progress(
        series: Builder, capsys: Capture) -> None:
    root = Path(series(progress("reading", chapter="1", part="2", volume="2")))
    volume = str(root / "volumes" / "02-parts")
    out = run(capsys, "search", volume, "gamma|delta|final", "--regex")[1]
    assert "**gamma**" in out and "**delta**" not in out and "**final**" not in out
    assert "alpha" in run(capsys, "read", volume, "part 1 chapter 1")[1]
    assert "alpha" in run(capsys, "read", volume, "volume 2 part 1 chapter 1")[1]
    code, _, err = run(capsys, "read", volume, "volume 1 chapter 1")
    assert code == 2 and "volume 2 only" in err


def test_a_later_volume_directory_is_past_the_progress(series: Builder, capsys: Capture) -> None:
    root = Path(series(progress("reading", chapter="2", volume="1")))
    code, _, err = run(capsys, "search", str(root / "volumes" / "02-parts"), "alpha")
    assert code == 2 and "Nothing here is within the reading progress" in err


@pytest.mark.parametrize("cwd, target", [("volumes", "02-parts"), ("volumes/02-parts", ".")])
def test_relative_volume_path_still_finds_the_series(
        series: Builder, capsys: Capture, monkeypatch: pytest.MonkeyPatch,
        cwd: str, target: str) -> None:
    root = Path(series(progress("reading", chapter="1", part="2", volume="2")))
    monkeypatch.chdir(root / cwd)
    out = run(capsys, "search", target, "gamma|delta", "--regex")[1]
    assert "**gamma**" in out and "**delta**" not in out


def test_series_check_reports_each_volume(series: Builder, capsys: Capture) -> None:
    out = run(capsys, "check", series(progress("not started", volume="2")))[1]
    assert "volume 2, not started" in out
    assert "## Volume 1" in out and "Reading progress:             whole volume" in out
    assert "## Volume 2" in out and "Reading progress:             not read yet" in out


def test_series_check_reports_invalid_progress(series: Builder, capsys: Capture) -> None:
    out = run(capsys, "check", series("---\nstatus: reading\nchpter: 2\n---\n"))[1]
    assert "Reading progress: ERROR" in out and "chpter: unknown field" in out


def test_series_rejects_volume_folder_without_prefix(tmp_path: Path, capsys: Capture) -> None:
    make_book(tmp_path / "series" / "volumes" / "flat", "Flat Book", FLAT_FILES, FLAT_TOC)
    (tmp_path / "series" / "reading-progress.md").write_text(
        progress("finished", volume="1"), encoding="utf-8")
    code, _, err = run(capsys, "check", str(tmp_path / "series"))
    assert code == 2 and "volume prefix" in err


# -- ranges, output budget and paging -----------------------------------------

def test_from_skips_earlier_chapters(flat: Builder, capsys: Capture) -> None:
    book = flat(progress("finished"))
    out = run(capsys, "search", book, "gate|Gilliam", "--regex", "--from", "chapter 3")[1]
    assert "range: from chapter 3" in out
    assert "**Gilliam**" in out and "**gate**" not in out


def test_from_and_to_make_a_range(flat: Builder, capsys: Capture) -> None:
    book = flat(progress("finished"))
    out = run(capsys, "search", book, "tattoo|Gilliam|Quiet|final", "--regex",
              "--from", "chapter 2", "--to", "chapter 3")[1]
    assert "range: from chapter 2 through chapter 3" in out
    assert "**tattoo**" in out and "**Gilliam**" in out
    assert "**Quiet**" not in out and "**final**" not in out


def test_to_before_from_is_an_error(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(progress("finished")), "gate",
                       "--from", "chapter 4", "--to", "chapter 2")
    assert code == 2 and "--to must not come before --from" in err


def test_from_never_widens_past_progress(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(), "Gilliam", "--from", "chapter 3")
    assert code == 2 and "--from is past the reading progress" in err


def test_all_and_to_do_not_mix(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "search", flat(progress("finished")), "gate", "--all",
                       "--to", "chapter 2")
    assert code == 2 and "--all cannot be combined with --to" in err


def test_chapters_listing_honours_from(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "chapters", flat(progress("finished")), "--from", "chapter 4")[1]
    assert "Chapter 4: Aftermath" in out and "Chapter 2: The Garden" not in out


def test_output_budget_prints_next_page_command_that_resumes(
        flat: Builder, capsys: Capture) -> None:
    book = flat(progress("finished"))
    out = run(capsys, "search", book, "a", "--case-sensitive", "--from", "chapter 1",
              "--max-chars", "1")[1]  # one hit per page
    assert "Output limit reached" in out and "Remaining matches by section" in out
    argv = next_page(out)
    assert argv[:3] == ["search", Path(book).as_posix(), "a"]
    assert "--case-sensitive" in argv and "--max-chars" in argv
    assert argv[argv.index("--from") + 1] != "chapter 1"  # the next page starts later
    resumed = run(capsys, *argv)[1]
    first_hit = [line for line in resumed.splitlines() if line.startswith("  ¶")][0]
    assert first_hit not in out  # the next page starts with a hit not shown before


def test_next_page_keeps_to(series: Builder, capsys: Capture) -> None:
    root = series(progress("finished", volume="2"))
    out = run(capsys, "search", root, "e", "--from", "volume 1 chapter 1", "--to", "ch3",
              "--max-chars", "1")[1]
    argv = next_page(out)
    assert argv[argv.index("--to") + 1] == "ch3"
    assert argv[argv.index("--from") + 1].startswith("volume 1 ")


@pytest.mark.parametrize("arg, quoted", [
    ("Valka", "Valka"),
    ("books/jane-doe/glass-crown", "books/jane-doe/glass-crown"),
    ("the Order", "'the Order'"),
    ("volume 1 chapter 3", "'volume 1 chapter 3'"),
    (r"(Anaïs).{0,300}(hair|eyes)$", r"'(Anaïs).{0,300}(hair|eyes)$'"),
    ("Anaïs's", '"Anaïs\'s"'),
])
def test_printed_arguments_are_quoted_for_the_shell(arg: str, quoted: str) -> None:
    assert shell_quote(arg) == quoted
    assert shlex.split(quoted) == [arg]


def test_capture_groups_limit_highlighting(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "search", flat(), r"(Valka).{0,40}(fine)", "--regex")[1]
    assert "**Valka**" in out and "**fine**" in out and "**Valka’s tattoo" not in out


def test_word_applies_to_regex_ends(flat: Builder, capsys: Capture) -> None:
    book = flat()
    assert "No matches" in run(capsys, "search", book, "Val|gat", "--regex", "--word")[1]
    assert "**gate**" in run(capsys, "search", book, "Valka|gate", "--regex", "--word")[1]


# -- read paging and reading on -------------------------------------------------

def _read_all(capsys: Capture, *argv: str) -> tuple[list[str], list[list[str]]]:
    """Follow the next-page commands; return the paragraphs seen and the commands run."""
    seen: list[str] = []
    commands: list[list[str]] = []
    out = run(capsys, *argv)[1]
    for _ in range(30):
        seen += [line for line in out.splitlines() if line.startswith("¶")]
        if "Output limit reached" not in out:
            break
        commands.append(next_page(out))
        out = run(capsys, *commands[-1])[1]
    return seen, commands


def test_read_pages_through_a_chapter_with_nested_sections(flat: Builder, capsys: Capture) -> None:
    # chapter 2 = sections 3 (two paragraphs) and 4 (the nested interlude)
    seen, commands = _read_all(capsys, "read", flat(), "chapter 2", "--max-chars", "1")
    text = " ".join(seen)
    assert "tattoo" in text and "moon" in text and "Continuation" in text
    assert len(seen) == len(set(seen))  # nothing repeated, nothing skipped
    assert all(argv[argv.index("--to") + 1] == "chapter 2" for argv in commands)


def test_read_paging_with_a_paragraph_range(flat: Builder, capsys: Capture) -> None:
    book = flat()
    out = run(capsys, "read", book, "--from", "section 3 paragraph 1",
              "--to", "section 3 paragraph 2", "--max-chars", "1")[1]
    argv = next_page(out)
    assert argv[argv.index("--from") + 1] == "chapter 2 paragraph 2"
    assert argv[argv.index("--to") + 1] == "section 3 paragraph 2"
    assert "tattoo" in run(capsys, *argv)[1]


def test_read_from_goes_on_to_the_reading_progress(flat: Builder, capsys: Capture) -> None:
    book = flat()  # progress: chapter 2
    out = run(capsys, "read", book, "--from", "section 3")[1]
    assert "tattoo" in out and "moon" in out and "Continuation" in out
    assert "gate" not in out and "Gilliam" not in out
    assert "[The reading progress ends here.]" in out
    (Path(book) / "reading-progress.md").write_text(progress("finished"), encoding="utf-8")
    out = run(capsys, "read", book, "--from", "chapter 5")[1]
    assert "final scene" in out and "reading progress ends here" not in out


def test_read_from_pages_on(flat: Builder, capsys: Capture) -> None:
    seen, commands = _read_all(capsys, "read", flat(progress("finished")),
                               "--from", "section 5", "--max-chars", "1")
    text = " ".join(seen)
    assert "Gilliam" in text and "Quiet" in text and "final scene" in text
    assert "tattoo" not in text and len(seen) == len(set(seen))
    assert commands and all("--to" not in argv for argv in commands)


def test_read_to_a_later_chapter(flat: Builder, capsys: Capture) -> None:
    out = run(capsys, "read", flat(progress("finished")), "--from", "chapter 1",
              "--to", "chapter 4")[1]
    for text in ("gate", "tattoo", "moon", "Continuation", "Gilliam", "Quiet"):
        assert text in out
    assert "final scene" not in out


def test_read_past_progress_needs_permission(flat: Builder, capsys: Capture) -> None:
    book = flat()  # progress: chapter 2
    code, _, err = run(capsys, "read", book, "--from", "chapter 1", "--to", "chapter 4")
    assert code == 2 and "--allow-spoilers" in err
    out = run(capsys, "read", book, "--from", "chapter 1", "--to", "chapter 4",
              "--allow-spoilers")[1]
    assert "Gilliam" in out and "Quiet" in out


def test_read_pages_through_a_whole_book(flat: Builder, capsys: Capture) -> None:
    seen, commands = _read_all(capsys, "read", flat(progress("finished")),
                               "--from", "chapter 1", "--to", "section 7", "--max-chars", "1")
    text = " ".join(seen)
    assert "gate" in text and "moon" in text and "final scene" in text
    assert len(seen) == len(set(seen))  # nothing repeated, nothing skipped
    assert all(argv[argv.index("--to") + 1] == "section 7" for argv in commands)


def test_read_to_a_chapter_in_a_later_part(parts: Builder, capsys: Capture) -> None:
    out = run(capsys, "read", parts(progress("finished")), "--from", "part 1 chapter 2",
              "--to", "part 2 chapter 1")[1]
    assert "beta" in out and "part two page" in out and "gamma" in out
    assert "alpha" not in out and "delta" not in out


def test_read_to_must_follow_from(flat: Builder, capsys: Capture) -> None:
    code, _, err = run(capsys, "read", flat(progress("finished")), "--from", "chapter 3",
                       "--to", "chapter 1")
    assert code == 2 and "--to must not come before --from" in err


def test_read_across_volumes(series: Builder, capsys: Capture) -> None:
    out = run(capsys, "read", series(progress("finished", volume="2")),
              "--from", "volume 1 chapter 5", "--to", "volume 2 part 1 chapter 1")[1]
    assert "final scene" in out and "part one page" in out and "alpha" in out
    assert "beta" not in out and "Quiet" not in out


# -- libraries from before volumes/ ---------------------------------------------

def test_a_series_with_books_folder_says_to_rename_it(tmp_path: Path, capsys: Capture) -> None:
    root = tmp_path / "series"
    make_book(root / "books" / "01-flat", "Flat Book", FLAT_FILES, FLAT_TOC)
    (root / "reading-progress.md").write_text(progress("finished", volume="1"), encoding="utf-8")
    for target in (root, root / "books" / "01-flat"):
        code, _, err = run(capsys, "check", str(target))
        assert code == 2 and "Rename that folder to volumes/" in err
