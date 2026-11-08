"""Command-line pieces shared by the book-search commands.

Every command takes the same target and boundary flags, so a story point or
start point means exactly the same thing everywhere.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path

from book_companion.core.boundary import Scope
from book_companion.core.errors import BookError
from book_companion.core.library import Target, load_target

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
            --start-chapter 66 --chapter 71. When output reaches --max-chars,
            the tool prints the flags that continue from where it stopped.
"""

FORMATTER = argparse.RawDescriptionHelpFormatter


def positive_int(value: str) -> int:
    if not re.fullmatch(r"[1-9]\d*", value):
        raise argparse.ArgumentTypeError(f"expected a whole number >= 1, got {value!r}")
    return int(value)


def add_target(p: argparse.ArgumentParser) -> None:
    p.add_argument("target", type=Path,
                   help="a series directory (with books/), one book directory inside it, "
                        "or a standalone book directory")


def add_point(p: argparse.ArgumentParser, title: str) -> None:
    group = p.add_argument_group(title)
    group.add_argument("--book", type=positive_int, metavar="N",
                       help="volume number, in a series directory")
    exclusive = group.add_mutually_exclusive_group()
    exclusive.add_argument("--chapter", type=positive_int, metavar="N", help="chapter number")
    exclusive.add_argument("--section", type=positive_int, metavar="N",
                           help="section number, for places without a chapter number")
    group.add_argument("--part", type=positive_int, metavar="P",
                       help="with --chapter, when numbering restarts in each part")


def add_start(p: argparse.ArgumentParser, with_paragraph: bool) -> None:
    group = p.add_argument_group("start point (optional; begins later, never needs permission)")
    group.add_argument("--start-book", type=positive_int, metavar="N",
                       help="volume number to start in, in a series directory")
    exclusive = group.add_mutually_exclusive_group()
    exclusive.add_argument("--start-chapter", type=positive_int, metavar="N",
                           help="start at this chapter")
    exclusive.add_argument("--start-section", type=positive_int, metavar="N",
                           help="start at this section")
    group.add_argument("--start-part", type=positive_int, metavar="P",
                       help="with --start-chapter, when numbering restarts in each part")
    if with_paragraph:
        group.add_argument("--start-paragraph", type=positive_int, metavar="P",
                           help="start at this paragraph of the start section (or of the "
                                "front matter, without a section)")


def add_spoilers(p: argparse.ArgumentParser, with_all: bool) -> None:
    if with_all:
        p.add_argument("--all", action="store_true",
                       help="use every book in full (needs --allow-spoilers unless all "
                            "are finished)")
    else:
        p.set_defaults(all=False)
    p.add_argument("--allow-spoilers", action="store_true",
                   help="allow going past recorded progress; only when the user explicitly "
                        "allowed it for this request")


def print_scopes(target: Target, scopes: list[Scope], verb: str) -> None:
    """Print what each book contributes; fail if nothing is within the boundary."""
    shown = target.selected(scopes)
    count = len(shown)
    books = f" ({count} book{'s' if count != 1 else ''})" if target.is_series else ""
    print(f"{verb} {target.name}{books}")
    for volume, scope in shown:
        print(f"  {volume.name}: {scope.description}")
    if not any(scope.included for _, scope in shown):
        raise BookError("No text is within the reading boundary (nothing completed yet). "
                        "Ask the user what they have read.")


Handler = Callable[[Target, argparse.Namespace], None]


def run[C: StrEnum](parser: argparse.ArgumentParser, commands: Mapping[C, Handler],
                    argv: list[str] | None) -> int:
    """Parse arguments, load the target and run the chosen command."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parser.parse_args(argv)
    command_type = type(next(iter(commands)))
    try:
        commands[command_type(args.command)](load_target(args.target), args)
    except BookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
