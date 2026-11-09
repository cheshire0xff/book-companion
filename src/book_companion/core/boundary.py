"""What text may be used: the recorded reading progress, and ranges of places within it."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace

from book_companion.core.errors import BookError
from book_companion.core.library import Target, Volume
from book_companion.core.places import END, Position, parse_place, resolve, section_place
from book_companion.core.progress import Progress, Status
from book_companion.core.structure import Book, Section, find_chapter


def _completed(book: Book, progress: Progress) -> int | None:
    """Last section of the book being read that is completed: None = all, 0 = none."""
    if progress.status is Status.FINISHED:
        return None
    if progress.chapter is not None:
        return book.subtree_end(find_chapter(book, progress.chapter, progress.part))
    if progress.section is not None:
        return book.subtree_end(book.section(progress.section))
    return 0


def recorded_end(target: Target) -> Position | None:
    """The last position the reading progress allows; None when nothing is completed yet.

    In a series, volumes before the one being read are read in full, that volume up to
    its last completed chapter or section, and later volumes not at all.
    """
    progress = target.progress()
    path = target.progress_path
    if not target.is_series:
        if progress.book is not None:
            raise BookError(f"{path}: 'book' is only used in a series' reading-progress.md.")
        covered = [_completed(target.volumes[0].book, progress)]
    else:
        if progress.book is None:
            raise BookError(f"{path}: set 'book' to the volume number being read.")
        highest = max(v.series_number for v in target.volumes)
        if progress.book > highest + 1:
            raise BookError(f"{path}: volume {progress.book} is past the imported volumes "
                            f"(the highest is {highest}); check the number.")
        covered = [None if v.series_number < progress.book
                   else _completed(v.book, progress) if v.series_number == progress.book
                   else 0 for v in target.volumes]
    end = None
    for index, (volume, last) in enumerate(zip(target.volumes, covered, strict=True)):
        if last == 0:
            break
        end = Position(index, len(volume.book.sections) if last is None else last, END)
    return end


def whole(target: Target) -> tuple[Position, Position]:
    """The first and last positions of what the target covers."""
    if target.only is not None:
        first = last = target.volumes.index(target.volume(None))
    else:
        first, last = 0, len(target.volumes) - 1
    return Position(first, 0, 1), Position(last, len(target.volumes[last].book.sections), END)


def _section(volume: Volume, number: int) -> Section | None:
    return volume.book.sections[number - 1] if number else None


def describe(target: Target, position: Position, end: bool, with_volume: bool = True) -> str:
    """A position as a place: the start of a place, or (end=True) the end of one."""
    volume = target.volumes[position.volume]
    if end and position.section == len(volume.book.sections) and position.paragraph == END:
        if not target.is_series:
            return "the end of the book"
        return f"the end of volume {volume.number}" if with_volume else "the end of the volume"
    first = not end and position.paragraph == 1
    paragraph = None if position.paragraph == END or first else position.paragraph
    section = _section(volume, position.section)
    if end and paragraph is None and section is not None:
        # name the outermost section that ends here: chapter 2, not its nested interlude
        book = volume.book
        section = next((s for s in book.sections if book.subtree_end(s) == section.number),
                       section)
    place = section_place(target, volume, section, paragraph)
    if not with_volume:
        place = replace(place, volume=None)
    return str(place) or "the front matter"


def progress_text(target: Target, end: Position | None) -> str:
    return f"through {describe(target, end, end=True)}" if end else "nothing completed yet"


def coverage(target: Target, index: int, start: Position, end: Position,
             outside: str = "excluded") -> str:
    """What part of one volume lies between start and end."""
    if not start.volume <= index <= end.volume:
        return outside
    volume_start = Position(index, 0, 1)
    volume_end = Position(index, len(target.volumes[index].book.sections), END)
    words = []
    if start > volume_start:
        words.append(f"from {describe(target, start, end=False, with_volume=False)}")
    if end < volume_end:
        words.append(f"through {describe(target, end, end=True, with_volume=False)}")
    return " ".join(words) or ("whole volume" if target.is_series else "whole book")


@dataclass(frozen=True)
class Selection:
    """The stretch of text a command works on."""

    start: Position
    end: Position
    progress: Position | None  # the recorded reading progress
    to_progress: bool  # the end is the reading progress (no --to, --all or place)


def select(target: Target, args: argparse.Namespace, place: str | None = None) -> Selection:
    """The text between --from and --to (or one place to read), within the reading progress
    unless --allow-spoilers was given."""
    progress = recorded_end(target)
    first, last = whole(target)
    if place is not None:
        if args.from_place is not None or args.to_place is not None:
            raise BookError("Give one place to read, or --from/--to, not both.")
        where = parse_place(place)
        start = resolve(target, where).start
        end = resolve(target, replace(where, paragraph=None)).end if where.paragraph else (
            resolve(target, where).end)
        explicit = True
    else:
        start = resolve(target, parse_place(args.from_place)).start if args.from_place else first
        if getattr(args, "all", False):
            if args.to_place is not None:
                raise BookError("--all cannot be combined with --to.")
            end, explicit = last, True
        elif args.to_place is not None:
            volume = target.volumes[start.volume].number if args.from_place else None
            end, explicit = resolve(target, parse_place(args.to_place), volume).end, True
        elif progress is None:
            raise BookError("Nothing is completed yet, so no text is within the reading "
                            "boundary. Ask the user what they have read.")
        else:
            end, explicit = progress, False
    if explicit and (progress is None or end > progress) and not args.allow_spoilers:
        raise BookError(f"That goes beyond the reading progress "
                        f"({progress_text(target, progress)}). Add --allow-spoilers only if the "
                        "user explicitly allowed it for this request.")
    start, end = max(start, first), min(end, last)
    if start > end:
        if explicit:
            raise BookError("--to must not come before --from.")
        if args.from_place:
            raise BookError(f"--from is past the reading progress "
                            f"({progress_text(target, progress)}).")
        raise BookError(f"Nothing here is within the reading progress "
                        f"({progress_text(target, progress)}).")
    return Selection(start, end, progress, not explicit)


@dataclass
class Block:
    """A run of paragraphs within a selection: of one section, or of a volume's front matter."""

    volume: Volume
    section: Section | None  # None = front matter
    paragraphs: list[str]
    first: int  # index of the first paragraph within the selection
    stop: int  # index after the last one

    @property
    def number(self) -> int:
        return self.section.number if self.section is not None else 0


def blocks(target: Target, selection: Selection) -> list[Block]:
    start, end = selection.start, selection.end
    found: list[Block] = []
    for index in range(start.volume, end.volume + 1):
        volume = target.volumes[index]
        parts: list[tuple[int, Section | None, list[str]]] = [(0, None, volume.book.front)]
        parts += [(s.number, s, s.paragraphs) for s in volume.book.sections]
        for number, section, paragraphs in parts:
            here = (index, number)
            if here < (start.volume, start.section) or here > (end.volume, end.section):
                continue
            first = start.paragraph - 1 if here == (start.volume, start.section) else 0
            stop = (min(len(paragraphs), end.paragraph)
                    if here == (end.volume, end.section) else len(paragraphs))
            found.append(Block(volume, section, paragraphs, first, stop))
    return found
