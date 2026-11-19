"""What the library check reports: findings, each with a path and what to do about it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Severity(StrEnum):
    ERROR = "error"  # a tool or skill can't use this as it is
    WARNING = "warning"  # against the library's conventions; it works, but take a look
    WAITING = "waiting"  # not a problem: something to import or generate next


class Code(StrEnum):
    """What kind of finding this is: a stable id, for tests and for agents. RULES says
    what each one means."""

    # layout
    LEFTOVER_BOOK = "leftover-book"
    OLD_BOOKS_FOLDER = "old-books-folder"
    UNKNOWN_FOLDER = "unknown-folder"
    SLUG = "slug"
    # books
    NO_VOLUMES = "no-volumes"
    VOLUME_NUMBER = "volume-number"
    MISSING_FILE = "missing-file"
    EMPTY_FILE = "empty-file"
    UNREADABLE_BOOK = "unreadable-book"
    STRUCTURE = "structure"
    STRAY_PROGRESS = "stray-progress"
    # reading progress and memory
    NO_PROGRESS = "no-progress"
    BAD_PROGRESS = "bad-progress"
    EARLY_MEMORY = "early-memory"
    # entities
    NO_DESCRIPTION = "no-description"
    IMAGE_WITHOUT_PROMPT = "image-without-prompt"
    PENDING_PROMPT = "pending-prompt"
    # files where they don't belong, and files to import
    STRAY_FILE = "stray-file"
    INCOMING = "incoming"

    @property
    def severity(self) -> Severity:
        return RULES[self].severity


@dataclass(frozen=True)
class Rule:
    severity: Severity
    description: str  # what the check reports, in one line; `book-library check --help` lists it


# Every rule of the check, in the order --help lists them (by severity, then this order).
RULES: dict[Code, Rule] = {
    Code.LEFTOVER_BOOK: Rule(
        Severity.ERROR,
        "a book folder (with book-html/ or source.epub) directly in an author's or a series' "
        "folder, instead of in volumes/ or standalone/"),
    Code.OLD_BOOKS_FOLDER: Rule(
        Severity.ERROR, "a series' books/ folder, the old name of volumes/"),
    Code.UNKNOWN_FOLDER: Rule(
        Severity.WARNING,
        "a folder in an author's folder that is neither standalone/, a book, nor a series "
        "(with volumes/ or reading-progress.md)"),
    Code.SLUG: Rule(
        Severity.WARNING,
        "an author, series, volume, standalone book or entity folder whose name isn't a "
        "lowercase, hyphen-separated slug (for a volume, the name after its number)"),
    Code.NO_VOLUMES: Rule(
        Severity.ERROR, "a series without volumes/, or with no folders in it"),
    Code.VOLUME_NUMBER: Rule(
        Severity.ERROR,
        "a folder in volumes/ without a number prefix (01-...), or with another volume's "
        "number; hidden folders count too, as book-search loads them"),
    Code.MISSING_FILE: Rule(
        Severity.ERROR,
        "a book (a series volume or a standalone book) without source.epub, book.txt, "
        "book-html/ or metadata.md"),
    Code.EMPTY_FILE: Rule(Severity.ERROR, "an empty book.txt"),
    Code.UNREADABLE_BOOK: Rule(
        Severity.ERROR,
        "a book-html/ that book-search can't read (no .opf, spine or toc.ncx, or XHTML that "
        "doesn't parse), or in whose text it finds none of the contents' items"),
    Code.STRUCTURE: Rule(
        Severity.WARNING,
        "a caveat that book-search check reports for a book: no numbered chapters, a chapter "
        "number used twice, gaps in the numbering, contents items or spine files it can't "
        "find, or no contents page"),
    Code.STRAY_PROGRESS: Rule(
        Severity.WARNING, "a reading-progress.md inside a series volume, which the tools ignore"),
    Code.NO_PROGRESS: Rule(
        Severity.ERROR, "a series or standalone book without reading-progress.md"),
    Code.BAD_PROGRESS: Rule(
        Severity.ERROR,
        "a reading-progress.md with invalid front matter, or one naming a story point the "
        "books don't have: a volume more than one past the last imported one, a chapter or "
        "section that volume lacks, a chapter without the part its book needs, or a volume "
        "in a standalone book (checked once every volume can be read)"),
    Code.EARLY_MEMORY: Rule(
        Severity.WARNING,
        "a book memory (chapters.md, chapters-condensed.md or reference.md) of a book that "
        "reading-progress.md doesn't record as finished: a spoiler risk"),
    Code.NO_DESCRIPTION: Rule(Severity.WARNING, "an entity folder without description.md"),
    Code.IMAGE_WITHOUT_PROMPT: Rule(
        Severity.WARNING, "an image in pics/ without its <name>.prompt.md sidecar"),
    Code.PENDING_PROMPT: Rule(
        Severity.WAITING, "a .prompt.md sidecar in pics/ whose image isn't imported yet"),
    Code.STRAY_FILE: Rule(
        Severity.WARNING,
        "a file in pics/ that is neither an image nor a sidecar, or anything in _incoming/ "
        "but EPUBs in epubs/ and images in images/"),
    Code.INCOMING: Rule(
        Severity.WAITING,
        "an EPUB in _incoming/epubs/ or an image in _incoming/images/, waiting to be imported"),
}


def relative(root: Path, path: Path) -> str:
    """A path as the report shows it: relative to the library root, with forward slashes,
    so that a command in a fix runs as printed from the library root."""
    return path.relative_to(root).as_posix()


@dataclass(frozen=True)
class Finding:
    code: Code
    path: Path  # the file or folder concerned
    problem: str  # what is wrong, as a sentence; the report shows the path before it
    fix: str  # what to do about it, as a sentence

    @property
    def severity(self) -> Severity:
        return self.code.severity


@dataclass(frozen=True)
class Group:
    """The findings of one series or standalone book, or of the library around them."""

    name: str  # the folder, relative to the library root
    findings: list[Finding]


@dataclass(frozen=True)
class Report:
    root: Path
    groups: list[Group]

    @property
    def findings(self) -> list[Finding]:
        return [finding for group in self.groups for finding in group.findings]

    def count(self, severity: Severity) -> int:
        return sum(1 for finding in self.findings if finding.severity is severity)
