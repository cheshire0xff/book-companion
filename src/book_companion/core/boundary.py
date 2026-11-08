"""What text may be used: recorded progress, narrowing, start points."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from book_companion.core.errors import BookError
from book_companion.core.library import Target, Volume
from book_companion.core.progress import Progress, Status
from book_companion.core.structure import Book, Section, describe_chapter, find_chapter


@dataclass(frozen=True)
class Scope:
    """Which part of one book may be used."""

    included: bool
    limit: int | None  # last allowed section number; None = whole book
    description: str

    def allows(self, section: Section) -> bool:
        return self.included and (self.limit is None or 0 < section.number <= self.limit)

    def exceeds(self, other: Scope) -> bool:
        if not self.included:
            return False
        if not other.included:
            return True
        if other.limit is None:
            return False
        return self.limit is None or self.limit > other.limit


def point_scope(book: Book, chapter: int | None, part: int | None,
                section: int | None, source: str) -> Scope:
    if section is not None:
        return Scope(True, book.subtree_end(book.section(section)),
                     f"{source}: through section {section}")
    if chapter is not None:
        return Scope(True, book.subtree_end(find_chapter(book, chapter, part)),
                     f"{source}: through {describe_chapter(chapter, part)}")
    return Scope(True, None, f"{source}: whole book")


def _scope_in_book(book: Book, progress: Progress) -> Scope:
    if progress.status is Status.FINISHED:
        return Scope(True, None, f"{Status.FINISHED}: whole book")
    if progress.chapter is None and progress.section is None:
        return Scope(False, 0, f"{progress.status}: nothing completed yet (excluded)")
    return point_scope(book, progress.chapter, progress.part, progress.section, progress.status)


def recorded_scopes(target: Target) -> list[Scope]:
    """Scope of every volume according to the reading-progress.md story point.

    In a series, books before the current one are read in full, the current book
    is limited by status/chapter/section, and later books are excluded.
    """
    progress = target.progress()
    path = target.progress_path
    if not target.is_series:
        if progress.book is not None:
            raise BookError(f"{path}: 'book' is only used in a series' reading-progress.md.")
        return [_scope_in_book(target.volumes[0].book, progress)]
    if progress.book is None:
        raise BookError(f"{path}: set 'book' to the volume number being read.")
    highest = max(v.series_number for v in target.volumes)
    if progress.book > highest + 1:
        raise BookError(f"{path}: book {progress.book} is past the imported books "
                        f"(highest is {highest}); check the number.")
    scopes = []
    for volume in target.volumes:
        if volume.series_number < progress.book:
            scopes.append(Scope(True, None, "earlier book: whole book"))
        elif volume.series_number == progress.book:
            scopes.append(_scope_in_book(volume.book, progress))
        else:
            scopes.append(Scope(False, 0, "later book: not read yet (excluded)"))
    return scopes


def resolve_scopes(target: Target, args: argparse.Namespace) -> list[Scope]:
    """Scopes for search/chapters: recorded progress, optionally narrowed or widened."""
    recorded = recorded_scopes(target)
    point_given = args.chapter is not None or args.section is not None
    if args.part is not None and args.chapter is None:
        raise BookError("--part is only used together with --chapter.")

    if args.all:
        if args.book is not None or point_given:
            raise BookError("--all cannot be combined with --book, --chapter or --section.")
        requested = [Scope(True, None, "--all: whole book") for _ in target.volumes]
    elif args.book is not None or point_given:
        chosen = target.volume(args.book)
        requested = []
        for volume, scope in zip(target.volumes, recorded, strict=True):
            if volume is chosen:
                requested.append(point_scope(volume.book, args.chapter, args.part,
                                             args.section, "requested"))
            elif target.is_series and volume.series_number < chosen.series_number:
                requested.append(scope)
            else:
                requested.append(Scope(False, 0, "after the requested story point (excluded)"))
    else:
        return recorded

    recorded_selected = [have for _, have in target.selected(recorded)]
    beyond = [v.name for (v, want), have in zip(target.selected(requested), recorded_selected,
                                                strict=True)
              if want.exceeds(have)]
    if beyond and not args.allow_spoilers:
        raise BookError(
            f"That goes beyond the reading progress of {', '.join(beyond)}. Add "
            "--allow-spoilers only if the user explicitly allowed it for this request.")
    return requested


@dataclass(frozen=True)
class Start:
    """Where a search or listing begins (it only ever narrows)."""

    volume_index: int
    section: int  # section number; 0 = the book's front matter
    paragraph: int  # 0-based paragraph index within that section

    def describe(self, target: Target) -> str:
        volume = target.volumes[self.volume_index]
        book = f"book {volume.number}, " if target.is_series else ""
        where = f"section {self.section}" if self.section else "front matter"
        paragraph = f", ¶{self.paragraph + 1}" if self.paragraph else ""
        return f"{book}{where}{paragraph}"


def resolve_start(target: Target, args: argparse.Namespace) -> Start | None:
    paragraph = getattr(args, "start_paragraph", None)
    values = (args.start_book, args.start_chapter, args.start_section, args.start_part, paragraph)
    if all(value is None for value in values):
        return None
    if args.start_part is not None and args.start_chapter is None:
        raise BookError("--start-part is only used together with --start-chapter.")
    if target.is_series and target.only is None and args.start_book is None:
        raise BookError("In a series directory, a start point needs --start-book N.")
    volume = target.volume(args.start_book)
    if args.start_chapter is not None:
        section = find_chapter(volume.book, args.start_chapter, args.start_part).number
    elif args.start_section is not None:
        section = volume.book.section(args.start_section).number
    else:
        section = 0
    return Start(target.volumes.index(volume), section, (paragraph or 1) - 1)


@dataclass
class Block:
    """A run of paragraphs that may be searched: one section, or a book's front matter."""

    volume: Volume
    section: Section | None  # None = front matter
    paragraphs: list[str]
    first: int = 0  # first paragraph index to search (a start point)


def allowed_text(target: Target, scopes: list[Scope], start: Start | None) -> list[Block]:
    blocks: list[Block] = []
    for index, (volume, scope) in enumerate(zip(target.volumes, scopes, strict=True)):
        if target.only is not None and volume.number != target.only:
            continue
        if not scope.included or (start is not None and index < start.volume_index):
            continue
        here = start if start is not None and index == start.volume_index else None
        if here is None or here.section == 0:
            blocks.append(Block(volume, None, volume.book.front,
                                here.paragraph if here is not None else 0))
        for section in volume.book.sections:
            if not scope.allows(section) or (here is not None and section.number < here.section):
                continue
            first = here.paragraph if here is not None and section.number == here.section else 0
            blocks.append(Block(volume, section, section.paragraphs, first))
    if start is not None and not blocks:
        raise BookError("The start point is after the end of the searchable range.")
    return blocks
