"""book-search: spoiler-bounded search, reading and structure checks."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from book_companion.core.boundary import (
    Block,
    Scope,
    allowed_text,
    recorded_scopes,
    resolve_scopes,
    resolve_start,
)
from book_companion.core.errors import BookError
from book_companion.core.library import Target, Volume, load_target, location
from book_companion.core.structure import describe_chapter, find_chapter
from book_companion.core.text import Match, compile_query, find_matches, highlight, snippet

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
  progress  One reading-progress.md per series (in the series directory), or
            per standalone book. It records a story point: the book being read
            (book:) and its last completed chapter or section. Earlier books
            count as read, later books as unread.
  boundary  How far text may be used: the recorded story point by default.
            --book/--chapter/--part/--section narrow it to an earlier story
            point. Anything past recorded progress, including --all, needs
            --allow-spoilers, which is only for when the user explicitly
            allowed it for that request.
  start     --start-book/--start-chapter/--start-part/--start-section make a
            search or listing begin later, e.g. only chapters 66-71 with
            --start-chapter 66 --chapter 71. When search output reaches
            --max-chars, the tool prints the --start-* flags (down to
            --start-paragraph) that continue from the next hit.
"""


def print_header(target: Target, scopes: list[Scope], verb: str) -> None:
    shown = target.selected(scopes)
    count = len(shown)
    books = f" ({count} book{'s' if count != 1 else ''})" if target.is_series else ""
    print(f"{verb} {target.name}{books}")
    for volume, scope in shown:
        print(f"  {volume.name}: {scope.description}")
    if not any(scope.included for _, scope in shown):
        raise BookError("No text is within the reading boundary (nothing completed yet). "
                        "Ask the user what they have read.")


@dataclass
class Hit:
    block: Block
    index: int  # paragraph index within the block
    matches: list[Match]


def _counts_by_section(target: Target, hits: list[Hit]) -> list[str]:
    counts: dict[int, list] = {}
    for hit in hits:
        counts.setdefault(id(hit.block), [hit.block, 0])[1] += len(hit.matches)
    return [f"  {n:4}  {location(target, b.volume, b.section)}" for b, n in counts.values()]


def _continue_flags(target: Target, hit: Hit) -> str:
    flags = [f"--start-book {hit.block.volume.number}"] if target.is_series else []
    if hit.block.section is not None:
        flags.append(f"--start-section {hit.block.section.number}")
    flags.append(f"--start-paragraph {hit.index + 1}")
    return " ".join(flags)


def _print_hits(target: Target, hits: list[Hit], args: argparse.Namespace) -> int:
    """Print hits until the character budget is used up; return how many were shown."""
    by_block: dict[int, dict[int, list[Match]]] = {}
    for hit in hits:
        by_block.setdefault(id(hit.block), {})[hit.index] = hit.matches
    used = shown = 0
    current: Block | None = None
    printed: set[int] = set()
    last: int | None = None
    for hit in hits:
        block = hit.block
        same_block = block is current
        lines = [] if same_block else [f"\n## {location(target, block.volume, block.section)}"]
        new_printed = set(printed) if same_block else set()
        new_last = last if same_block else None
        if args.context or args.full:
            first = max(0, hit.index - args.context)
            stop = min(len(block.paragraphs), hit.index + args.context + 1)
            for j in range(first, stop):
                if j in new_printed:
                    continue
                if new_last is not None and j != new_last + 1:
                    lines.append("   ⋮")
                matches = by_block[id(block)].get(j)
                text = (highlight(block.paragraphs[j], [s for m in matches for s in m])
                        if matches else block.paragraphs[j])
                lines.append(f"{'»' if matches else ' '} ¶{j + 1}  {text}")
                new_printed.add(j)
                new_last = j
        else:
            extra = f"  (+{len(hit.matches) - 1} more)" if len(hit.matches) > 1 else ""
            lines.append(f"  ¶{hit.index + 1}  "
                         f"{snippet(block.paragraphs[hit.index], hit.matches)}{extra}")
        text = "\n".join(lines)
        if shown and used + len(text) > args.max_chars:
            break
        if text:
            print(text)
            used += len(text) + 1
        shown += 1
        current, printed, last = block, new_printed, new_last
    return shown


