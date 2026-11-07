#!/usr/bin/env python3
"""Spoiler-bounded search for books converted by tools/epub_to_txt.ps1.

Works on one book directory (holding book-html/ and reading-progress.md) or on a
series directory (holding books/<volume>-<slug>/ book directories). Text is only
ever searched, listed or printed up to each book's reading progress.

Run from the project root, for example:

    uv run tools/book_search.py search   <series-dir> "Valka" --word
    uv run tools/book_search.py search   <series-dir> "Valka" --book 1 --chapter 46
    uv run tools/book_search.py read     <series-dir> --book 1 --chapter 46
    uv run tools/book_search.py chapters <series-dir>
    uv run tools/book_search.py check    <series-dir>

Run with --help for the concepts (chapter, part, section, book, boundary).
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

CONCEPTS = """\
concepts:
  chapter   The number a reader uses ("chapter 46"). The tool reads it from the
            book's table of contents.
  part      Only for books whose chapter numbering restarts in each part:
            "Book Two, chapter 5" is --part 2 --chapter 5.
  section   Every item of the table of contents, numbered 1, 2, 3... in reading
            order: cover, prologue, part pages, chapters, interludes, epilogue.
            Every chapter is also a section. Use --section only for a place
            without a chapter number; 'chapters' lists the section numbers.
  book      In a series directory, the volume number from the book folder's
            prefix (01-empire-of-silence is --book 1).
  boundary  How far text may be used. By default each book's own
            reading-progress.md. --book/--chapter/--part/--section narrow it to
            an earlier story point: earlier books up to their progress, the
            given book up to that point, later books not at all. Anything past
            recorded progress, including --all, needs --allow-spoilers, which is
            only for when the user explicitly allowed it for that request.
