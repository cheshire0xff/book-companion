"""Typed records produced by the extraction passes, as pydantic models.

Only what the tool relies on is structured: entity ids, the links from notes and
aliases to entities, and references into the text. What a note says is free text,
written for the agent that reads it later.

A worker's result is validated with the section's text as the validation context
(`Source`): names are checked against the text, and each quoted reference is
checked and turned into a span. Stored records hold only those spans; the words
are cut from the book when a note is shown. Checks that need the existing notes
(reading order, known entities) live in ingest.py.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    StringConstraints,
    ValidationError,
    ValidationInfo,
    model_validator,
)

from book_companion.core.errors import BookError, explain
from book_companion.core.text import locate, normalize


class Pass(StrEnum):
    CORE = "core"
    APPEARANCE = "appearance"
    WORLD = "world"
    THREADS = "threads"


class RecordType(StrEnum):
    """The record lists of a result, which are also the notes files."""

    ENTITIES = "entities"
    ALIASES = "aliases"
    NOTES = "notes"
    RECAP = "recap"


PASS_RECORDS: dict[Pass, frozenset[RecordType]] = {
    Pass.CORE: frozenset(RecordType),
    Pass.APPEARANCE: frozenset({RecordType.ENTITIES, RecordType.NOTES}),
    Pass.WORLD: frozenset({RecordType.ENTITIES, RecordType.NOTES}),
    Pass.THREADS: frozenset({RecordType.ENTITIES, RecordType.NOTES}),
}

QUOTE_MAX = 300
NOTE_WORDS = 80


# -- field types -----------------------------------------------------------------


def _squash(value: object) -> object:
    """Collapse runs of whitespace, so limits and checks see normal text."""
    return " ".join(value.split()) if isinstance(value, str) else value


def _max_words(limit: int) -> Callable[[str], str]:
    def check(value: str) -> str:
        if len(value.split()) > limit:
            raise ValueError(f"has {len(value.split())} words; the limit is {limit}")
        return value
    return check


Squashed = BeforeValidator(_squash)
Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
Name = Annotated[str, Squashed, StringConstraints(min_length=1, max_length=120)]
Quote = Annotated[str, Squashed, StringConstraints(min_length=1, max_length=QUOTE_MAX)]
NoteText = Annotated[str, Squashed, StringConstraints(min_length=1),
                     AfterValidator(_max_words(NOTE_WORDS))]
RecapText = Annotated[str, Squashed, StringConstraints(min_length=1),
                      AfterValidator(_max_words(150))]
StoryText = Annotated[str, Squashed, StringConstraints(min_length=1),
                      AfterValidator(_max_words(400))]
Number = Annotated[int, Field(strict=True, ge=1)]
Offset = Annotated[int, Field(strict=True, ge=0)]


# -- the text a result is checked against ------------------------------------------


@dataclass(frozen=True)
class Source:
    """The paragraphs of the section a worker's result is about (the validation context)."""

    paragraphs: tuple[str, ...]
    text: str  # all paragraphs, normalized

    @classmethod
    def of(cls, paragraphs: list[str]) -> Source:
        return cls(tuple(paragraphs), normalize("\n".join(paragraphs)))

    def mentions(self, name: str) -> bool:
        return re.search(rf"(?<!\w){re.escape(normalize(name))}(?!\w)", self.text) is not None


def _source(info: ValidationInfo) -> Source | None:
    return info.context if isinstance(info.context, Source) else None


class Cite(BaseModel):
    """A reference as a worker writes it: a paragraph and an exact quote from it."""

    model_config = ConfigDict(extra="forbid")

    paragraph: Number
    quote: Quote


class Ref(BaseModel):
    """A reference as stored: a paragraph and the span of the quoted words in it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paragraph: Number
    start: Offset
    end: Offset

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("'end' must be after 'start'")
        return self


def _locate(value: Any, info: ValidationInfo) -> Any:
    """With a Source, read a worker's {paragraph, quote} and turn it into a stored span."""
    source = _source(info)
    if source is None:
        return value  # a stored reference
    cite = Cite.model_validate(value)
    count = len(source.paragraphs)
    if cite.paragraph > count:
        raise ValueError(f"paragraph {cite.paragraph} does not exist; this section has {count}")
    text = source.paragraphs[cite.paragraph - 1]
    span = locate(text, cite.quote)
    if span is None:
        raise ValueError(f"the quote is not in paragraph {cite.paragraph} (quotes must be "
                         f"exact, contiguous excerpts). That paragraph begins: {text[:120]!r}")
    return {"paragraph": cite.paragraph, "start": span[0], "end": span[1]}


