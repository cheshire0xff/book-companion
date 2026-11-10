"""The example library in examples/library: real Calibre output, kept clean."""

from __future__ import annotations

from pathlib import Path

from book_companion.library.check import check_library
from book_companion.library.findings import Code
from book_companion.search.cli import main as search
from helpers import Capture

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "library"
SERIES = str(EXAMPLE / "books" / "odile-fenwright" / "salt-lanterns")
TWIST = "bell-ringer"  # only in volume 2 chapter 5, past the reading progress


def run(capsys: Capture, *argv: str) -> tuple[int, str, str]:
    code = search(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_the_example_library_checks_clean() -> None:
    findings = check_library(EXAMPLE).findings
    assert [finding.code for finding in findings] == [Code.PENDING_PROMPT] * 2


def test_the_example_series_structure(capsys: Capture) -> None:
    code, out, _ = run(capsys, "check", SERIES)
    assert code == 0 and out.count("Result: OK") == 2
    assert "volume 2, reading" in out and "through chapter 3" in out
    assert "chapter numbering restarts in each part" in out  # volume 1


def test_the_example_search_finds_what_was_read(capsys: Capture) -> None:
    code, out, _ = run(capsys, "search", SERIES, "fogglass", "--count")
    assert code == 0
    assert "(volume 1 part 1 chapter 2, section 5)" in out
    assert "(volume 2 chapter 3, section 4)" in out


def test_the_example_twist_stays_behind_the_progress(capsys: Capture) -> None:
    out = run(capsys, "search", SERIES, TWIST)[1]
    assert "No matches" in out
    code, _, err = run(capsys, "search", SERIES, TWIST, "--all")
    assert code == 2 and "beyond the reading progress" in err
    code, out, _ = run(capsys, "search", SERIES, TWIST, "--all", "--allow-spoilers")
    assert code == 0 and "(volume 2 chapter 5, section 6)" in out
