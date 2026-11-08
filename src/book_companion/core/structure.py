"""Loading one book's structure (sections, paragraphs) from its book-html/."""

from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from book_companion.core.errors import BookError
from book_companion.core.labels import parse_chapter_number, parse_part_number
from book_companion.core.text import fold

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


def describe_chapter(chapter: int, part: int | None) -> str:
    return f"part {part}, chapter {chapter}" if part is not None else f"chapter {chapter}"


def find_chapter(book: Book, chapter: int, part: int | None) -> Section:
    hits = [s for s in book.sections
            if s.chapter == chapter and (part is None or s.part == part)]
    if not hits:
        raise BookError(f"No section is numbered {describe_chapter(chapter, part)}. "
                        "Run 'check' to see the numbering.")
    if len(hits) > 1:
        parts = sorted({s.part for s in hits if s.part is not None})
        if part is None and len(parts) == len(hits):
            raise BookError(
                f"Chapter {chapter} appears in parts {', '.join(map(str, parts))}; the numbering "
                "restarts in each part. Give the part (--part, or 'part:' in reading-progress.md).")
        raise BookError(
            f"{describe_chapter(chapter, part).capitalize()} is ambiguous: sections "
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
