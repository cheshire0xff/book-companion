"""The strict front-matter block of reading-progress.md.

The block is read line by line (so a repeated key is caught), and its values are
validated by the `Progress` model.
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, ValidationError, model_validator

from book_companion.core.errors import BookError, explain


class Status(StrEnum):
    NOT_STARTED = "not started"
    READING = "reading"
    FINISHED = "finished"


def _whole_number(value: object) -> object:
    """Front-matter numbers: a whole number >= 1, or empty."""
    if isinstance(value, str):
        if not value:
            return None
        if not re.fullmatch(r"[1-9]\d*", value):
            raise ValueError(f"must be a whole number or empty; found {value!r}")
        return int(value)
    return value


def _date_or_empty(value: object) -> object:
    if isinstance(value, str):
        if not value:
            return None
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError(f"must be YYYY-MM-DD or empty; found {value!r}")
    return value


WholeNumber = Annotated[int | None, BeforeValidator(_whole_number)]
OptionalDate = Annotated[date | None, BeforeValidator(_date_or_empty)]


class Progress(BaseModel):
    """The front-matter values: a story point (volume, then chapter or section)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Status
    volume: WholeNumber = None
    chapter: WholeNumber = None
    part: WholeNumber = None
    section: WholeNumber = None
    updated: OptionalDate = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.chapter is not None and self.section is not None:
            raise ValueError("set chapter or section, not both")
        if self.part is not None and self.chapter is None:
            raise ValueError("part is only used together with chapter")
        return self


def parse_progress(path: Path) -> Progress:
    """Read the front-matter block at the top of reading-progress.md."""
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
        name, sep, value = line.partition(":")
        if not sep:
            raise BookError(f"{path}:{line_no}: expected 'key: value'.")
        key = name.strip().lower()
        if key in values:
            raise BookError(f"{path}:{line_no}: {key!r} is set twice.")
        values[key] = value.strip()
    try:
        return Progress.model_validate(values)
    except ValidationError as error:
        raise explain(error, str(path)) from None
