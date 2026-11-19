"""The library check: walk the whole library and report what the tools and skills can't
use as it is.

It only reads: it never moves, fixes or deletes anything. Like `book-search check`, it
never shows a book's titles or text, only paths, counts and chapter numbers. Its walk is
strict on purpose, unlike the viewer's scan, which skips what it can't show.
"""

from __future__ import annotations

from pathlib import Path

from book_companion.core.boundary import recorded_end
from book_companion.core.cli import shell_quote
from book_companion.core.errors import BookError
from book_companion.core.layout import (
    BOOK_HTML,
    BOOK_TXT,
    BOOKS,
    ENTITIES,
    IMAGE_SUFFIXES,
    INCOMING,
    INCOMING_EPUBS,
    INCOMING_IMAGES,
    MEMORY_FILES,
    METADATA_FILE,
    PROGRESS_FILE,
    SOURCE_EPUB,
    STANDALONE,
    VOLUMES,
    slugify,
    subdirs,
    volume_dirs,
    volume_number,
)
from book_companion.core.progress import Progress, parse_progress
from book_companion.core.structure import Book, load_book, summarize
from book_companion.core.target import Target, Volume
from book_companion.library.entities import check_entities
from book_companion.library.findings import Code, Finding, Group, Report, relative
from book_companion.library.names import check_slug

OLD_VOLUMES = "books"  # what a series' volumes/ folder was called before


def check_library(root: Path) -> Report:
    """Check the library in `root`, the folder that holds books/."""
    if not (root / BOOKS).is_dir():
        raise BookError(f"{root} has no {BOOKS}/ folder. Run the check in your library "
                        "folder, or pass the library's path.")
    around: list[Finding] = []  # in books/, outside any series or standalone book
    groups: list[Group] = []
    for author in subdirs(root / BOOKS):
        around += check_slug(author)
        for folder in subdirs(author):
            if folder.name == STANDALONE:
                groups += [Group(relative(root, book), _standalone(root, book))
                           for book in subdirs(folder)]
            elif _is_book(folder):
                around.append(Finding(
                    Code.LEFTOVER_BOOK, folder, "a book folder directly in an author's folder.",
                    f"Move it to {VOLUMES}/<volume>-<book-slug>/ in its series, or to "
                    f"{STANDALONE}/<book-slug>/."))
            elif _is_series(folder):
                groups.append(Group(relative(root, folder), _series(root, folder)))
            else:
                around.append(Finding(
                    Code.UNKNOWN_FOLDER, folder,
                    f"neither a series (it has no {VOLUMES}/ or {PROGRESS_FILE}) nor "
                    f"{STANDALONE}/.",
                    "Move what it holds into a series or standalone book."))
    incoming = _incoming(root / INCOMING)
    return Report(root, ([Group(BOOKS, around)] if around else []) + groups
                  + ([Group(INCOMING, incoming)] if incoming else []))


def _is_book(folder: Path) -> bool:
    return (folder / BOOK_HTML).is_dir() or (folder / SOURCE_EPUB).is_file()


def _is_series(folder: Path) -> bool:
    return ((folder / VOLUMES).is_dir() or (folder / PROGRESS_FILE).is_file()
            or (folder / OLD_VOLUMES).is_dir())


# -- a series, or a standalone book ------------------------------------------------

def _series(root: Path, series_dir: Path) -> list[Finding]:
    found = check_slug(series_dir)
    if (series_dir / OLD_VOLUMES).is_dir():
        found.append(Finding(Code.OLD_BOOKS_FOLDER, series_dir / OLD_VOLUMES,
                             f"the name a series' {VOLUMES}/ folder had before.",
                             f"Rename it to {VOLUMES}/, or move its volumes into {VOLUMES}/."))
    progress = _progress(series_dir / PROGRESS_FILE, found)
    volumes = _volumes(root, series_dir, found)
    if progress is not None and volumes is not None:
        _boundary(root, Target(series_dir.name, volumes, True, series_dir / PROGRESS_FILE),
                  found)
    if progress is not None:
        for book_dir in volume_dirs(series_dir):
            if (number := volume_number(book_dir)) is not None:
                _memory(book_dir, progress.read_in_full(number, standalone=False), found)

    categories: list[Path] = []
    for folder in subdirs(series_dir):
        if folder.name in (VOLUMES, OLD_VOLUMES):
            continue
        if folder.name == ENTITIES:
            categories += subdirs(folder)
        elif _is_book(folder):
            found.append(Finding(Code.LEFTOVER_BOOK, folder,
                                 f"a book folder outside {VOLUMES}/.",
                                 f"Move it to {VOLUMES}/<volume>-<book-slug>/."))
        else:
            categories.append(folder)
    return found + check_entities(categories)


