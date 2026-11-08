"""The strict front-matter block of reading-progress.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from book_companion.core.errors import BookError


class ProgressKey(StrEnum):
    BOOK = "book"
    STATUS = "status"
    CHAPTER = "chapter"
    PART = "part"
    SECTION = "section"
    UPDATED = "updated"


class Status(StrEnum):
    NOT_STARTED = "not started"
    READING = "reading"
    FINISHED = "finished"


NUMBER_KEYS = (ProgressKey.BOOK, ProgressKey.CHAPTER, ProgressKey.PART, ProgressKey.SECTION)


@dataclass(frozen=True)
class Progress:
    status: Status
    book: int | None = None
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

    values: dict[ProgressKey, str] = {}
    for line_no, raw in enumerate(lines[1:end], start=2):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name, sep, value = line.partition(":")
        if not sep:
            raise BookError(f"{path}:{line_no}: expected 'key: value'.")
        try:
            key = ProgressKey(name.strip().lower())
        except ValueError:
            raise BookError(f"{path}:{line_no}: unknown key {name.strip()!r} "
                            f"(allowed: {', '.join(ProgressKey)}).") from None
        if key in values:
            raise BookError(f"{path}:{line_no}: {key!r} is set twice.")
        values[key] = value.strip()

    raw_status = values.get(ProgressKey.STATUS, "")
    try:
        status = Status(raw_status)
    except ValueError:
        raise BookError(f"{path}: status must be one of {', '.join(Status)}; "
                        f"found {raw_status!r}.") from None
    numbers: dict[ProgressKey, int | None] = {}
    for key in NUMBER_KEYS:
        value = values.get(key, "")
        if value and not re.fullmatch(r"[1-9]\d*", value):
            raise BookError(f"{path}: {key} must be a whole number or empty; found {value!r}.")
        numbers[key] = int(value) if value else None
    updated = values.get(ProgressKey.UPDATED, "")
    if updated and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
        raise BookError(f"{path}: updated must be YYYY-MM-DD or empty; found {updated!r}.")

    progress = Progress(status, book=numbers[ProgressKey.BOOK],
                        chapter=numbers[ProgressKey.CHAPTER], part=numbers[ProgressKey.PART],
                        section=numbers[ProgressKey.SECTION])
    if progress.chapter is not None and progress.section is not None:
        raise BookError(f"{path}: set chapter or section, not both.")
    if progress.part is not None and progress.chapter is None:
        raise BookError(f"{path}: part is only used together with chapter.")
    return progress