RefField = Annotated[Ref, BeforeValidator(_locate)]
Refs = Annotated[list[RefField], Field(min_length=1)]


# -- records ------------------------------------------------------------------------


class Origin(BaseModel):
    """Which pass over which section produced a record."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    pass_: Pass = Field(alias="pass")
    book: int | None  # volume number; None for a standalone book
    section: int


class Record(BaseModel):
    """Base of every stored record. The origin is attached after validation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    _origin: Origin | None = PrivateAttr(default=None)

    @property
    def origin(self) -> Origin:
        if self._origin is None:
            raise RuntimeError("record has no origin yet")
        return self._origin

    def placed(self, origin: Origin) -> Self:
        self._origin = origin
        return self

    def references(self) -> list[str]:
        """Entity ids this record refers to (not counting an entity's own id)."""
        return []


class Named(Record):
    """A record that introduces a name, which must appear in the section."""

    name: Name

    @model_validator(mode="after")
    def _in_the_text(self, info: ValidationInfo) -> Self:
        source = _source(info)
        if source is not None and not source.mentions(self.name):
            raise ValueError(f"the name {self.name!r} does not appear in this section; "
                             "use the name as this section gives it")
        return self


class Entity(Named):
    id: Id
    kind: Id  # a free label such as character, place, group, species, ship


class Alias(Named):
    entity: Id

    def references(self) -> list[str]:
        return [self.entity]


class Note(Record):
    about: list[Id] = []
    text: NoteText
    refs: Refs

    def references(self) -> list[str]:
        return list(self.about)


class Recap(Record):
    text: RecapText
    story_so_far: StoryText


MODELS: dict[RecordType, type[Record]] = {
    RecordType.ENTITIES: Entity,
    RecordType.ALIASES: Alias,
    RecordType.NOTES: Note,
    RecordType.RECAP: Recap,
}


class Header(BaseModel):
    """Which pass and section a result is for; read first, to find the section's text."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    pass_: Pass = Field(alias="pass")
    book: Number | None = None
    section: Number

    def origin(self) -> Origin:
        return Origin(pass_=self.pass_, book=self.book, section=self.section)


class SectionResult(Header):
    """What a worker hands in for one pass over one section."""

    model_config = ConfigDict(extra="forbid")

    entities: list[Entity] = []
    aliases: list[Alias] = []
    notes: list[Note] = []
    recap: Recap | None = None

    @model_validator(mode="after")
    def _fits_the_pass(self) -> Self:
        allowed = PASS_RECORDS[self.pass_]
        for kind, records in self.records().items():
            if records and kind not in allowed:
                names = ", ".join(sorted(allowed))
                raise ValueError(f"the {self.pass_} pass does not record {kind} "
                                 f"(it records {names})")
        if self.pass_ is Pass.CORE and self.recap is None:
            raise ValueError("the core pass needs a 'recap'")
        if self.pass_ is Pass.APPEARANCE:
            for i, note in enumerate(self.notes):
                if not note.about:
                    raise ValueError(f"notes[{i}]: an appearance note needs at least one "
                                     "entity in 'about'")
        return self

    def records(self) -> dict[RecordType, list[Record]]:
        return {
            RecordType.ENTITIES: list(self.entities),
            RecordType.ALIASES: list(self.aliases),
            RecordType.NOTES: list(self.notes),
            RecordType.RECAP: [self.recap] if self.recap else [],
        }


# -- conversion ------------------------------------------------------------------------


def parse_header(data: Any, where: str) -> Header:
    try:
        return Header.model_validate(data)
    except ValidationError as error:
        raise explain(error, where) from None


def parse_result(data: Any, where: str, source: Source) -> SectionResult:
    try:
        return SectionResult.model_validate(data, context=source)
    except ValidationError as error:
        raise explain(error, where) from None


def record_to_json(record: Record) -> dict[str, Any]:
    body = record.model_dump(mode="json", by_alias=True, exclude_defaults=True)
    return record.origin.model_dump(mode="json", by_alias=True) | body


def record_from_json(kind: RecordType, data: Any, where: str) -> Record:
    if not isinstance(data, dict):
        raise BookError(f"{where}: expected a JSON object.")
    body = dict(data)
    try:
        origin = Origin.model_validate({key: body.pop(key, None)
                                        for key in ("pass", "book", "section")})
        return MODELS[kind].model_validate(body).placed(origin)
    except ValidationError as error:
        raise explain(error, where) from None
