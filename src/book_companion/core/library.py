"""Targets: a whole series, one book of a series, or a standalone book."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from book_companion.core.errors import BookError
from book_companion.core.progress import Progress, parse_progress
from book_companion.core.structure import Book, load_book


@dataclass
class Volume:
    path: Path
    number: int | None  # volume number from the folder prefix, e.g. 01-
    book: Book

    @property
    def name(self) -> str:
        title = self.book.title or self.path.name
        return f"Volume {self.number}: {title}" if self.number is not None else title

    @property
    def short_title(self) -> str:
        return self.book.title or self.path.name

    @property
    def series_number(self) -> int:
        """The volume number of a book in a series (series code only; never None there)."""
        if self.number is None:
            raise RuntimeError(f"{self.path} is a standalone book, not a series volume")
        return self.number


@dataclass
class Target:
    """What a command works on: a whole series, one book of a series, or a standalone book."""

    name: str
    volumes: list[Volume]  # every book of the series, or the one standalone book
    is_series: bool
    progress_path: Path
    only: int | None = None  # set when the target is one book directory inside a series

    def selected[T](self, items: list[T]) -> list[tuple[Volume, T]]:
        """Pair each volume with its item, keeping only the volumes this target covers."""
        return [(v, item) for v, item in zip(self.volumes, items, strict=True)
                if self.only is None or v.number == self.only]

    def volume(self, number: int | None) -> Volume:
        if not self.is_series:
            if number is not None:
                raise BookError("This is a standalone book, so places leave out the volume.")
            return self.volumes[0]
        if number is None:
            if self.only is None:
                raise BookError("This is a series directory; say which volume, e.g. "
                                '"volume 1 chapter 3".')
            number = self.only
        elif self.only is not None and number != self.only:
            raise BookError(f"This target is volume {self.only} only; point at the series "
                            "directory to use other volumes.")
        for volume in self.volumes:
            if volume.number == number:
                return volume
        available = ", ".join(str(v.number) for v in self.volumes)
        raise BookError(f"No volume {number} in this series (volumes: {available}).")

    def progress(self) -> Progress:
        return parse_progress(self.progress_path)


def load_target(path: Path) -> Target:
    # Absolute, so that '.' or a bare '01-…' still shows the series folders above it.
    # abspath, not resolve(): it keeps symlinked folders and mapped drives as given.
    path = Path(os.path.abspath(path))
    prefix = re.match(r"(\d+)-", path.name)
    if (path / "book-html").is_dir():
        if path.parent.name == "volumes" and prefix:  # one volume inside a series
            series_dir = path.parent.parent
            return Target(f"{series_dir.name}/{path.name}", _load_series(series_dir), True,
                          series_dir / "reading-progress.md", only=int(prefix.group(1)))
        return Target(path.name, [Volume(path, None, load_book(path))], False,
                      path / "reading-progress.md")
    if (path / "volumes").is_dir():
        return Target(path.name, _load_series(path), True, path / "reading-progress.md")
    raise BookError(f"{path} is neither a book directory (with book-html/) "
                    "nor a series directory (with volumes/).")


def _load_series(series_dir: Path) -> list[Volume]:
    books_dir = series_dir / "volumes"
    numbered: list[tuple[int, Path]] = []
    for book_dir in sorted(d for d in books_dir.iterdir() if d.is_dir()):
        prefix = re.match(r"(\d+)-", book_dir.name)
        if not prefix:
            raise BookError(f"{book_dir} has no volume prefix; volumes must be "
                            "named <volume>-<slug>, e.g. 01-empire-of-silence.")
        if not (book_dir / "book-html").is_dir():
            raise BookError(f"{book_dir} has no book-html/; finish importing it first.")
        numbered.append((int(prefix.group(1)), book_dir))
    if not numbered:
        raise BookError(f"{books_dir} contains no volumes.")
    numbers = [number for number, _ in numbered]
    if len(set(numbers)) != len(numbers):
        raise BookError(f"Two volumes in {books_dir} share a volume number.")
    return [Volume(book_dir, number, load_book(book_dir))
            for number, book_dir in sorted(numbered)]