def cmd_search(target: Target, args: argparse.Namespace) -> None:
    scopes = resolve_scopes(target, args)
    start = resolve_start(target, args)
    pattern = compile_query(args.query, args.regex, args.word, args.case_sensitive)
    print_header(target, scopes, "Searching")
    blocks = allowed_text(target, scopes, start)
    if start is not None:
        print(f"  starting at: {start.describe(target)}")

    hits = [Hit(block, i, matches)
            for block in blocks
            for i in range(block.first, len(block.paragraphs))
            if (matches := find_matches(block.paragraphs[i], pattern))]
    if not hits:
        print(f"\nNo matches for {args.query!r} within the boundary.")
        return
    sections = len({id(hit.block) for hit in hits})
    print(f"\n{args.query!r}: {sum(len(h.matches) for h in hits)} matches in {len(hits)} "
          f"paragraphs across {sections} sections")

    if args.count:
        print("\n".join(_counts_by_section(target, hits)))
        return

    shown = _print_hits(target, hits, args)
    if shown < len(hits):
        rest = hits[shown:]
        print(f"\n--- Output limit reached (--max-chars {args.max_chars}): "
              f"{shown} of {len(hits)} matching paragraphs shown.")
        print("Remaining matches by section:")
        remaining = _counts_by_section(target, rest)
        print("\n".join(remaining[:25]))
        if len(remaining) > 25:
            print(f"  … and {len(remaining) - 25} more sections")
        print(f"Continue: rerun with  {_continue_flags(target, rest[0])}  "
              "(replacing any --start-* flags).")
        print("Or narrow it: a tighter query, --word, or a --start-*/--chapter range.")


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

    scope = recorded_scopes(target)[target.volumes.index(volume)]
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
        print(f"## {location(target, volume, current)}\n")
        first = (args.start or 1) if ranged else 1
        final = (args.end or len(current.paragraphs)) if ranged else len(current.paragraphs)
        for i in range(max(1, first), min(len(current.paragraphs), final) + 1):
            print(f"¶{i}  {current.paragraphs[i - 1]}\n")


def cmd_chapters(target: Target, args: argparse.Namespace) -> None:
    scopes = resolve_scopes(target, args)
    start = resolve_start(target, args)
    print_header(target, scopes, "Table of contents of")
    allowed_text(target, scopes, start)  # validates the start point
    for index, (volume, scope) in enumerate(zip(target.volumes, scopes, strict=True)):
        if target.only is not None and volume.number != target.only:
            continue
        if not scope.included or (start is not None and index < start.volume_index):
            continue
        here = start is not None and index == start.volume_index
        book = volume.book
        print(f"\n## {volume.name}")
        part_column = f"{'part':>4}  " if book.has_parts else ""
        print(f"{'section':>7}  {part_column}{'ch':>4}  {'¶':>4}  label")
        hidden = 0
        for section in book.sections:
            if here and section.number < start.section:
                continue
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


def _structure_report(volume: Volume, scope: Scope | None) -> list[str]:
    """Structure and progress of one book, without any titles or text."""
    book = volume.book
    numbered = [s for s in book.sections if s.chapter is not None]
    numbers = [s.chapter for s in numbered]
    keys = [(s.part, s.chapter) for s in numbered]
    duplicates = sorted({describe_chapter(n, p) for p, n in keys if keys.count((p, n)) > 1})
    parts = sorted({s.part for s in numbered if s.part is not None})
    restarts = len(set(numbers)) < len(numbers) and not duplicates
    gaps = []
    for part in parts or [None]:
        values = sorted({s.chapter for s in numbered if s.part == part or not parts})
        if values:
            gaps += [describe_chapter(n, part if parts else None)
                     for n in sorted(set(range(values[0], values[-1] + 1)) - set(values))]
    unlocated = sum(1 for s in book.toc if s.number == 0)
    empty = sum(1 for s in book.sections if not s.paragraphs)

    warnings = []
    progress = scope.description if scope is not None else "ERROR (see above)"
    if scope is None:
        warnings.append("reading-progress.md is invalid")
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
        f"  Unlisted spine files:         {book.unlisted_files} "
        "(attached to the preceding section)",
        f"  Missing spine files:          {book.missing_files}",
        f"  Front-matter paragraphs:      {len(book.front)}",
        f"  Reading progress:             {progress}",
        "  Result: " + ("OK" if not warnings else "WARN\n    - " + "\n    - ".join(warnings)),
    ]
    return lines


