"""book-convert: convert an EPUB to plain text and an HTML package with Calibre.

Each conversion writes the requested TXT file and a sibling ``<name>-html/``
directory, the exploded HTML package that book-search reads. The HTML is
converted into a temporary directory first, so a failed conversion never
leaves a half-written ``<name>-html/`` behind or damages an existing one.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path

from book_companion.core.cli import utf8_streams
from book_companion.core.errors import BookError

HTML_SUFFIXES = frozenset({".html", ".htm", ".xhtml"})
FAILURE_TAIL_LINES = 20


def install_locations() -> list[Path]:
    """Where Calibre's installers put ebook-convert without adding it to PATH.

    Only Windows and macOS: on Linux, packages and Calibre's installer put it on PATH.
    """
    places = [Path(base) / "Calibre2" / "ebook-convert.exe"
              for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"))
              if base]
    places.append(Path("/Applications/calibre.app/Contents/MacOS/ebook-convert"))
    return places


def find_converter() -> list[str]:
    """The command that runs Calibre's ebook-convert."""
    if found := shutil.which("ebook-convert"):
        return [found]
    for place in install_locations():
        if place.is_file():
            return [str(place)]
    raise BookError("Calibre's ebook-convert was not found. Install Calibre "
                    "(https://calibre-ebook.com/download) or add ebook-convert to PATH.")


def _run(converter: Sequence[str], source: Path, destination: Path) -> None:
    try:
        result = subprocess.run([*converter, str(source), str(destination)],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", check=False)
    except OSError as exc:
        raise BookError(f"Could not run {converter[0]}: {exc}") from exc
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip().splitlines()
        tail = "\n".join(output[-FAILURE_TAIL_LINES:])
        raise BookError(f"ebook-convert failed with exit code {result.returncode} for "
                        f"output: {destination}" + (f"\n{tail}" if tail else ""))


def _has_html(directory: Path) -> bool:
    return any(path.is_file() and path.suffix.lower() in HTML_SUFFIXES
               and path.stat().st_size > 0 for path in directory.rglob("*"))


def convert(input_file: Path, output_file: Path, *, force: bool,
            converter: Sequence[str]) -> tuple[Path, Path]:
    """Convert an EPUB; return the TXT file and the HTML directory."""
    source = Path(os.path.abspath(input_file))
    if not source.exists():
        raise BookError(f"Input file not found: {source}")
    if source.is_dir():
        raise BookError(f"Input path is a directory: {source}")
    if source.suffix.lower() != ".epub":
        raise BookError(f"Input file must have an .epub extension: {source}")

    text = Path(os.path.abspath(output_file))
    if text.suffix.lower() != ".txt":
        raise BookError(f"Output file must have a .txt extension: {text}")
    if not text.parent.is_dir():
        raise BookError(f"Output directory does not exist: {text.parent}")
    if text.is_dir():
        raise BookError(f"Output path is a directory: {text}")
    if text.exists() and not force:
        raise BookError(f"Output file already exists. Use --force to replace it: {text}")

    html = text.with_name(text.stem + "-html")
    if html.exists():
        if not html.is_dir():
            raise BookError(f"HTML output path exists as a file: {html}")
        if not force:
            raise BookError(f"HTML output directory already exists. "
                            f"Use --force to replace it: {html}")

    _run(converter, source, text)
    if not text.is_file():
        raise BookError(f"Conversion completed without creating the output file: {text}")
    if text.stat().st_size == 0:
        raise BookError(f"Conversion created an empty output file: {text}")

    # No extension: Calibre writes an exploded HTML package into this directory.
    staging = text.with_name(f"{text.stem}-html-{uuid.uuid4().hex}")
    try:
        _run(converter, source, staging)
        if not staging.is_dir():
            raise BookError(f"HTML conversion completed without creating a directory: {staging}")
        if not _has_html(staging):
            raise BookError(f"HTML conversion created no non-empty HTML files: {staging}")
        if html.exists():
            shutil.rmtree(html)
        staging.rename(html)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return text, html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="book-convert",
        description="Convert an EPUB to plain text and an HTML package with Calibre's "
                    "ebook-convert. Prints the paths of the TXT file and the HTML directory.")
    parser.add_argument("input", type=Path, help="the source EPUB")
    parser.add_argument("output", type=Path,
                        help="the TXT file to create; a sibling <name>-html/ directory "
                             "is created next to it")
    parser.add_argument("--force", action="store_true",
                        help="replace an existing TXT file and HTML directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    utf8_streams()
    args = build_parser().parse_args(argv)
    try:
        text, html = convert(args.input, args.output, force=args.force,
                             converter=find_converter())
    except BookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(text)
    print(html)
    return 0
