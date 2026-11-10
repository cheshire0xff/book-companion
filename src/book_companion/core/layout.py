"""The library's layout: the folder and file names the tools and skills agree on.

skills/book-companion/library.md describes the same layout for agents.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

BOOKS = "books"  # in the library root: books/<author>/<series>/ and books/<author>/standalone/
INCOMING = "_incoming"  # in the library root: files waiting to be imported
INCOMING_EPUBS = "epubs"
INCOMING_IMAGES = "images"
STANDALONE = "standalone"
VOLUMES = "volumes"  # in a series: volumes/<volume>-<book-slug>/
ENTITIES = "entities"  # in a standalone book: entities/<category>/<entity>/
PICS = "pics"  # in an entity: images and their prompt sidecars

PROGRESS_FILE = "reading-progress.md"  # one per series, or per standalone book
SERIES_NOTE = "series.md"
SOURCE_EPUB = "source.epub"
BOOK_TXT = "book.txt"
BOOK_HTML = "book-html"
METADATA_FILE = "metadata.md"
REVIEW_FILE = "review.md"
MEMORY_FILES = ("chapters.md", "chapters-condensed.md", "reference.md")  # finished books only
DESCRIPTION_FILE = "description.md"
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
PROMPT_SUFFIX = ".prompt.md"

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")  # readable, lowercase, hyphen-separated
_VOLUME_PREFIX = re.compile(r"^(\d+)-")


def slugify(name: str) -> str:
    """A slug for a name: "Anaïs Mataro" becomes anais-mataro."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "-".join(re.findall(r"[a-z0-9]+", plain.lower()))


def volume_number(path: Path) -> int | None:
    """The volume number from a volume folder's prefix (01-empire-of-silence is 1)."""
    prefix = _VOLUME_PREFIX.match(path.name)
    return int(prefix.group(1)) if prefix else None


def volume_slug(path: Path) -> str:
    """A volume folder's name without its number prefix."""
    return _VOLUME_PREFIX.sub("", path.name, count=1)


def volume_dirs(series_dir: Path) -> list[Path]:
    """Every folder in a series' volumes/, sorted; book-search loads them all, so none is
    skipped (unlike subdirs)."""
    volumes = series_dir / VOLUMES
    return sorted(path for path in volumes.iterdir() if path.is_dir()) if volumes.is_dir() else []


def subdirs(directory: Path) -> list[Path]:
    """The folders in a directory, sorted, leaving out hidden (.) and private (_) ones."""
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir()
                  if path.is_dir() and not path.name.startswith((".", "_")))