def cmd_check(target: Target, _args: argparse.Namespace) -> None:
    print("Structure check (no titles or text shown)")
    scopes: list[Scope | None]
    try:
        scopes = list(recorded_scopes(target))
        progress = target.progress()
        where = f"book {progress.book}, " if progress.book is not None else ""
        print(f"Reading progress ({target.progress_path}): {where}{progress.status}")
    except BookError as exc:
        scopes = [None] * len(target.volumes)
        print(f"Reading progress: ERROR\n  - {exc}")
    for volume, scope in target.selected(scopes):
        label = f"Book {volume.number}" if volume.number is not None else volume.path.name
        print(f"\n## {label}")
        print("\n".join(_structure_report(volume, scope)))


class Command(StrEnum):
    CHECK = "check"
    CHAPTERS = "chapters"
    SEARCH = "search"
    READ = "read"


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
                       help="a series directory (with books/), one book directory inside "
                            "it, or a standalone book directory")

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

    def add_start(p: argparse.ArgumentParser, with_paragraph: bool) -> None:
        group = p.add_argument_group("start point (optional; begins later, never needs permission)")
        group.add_argument("--start-book", type=_positive, metavar="N",
                           help="volume number to start in, in a series directory")
        exclusive = group.add_mutually_exclusive_group()
        exclusive.add_argument("--start-chapter", type=_positive, metavar="N",
                               help="start at this chapter")
        exclusive.add_argument("--start-section", type=_positive, metavar="N",
                               help="start at this section")
        group.add_argument("--start-part", type=_positive, metavar="P",
                           help="with --start-chapter, when numbering restarts in each part")
        if with_paragraph:
            group.add_argument("--start-paragraph", type=_positive, metavar="P",
                               help="start at this paragraph of the start section (or of "
                                    "the front matter, without a section)")

    def add_spoilers(p: argparse.ArgumentParser, with_all: bool) -> None:
        if with_all:
            p.add_argument("--all", action="store_true",
                           help="use every book in full (needs --allow-spoilers unless "
                                "all are finished)")
        p.add_argument("--allow-spoilers", action="store_true",
                       help="allow going past recorded progress; only when the user "
                            "explicitly allowed it for this request")

    check = sub.add_parser(Command.CHECK, help="structure and progress report, no titles or text",
                           epilog=CONCEPTS, formatter_class=formatter)
    add_target(check)

    chapters = sub.add_parser(Command.CHAPTERS, help="list sections within the boundary",
                              epilog=CONCEPTS, formatter_class=formatter)
    add_target(chapters)
    add_point(chapters, "story point (narrows the boundary; default: reading progress)")
    add_start(chapters, with_paragraph=False)
    add_spoilers(chapters, with_all=True)

    search = sub.add_parser(Command.SEARCH, help="search text within the boundary",
                            epilog=CONCEPTS, formatter_class=formatter)
    add_target(search)
    search.add_argument("query")
    add_point(search, "story point (narrows the boundary; default: reading progress)")
    add_start(search, with_paragraph=True)
    add_spoilers(search, with_all=True)
    output = search.add_argument_group("matching and output")
    output.add_argument("--regex", action="store_true",
                        help="treat the query as a regular expression; if it has capture "
                             "groups ( ), only the groups are highlighted")
    output.add_argument("--word", action="store_true",
                        help="match whole words only; works with --regex, where it "
                             "applies to the two ends of the whole pattern")
    output.add_argument("--case-sensitive", action="store_true")
    output.add_argument("--context", type=int, default=0, metavar="N",
                        help="show N whole paragraphs around each hit")
    output.add_argument("--full", action="store_true", help="show whole matching paragraphs")
    output.add_argument("--count", action="store_true", help="only count matches per section")
    output.add_argument("--max-chars", type=_positive, default=12000, metavar="N",
                        help="stop printing results after about N characters (default "
                             "12000) and print the --start-* flags that continue")

    read = sub.add_parser(Command.READ, help="print a chapter or section within the boundary",
                          epilog=CONCEPTS, formatter_class=formatter)
    add_target(read)
    add_point(read, "what to read")
    add_spoilers(read, with_all=False)
    read.add_argument("--from", dest="start", type=_positive, metavar="P",
                      help="first paragraph (reads only that section)")
    read.add_argument("--to", dest="end", type=_positive, metavar="Q",
                      help="last paragraph (reads only that section)")
    return parser


COMMANDS = {
    Command.CHECK: cmd_check,
    Command.CHAPTERS: cmd_chapters,
    Command.SEARCH: cmd_search,
    Command.READ: cmd_read,
}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        COMMANDS[Command(args.command)](load_target(args.target), args)
    except BookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
