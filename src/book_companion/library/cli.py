"""book-library: commands over the whole library.

check walks the library and reports, one line each, what the tools and skills can't
use as it is, with its path and what to do about it, grouped by series.
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from enum import StrEnum
from pathlib import Path

from book_companion.core.cli import FORMATTER, utf8_streams
from book_companion.core.errors import BookError
from book_companion.library.check import check_library
from book_companion.library.findings import RULES, Report, Severity, relative

SEVERITY_HEADINGS = {
    Severity.ERROR: "errors: a tool or skill can't use this as it is; the exit status is then 1",
    Severity.WARNING: "warnings: against the library's conventions; it works, but take a look",
    Severity.WAITING: "waiting: not a problem, but something to import or generate next",
}

CHECK_NOTES = """\
not checked:
  what metadata.md, description.md, prompt sidecars, book memories and
  review.md say (only whether they are there); whether source.epub is a valid
  EPUB; folders whose names start with . or _ (except in volumes/); anything
  outside books/ and _incoming/.

The check only reads: it never moves, fixes or deletes anything. It shows no
book titles or text, only paths, counts and chapter numbers. Paths are
relative to the library folder, so the commands it suggests run from there.

exit status: 0 without errors, 1 with errors, 2 if the folder has no books/.
"""


def check_epilog() -> str:
    """Every rule of the check, by severity, from RULES, then the notes."""
    lines: list[str] = []
    for severity in Severity:
        lines.append(SEVERITY_HEADINGS[severity])
        for rule in RULES.values():
            if rule.severity is severity:
                lines += textwrap.wrap(rule.description, width=79, initial_indent="  - ",
                                       subsequent_indent="    ", break_on_hyphens=False)
        lines.append("")
    return "\n".join(lines) + "\n" + CHECK_NOTES


class Command(StrEnum):
    CHECK = "check"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="book-library",
                                     description="Commands over the whole library.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser(
        Command.CHECK, help="report what the tools and skills can't use as it is",
        description="Walk the whole library and report, one line each, what the tools and "
                    "skills can't use as it is, with what to do about it.",
        epilog=check_epilog(), formatter_class=FORMATTER)
    check.add_argument("library", type=Path, nargs="?", default=Path("."),
                       help="the library folder, the one that holds books/ "
                            "(default: the current folder)")
    return parser


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 or word == 'waiting' else 's'}"


def render(report: Report) -> str:
    """The report, errors first within each group, then warnings, then what is waiting."""
    rank = {severity: index for index, severity in enumerate(Severity)}
    lines = [f"Library check of {report.root} (nothing is changed)"]
    for group in report.groups:
        lines += ["", f"## {group.name}"]
        if not group.findings:
            lines.append("  ok")
        lines += [f"  {finding.severity:<8} {relative(report.root, finding.path)}: "
                  f"{finding.problem} {finding.fix}"
                  for finding in sorted(group.findings, key=lambda f: rank[f.severity])]
    counts = ", ".join(_plural(report.count(severity), severity) for severity in Severity)
    lines += ["", f"Result: {counts}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    utf8_streams()
    args = build_parser().parse_args(argv)
    # abspath, not resolve(), as for book-search targets: it keeps mapped drives as given
    root = Path(os.path.abspath(args.library))
    try:
        report = check_library(root)
    except BookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(render(report))
    return 1 if report.count(Severity.ERROR) else 0
