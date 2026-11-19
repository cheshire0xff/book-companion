"""The strict front-matter block of reading-progress.md, validated by the `Progress` model."""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator

from book_companion.core.frontmatter import load_front_matter


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

    def read_in_full(self, volume: int | None, *, standalone: bool) -> bool:
        """Whether a book is read to its end, so its memory and review are no spoilers.

        volume: the series volume's number (None if its folder has no number prefix);
        ignored for a standalone book.
        """
        if standalone:
            return self.status is Status.FINISHED
        if volume is None or self.volume is None:
            return False
        return volume < self.volume or (volume == self.volume
                                        and self.status is Status.FINISHED)


def parse_progress(path: Path) -> Progress:
    """Read the front-matter block at the top of reading-progress.md."""
    return load_front_matter(path, Progress, template="spoiler-rules.md")