def _standalone(root: Path, book_dir: Path) -> list[Finding]:
    found = check_slug(book_dir)
    progress = _progress(book_dir / PROGRESS_FILE, found)
    book = _book(root, book_dir, found, in_series=False)
    if progress is not None and book is not None:
        _boundary(root, Target(book_dir.name, [Volume(book_dir, None, book)], False,
                               book_dir / PROGRESS_FILE), found)
    if progress is not None:
        _memory(book_dir, progress.read_in_full(None, standalone=True), found)
    categories = [folder for folder in subdirs(book_dir)
                  if folder.name not in (BOOK_HTML, ENTITIES)] + subdirs(book_dir / ENTITIES)
    return found + check_entities(categories)


def _volumes(root: Path, series_dir: Path, found: list[Finding]) -> list[Volume] | None:
    """The series' volumes, or None when one of them can't be used (and is reported)."""
    dirs = volume_dirs(series_dir)
    if not dirs:
        where = series_dir / VOLUMES
        found.append(Finding(Code.NO_VOLUMES, where,
                             "holds no volume folders." if where.is_dir() else "missing.",
                             f"Import the series' books with book-import, into "
                             f"{VOLUMES}/<volume>-<book-slug>/."))
        return None
    volumes: list[Volume] = []
    complete = True
    taken: dict[int, Path] = {}
    for book_dir in dirs:
        number = volume_number(book_dir)
        if number is None:
            complete = False
            found.append(Finding(Code.VOLUME_NUMBER, book_dir, "has no volume number prefix.",
                                 f"Rename it <volume>-<book-slug>, e.g. "
                                 f"01-{slugify(book_dir.name)}."))
        else:
            found += check_slug(book_dir, volume=True)
            if number in taken:
                complete = False
                found.append(Finding(Code.VOLUME_NUMBER, book_dir,
                                     f"has volume number {number}, as {taken[number].name} does.",
                                     "Renumber the one that is out of place."))
            taken.setdefault(number, book_dir)
        book = _book(root, book_dir, found, in_series=True)
        if book is None:
            complete = False
        elif number is not None:
            volumes.append(Volume(book_dir, number, book))
    return sorted(volumes, key=lambda volume: volume.series_number) if complete else None


def _book(root: Path, book_dir: Path, found: list[Finding], *, in_series: bool) -> Book | None:
    """One book's files, and its structure as book-search reads it; None if unreadable."""
    if not (book_dir / SOURCE_EPUB).is_file():
        found.append(Finding(Code.MISSING_FILE, book_dir / SOURCE_EPUB, "missing.",
                             "Put the book's original EPUB here as source.epub "
                             "(book-import moves it here)."))
    text = book_dir / BOOK_TXT
    if not text.is_file():
        found.append(Finding(Code.MISSING_FILE, text, "missing.", _convert(root, book_dir)))
    elif text.stat().st_size == 0:
        found.append(Finding(Code.EMPTY_FILE, text, "empty.", _convert(root, book_dir)))
    if not (book_dir / METADATA_FILE).is_file():
        found.append(Finding(Code.MISSING_FILE, book_dir / METADATA_FILE, "missing.",
                             "Write it from the EPUB's metadata, as book-import does."))
    if in_series and (book_dir / PROGRESS_FILE).is_file():
        found.append(Finding(Code.STRAY_PROGRESS, book_dir / PROGRESS_FILE,
                             "ignored: a series keeps one reading-progress.md, in the series "
                             "folder.",
                             "Move anything worth keeping into the series' reading-progress.md, "
                             "then remove this one."))

    html = book_dir / BOOK_HTML
    if not html.is_dir():
        found.append(Finding(Code.MISSING_FILE, html, "missing; book-search reads the book "
                             "from it.", _convert(root, book_dir)))
        return None
    try:
        book = load_book(book_dir)
    except BookError as exc:
        found.append(Finding(Code.UNREADABLE_BOOK, html, f"book-search can't read it: {exc}",
                             _convert(root, book_dir)))
        return None
    if not book.sections:
        found.append(Finding(Code.UNREADABLE_BOOK, html, "book-search found none of the table "
                             "of contents' items in the text.", _convert(root, book_dir)))
        return None
    check = _command("book-search", "check", relative(root, book_dir))
    for warning in summarize(book).warnings:
        found.append(Finding(Code.STRUCTURE, html, f"book-search: {warning}.",
                             f"See {check}; note an expected caveat in {METADATA_FILE}."))
    return book


