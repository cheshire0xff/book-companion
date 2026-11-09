"""book-search: spoiler-bounded search, reading and structure checks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import StrEnum

from book_companion.core.boundary import (
    Block,
    Scope,
    allowed_text,
    recorded_scopes,
    resolve_scopes,
    resolve_start,
)
from book_companion.core.cli import (
    CONCEPTS,
    FORMATTER,
    add_point,
    add_spoilers,
    add_start,
    add_target,
    positive_int,
    print_scopes,
    run,
)
from book_companion.core.errors import BookError
from book_companion.core.library import Target, Volume, location
from book_companion.core.structure import Book, Section, describe_chapter, find_chapter
from book_companion.core.text import Match, compile_query, find_matches, highlight, snippet


@dataclass
class Hit:
    block: Block
    index: int  # paragraph index within the block
    matches: list[Match]


def _counts_by_section(target: Target, hits: list[Hit]) -> list[str]:
    blocks: dict[int, Block] = {}
    counts: dict[int, int] = {}
    for hit in hits:
        blocks.setdefault(id(hit.block), hit.block)
        counts[id(hit.block)] = counts.get(id(hit.block), 0) + len(hit.matches)
    return [f"  {counts[key]:4}  {location(target, block.volume, block.section)}"
            for key, block in blocks.items()]


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
    print_scopes(target, scopes, "Searching")
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


def _through(book: Book, args: argparse.Namespace) -> Section | None:
    """The later point a read goes on through, if --through-* was given."""
    if args.through_part is not None and args.through_chapter is None:
        raise BookError("--through-part is only used together with --through-chapter.")
    if args.through_chapter is not None:
        return find_chapter(book, args.through_chapter, args.through_part)
    if args.through_section is not None:
        return book.section(args.through_section)
    return None


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
    through = _through(book, args)
    if through is not None and through.number < section.number:
        raise BookError("--through-chapter/--through-section must not come before what is "
                        "being read.")

    scope = recorded_scopes(target)[target.volumes.index(volume)]
    if args.allow_spoilers:
        scope = Scope(True, None, "--allow-spoilers: whole book")
    elif not scope.allows(section):
        raise BookError("That is beyond the reading progress. Add --allow-spoilers only "
                        "if the user explicitly allowed it for this request.")

    ranged = args.start is not None or args.end is not None
    resuming = args.start_section is not None or args.start_paragraph is not None
    if ranged and resuming:
        raise BookError("Use --from/--to or --start-section/--start-paragraph, not both.")
    if ranged and through is not None:
        raise BookError("--from/--to read part of one section; leave out "
                        "--through-chapter/--through-section.")
    last = section.number if ranged else max(book.subtree_end(section),
                                             book.subtree_end(through or section))
    first_section = args.start_section or section.number
    if not section.number <= first_section <= last:
        raise BookError(f"--start-section must be within sections {section.number}-{last} "
                        "of what is being read.")

    flags = [f"--book {volume.number}"] if target.is_series and target.only is None else []
    flags.append(f"--section {section.number}")
    if through is not None:
        flags.append(f"--through-section {through.number}")
    if args.allow_spoilers:
        flags.append("--allow-spoilers")
    used = 0
    printed = False
    for current in book.sections[first_section - 1:last]:
        if not scope.allows(current):
            print("[The rest is beyond the reading progress.]")
            break
        heading = f"## {location(target, volume, current)}\n"
        print(heading)
        used += len(heading) + 1
        if ranged:
            first, final = args.start or 1, args.end or len(current.paragraphs)
        else:
            first = (args.start_paragraph or 1) if current.number == first_section else 1
            final = len(current.paragraphs)
        for i in range(max(1, first), min(len(current.paragraphs), final) + 1):
            text = f"¶{i}  {current.paragraphs[i - 1]}\n"
            if printed and used + len(text) > args.max_chars:
                more = ([f"--from {i}"] + ([f"--to {args.end}"] if args.end else []) if ranged
                        else [f"--start-section {current.number}", f"--start-paragraph {i}"])
                print(f"--- Output limit reached (--max-chars {args.max_chars}). Continue: "
                      f"rerun read with  {' '.join(flags + more)}")
                return
            print(text)
            used += len(text) + 1
            printed = True


def cmd_chapters(target: Target, args: argparse.Namespace) -> None:
    scopes = resolve_scopes(target, args)
    start = resolve_start(target, args)
    print_scopes(target, scopes, "Table of contents of")
    allowed_text(target, scopes, start)  # validates the start point
    for index, (volume, scope) in enumerate(zip(target.volumes, scopes, strict=True)):
        if target.only is not None and volume.number != target.only:
            continue
        if not scope.included or (start is not None and index < start.volume_index):
            continue
        first = start.section if start is not None and index == start.volume_index else 0
        book = volume.book
        print(f"\n## {volume.name}")
        part_column = f"{'part':>4}  " if book.has_parts else ""
        print(f"{'section':>7}  {part_column}{'ch':>4}  {'¶':>4}  label")
        hidden = 0
        for section in book.sections:
            if section.number < first:
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
    keys = [(s.part, s.chapter) for s in book.sections if s.chapter is not None]
    numbers = [chapter for _, chapter in keys]
    duplicates = sorted({describe_chapter(n, p) for p, n in keys if keys.count((p, n)) > 1})
    parts = sorted({p for p, _ in keys if p is not None})
    restarts = len(set(numbers)) < len(numbers) and not duplicates
    gaps: list[str] = []
    groups: list[int | None] = list(parts) or [None]
    for part in groups:
        values = sorted({n for p, n in keys if p == part or not parts})
        if values:
            gaps += [describe_chapter(n, part)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Spoiler-bounded search over converted books.",
        epilog=CONCEPTS, formatter_class=FORMATTER)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser(Command.CHECK, help="structure and progress report, no titles or text",
                           epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(check)

    chapters = sub.add_parser(Command.CHAPTERS, help="list sections within the boundary",
                              epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(chapters)
    add_point(chapters, "story point (narrows the boundary; default: reading progress)")
    add_start(chapters, with_paragraph=False)
    add_spoilers(chapters, with_all=True)

    search = sub.add_parser(Command.SEARCH, help="search text within the boundary",
                            epilog=CONCEPTS, formatter_class=FORMATTER)
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
    output.add_argument("--max-chars", type=positive_int, default=12000, metavar="N",
                        help="stop printing results after about N characters (default "
                             "12000) and print the --start-* flags that continue; lower it "
                             "if your output gets cut off")

    read = sub.add_parser(Command.READ,
                          help="print a chapter, a section, or a run of them, within the boundary",
                          epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(read)
    add_point(read, "what to read")
    on = read.add_argument_group(
        "reading on (optional): go on through a later point, e.g. a whole book in order")
    ends = on.add_mutually_exclusive_group()
    ends.add_argument("--through-chapter", type=positive_int, metavar="N",
                      help="go on through this chapter, e.g. --chapter 1 --through-chapter 10")
    ends.add_argument("--through-section", type=positive_int, metavar="N",
                      help="go on through this section")
    on.add_argument("--through-part", type=positive_int, metavar="P",
                    help="with --through-chapter, when numbering restarts in each part")
    add_spoilers(read, with_all=False)
    paragraphs = read.add_argument_group("paragraph range")
    paragraphs.add_argument("--from", dest="start", type=positive_int, metavar="P",
                            help="first paragraph (reads only that section, not nested ones)")
    paragraphs.add_argument("--to", dest="end", type=positive_int, metavar="Q",
                            help="last paragraph (reads only that section, not nested ones)")
    paging = read.add_argument_group(
        "paging (the tool prints these flags when output is cut off)")
    paging.add_argument("--max-chars", type=positive_int, default=24000, metavar="N",
                        help="stop after about N characters (default 24000) and print "
                             "the flags that continue; lower it if your output gets cut off")
    paging.add_argument("--start-section", type=positive_int, metavar="N",
                        help="continue at this section of what is being read")
    paging.add_argument("--start-paragraph", type=positive_int, metavar="P",
                        help="continue at this paragraph of the start section")
    return parser


COMMANDS = {
    Command.CHECK: cmd_check,
    Command.CHAPTERS: cmd_chapters,
    Command.SEARCH: cmd_search,
    Command.READ: cmd_read,
}


def main(argv: list[str] | None = None) -> int:
    return run(build_parser(), COMMANDS, argv)
