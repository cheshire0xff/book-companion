"""Command-line pieces shared by the book-search commands.

Every command takes the same target and range flags, so a place, --from or --to
means exactly the same thing everywhere.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path

from book_companion.core.boundary import Selection, coverage, progress_text
from book_companion.core.errors import BookError
from book_companion.core.library import Target, load_target

CONCEPTS = """\
places:
  A place names a volume, part, chapter or section, and paragraph, in that
  order, in full or short words. Quote it.
    "volume 1 chapter 46"                 "v1 ch46"
    "volume 2 part 1 chapter 3"           "v2 pt1 ch3"
    "volume 2 section 4"                  "v2 s4"
    "volume 1 chapter 9 paragraph 3"      "v1 ch9 p3"
    "volume 2"                            "v2"
  A chapter or section includes the sections nested in it, such as an
  interlude inside a chapter; with a paragraph, the place is that paragraph.
  Results end every heading with the place of that section, ready to copy.

concepts:
  chapter   The number a reader uses ("chapter 46"), read from the book's
            table of contents.
  part      Only for books whose chapter numbering restarts in each part, and
            always with a chapter: "Book Two, chapter 5" is "part 2 chapter 5".
  section   Every item of the table of contents, numbered 1, 2, 3... in reading
            order: cover, prologue, part pages, chapters, interludes, epilogue.
            Every chapter is also a section. Use a section for a place without
            a chapter number; 'chapters' lists the numbers.
  volume    In a series directory, the number from the volume folder's prefix
            (volumes/01-empire-of-silence is volume 1). Every place names it, except a
            --to without one, which is in the volume of --from. In one volume's
            directory, or a standalone book, leave it out.
  range     --from PLACE is where to begin (default: the start). --to PLACE is
            the last place to include, through its end (default: the reading
            progress). A --to earlier than the reading progress works as of
            that story point.
  progress  One reading-progress.md per series (in the series directory), or
            per standalone book. It records a story point: the volume being
            read (volume:) and its last completed chapter or section. Earlier volumes
            count as read, later ones as unread.
  boundary  Text past the reading progress, through --to, --all or a place to
            read, needs --allow-spoilers, which is only for when the user
            explicitly allowed it for that request.
  paging    When output reaches --max-chars, the tool prints the command that
            shows the next page.
"""

FORMATTER = argparse.RawDescriptionHelpFormatter


def positive_int(value: str) -> int:
    if not re.fullmatch(r"[1-9]\d*", value):
        raise argparse.ArgumentTypeError(f"expected a whole number >= 1, got {value!r}")
    return int(value)


def add_target(p: argparse.ArgumentParser) -> None:
    p.add_argument("target", type=Path,
                   help="a series directory (with volumes/), one volume directory inside it, "
                        "or a standalone book directory")


def add_range(p: argparse.ArgumentParser, title: str, begin: str, end: str) -> None:
    group = p.add_argument_group(title)
    group.add_argument("--from", dest="from_place", metavar="PLACE", help=begin)
    group.add_argument("--to", dest="to_place", metavar="PLACE", help=end)


def add_spoilers(p: argparse.ArgumentParser, with_all: bool) -> None:
    if with_all:
        p.add_argument("--all", action="store_true",
                       help="use every volume in full (needs --allow-spoilers unless all are "
                            "read)")
    p.add_argument("--allow-spoilers", action="store_true",
                   help="allow going past recorded progress; only when the user explicitly "
                        "allowed it for this request")


def print_selection(target: Target, selection: Selection, verb: str) -> None:
    """Print the reading progress and what each volume contributes."""
    shown = target.selected(list(range(len(target.volumes))))
    count = len(shown)
    volumes = f" ({count} volume{'s' if count != 1 else ''})" if target.is_series else ""
    print(f"{verb} {target.name}{volumes}")
    print(f"  reading progress: {progress_text(target, selection.progress)}")
    if target.is_series:
        for volume, index in shown:
            print(f"  {volume.name}: "
                  f"{coverage(target, index, selection.start, selection.end)}")
    else:
        print(f"  range: {coverage(target, 0, selection.start, selection.end)}")


def shell_quote(arg: str) -> str:
    """Quote an argument so that it pastes unchanged into PowerShell or a POSIX shell."""
    if re.fullmatch(r"[\w./:-]+", arg):
        return arg
    if "'" not in arg:
        return f"'{arg}'"  # literal in both shells
    return '"' + re.sub(r'(["$`\\])', r"\\\1", arg) + '"'


def command_line(command: str, target: Path, *args: str) -> str:
    """A book-search command line that can be run as printed."""
    return " ".join(shell_quote(part)
                    for part in ("book-search", command, target.as_posix(), *args))


Handler = Callable[[Target, argparse.Namespace], None]


def utf8_streams() -> None:
    """Print UTF-8 whatever the console's code page, replacing what cannot be encoded."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def run[C: StrEnum](parser: argparse.ArgumentParser, commands: Mapping[C, Handler],
                    argv: list[str] | None) -> int:
    """Parse arguments, load the target and run the chosen command."""
    utf8_streams()
    args = parser.parse_args(argv)
    command_type = type(next(iter(commands)))
    try:
        commands[command_type(args.command)](load_target(args.target), args)
    except BookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
