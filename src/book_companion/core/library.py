"""Targets: a whole series, one book of a series, or a standalone book."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from book_companion.core.errors import BookError
from book_companion.core.progress import Progress, parse_progress
from book_companion.core.structure import Book, Section, load_book


@dataclass
class Volume:
    path: Path
    number: int | None  # volume number from the folder prefix, e.g. 01-
    book: Book

    @property
    def name(self) -> str:
        title = self.book.title or self.path.name
        return f"Book {self.number}: {title}" if self.number is not None else title

    @property
    def short_title(self) -> str:
        return self.book.title or self.path.name


@dataclass
class Target:
    """What a command works on: a whole series, one book of a series, or a standalone book."""

    name: str
    volumes: list[Volume]  # every book of the series, or the one standalone book
    is_series: bool
    progress_path: Path
    only: int | None = None  # set when the target is one book directory inside a series

    def selected(self, items: list) -> list[tuple[Volume, object]]:
        """Pair each volume with its item, keeping only the volumes this target covers."""
        return [(v, item) for v, item in zip(self.volumes, items, strict=True)
                if self.only is None or v.number == self.only]

    def volume(self, number: int | None) -> Volume:
        if not self.is_series:
            if number is not None:
                raise BookError("--book is only for series directories.")
            return self.volumes[0]
        if number is None:
            if self.only is None:
                raise BookError("This is a series directory; say which book with --book N.")
            number = self.only
        elif self.only is not None and number != self.only:
            raise BookError(f"This target is book {self.only} only; point at the series "
                            "directory to use other books.")
        for volume in self.volumes:
            if volume.number == number:
                return volume
        available = ", ".join(str(v.number) for v in self.volumes)
        raise BookError(f"No book {number} in this series (books: {available}).")

    def progress(self) -> Progress:
        return parse_progress(self.progress_path)


def load_target(path: Path) -> Target:
    prefix = re.match(r"(\d+)-", path.name)
    if (path / "book-html").is_dir():
        if path.parent.name == "books" and prefix:  # one book inside a series
            series_dir = path.parent.parent
            return Target(f"{series_dir.name}/{path.name}", _load_series(series_dir), True,
                          series_dir / "reading-progress.md", only=int(prefix.group(1)))
        return Target(path.name, [Volume(path, None, load_book(path))], False,
                      path / "reading-progress.md")
    if (path / "books").is_dir():
        return Target(path.name, _load_series(path), True, path / "reading-progress.md")
    raise BookError(f"{path} is neither a book directory (with book-html/) "
                    "nor a series directory (with books/).")


def _load_series(series_dir: Path) -> list[Volume]:
    books_dir = series_dir / "books"
    volumes: list[Volume] = []
    for book_dir in sorted(d for d in books_dir.iterdir() if d.is_dir()):
        prefix = re.match(r"(\d+)-", book_dir.name)
        if not prefix:
            raise BookError(f"{book_dir} has no volume prefix; series books must be "
                            "named <volume>-<slug>, e.g. 01-empire-of-silence.")
        if not (book_dir / "book-html").is_dir():
            raise BookError(f"{book_dir} has no book-html/; finish importing it first.")
        volumes.append(Volume(book_dir, int(prefix.group(1)), load_book(book_dir)))
    if not volumes:
        raise BookError(f"{books_dir} contains no books.")
    numbers = [v.number for v in volumes]
    if len(set(numbers)) != len(numbers):
        raise BookError(f"Two books in {books_dir} share a volume number.")
    volumes.sort(key=lambda v: v.number)
    return volumes


def location(target: Target, volume: Volume, section: Section | None) -> str:
    """Heading for a block of text, naming the book in a series."""
    prefix = f"{volume.short_title} · " if target.is_series else ""
    if section is None:
        return f"{prefix}Front matter"
    where = (f"book {volume.number}, section {section.number}" if target.is_series
             else f"section {section.number}")
    return f"{prefix}{section.heading}  ({where})"
