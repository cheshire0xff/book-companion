"""Tests for places: parsing "volume 2 part 1 chapter 3 paragraph 6" and locating it."""

from __future__ import annotations

from pathlib import Path

import pytest

from book_companion.core.errors import BookError
from book_companion.core.places import (
    END,
    Place,
    Position,
    location,
    parse_place,
    resolve,
    section_place,
)
from book_companion.core.target import load_target
from helpers import Builder, Toc, make_book, progress


@pytest.mark.parametrize("text", [
    "volume 2 part 1 chapter 3 paragraph 6",
    "v2 pt1 ch3 p6",
    "v2 part 1 ch3 paragraph 6",
])
def test_full_and_short_forms_mean_the_same(text: str) -> None:
    assert parse_place(text) == Place(volume=2, part=1, chapter=3, paragraph=6)


@pytest.mark.parametrize("text, place", [
    ("chapter 46", Place(chapter=46)),
    ("s4", Place(section=4)),
    ("volume 2", Place(volume=2)),
    ("section 5 paragraph 3", Place(section=5, paragraph=3)),
    ("p2", Place(paragraph=2)),  # the front matter
])
def test_places_leave_parts_out(text: str, place: Place) -> None:
    assert parse_place(text) == place
    assert parse_place(str(place)) == place  # the full form reads back


@pytest.mark.parametrize("text, message", [
    ("Chapter 3", "Cannot read"),
    ("chapter 3, paragraph 2", "Cannot read"),
    ("ch 3", "Cannot read"),
    ("chapter3", "Cannot read"),
    ("chapter 03", "Cannot read"),
    ("v2  ch3", "Cannot read"),
    ("ch3 ", "Cannot read"),
    ("", "Cannot read"),
    ("chapter 3 volume 1", "in that order"),
    ("chapter 3 section 4", "in that order"),
    ("ch3 ch4", "in that order"),
    ("part 2", "a part goes with a chapter"),
    ("v1 pt2 s4", "a part goes with a chapter"),
])
def test_places_are_strict(text: str, message: str) -> None:
    with pytest.raises(BookError, match=message):
        parse_place(text)


def test_a_chapter_covers_its_nested_sections(flat: Builder) -> None:
    target = load_target(Path(flat()))  # chapter 2 = section 3, with section 4 nested in it
    assert resolve(target, Place(chapter=2)).start == Position(0, 3, 1)
    assert resolve(target, Place(chapter=2)).end == Position(0, 4, END)
    assert resolve(target, Place(section=3)).end == Position(0, 4, END)
    point = resolve(target, Place(chapter=2, paragraph=2))
    assert point.start == point.end == Position(0, 3, 2)


def test_a_volume_is_the_whole_volume(series: Builder) -> None:
    target = load_target(Path(series(progress("reading", chapter="1", volume="1"))))
    span = resolve(target, Place(volume=2))
    assert span.start == Position(1, 0, 1)
    assert span.end == Position(1, len(target.volumes[1].book.sections), END)


def test_series_places_name_their_volume(series: Builder) -> None:
    target = load_target(Path(series(progress("reading", chapter="1", volume="1"))))
    with pytest.raises(BookError, match='e.g. "volume 1 chapter 1"'):
        resolve(target, Place(chapter=1))
    assert resolve(target, Place(chapter=1), volume=1).start == Position(0, 2, 1)
    with pytest.raises(BookError, match="No volume 3"):
        resolve(target, Place(volume=3, chapter=1))


def test_standalone_places_leave_out_the_volume(flat: Builder) -> None:
    target = load_target(Path(flat()))
    with pytest.raises(BookError, match="leave out the volume"):
        resolve(target, Place(volume=1, chapter=1))


def test_a_missing_paragraph_is_an_error(flat: Builder) -> None:
    target = load_target(Path(flat()))
    with pytest.raises(BookError, match='"chapter 1" has 2 paragraphs; there is no paragraph 9'):
        resolve(target, Place(chapter=1, paragraph=9))


def test_restarting_numbering_needs_the_part(parts: Builder) -> None:
    target = load_target(Path(parts(progress("finished"))))
    with pytest.raises(BookError, match="restarts in each part"):
        resolve(target, Place(chapter=1))
    assert resolve(target, Place(part=2, chapter=1)).start.section == 5


@pytest.mark.parametrize("fixture", ["flat", "parts", "series"])
def test_every_section_has_a_place_that_finds_it(
        fixture: str, request: pytest.FixtureRequest) -> None:
    build: Builder = request.getfixturevalue(fixture)
    target = load_target(Path(build(progress("finished", volume="2" if fixture == "series"
                                              else ""))))
    for index, volume in enumerate(target.volumes):
        for section in volume.book.sections:
            place = section_place(target, volume, section)
            assert resolve(target, parse_place(str(place))).start == Position(
                index, section.number, 1)
            assert str(place) in location(target, volume, section)


def test_restarting_numbering_names_every_chapter_with_its_part(tmp_path: Path) -> None:
    toc: Toc = [("Part One", "p1.xhtml", [(f"Chapter {n}", f"a{n}.xhtml", []) for n in (1, 2, 3)]),
                ("Part Two", "p2.xhtml", [(f"Chapter {n}", f"b{n}.xhtml", []) for n in (1, 2)])]
    files = [(src, "<p>text</p>") for _, top, children in toc
             for src in [top] + [child for _, child, _ in children]]
    book = make_book(tmp_path / "restart", "Restart", files, toc, progress("finished"))
    target = load_target(book)
    volume = target.volumes[0]
    chapter_three = volume.book.sections[3]  # only part one has a chapter 3
    assert str(section_place(target, volume, chapter_three)) == "part 1 chapter 3"


def test_places_use_a_chapter_where_they_can(parts: Builder) -> None:
    target = load_target(Path(parts(progress("finished"))))
    volume = target.volumes[0]
    places = [str(section_place(target, volume, s)) for s in volume.book.sections]
    assert places == ["section 1", "part 1 chapter 1", "part 1 chapter 2",
                      "section 4", "part 2 chapter 1", "part 2 chapter 2"]
    assert location(target, volume, volume.book.sections[1]) == (
        "Chapter One: Dawn  (part 1 chapter 1, section 2)")
