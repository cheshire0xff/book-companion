"""What book-view shows: the series, books, entities and images found in a library.

The scan reads only folder listings, the first lines of notes and the front matter
of reading-progress.md. It never opens book.txt or book-html/, and everything the
viewer serves is something this scan found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from book_companion.core.errors import BookError
from book_companion.core.progress import Progress, Status, parse_progress

PROGRESS_FILE = "reading-progress.md"
SERIES_NOTE = "series.md"
NOTE_FILES = ("metadata.md", "review.md", "reference.md", "chapters.md", "chapters-condensed.md")
SAFE_NOTES = frozenset({"metadata.md"})  # bibliographic facts and the memory log, never a spoiler
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
PROMPT_SUFFIX = ".prompt.md"
NOT_CATEGORIES = frozenset({"volumes", "entities", "book-html"})


@dataclass
class Image:
    path: Path
    prompt: Path | None  # the <stem>.prompt.md sidecar


@dataclass
class Entity:
    path: Path
    category: str
    name: str
    description: Path | None
    images: list[Image]  # newest version first
    pending: list[Path]  # prompt sidecars that have no image yet


@dataclass
class Volume:
    path: Path
    number: int | None  # from the folder prefix, e.g. 01-; None for a standalone book
    title: str
    notes: list[Path]
    read: bool  # fully read, so its memory notes are not spoilers


@dataclass
class Series:
    """A series directory, or a standalone book (a series of one)."""

    path: Path
    title: str
    author: str
    standalone: bool
    progress: Progress | None
    progress_error: str | None
    volumes: list[Volume]
    categories: dict[str, list[Entity]]
    note: Path | None  # series.md

    @property
    def entities(self) -> list[Entity]:
        return [entity for group in self.categories.values() for entity in group]


@dataclass
class Library:
    root: Path
    series: list[Series]


def link_path(root: Path, path: Path, directory: bool = False) -> str:
    """The URL path (unquoted) that shows a file or folder of the library."""
    relative = path.relative_to(root).as_posix()
    return f"/{relative}/" if directory else f"/{relative}"


def slug_title(slug: str) -> str:
    return " ".join(word.capitalize() for word in re.split(r"[-_\s]+", slug) if word)


def is_spoiler(volume: Volume, note: Path) -> bool:
    return not volume.read and note.name not in SAFE_NOTES


def scan(root: Path) -> Library:
    found: list[Series] = []
    for author in _subdirs(root / "books"):
        for directory in _subdirs(author):
            if directory.name == "standalone":
                found.extend(_series(book, standalone=True) for book in _subdirs(directory)
                             if (book / PROGRESS_FILE).is_file()
                             or (book / "metadata.md").is_file())
            elif (directory / PROGRESS_FILE).is_file() or (directory / "volumes").is_dir():
                found.append(_series(directory, standalone=False))
    found.sort(key=lambda s: (s.author.casefold(), s.title.casefold()))
    return Library(root, found)


def _subdirs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir()
                  if path.is_dir() and not path.name.startswith((".", "_")))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _metadata(book_dir: Path) -> dict[str, str]:
    """The '- Key: value' lines of metadata.md, before its first '##' section."""
    path = book_dir / "metadata.md"
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in _read(path).splitlines():
        if line.startswith("## "):
            break
        if match := re.fullmatch(r"\s*[-*]\s+([^:]+?):\s*(.+?)\s*", line):
            values.setdefault(match.group(1).strip().lower(), match.group(2))
    return values


def _heading(path: Path) -> str | None:
    for line in _read(path).splitlines():
        if match := re.fullmatch(r"#\s+(.+?)\s*#*\s*", line):
            return match.group(1)
    return None


def _fully_read(number: int | None, progress: Progress | None, standalone: bool) -> bool:
    if progress is None:
        return False
    if standalone:
        return progress.status is Status.FINISHED
    if number is None or progress.volume is None:
        return False
    return number < progress.volume or (number == progress.volume
                                      and progress.status is Status.FINISHED)


def _volume(book_dir: Path, number: int | None, progress: Progress | None,
            standalone: bool) -> Volume:
    title = _metadata(book_dir).get("title") or slug_title(re.sub(r"^\d+-", "", book_dir.name))
    notes = [book_dir / name for name in NOTE_FILES if (book_dir / name).is_file()]
    return Volume(book_dir, number, title, notes, _fully_read(number, progress, standalone))


def _series(path: Path, standalone: bool) -> Series:
    try:
        progress, error = parse_progress(path / PROGRESS_FILE), None
    except BookError as exc:
        progress, error = None, str(exc)

    if standalone:
        volumes = [_volume(path, None, progress, standalone=True)]
    else:
        volumes = []
        for book_dir in _subdirs(path / "volumes"):
            prefix = re.match(r"(\d+)-", book_dir.name)
            number = int(prefix.group(1)) if prefix else None
            volumes.append(_volume(book_dir, number, progress, standalone=False))
        volumes.sort(key=lambda v: (v.number is None, v.number or 0, v.path.name))

    metadata = next((m for v in volumes if (m := _metadata(v.path))), {})
    if standalone:
        title = volumes[0].title
    else:
        title = metadata.get("series") or slug_title(path.name)
    author = metadata.get("author(s)") or metadata.get("author") or slug_title(
        path.parent.parent.name if standalone else path.parent.name)
    note = path / SERIES_NOTE
    return Series(path, title, author, standalone, progress, error, volumes,
                  _categories(path), note if note.is_file() else None)


def _categories(series_dir: Path) -> dict[str, list[Entity]]:
    categories: dict[str, list[Entity]] = {}
    for base in (series_dir, series_dir / "entities"):
        for category in _subdirs(base):
            if category.name in NOT_CATEGORIES:
                continue
            entities = [entity for directory in _subdirs(category)
                        if (entity := _entity(directory, category.name))]
            if entities:
                group = categories.setdefault(category.name, [])
                group.extend(entities)
                group.sort(key=lambda e: e.name.casefold())
    return categories


def _entity(directory: Path, category: str) -> Entity | None:
    description = directory / "description.md"
    pics = directory / "pics"
    if not description.is_file() and not pics.is_dir():
        return None
    files = sorted((p for p in pics.iterdir() if p.is_file()), reverse=True) \
        if pics.is_dir() else []
    images: list[Image] = []
    for path in files:
        if path.suffix.lower() in IMAGE_SUFFIXES:
            prompt = path.with_name(path.stem + PROMPT_SUFFIX)
            images.append(Image(path, prompt if prompt.is_file() else None))
    with_image = {image.prompt for image in images}
    pending = [path for path in files
               if path.name.endswith(PROMPT_SUFFIX) and path not in with_image]
    name = (_heading(description) if description.is_file() else None) or slug_title(directory.name)
    return Entity(directory, category, name, description if description.is_file() else None,
                  images, pending)