def _convert(root: Path, book_dir: Path) -> str:
    """How to make book.txt and book-html/ again."""
    if not (book_dir / SOURCE_EPUB).is_file():
        return "Import the book again from its EPUB with book-import."
    command = ["book-convert", relative(root, book_dir / SOURCE_EPUB),
               relative(root, book_dir / BOOK_TXT)]
    if (book_dir / BOOK_TXT).exists() or (book_dir / BOOK_HTML).exists():
        return ("Convert the EPUB again, which replaces book.txt and book-html/, so ask the "
                f"user first: {_command(*command, '--force')}")
    return f"Convert the EPUB: {_command(*command)}"


def _command(*args: str) -> str:
    return " ".join(shell_quote(arg) for arg in args)


# -- reading progress and memory ---------------------------------------------------

def _progress(path: Path, found: list[Finding]) -> Progress | None:
    if not path.is_file():
        found.append(Finding(Code.NO_PROGRESS, path, "missing.",
                             "Create it from the template in spoiler-rules.md, as book-import "
                             "does; ask the user how far they have read."))
        return None
    try:
        return parse_progress(path)
    except BookError as exc:
        found.append(Finding(Code.BAD_PROGRESS, path, _detail(exc, path),
                             "Correct its front matter, following the template in "
                             "spoiler-rules.md."))
        return None


def _boundary(root: Path, target: Target, found: list[Finding]) -> None:
    """Whether the recorded story point exists in the books, as book-search finds it."""
    try:
        recorded_end(target)
    except BookError as exc:
        folder = target.progress_path.parent
        found.append(Finding(Code.BAD_PROGRESS, target.progress_path,
                             _detail(exc, target.progress_path),
                             f"Correct its front matter; "
                             f"{_command('book-search', 'check', relative(root, folder))} "
                             "shows the numbering."))


def _memory(book_dir: Path, read: bool, found: list[Finding]) -> None:
    if read:
        return
    for name in MEMORY_FILES:
        if (book_dir / name).is_file():
            found.append(Finding(
                Code.EARLY_MEMORY, book_dir / name,
                "a book memory, but reading-progress.md doesn't record this book as finished: "
                "a spoiler risk.",
                "If the user has finished the book, record that in reading-progress.md; "
                "otherwise ask them what to do with the memory."))


def _detail(error: BookError, path: Path) -> str:
    """The error's message without the path it starts with; the report shows that path."""
    message = str(error)
    rest = message.removeprefix(str(path))
    if rest == message:
        return message
    if rest.startswith(": "):
        return rest[2:]
    if rest.startswith(":"):  # a line number
        return f"line {rest[1:]}"
    return f"{path.name}{rest}"


# -- _incoming/ --------------------------------------------------------------------

def _incoming(incoming: Path) -> list[Finding]:
    """What waits in _incoming/ to be imported."""
    kinds = {
        INCOMING_EPUBS: (frozenset({".epub"}), "an EPUB", "Import it with book-import."),
        INCOMING_IMAGES: (IMAGE_SUFFIXES, "an image", "Import it with book-images."),
    }
    found: list[Finding] = []
    for entry in _visible(incoming):
        kind = kinds.get(entry.name) if entry.is_dir() else None
        if kind is None:
            found.append(Finding(Code.STRAY_FILE, entry,
                                 f"{INCOMING}/ holds only {INCOMING_EPUBS}/ and "
                                 f"{INCOMING_IMAGES}/.",
                                 f"Move EPUBs into {INCOMING}/{INCOMING_EPUBS}/ and images into "
                                 f"{INCOMING}/{INCOMING_IMAGES}/."))
            continue
        suffixes, what, fix = kind
        for path in _visible(entry):
            if path.is_file() and path.suffix.lower() in suffixes:
                found.append(Finding(Code.INCOMING, path, f"{what} waiting to be imported.", fix))
            else:
                found.append(Finding(Code.STRAY_FILE, path, f"not {what}.",
                                     f"Move it out of {INCOMING}/{entry.name}/."))
    return found


def _visible(directory: Path) -> list[Path]:
    """A folder's entries, sorted, without hidden ones such as .gitkeep."""
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir() if not path.name.startswith("."))
