"""book-search: spoiler-bounded search, reading and structure checks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from enum import StrEnum

from book_companion.core.boundary import Block, blocks, coverage, recorded_end, select, whole
from book_companion.core.cli import (
    CONCEPTS,
    FORMATTER,
    add_range,
    add_spoilers,
    add_target,
    command_line,
    positive_int,
    print_selection,
    run,
)
from book_companion.core.errors import BookError
from book_companion.core.places import Position, location, parse_place, section_place
from book_companion.core.structure import summarize
from book_companion.core.target import Target, Volume
from book_companion.core.text import Match, compile_query, find_matches, highlight, snippet

SEARCH_MAX_CHARS = 12000
READ_MAX_CHARS = 24000
RANGE = "range (optional; default: from the start up to the reading progress)"


@dataclass
class Hit:
    block: Block
    index: int  # paragraph index within the block
    matches: list[Match]


def _counts_by_section(target: Target, hits: list[Hit]) -> list[str]:
    blocks_seen: dict[int, Block] = {}
    counts: dict[int, int] = {}
    for hit in hits:
        blocks_seen.setdefault(id(hit.block), hit.block)
        counts[id(hit.block)] = counts.get(id(hit.block), 0) + len(hit.matches)
    return [f"  {counts[key]:4}  {location(target, block.volume, block.section)}"
            for key, block in blocks_seen.items()]


def _from_flags(target: Target, block: Block, index: int) -> list[str]:
    """--from at paragraph `index` (0-based) of a block; nothing at the very start."""
    place = section_place(target, block.volume, block.section, index + 1 if index else None)
    return ["--from", str(place)] if str(place) else []


def _search_options(args: argparse.Namespace) -> list[str]:
    """The options of a search other than --from, as typed on the command line."""
    options: list[str] = []
    max_chars = None if args.max_chars == SEARCH_MAX_CHARS else args.max_chars
    for flag, value in (("--to", args.to_place), ("--context", args.context or None),
                        ("--max-chars", max_chars)):
        if value is not None:
            options += [flag, str(value)]
    for flag, on in (("--all", args.all), ("--allow-spoilers", args.allow_spoilers),
                     ("--regex", args.regex), ("--word", args.word),
                     ("--case-sensitive", args.case_sensitive), ("--full", args.full)):
        if on:
            options.append(flag)
    return options


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
            stop = min(block.stop, hit.index + args.context + 1)
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
    selection = select(target, args)
    pattern = compile_query(args.query, args.regex, args.word, args.case_sensitive)
    print_selection(target, selection, "Searching")

    hits = [Hit(block, i, matches)
            for block in blocks(target, selection)
            for i in range(block.first, block.stop)
            if (matches := find_matches(block.paragraphs[i], pattern))]
    if not hits:
        print(f"\nNo matches for {args.query!r} within the range.")
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
        command = command_line("search", args.target, args.query,
                               *_from_flags(target, rest[0].block, rest[0].index),
                               *_search_options(args))
        print(f"Next page:  {command}")
        print("Or narrow it: a tighter query, --word, or a --from/--to range.")


def _read_options(args: argparse.Namespace) -> list[str]:
    """The options of a read other than --from, as typed on the command line."""
    options: list[str] = []
    if args.to_place is not None:
        options += ["--to", args.to_place]
    elif args.place is not None and str(end := replace(parse_place(args.place),
                                                       paragraph=None)):
        options += ["--to", str(end)]
    if args.allow_spoilers:
        options.append("--allow-spoilers")
    if args.max_chars != READ_MAX_CHARS:
        options += ["--max-chars", str(args.max_chars)]
    return options


def cmd_read(target: Target, args: argparse.Namespace) -> None:
    if args.place is None and args.from_place is None and args.to_place is None:
        raise BookError('Say what to read: a place such as "volume 1 chapter 3", or '
                        "--from PLACE, with --to PLACE to stop before the reading progress.")
    selection = select(target, args, args.place)
    used = 0
    printed = False
    for block in blocks(target, selection):
        if block.section is None and block.first >= block.stop:
            continue  # no front matter here
        heading = f"## {location(target, block.volume, block.section)}\n"
        print(heading)
        used += len(heading) + 1
        for i in range(block.first, block.stop):
            text = f"¶{i + 1}  {block.paragraphs[i]}\n"
            if printed and used + len(text) > args.max_chars:
                command = command_line("read", args.target, *_from_flags(target, block, i),
                                       *_read_options(args))
                print(f"--- Output limit reached (--max-chars {args.max_chars}).")
                print(f"Next page:  {command}")
                return
            print(text)
            used += len(text) + 1
            printed = True
    if selection.to_progress and selection.end < whole(target)[1]:
        print("[The reading progress ends here.]")


def cmd_chapters(target: Target, args: argparse.Namespace) -> None:
    selection = select(target, args)
    print_selection(target, selection, "Table of contents of")
    start, end = selection.start, selection.end
    for index in range(start.volume, end.volume + 1):
        volume = target.volumes[index]
        book = volume.book
        first = start.section if index == start.volume else 0
        last = end.section if index == end.volume else len(book.sections)
        print(f"\n## {volume.name}")
        part_column = f"{'part':>4}  " if book.has_parts else ""
        print(f"{'section':>7}  {part_column}{'ch':>4}  {'¶':>4}  label")
        for section in book.sections[max(first, 1) - 1:last]:
            chapter = str(section.chapter) if section.chapter is not None else "-"
            part = (f"{section.part if section.part is not None else '-':>4}  "
                    if book.has_parts else "")
            indent = "  " * (section.depth - 1)
            print(f"{section.number:>7}  {part}{chapter:>4}  {len(section.paragraphs):>4}  "
                  f"{indent}{section.heading}")
        if hidden := len(book.sections) - last:
            print(f"({hidden} later sections hidden)")


def _structure_report(volume: Volume, progress: str | None) -> list[str]:
    """Structure and progress of one volume, without any titles or text."""
    book = volume.book
    summary = summarize(book)
    numbers, parts = summary.numbers, summary.parts
    warnings = ["reading-progress.md is invalid"] if progress is None else []
    warnings += summary.warnings

    lines = [
        f"  Sections located:             {len(book.sections)} of {len(book.toc)}",
        f"  Numbered chapters:            {len(numbers)}"
        + (f" ({min(numbers)}-{max(numbers)})" if numbers else ""),
        f"  Parts:                        {len(parts) or 'none'}"
        + ("; chapter numbering restarts in each part (places and progress need the part)"
           if book.numbering_restarts else ""),
        f"  Duplicate chapter numbers:    {', '.join(summary.duplicates) or 'none'}",
        f"  Gaps in chapter numbers:      {', '.join(summary.gaps) or 'none'}",
        f"  Sections without a chapter:   {len(book.sections) - len(numbers)}",
        f"  Sections without own text:    {summary.empty}",
        f"  Contents pages excluded:      {len(book.toc_pages)}",
        f"  Unlisted spine files:         {book.unlisted_files} "
        "(attached to the preceding section)",
        f"  Missing spine files:          {book.missing_files}",
        f"  Front-matter paragraphs:      {len(book.front)}",
        f"  Reading progress:             {progress or 'ERROR (see above)'}",
        "  Result: " + ("OK" if not warnings else "WARN\n    - " + "\n    - ".join(warnings)),
    ]
    return lines


def cmd_check(target: Target, _args: argparse.Namespace) -> None:
    print("Structure check (no titles or text shown)")
    descriptions: list[str | None]
    try:
        end = recorded_end(target)
        progress = target.progress()
        where = f"volume {progress.volume}, " if progress.volume is not None else ""
        print(f"Reading progress ({target.progress_path}): {where}{progress.status}")
        start = Position(0, 0, 1)
        descriptions = [coverage(target, index, start, end, outside="not read yet")
                        if end is not None else "nothing completed yet"
                        for index in range(len(target.volumes))]
    except BookError as exc:
        descriptions = [None] * len(target.volumes)
        print(f"Reading progress: ERROR\n  - {exc}")
    for volume, description in target.selected(descriptions):
        label = f"Volume {volume.number}" if volume.number is not None else volume.path.name
        print(f"\n## {label}")
        print("\n".join(_structure_report(volume, description)))


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
    add_range(chapters, RANGE, begin='begin the listing here, e.g. --from "volume 2"',
              end='end the listing with this place, e.g. --to "volume 1 chapter 12"')
    add_spoilers(chapters, with_all=True)

    search = sub.add_parser(Command.SEARCH, help="search text within the boundary",
                            epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(search)
    search.add_argument("query")
    add_range(search, RANGE, begin='begin the search here, e.g. --from "volume 1 chapter 66"',
              end='end the search with this place, e.g. --to "volume 1 chapter 71"; '
                  "earlier than the reading progress, it searches as of that story point")
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
    output.add_argument("--max-chars", type=positive_int, default=SEARCH_MAX_CHARS, metavar="N",
                        help=f"stop printing results after about N characters (default "
                             f"{SEARCH_MAX_CHARS}) and print the command that shows the next "
                             "page; lower it if your output gets cut off")

    read = sub.add_parser(Command.READ,
                          help="print a chapter, a section, or a run of them, within the boundary",
                          epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(read)
    read.add_argument("place", nargs="?",
                      help='one chapter or section to read, e.g. "volume 1 chapter 46", with the '
                           "sections nested in it; from a paragraph, e.g. "
                           '"volume 1 chapter 46 paragraph 12", it reads on to the end of that '
                           "chapter")
    add_range(read, "range (instead of a place)",
              begin='begin reading here, e.g. --from "volume 1 chapter 40" or '
                    '--from "volume 1 chapter 46 paragraph 12"',
              end='the last place to read, e.g. --to "chapter 46" or --to "chapter 46 '
                  'paragraph 30"; without --to, reading goes on up to the reading progress, '
                  "a page at a time")
    add_spoilers(read, with_all=False)
    paging = read.add_argument_group("paging")
    paging.add_argument("--max-chars", type=positive_int, default=READ_MAX_CHARS, metavar="N",
                        help=f"stop after about N characters (default {READ_MAX_CHARS}) and "
                             "print the command that shows the next page; lower it if your "
                             "output gets cut off")
    return parser


COMMANDS = {
    Command.CHECK: cmd_check,
    Command.CHAPTERS: cmd_chapters,
    Command.SEARCH: cmd_search,
    Command.READ: cmd_read,
}


def main(argv: list[str] | None = None) -> int:
    return run(build_parser(), COMMANDS, argv)
