"""Places in a book, written in words: "volume 2 part 1 chapter 3 paragraph 6".

Every word also has a short form ("v2 pt1 ch3 p6"). A place resolves, against a
target's tables of contents, to a span of positions in reading order.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, replace

from book_companion.core.errors import BookError
from book_companion.core.library import Target, Volume
from book_companion.core.structure import Section, find_chapter

FORMS = '"volume 2 part 1 chapter 3 paragraph 6" or "v2 pt1 ch3 p6"'

_SHORT = {"v": "volume", "pt": "part", "ch": "chapter", "s": "section", "p": "paragraph"}
_RANK = {"volume": 0, "part": 1, "chapter": 2, "section": 2, "paragraph": 3}
_TOKEN = re.compile(r"(volume|part|chapter|section|paragraph) ([1-9]\d*)"
                    r"|(pt|ch|v|s|p)([1-9]\d*)")

END = sys.maxsize  # a paragraph number that means "through the end of the section"


@dataclass(frozen=True)
class Place:
    """A place as written; the parts left out are None."""

    volume: int | None = None
    part: int | None = None
    chapter: int | None = None
    section: int | None = None
    paragraph: int | None = None

    def __str__(self) -> str:
        """The full form, e.g. 'volume 2 part 1 chapter 3'."""
        words = (("volume", self.volume), ("part", self.part), ("chapter", self.chapter),
                 ("section", self.section), ("paragraph", self.paragraph))
        return " ".join(f"{name} {value}" for name, value in words if value is not None)


def parse_place(text: str) -> Place:
    """Read a place in full or short words, in order: volume, part, chapter or section,
    paragraph. A paragraph without a chapter or section is in the front matter."""
    values: dict[str, int] = {}
    position, rank = 0, -1
    while True:
        match = _TOKEN.match(text, position)
        if match is None:
            raise BookError(f"Cannot read the place {text!r}. Write it like {FORMS}.")
        name = match.group(1) or _SHORT[match.group(3)]
        if _RANK[name] <= rank:
            raise BookError(f"In the place {text!r}, give volume, part, chapter or section, "
                            "and paragraph in that order, each at most once.")
        values[name] = int(match.group(2) or match.group(4))
        rank = _RANK[name]
        position = match.end()
        if position == len(text):
            break
        if text[position] != " ":
            raise BookError(f"Cannot read the place {text!r}. Write it like {FORMS}.")
        position += 1
    if "part" in values and "chapter" not in values:
        raise BookError(f"In the place {text!r}, a part goes with a chapter, e.g. "
                        '"volume 2 part 1 chapter 3".')
    return Place(**values)


@dataclass(frozen=True, order=True)
class Position:
    """A point in reading order within a target."""

    volume: int  # index of the volume in target.volumes
    section: int  # section number; 0 = the front matter, before the first contents item
    paragraph: int  # 1-based; END = the last paragraph


@dataclass(frozen=True)
class Span:
    """Where a place begins and ends."""

    start: Position
    end: Position


def resolve(target: Target, place: Place, volume: int | None = None) -> Span:
    """Locate a place. `volume` stands in for the volume number when the place leaves it out.

    A chapter or section covers the sections nested in it; with a paragraph, the place is
    that one paragraph; a volume alone is the whole volume.
    """
    chosen = _volume(target, place, volume)
    index = target.volumes.index(chosen)
    book = chosen.book
    section: Section | None = None
    if place.chapter is not None:
        section = find_chapter(book, place.chapter, place.part)
    elif place.section is not None:
        section = book.section(place.section)
    if place.paragraph is not None:
        paragraphs = section.paragraphs if section is not None else book.front
        if place.paragraph > len(paragraphs):
            where = section_place(target, chosen, section) if section is not None else None
            name = f'"{where}"' if where is not None else "The front matter"
            count = f"{len(paragraphs)} paragraph{'s' if len(paragraphs) != 1 else ''}"
            raise BookError(f"{name} has {count}; there is no paragraph {place.paragraph}.")
        point = Position(index, section.number if section is not None else 0, place.paragraph)
        return Span(point, point)
    if section is None:
        return Span(Position(index, 0, 1), Position(index, len(book.sections), END))
    return Span(Position(index, section.number, 1),
                Position(index, book.subtree_end(section), END))


def _volume(target: Target, place: Place, default: int | None) -> Volume:
    if not target.is_series:
        if place.volume is not None:
            raise BookError(f'"{place}": this is a standalone book, so leave out the volume.')
        return target.volumes[0]
    number = place.volume if place.volume is not None else default
    if number is None and target.only is None:
        raise BookError(f'"{place}": in a series directory a place names its volume, '
                        f'e.g. "{replace(place, volume=1)}".')
    return target.volume(number)


def section_place(target: Target, volume: Volume, section: Section | None,
                  paragraph: int | None = None) -> Place:
    """The place that names a section (or the front matter), as briefly as is unambiguous."""
    number = volume.number if target.is_series else None
    if section is None:
        return Place(volume=number, paragraph=paragraph)
    if section.chapter is not None:
        for part in dict.fromkeys((None, section.part)):
            try:
                if find_chapter(volume.book, section.chapter, part) is section:
                    return Place(volume=number, part=part, chapter=section.chapter,
                                 paragraph=paragraph)
            except BookError:
                continue
    return Place(volume=number, section=section.number, paragraph=paragraph)


def location(target: Target, volume: Volume, section: Section | None) -> str:
    """Heading for a block of text, ending with the place that names it."""
    prefix = f"{volume.short_title} · " if target.is_series else ""
    if section is None:
        where = f"  ({section_place(target, volume, None)})" if target.is_series else ""
        return f"{prefix}Front matter{where}"
    place = section_place(target, volume, section)
    where = str(place) if place.section is not None else f"{place}, section {section.number}"
    return f"{prefix}{section.heading}  ({where})"