"""

OPF_NS = "{http://www.idpf.org/2007/opf}"
NCX_NS = "{http://www.daisy.org/z3986/2005/ncx/}"
DC_NS = "{http://purl.org/dc/elements/1.1/}"

BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "dd", "div", "dl", "dt",
    "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hr", "li", "nav", "ol", "p", "pre", "section", "table", "td",
    "th", "tr", "ul",
}
SKIP_TAGS = {"head", "script", "style"}


class BookError(Exception):
    """A problem the caller must resolve; printed without a traceback."""


# --------------------------------------------------------------------------
# Reading chapter and part numbers from table-of-contents labels
# --------------------------------------------------------------------------

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
_ROMAN = re.compile(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})")
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _words_to_int(tokens: list[str]) -> int | None:
    """Parse leading English number words ("one hundred and five"); None if none."""
    total = current = 0
    used = False
    for token in tokens:
        word = token.lower()
        if word in _UNITS:
            current += _UNITS[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred" and used:
            current *= 100
        elif word == "thousand" and used:
            total += current * 1000
            current = 0
        elif word == "and" and used:
            continue
        else:
            break
        used = True
    return total + current if used else None


def _roman_to_int(token: str) -> int | None:
    if not token or not _ROMAN.fullmatch(token):
        return None
    values = [_ROMAN_VALUES[c] for c in token]
    return sum(-v if i + 1 < len(values) and v < values[i + 1] else v
               for i, v in enumerate(values))


def parse_number(text: str) -> int | None:
    """Parse a leading number written as digits, upper-case Roman numerals or words."""
    text = text.strip()
    digits = re.match(r"(\d+)\b", text)
    if digits:
        return int(digits.group(1))
    first = re.match(r"([A-Za-z]+)\b", text)
    if first and first.group(1).isupper():
        roman = _roman_to_int(first.group(1))
        if roman:
            return roman
    return _words_to_int(re.findall(r"[A-Za-z]+", re.split(r"[:,;.]", text)[0]))


def parse_chapter_number(label: str) -> int | None:
    """Return the chapter number a TOC label names, or None.

    Handles "Chapter 12: Title", "Chapter Twelve", "Chapter XII", "12. Title"
    and bare "12". Labels such as "Prologue" or "Book One: ..." return None.
    """
    text = " ".join(label.split())
    match = re.match(r"(?i)(?:chapter|ch\.)\s+(.*)", text)
    if not match:
        bare = re.match(r"(\d+)(?:$|[\s.:)\-–—])", text)
        return int(bare.group(1)) if bare else None
    return parse_number(match.group(1))


def parse_part_number(label: str) -> int | None:
    """Return the part number of a label such as "Book One: Title" or "Part II"."""
    match = re.match(r"(?i)(?:book|part|volume|act)\s+(.*)", " ".join(label.split()))
    return parse_number(match.group(1)) if match else None


# --------------------------------------------------------------------------
# Loading one book's structure from book-html/
# --------------------------------------------------------------------------


@dataclass
class Section:
    """One table-of-contents item and the text that belongs to it."""

    toc_order: int
    label: str
    depth: int
    href: str
    fragment: str | None
    chapter: int | None
    part: int | None = None  # number of the most recent "Book/Part N" item
    is_part: bool = False
    number: int = 0  # 1-based position in reading order; 0 = not located
    paragraphs: list[str] = field(default_factory=list)

    @property
    def heading(self) -> str:
        return self.label or f"Section {self.number}"


@dataclass
class Book:
    title: str
    front: list[str]  # text before the first table-of-contents item
    sections: list[Section]  # located sections, in reading order
    toc: list[Section]  # every table-of-contents item, in TOC order
    toc_pages: list[str]
    unlisted_files: int
    missing_files: int

    @property
    def has_parts(self) -> bool:
        return any(s.part is not None and s.chapter is not None for s in self.toc)

    def section(self, number: int) -> Section:
        if not 1 <= number <= len(self.sections):
            raise BookError(f"Section {number} does not exist "
                            f"(this book has sections 1-{len(self.sections)}).")
        return self.sections[number - 1]

    def subtree_end(self, section: Section) -> int:
        """Last section number covered by finishing `section`.

        Nested items without their own chapter or part number (an interlude or
        scene inside a chapter) belong to it; nested chapters of a part do not.
        """
        end = section.number
        for later in self.toc[section.toc_order + 1:]:
            if later.depth <= section.depth or later.chapter is not None or later.is_part:
                break
            end = max(end, later.number)
        return end


def _describe(chapter: int, part: int | None) -> str:
    return f"part {part}, chapter {chapter}" if part is not None else f"chapter {chapter}"


def find_chapter(book: Book, chapter: int, part: int | None) -> Section:
    hits = [s for s in book.sections
            if s.chapter == chapter and (part is None or s.part == part)]
    if not hits:
        raise BookError(f"No section is numbered {_describe(chapter, part)}. "
                        "Run 'check' to see the numbering.")
    if len(hits) > 1:
        parts = sorted({s.part for s in hits if s.part is not None})
        if part is None and len(parts) == len(hits):
            raise BookError(
                f"Chapter {chapter} appears in parts {', '.join(map(str, parts))}; the numbering "
                "restarts in each part. Give the part (--part, or 'part:' in reading-progress.md).")
        raise BookError(
            f"{_describe(chapter, part).capitalize()} is ambiguous: sections "
            f"{', '.join(str(s.number) for s in hits)} all carry that number. Use a section "
            "number instead (--section, or 'section:' in reading-progress.md).")
    return hits[0]


@dataclass(frozen=True)
class _Anchor:
    id: str


def _local(tag: object) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _join(base_dir: str, href: str) -> str:
    return posixpath.normpath(posixpath.join(base_dir, unquote(href)))


def _parse_xml(path: Path) -> ET.Element:
    try:
        return ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise BookError(f"Cannot parse {path}: {exc}") from exc


def _extract(path: Path, wanted_ids: set[str]) -> list[str | _Anchor]:
    """Split an XHTML file into paragraphs, with anchors for wanted ids."""
    root = _parse_xml(path)
    body = next((el for el in root.iter() if _local(el.tag) == "body"), root)
    items: list[str | _Anchor] = []
    buffer: list[str] = []

    def flush() -> None:
        text = " ".join("".join(buffer).split())
        buffer.clear()
        if text:
            items.append(text)

    def walk(el: ET.Element) -> None:
        tag = _local(el.tag)
        if tag in SKIP_TAGS:
            return
        block = tag in BLOCK_TAGS
        if block:
            flush()
        el_id = el.get("id")
        if el_id in wanted_ids:
            flush()
            items.append(_Anchor(el_id))
        if tag == "br":
            buffer.append(" ")
        if el.text:
            buffer.append(el.text)
        for child in el:
            walk(child)
            if child.tail:
                buffer.append(child.tail)
        if block:
            flush()

    walk(body)
    flush()
    return items


def _label_key(text: str) -> str:
    return " ".join(fold(text)[0].casefold().split()).strip(" .")


def _is_toc_page(paragraphs: list[str], label_keys: set[str]) -> bool:
    hits = sum(1 for p in paragraphs if _label_key(p) in label_keys)
    return hits >= 5 and hits >= 0.5 * len(paragraphs)


def _parse_ncx(path: Path, ncx_dir: str) -> list[Section]:
    root = _parse_xml(path)
    nav_map = root.find(f"{NCX_NS}navMap")
    toc: list[Section] = []

    def walk(parent: ET.Element, depth: int) -> None:
        for point in parent.findall(f"{NCX_NS}navPoint"):
            text_el = point.find(f"{NCX_NS}navLabel/{NCX_NS}text")
            label = " ".join((text_el.text or "").split()) if text_el is not None else ""
            content = point.find(f"{NCX_NS}content")
            src = content.get("src", "") if content is not None else ""
            href, _, fragment = src.partition("#")
            toc.append(Section(
                toc_order=len(toc), label=label, depth=depth,
                href=_join(ncx_dir, href), fragment=unquote(fragment) or None,
                chapter=parse_chapter_number(label),
            ))
            walk(point, depth + 1)

    if nav_map is not None:
        walk(nav_map, 1)
    return toc


def load_book(book_dir: Path) -> Book:
    html_dir = book_dir / "book-html"
    if not html_dir.is_dir():
        raise BookError(f"No book-html/ directory in {book_dir}")
    opfs = sorted(html_dir.glob("*.opf")) or sorted(html_dir.rglob("*.opf"))
    if not opfs:
        raise BookError(f"No .opf package file in {html_dir}")
    opf_path = opfs[0]
    opf_dir = opf_path.parent.relative_to(html_dir).as_posix()
    opf = _parse_xml(opf_path)

    manifest: dict[str, tuple[str, str, str]] = {}
    for item in opf.iter(f"{OPF_NS}item"):
        if item.get("id") and item.get("href"):
            manifest[item.get("id")] = (
                _join(opf_dir, item.get("href")),
                item.get("media-type", ""),
                item.get("properties", ""),
            )
    spine_el = opf.find(f"{OPF_NS}spine")
    if spine_el is None:
        raise BookError(f"{opf_path} has no spine (reading order)")
    spine = [manifest[ref.get("idref")][0]
             for ref in spine_el.iter(f"{OPF_NS}itemref")
             if ref.get("idref") in manifest]

    hinted_toc_pages = {href for href, _, props in manifest.values() if "nav" in props.split()}
    for ref in opf.iter(f"{OPF_NS}reference"):
        if ref.get("type", "").lower() == "toc" and ref.get("href"):
            hinted_toc_pages.add(_join(opf_dir, ref.get("href").split("#")[0]))

    ncx_href = manifest.get(spine_el.get("toc", ""), ("",))[0] or next(
        (href for href, media, _ in manifest.values()
         if media == "application/x-dtbncx+xml"), "")
    if not ncx_href or not (html_dir / ncx_href).is_file():
        raise BookError("No toc.ncx found; chapter boundaries cannot be determined.")
    toc = _parse_ncx(html_dir / ncx_href, posixpath.dirname(ncx_href))
    if not toc:
        raise BookError("toc.ncx has no entries; chapter boundaries cannot be determined.")

    current_part: int | None = None
    for section in toc:
        part = parse_part_number(section.label) if section.chapter is None else None
        if part is not None:
            current_part = part
            section.is_part = True
        section.part = current_part

    title_el = opf.find(f".//{DC_NS}title")
    title = " ".join((title_el.text or "").split()) if title_el is not None else ""

    label_keys: set[str] = set()
    for section in toc:
        if section.label:
            label_keys.add(_label_key(section.label))
            label_keys.update(_label_key(piece) for piece in re.split(r"[:—–]", section.label))
    label_keys.discard("")

    by_file: dict[str, list[Section]] = {}
    for section in toc:
        by_file.setdefault(section.href, []).append(section)

    front: list[str] = []
    ordered: list[Section] = []
    toc_pages: list[str] = []
    current: Section | None = None
    unlisted = missing = 0

    for href in spine:
        path = html_dir / href
        if not path.is_file():
            missing += 1
            continue
        file_sections = by_file.get(href, [])
        items = _extract(path, {s.fragment for s in file_sections if s.fragment})
        found = {item.id for item in items if isinstance(item, _Anchor)}
        starts: dict[str | None, list[Section]] = {}
        for section in file_sections:
            key = section.fragment if section.fragment in found else None
            starts.setdefault(key, []).append(section)

        paragraphs = [item for item in items if isinstance(item, str)]
        if href in hinted_toc_pages or _is_toc_page(paragraphs, label_keys):
            toc_pages.append(href)
            items = [item for item in items if isinstance(item, _Anchor)]
        if not file_sections and current is not None:
            unlisted += 1

        def begin(group: list[Section]) -> None:
            nonlocal current
            for section in group:
                section.number = len(ordered) + 1
                ordered.append(section)
            current = group[-1]

        if None in starts:
            begin(starts.pop(None))
        for item in items:
            if isinstance(item, _Anchor):
                if item.id in starts:
                    begin(starts.pop(item.id))
            elif current is None:
                front.append(item)
            else:
                current.paragraphs.append(item)

    return Book(title, front, ordered, toc, toc_pages, unlisted, missing)


# --------------------------------------------------------------------------
# Reading progress (front-matter block of reading-progress.md)
# --------------------------------------------------------------------------

PROGRESS_KEYS = ("status", "chapter", "part", "section", "updated")
STATUSES = ("not started", "reading", "finished")


@dataclass(frozen=True)
class Progress:
    status: str
    chapter: int | None = None
    part: int | None = None
    section: int | None = None


def parse_progress(path: Path) -> Progress:
    """Read the strict front-matter block at the top of reading-progress.md."""
    if not path.is_file():
        raise BookError(f"{path} is missing.")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].strip() != "---":
        raise BookError(f"{path} must start with a '---' front-matter block "
                        "(see the template in spoiler-rules.md).")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise BookError(f"{path}: the front-matter block is not closed with '---'.")

    values: dict[str, str] = {}
    for line_no, raw in enumerate(lines[1:end], start=2):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, sep, value = line.partition(":")
        key = key.strip().lower()
        if not sep:
            raise BookError(f"{path}:{line_no}: expected 'key: value'.")
        if key not in PROGRESS_KEYS:
            raise BookError(f"{path}:{line_no}: unknown key {key!r} "
                            f"(allowed: {', '.join(PROGRESS_KEYS)}).")
        if key in values:
            raise BookError(f"{path}:{line_no}: {key!r} is set twice.")
        values[key] = value.strip()

    status = values.get("status", "")
    if status not in STATUSES:
        raise BookError(f"{path}: status must be one of {', '.join(STATUSES)}; "
                        f"found {status!r}.")
    numbers: dict[str, int | None] = {}
    for key in ("chapter", "part", "section"):
        value = values.get(key, "")
        if value and not re.fullmatch(r"[1-9]\d*", value):
            raise BookError(f"{path}: {key} must be a whole number or empty; found {value!r}.")
        numbers[key] = int(value) if value else None
    updated = values.get("updated", "")
    if updated and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
        raise BookError(f"{path}: updated must be YYYY-MM-DD or empty; found {updated!r}.")

    progress = Progress(status, **numbers)
    if progress.chapter is not None and progress.section is not None:
        raise BookError(f"{path}: set chapter or section, not both.")
    if progress.part is not None and progress.chapter is None:
        raise BookError(f"{path}: part is only used together with chapter.")
    return progress


# --------------------------------------------------------------------------
# Targets (one book or a series) and boundaries
# --------------------------------------------------------------------------


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

    def progress(self) -> Progress:
        return parse_progress(self.path / "reading-progress.md")


@dataclass
class Target:
    name: str
    volumes: list[Volume]
    is_series: bool

    def volume(self, number: int | None) -> Volume:
        if not self.is_series:
            if number is not None:
                raise BookError("--book is only for series directories.")
            return self.volumes[0]
        if number is None:
            raise BookError("This is a series directory; say which book with --book N.")
        for volume in self.volumes:
            if volume.number == number:
                return volume
        available = ", ".join(str(v.number) for v in self.volumes)
        raise BookError(f"No book {number} in this series (books: {available}).")


def load_target(path: Path) -> Target:
    if (path / "book-html").is_dir():
        prefix = re.match(r"(\d+)-", path.name)
        number = int(prefix.group(1)) if prefix else None
        return Target(path.name, [Volume(path, number, load_book(path))], False)
    books_dir = path / "books"
    if not books_dir.is_dir():
        raise BookError(f"{path} is neither a book directory (with book-html/) "
                        "nor a series directory (with books/).")
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
    return Target(path.name, volumes, True)


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
                     f"{source}: through {_describe(chapter, part)}")
    return Scope(True, None, f"{source}: whole book")


def recorded_scope(volume: Volume) -> Scope:
    progress = volume.progress()
    if progress.status == "finished":
        return Scope(True, None, "finished: whole book")
    if progress.chapter is None and progress.section is None:
        return Scope(False, 0, f"{progress.status}: nothing completed yet (excluded)")
    return point_scope(volume.book, progress.chapter, progress.part, progress.section,
                       progress.status)


def progress_notes(target: Target) -> list[str]:
    statuses = [v.progress().status for v in target.volumes]
    notes = []
    for i, volume in enumerate(target.volumes):
        if statuses[i] != "finished" and any(s != "not started" for s in statuses[i + 1:]):
            notes.append(f"{volume.name} is not marked finished, but a later book has progress. "
                         "Its unread part is excluded; ask the user whether to mark it finished.")
    return notes


def resolve_scopes(target: Target, args: argparse.Namespace) -> list[Scope]:
    """Scopes for search/chapters: recorded progress, optionally narrowed or widened."""
    recorded = [recorded_scope(v) for v in target.volumes]
    point_given = args.chapter is not None or args.section is not None
    if args.part is not None and args.chapter is None:
        raise BookError("--part is only used together with --chapter.")

    if args.all:
        if args.book is not None or point_given:
            raise BookError("--all cannot be combined with --book, --chapter or --section.")
        requested = [Scope(True, None, "--all: whole book") for _ in target.volumes]
    elif args.book is not None or point_given:
        if target.is_series and args.book is None:
            raise BookError("In a series directory, --chapter/--section need --book N.")
        chosen = target.volume(args.book)
        requested = []
        for volume, scope in zip(target.volumes, recorded):
            if volume is chosen:
                requested.append(point_scope(volume.book, args.chapter, args.part,
                                             args.section, "requested"))
            elif volume.number is not None and chosen.number is not None \
                    and volume.number < chosen.number:
                requested.append(scope)
            else:
                requested.append(Scope(False, 0, "after the requested story point (excluded)"))
    else:
        return recorded

    beyond = [v.name for v, want, have in zip(target.volumes, requested, recorded)
              if want.exceeds(have)]
    if beyond and not args.allow_spoilers:
        raise BookError(
            f"That goes beyond the reading progress of {', '.join(beyond)}. Add "
            "--allow-spoilers only if the user explicitly allowed it for this request.")
    return requested


# --------------------------------------------------------------------------
# Searching and printing
# --------------------------------------------------------------------------

_FOLD_TABLE = str.maketrans({
    "‘": "'", "’": "'", "‛": "'", "′": "'", "“": '"', "”": '"', "„": '"',
    "‐": "-", "‑": "-", "–": "-", "—": "-", "\xa0": " ",
})


def fold(text: str) -> tuple[str, list[int]]:
    """Strip accents and normalize quotes/dashes; map folded indices to originals."""
    out: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        if ord(ch) < 128:
            out.append(ch)
            origin.append(i)
            continue
        for c in unicodedata.normalize("NFKD", ch.translate(_FOLD_TABLE)):
            if not unicodedata.combining(c):
                out.append(c)
                origin.append(i)
    return "".join(out), origin


def compile_query(query: str, regex: bool, word: bool, case_sensitive: bool) -> re.Pattern[str]:
    pattern = fold(query)[0] if regex else re.escape(fold(query)[0])
    if word:
        pattern = rf"\b(?:{pattern})\b"
    try:
        return re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)
    except re.error as exc:
        raise BookError(f"Invalid regular expression: {exc}") from exc


def find_spans(text: str, pattern: re.Pattern[str]) -> list[tuple[int, int]]:
    folded, origin = fold(text)
    return [(origin[m.start()], origin[m.end() - 1] + 1)
            for m in pattern.finditer(folded) if m.end() > m.start()]


def highlight(text: str, spans: list[tuple[int, int]]) -> str:
    out, pos = [], 0
    for start, end in spans:
        out += [text[pos:start], "**", text[start:end], "**"]
        pos = end
    return "".join(out + [text[pos:]])


def snippet(text: str, spans: list[tuple[int, int]], width: int = 160) -> str:
    start, end = spans[0]
    a, b = max(0, start - width), min(len(text), end + width)
    if a > 0:
        space = text.find(" ", a, start)
        a = space + 1 if space != -1 else a
    if b < len(text):
        space = text.rfind(" ", end, b)
        b = space if space != -1 else b
    inside = [(s - a, e - a) for s, e in spans if s >= a and e <= b]
    return ("…" if a > 0 else "") + highlight(text[a:b], inside) + ("…" if b < len(text) else "")


def _location(target: Target, volume: Volume, section: Section | None) -> str:
    """Heading for a block of text, naming the book in a series."""
    prefix = f"{volume.short_title} · " if target.is_series else ""
    if section is None:
        return f"{prefix}Front matter"
    where = (f"book {volume.number}, section {section.number}" if target.is_series
             else f"section {section.number}")
    return f"{prefix}{section.heading}  ({where})"


def allowed_text(target: Target, scopes: list[Scope]) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    for volume, scope in zip(target.volumes, scopes):
        if not scope.included:
            continue
        blocks.append((_location(target, volume, None), volume.book.front))
        blocks += [(_location(target, volume, s), s.paragraphs)
                   for s in volume.book.sections if scope.allows(s)]
    return blocks


def print_header(target: Target, scopes: list[Scope], verb: str) -> None:
    count = len(target.volumes)
    books = f" ({count} book{'s' if count != 1 else ''})" if target.is_series else ""
    print(f"{verb} {target.name}{books}")
    for volume, scope in zip(target.volumes, scopes):
        print(f"  {volume.name}: {scope.description}")
    for note in progress_notes(target):
        print(f"  note: {note}")
    if not any(scope.included for scope in scopes):
        raise BookError("No text is within the reading boundary (nothing completed yet). "
                        "Ask the user what they have read.")


def cmd_search(target: Target, args: argparse.Namespace) -> None:
    scopes = resolve_scopes(target, args)
    pattern = compile_query(args.query, args.regex, args.word, args.case_sensitive)
    print_header(target, scopes, "Searching")

    hits: list[tuple[str, list[str], dict[int, list[tuple[int, int]]]]] = []
    total_matches = total_paragraphs = 0
    for name, paragraphs in allowed_text(target, scopes):
        found = {}
        for i, paragraph in enumerate(paragraphs):
            spans = find_spans(paragraph, pattern)
            if spans:
                found[i] = spans
                total_matches += len(spans)
        if found:
            hits.append((name, paragraphs, found))
            total_paragraphs += len(found)

    if not hits:
        print(f"\nNo matches for {args.query!r} within the boundary.")
        return
    print(f"\n{args.query!r}: {total_matches} matches in {total_paragraphs} paragraphs "
          f"across {len(hits)} sections")

    if args.count:
        for name, _, found in hits:
            print(f"  {sum(len(s) for s in found.values()):4}  {name}")
        return

    shown = 0
    for name, paragraphs, found in hits:
        if shown >= args.max:
            break
        print(f"\n## {name}")
        if args.context or args.full:
            wanted = sorted({j for i in found
                             for j in range(max(0, i - args.context),
                                            min(len(paragraphs), i + args.context + 1))})
            previous = None
            for j in wanted:
                if j in found and shown >= args.max:
                    break
                if previous is not None and j != previous + 1:
                    print("   ⋮")
                marker = "»" if j in found else " "
                text = highlight(paragraphs[j], found[j]) if j in found else paragraphs[j]
                print(f"{marker} ¶{j + 1}  {text}")
                shown += j in found
                previous = j
        else:
            for i, spans in found.items():
                if shown >= args.max:
                    break
                extra = f"  (+{len(spans) - 1} more)" if len(spans) > 1 else ""
                print(f"  ¶{i + 1}  {snippet(paragraphs[i], spans)}{extra}")
                shown += 1
    if shown < total_paragraphs:
        print(f"\n… {total_paragraphs - shown} more matching paragraphs not shown; "
              "narrow the query, use --count, or raise --max.")


def cmd_read(target: Target, args: argparse.Namespace) -> None:
    volume = target.volume(args.book)
    book = volume.book
    if args.part is not None and args.chapter is None:
        raise BookError("--part is only used together with --chapter.")
    if args.chapter is not None:
        section = find_chapter(book, args.chapter, args.part)
    elif args.section is not None:
        section = book.section(args.section)
    else:
        raise BookError("Say what to read: --chapter N (with --part if needed) or --section N.")

    scope = recorded_scope(volume)
    if not scope.allows(section):
        if not args.allow_spoilers:
            raise BookError("That is beyond the reading progress. Add --allow-spoilers only "
                            "if the user explicitly allowed it for this request.")
        scope = Scope(True, None, "--allow-spoilers: whole book")

    ranged = args.start is not None or args.end is not None
    last = section.number if ranged else book.subtree_end(section)
    for current in book.sections[section.number - 1:last]:
        if not scope.allows(current):
            print("[The rest is beyond the reading progress.]")
            break
        print(f"## {_location(target, volume, current)}\n")
        first = (args.start or 1) if ranged else 1
        final = (args.end or len(current.paragraphs)) if ranged else len(current.paragraphs)
        for i in range(max(1, first), min(len(current.paragraphs), final) + 1):
            print(f"¶{i}  {current.paragraphs[i - 1]}\n")


def cmd_chapters(target: Target, args: argparse.Namespace) -> None:
    scopes = resolve_scopes(target, args)
    print_header(target, scopes, "Table of contents of")
    for volume, scope in zip(target.volumes, scopes):
        if not scope.included:
            continue
        book = volume.book
        print(f"\n## {volume.name}")
        part_column = f"{'part':>4}  " if book.has_parts else ""
        print(f"{'section':>7}  {part_column}{'ch':>4}  {'¶':>4}  label")
        hidden = 0
        for section in book.sections:
            if not scope.allows(section):
                hidden += 1
                continue
            chapter = str(section.chapter) if section.chapter is not None else "-"
            part = (f"{section.part if section.part is not None else '-':>4}  "
                    if book.has_parts else "")
            indent = "  " * (section.depth - 1)
            print(f"{section.number:>7}  {part}{chapter:>4}  {len(section.paragraphs):>4}  "
                  f"{indent}{section.heading}")
        if hidden:
            print(f"({hidden} later sections hidden)")


def _structure_report(volume: Volume) -> list[str]:
    """Structure and progress of one book, without any titles or text."""
    book = volume.book
    numbered = [s for s in book.sections if s.chapter is not None]
    numbers = [s.chapter for s in numbered]
    keys = [(s.part, s.chapter) for s in numbered]
    duplicates = sorted({_describe(n, p) for p, n in keys if keys.count((p, n)) > 1})
    parts = sorted({s.part for s in numbered if s.part is not None})
    restarts = len(set(numbers)) < len(numbers) and not duplicates
    gaps = []
    for part in parts or [None]:
        values = sorted({s.chapter for s in numbered if s.part == part or not parts})
        if values:
            gaps += [_describe(n, part if parts else None)
                     for n in sorted(set(range(values[0], values[-1] + 1)) - set(values))]
    unlocated = sum(1 for s in book.toc if s.number == 0)
    empty = sum(1 for s in book.sections if not s.paragraphs)

    warnings = []
    try:
        progress = recorded_scope(volume).description
    except BookError as exc:
        progress = "ERROR"
        warnings.append(str(exc))
    if not numbers:
        warnings.append("no table-of-contents labels carry chapter numbers; "
                        "record progress with 'section:'")
    if duplicates:
        warnings.append("some chapter numbers repeat; record progress with 'section:'")
    if gaps:
        warnings.append("chapter numbering has gaps")
    if unlocated or book.missing_files:
        warnings.append("some table-of-contents items or spine files could not be located")
    if not book.toc_pages:
        warnings.append("no contents page detected; if the book has one, searches may "
                        "match later chapter titles")

    lines = [
        f"  Sections located:             {len(book.sections)} of {len(book.toc)}",
        f"  Numbered chapters:            {len(numbers)}"
        + (f" ({min(numbers)}-{max(numbers)})" if numbers else ""),
        f"  Parts:                        {len(parts) or 'none'}"
        + ("; chapter numbering restarts in each part (progress needs 'part:')"
           if restarts else ""),
        f"  Duplicate chapter numbers:    {', '.join(duplicates) or 'none'}",
        f"  Gaps in chapter numbers:      {', '.join(gaps) or 'none'}",
        f"  Sections without a chapter:   {len(book.sections) - len(numbers)}",
        f"  Sections without own text:    {empty}",
        f"  Contents pages excluded:      {len(book.toc_pages)}",
        f"  Unlisted spine files:         {book.unlisted_files} (attached to the preceding section)",
        f"  Missing spine files:          {book.missing_files}",
        f"  Front-matter paragraphs:      {len(book.front)}",
        f"  Reading progress:             {progress}",
        "  Result: " + ("OK" if not warnings else "WARN\n    - " + "\n    - ".join(warnings)),
    ]
    return lines


def cmd_check(target: Target, _args: argparse.Namespace) -> None:
    print("Structure check (no titles or text shown)")
    for volume in target.volumes:
        label = f"Book {volume.number}" if volume.number is not None else volume.path.name
        print(f"\n## {label}")
        print("\n".join(_structure_report(volume)))
    for note in progress_notes_safe(target):
        print(f"\nnote: {note}")


def progress_notes_safe(target: Target) -> list[str]:
    try:
        return progress_notes(target)
    except BookError:
        return []  # individual progress errors are already reported per book


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------


def _positive(value: str) -> int:
    if not re.fullmatch(r"[1-9]\d*", value):
        raise argparse.ArgumentTypeError(f"expected a whole number >= 1, got {value!r}")
    return int(value)


def build_parser() -> argparse.ArgumentParser:
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        description="Spoiler-bounded search over converted books.",
        epilog=CONCEPTS, formatter_class=formatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_target(p: argparse.ArgumentParser) -> None:
        p.add_argument("target", type=Path,
                       help="a book directory (with book-html/) or a series directory "
                            "(with books/)")

    def add_point(p: argparse.ArgumentParser, title: str) -> None:
        group = p.add_argument_group(title)
        group.add_argument("--book", type=_positive, metavar="N",
                           help="volume number, in a series directory")
        exclusive = group.add_mutually_exclusive_group()
        exclusive.add_argument("--chapter", type=_positive, metavar="N", help="chapter number")
        exclusive.add_argument("--section", type=_positive, metavar="N",
                               help="section number, for places without a chapter number")
        group.add_argument("--part", type=_positive, metavar="P",
                           help="with --chapter, when numbering restarts in each part")

    def add_spoilers(p: argparse.ArgumentParser, with_all: bool) -> None:
        if with_all:
            p.add_argument("--all", action="store_true",
                           help="use every book in full (needs --allow-spoilers unless "
                                "all are finished)")
        p.add_argument("--allow-spoilers", action="store_true",
                       help="allow going past recorded progress; only when the user "
                            "explicitly allowed it for this request")

    check = sub.add_parser("check", help="structure and progress report, no titles or text",
                           epilog=CONCEPTS, formatter_class=formatter)
    add_target(check)

    chapters = sub.add_parser("chapters", help="list sections within the boundary",
                              epilog=CONCEPTS, formatter_class=formatter)
    add_target(chapters)
    add_point(chapters, "story point (narrows the boundary; default: reading progress)")
    add_spoilers(chapters, with_all=True)

    search = sub.add_parser("search", help="search text within the boundary",
                            epilog=CONCEPTS, formatter_class=formatter)
    add_target(search)
    search.add_argument("query")
    add_point(search, "story point (narrows the boundary; default: reading progress)")
    add_spoilers(search, with_all=True)
    output = search.add_argument_group("matching and output")
    output.add_argument("--regex", action="store_true", help="treat the query as a regex")
    output.add_argument("--word", action="store_true", help="match whole words only")
    output.add_argument("--case-sensitive", action="store_true")
    output.add_argument("--context", type=int, default=0, metavar="N",
                        help="show N whole paragraphs around each hit")
    output.add_argument("--full", action="store_true", help="show whole matching paragraphs")
    output.add_argument("--count", action="store_true", help="only count matches per section")
    output.add_argument("--max", type=_positive, default=40, metavar="N",
                        help="max paragraphs to show (default 40)")

    read = sub.add_parser("read", help="print a chapter or section within the boundary",
                          epilog=CONCEPTS, formatter_class=formatter)
    add_target(read)
    add_point(read, "what to read")
    add_spoilers(read, with_all=False)
    read.add_argument("--from", dest="start", type=_positive, metavar="P",
                      help="first paragraph (reads only that section)")
    read.add_argument("--to", dest="end", type=_positive, metavar="Q",
                      help="last paragraph (reads only that section)")
    return parser


COMMANDS = {"check": cmd_check, "chapters": cmd_chapters, "search": cmd_search, "read": cmd_read}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        COMMANDS[args.command](load_target(args.target), args)
    except BookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
