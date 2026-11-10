"""book-library check: each rule, on a clean synthetic library with one thing broken."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from book_companion.core.errors import BookError
from book_companion.library.check import check_library
from book_companion.library.cli import main
from book_companion.library.findings import RULES, Code, Severity, relative
from helpers import (
    FLAT_FILES,
    FLAT_TOC,
    PARTS_FILES,
    PARTS_TOC,
    Capture,
    make_book,
    make_library,
    make_volume,
    progress,
    toc_labels,
    write,
)

SERIES = "books/jane-doe/night-saga"
FIRST = f"{SERIES}/volumes/01-first-night"
SECOND = f"{SERIES}/volumes/02-second-night"
MIRA = f"{SERIES}/characters/mira-vale"
LONE = "books/jane-doe/standalone/lone-star"
CLEAN = {
    (Code.PENDING_PROMPT, f"{MIRA}/pics/mira-armored-v01.prompt.md"),
    (Code.INCOMING, "_incoming/epubs/third-night.epub"),
}

type Found = set[tuple[Code, str]]


@pytest.fixture
def library(tmp_path: Path) -> Path:
    return make_library(tmp_path / "library")


def problems(root: Path) -> Found:
    """What the check finds besides what it finds in the clean library."""
    report = check_library(root)
    return {(finding.code, relative(root, finding.path)) for finding in report.findings} - CLEAN


def problem_text(root: Path, code: Code) -> str:
    return next(f"{f.problem} {f.fix}" for f in check_library(root).findings if f.code is code)


def run(capsys: Capture, *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_every_code_has_a_rule() -> None:
    assert set(RULES) == set(Code)


def test_help_lists_every_rule_by_severity(capsys: Capture) -> None:
    with pytest.raises(SystemExit):
        main(["check", "--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    for rule in RULES.values():
        assert rule.description in help_text
    # each rule under its own severity's heading
    order = ["errors: ", RULES[Code.EMPTY_FILE].description, "warnings: ",
             RULES[Code.SLUG].description, "waiting: ", RULES[Code.INCOMING].description]
    positions = [help_text.index(text) for text in order]
    assert positions == sorted(positions)


def test_clean_library_only_has_things_waiting(library: Path) -> None:
    report = check_library(library)
    assert {(f.code, relative(library, f.path)) for f in report.findings} == CLEAN
    assert {f.severity for f in report.findings} == {Severity.WAITING}
    assert [group.name for group in report.groups] == [SERIES, LONE, "_incoming"]


# -- book files ---------------------------------------------------------------

def test_missing_book_files_are_errors(library: Path) -> None:
    (library / FIRST / "book.txt").unlink()
    (library / LONE / "source.epub").unlink()
    (library / SECOND / "metadata.md").unlink()
    assert problems(library) == {
        (Code.MISSING_FILE, f"{FIRST}/book.txt"),
        (Code.MISSING_FILE, f"{LONE}/source.epub"),
        (Code.MISSING_FILE, f"{SECOND}/metadata.md"),
    }


def test_a_missing_conversion_suggests_the_command_to_run(library: Path) -> None:
    (library / FIRST / "book.txt").unlink()
    fix = problem_text(library, Code.MISSING_FILE)
    assert (f"book-convert {FIRST}/source.epub {FIRST}/book.txt --force" in fix
            and "ask the user first" in fix)  # book-html/ is still there

    shutil.rmtree(library / FIRST / "book-html")
    fix = problem_text(library, Code.MISSING_FILE)
    assert fix.endswith(f"Convert the EPUB: book-convert {FIRST}/source.epub {FIRST}/book.txt")


def test_an_empty_text_is_an_error(library: Path) -> None:
    (library / LONE / "book.txt").write_text("", encoding="utf-8")
    assert problems(library) == {(Code.EMPTY_FILE, f"{LONE}/book.txt")}


def test_a_volume_without_book_html_skips_the_progress_check(library: Path) -> None:
    shutil.rmtree(library / SECOND / "book-html")  # the volume being read
    assert problems(library) == {(Code.MISSING_FILE, f"{SECOND}/book-html")}


def test_an_unreadable_book_is_an_error(library: Path) -> None:
    (library / FIRST / "book-html" / "toc.ncx").unlink()
    assert problems(library) == {(Code.UNREADABLE_BOOK, f"{FIRST}/book-html")}
    assert "No toc.ncx found" in problem_text(library, Code.UNREADABLE_BOOK)


def test_structure_caveats_are_warnings_without_titles(library: Path) -> None:
    shutil.rmtree(library / LONE / "book-html")
    make_book(library / LONE, "Parts Book", PARTS_FILES, PARTS_TOC)  # no contents page
    assert problems(library) == {(Code.STRUCTURE, f"{LONE}/book-html")}
    assert "no contents page detected" in problem_text(library, Code.STRUCTURE)


def test_a_progress_file_inside_a_volume_is_a_warning(library: Path) -> None:
    write(library / FIRST / "reading-progress.md", progress("finished"))
    assert problems(library) == {(Code.STRAY_PROGRESS, f"{FIRST}/reading-progress.md")}


# -- reading progress ---------------------------------------------------------

def test_a_missing_progress_file_is_an_error(library: Path) -> None:
    (library / SERIES / "reading-progress.md").unlink()
    assert problems(library) == {(Code.NO_PROGRESS, f"{SERIES}/reading-progress.md")}


@pytest.mark.parametrize("text, message", [
    ("---\nstatus: reading\nchpter: 2\n---\n", "chpter: unknown field"),
    ("---\nstatus: reading\nchapter 2\n---\n", "line 3: expected 'key: value'."),
    ("# Reading progress\n", "reading-progress.md must start with a '---' front-matter block"),
])
def test_invalid_front_matter_is_an_error(library: Path, text: str, message: str) -> None:
    write(library / SERIES / "reading-progress.md", text)
    assert problems(library) == {(Code.BAD_PROGRESS, f"{SERIES}/reading-progress.md")}
    detail = problem_text(library, Code.BAD_PROGRESS)
    assert detail.startswith(message) and str(library) not in detail


@pytest.mark.parametrize("text, message", [
    (progress("reading", volume="2", part="1", chapter="9"), "No section is numbered part 1, "
                                                             "chapter 9"),
    (progress("reading", volume="2", chapter="1"), "Chapter 1 appears in parts 1, 2"),
    (progress("reading", volume="4"), "volume 4 is past the imported volumes"),
])
def test_progress_past_the_books_is_an_error(library: Path, text: str, message: str) -> None:
    write(library / SERIES / "reading-progress.md", text)
    assert problems(library) == {(Code.BAD_PROGRESS, f"{SERIES}/reading-progress.md")}
    assert problem_text(library, Code.BAD_PROGRESS).startswith(message)


def test_a_volume_in_a_standalone_progress_is_an_error(library: Path) -> None:
    write(library / LONE / "reading-progress.md", progress("finished", volume="1"))
    assert problems(library) == {(Code.BAD_PROGRESS, f"{LONE}/reading-progress.md")}


def test_the_next_volume_may_be_read_before_it_is_imported(library: Path) -> None:
    write(library / SERIES / "reading-progress.md", progress("reading", volume="3"))
    assert problems(library) == set()


# -- book memory --------------------------------------------------------------

def test_a_memory_of_an_unfinished_book_is_a_spoiler_risk(library: Path) -> None:
    write(library / SERIES / "reading-progress.md", progress("reading", volume="1", chapter="2"))
    write(library / LONE / "reading-progress.md", progress("reading", chapter="2"))
    assert problems(library) == {
        (Code.EARLY_MEMORY, f"{FIRST}/chapters.md"),
        (Code.EARLY_MEMORY, f"{FIRST}/reference.md"),
        (Code.EARLY_MEMORY, f"{LONE}/chapters.md"),  # review.md may follow a stopped read
    }


def test_memory_is_not_judged_by_invalid_progress(library: Path) -> None:
    write(library / SERIES / "reading-progress.md", "---\nstatus: maybe\n---\n")
    assert problems(library) == {(Code.BAD_PROGRESS, f"{SERIES}/reading-progress.md")}


# -- layout -------------------------------------------------------------------

def test_book_folders_outside_volumes_are_leftovers(library: Path) -> None:
    make_volume(library / "books" / "jane-doe" / "old-book", "Old", FLAT_FILES, FLAT_TOC)
    make_volume(library / SERIES / "03-third-night", "Third", FLAT_FILES, FLAT_TOC)
    assert problems(library) == {
        (Code.LEFTOVER_BOOK, "books/jane-doe/old-book"),
        (Code.LEFTOVER_BOOK, f"{SERIES}/03-third-night"),
    }


def test_a_series_books_folder_is_the_old_name_of_volumes(library: Path) -> None:
    (library / SERIES / "volumes").rename(library / SERIES / "books")
    assert problems(library) == {
        (Code.OLD_BOOKS_FOLDER, f"{SERIES}/books"),
        (Code.NO_VOLUMES, f"{SERIES}/volumes"),
    }


def test_an_unknown_folder_in_an_author_folder_is_a_warning(library: Path) -> None:
    write(library / "books" / "jane-doe" / "misc" / "notes.md", "notes")
    assert problems(library) == {(Code.UNKNOWN_FOLDER, "books/jane-doe/misc")}
    assert check_library(library).groups[0].name == "books"


def test_volume_numbers_must_be_there_and_unique(library: Path) -> None:
    make_volume(library / SERIES / "volumes" / "third-night", "Third", FLAT_FILES, FLAT_TOC)
    make_volume(library / SERIES / "volumes" / "02-again", "Again", FLAT_FILES, FLAT_TOC)
    assert problems(library) == {
        (Code.VOLUME_NUMBER, f"{SERIES}/volumes/third-night"),
        (Code.VOLUME_NUMBER, f"{SERIES}/volumes/02-second-night"),  # sorted after 02-again
    }


def test_folder_names_should_be_slugs(library: Path) -> None:
    (library / MIRA).rename(library / SERIES / "characters" / "Mira Valë")
    (library / SECOND).rename(library / SERIES / "volumes" / "02-Second_Night")
    assert problems(library) == {
        (Code.SLUG, f"{SERIES}/characters/Mira Valë"),
        (Code.SLUG, f"{SERIES}/volumes/02-Second_Night"),
        (Code.PENDING_PROMPT, f"{SERIES}/characters/Mira Valë/pics/mira-armored-v01.prompt.md"),
    }
    fixes = [f.fix for f in check_library(library).findings if f.code is Code.SLUG]
    assert fixes == ["Rename it 02-second-night, if the user agrees.",
                     "Rename it mira-vale, if the user agrees."]


# -- entities -----------------------------------------------------------------

def test_entity_files(library: Path) -> None:
    (library / SERIES / "locations" / "black-tower" / "description.md").unlink()
    (library / MIRA / "pics" / "mira-portrait-v01.prompt.md").unlink()
    write(library / MIRA / "pics" / "notes.txt", "stray")
    write(library / LONE / "entities" / "characters" / "rook" / "pics" / "rook-v01.prompt.md",
          "# Image prompt: Rook\n")
    assert problems(library) == {
        (Code.NO_DESCRIPTION, f"{SERIES}/locations/black-tower"),
        (Code.IMAGE_WITHOUT_PROMPT, f"{MIRA}/pics/mira-portrait-v01.png"),
        (Code.STRAY_FILE, f"{MIRA}/pics/notes.txt"),
        (Code.NO_DESCRIPTION, f"{LONE}/entities/characters/rook"),
        (Code.PENDING_PROMPT, f"{LONE}/entities/characters/rook/pics/rook-v01.prompt.md"),
    }


# -- _incoming/ ---------------------------------------------------------------

def test_incoming_files_wait_and_strays_are_warnings(library: Path) -> None:
    (library / "_incoming" / "images" / "portrait.png").write_bytes(b"\x89PNG fake")
    write(library / "_incoming" / "epubs" / "readme.txt", "not an epub")
    (library / "_incoming" / "loose.epub").write_bytes(b"PK")
    assert problems(library) == {
        (Code.INCOMING, "_incoming/images/portrait.png"),
        (Code.STRAY_FILE, "_incoming/epubs/readme.txt"),
        (Code.STRAY_FILE, "_incoming/loose.epub"),
    }


# -- command line -------------------------------------------------------------

def test_cli_reports_each_series_and_exits_0_without_errors(library: Path,
                                                           capsys: Capture) -> None:
    code, out, _ = run(capsys, "check", str(library))
    assert code == 0
    assert f"## {LONE}\n  ok\n" in out
    assert (f"## {SERIES}\n  waiting  {MIRA}/pics/mira-armored-v01.prompt.md: a prompt "
            "prepared; its image is not imported yet.") in out
    assert ("  waiting  _incoming/epubs/third-night.epub: an EPUB waiting to be imported. "
            "Import it with book-import.") in out
    assert out.rstrip().endswith("Result: 0 errors, 0 warnings, 2 waiting")


def test_cli_exits_1_on_errors_but_not_on_warnings(library: Path, capsys: Capture) -> None:
    (library / SERIES / "locations" / "black-tower" / "description.md").unlink()
    assert run(capsys, "check", str(library))[0] == 0
    (library / FIRST / "metadata.md").unlink()
    code, out, _ = run(capsys, "check", str(library))
    assert code == 1
    assert f"  error    {FIRST}/metadata.md: missing." in out
    assert "Result: 1 error, 1 warning, 2 waiting" in out


def test_cli_lists_errors_first_in_each_group(library: Path, capsys: Capture) -> None:
    (library / SERIES / "locations" / "black-tower" / "description.md").unlink()  # warning
    (library / FIRST / "metadata.md").unlink()  # error, found later in the walk
    out = run(capsys, "check", str(library))[1]
    severities = [line.split()[0] for line in out.split(f"## {SERIES}\n")[1].split("\n\n")[0]
                  .splitlines()]
    assert severities == ["error", "warning", "waiting"]


def test_cli_never_shows_titles_or_text(library: Path, capsys: Capture) -> None:
    for book in (FIRST, SECOND):
        (library / book / "book.txt").unlink()  # findings about every book
    out = run(capsys, "check", str(library))[1]
    labels = toc_labels(FLAT_TOC) + toc_labels(PARTS_TOC)
    assert not [label for label in labels if label.split(": ")[-1] in out]
    assert "Anaïs" not in out and "moon" not in out


def test_cli_needs_a_library(tmp_path: Path, capsys: Capture) -> None:
    code, _, err = run(capsys, "check", str(tmp_path))
    assert code == 2 and "has no books/ folder" in err
    with pytest.raises(BookError):
        check_library(tmp_path)
