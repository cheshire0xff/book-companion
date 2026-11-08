"""Which sections each pass still has to do, and what the notes know before a point."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from book_companion.core.boundary import Scope
from book_companion.core.library import Target, Volume
from book_companion.core.structure import Section
from book_companion.core.text import normalize
from book_companion.notes.model import Entity, Origin, Pass, Recap, RecordType
from book_companion.notes.store import Position, Store, position

CAST_LIMIT = 60  # above this many known entities, the context shows only relevant ones
RECENT_RECAPS = 3


@dataclass(frozen=True)
class Unit:
    """One section with text, as a unit of work for the passes."""

    volume: Volume
    index: int  # volume index in reading order
    section: Section

    @property
    def book(self) -> int | None:
        return self.volume.number

    @property
    def position(self) -> Position:
        return (self.index, self.section.number)

    def origin(self, pass_: Pass) -> Origin:
        return Origin(pass_=pass_, book=self.book, section=self.section.number)


NON_STORY_LABELS = (
    "cover", "title page", "title", "copyright", "dedication", "contents",
    "table of contents", "acknowledgments", "acknowledgements", "also by", "about the author",
    "about the publisher", "praise for", "newsletter",
)


def is_story(section: Section) -> bool:
    """False for standard front and back matter, which the passes skip."""
    label = normalize(section.label).strip(" .:")
    return not any(label == name or label.startswith(name + " ") for name in NON_STORY_LABELS)


def units_within(target: Target, scopes: list[Scope]) -> list[Unit]:
    """Every story section with text inside the scopes, in reading order, across the series."""
    units = []
    for index, (volume, scope) in enumerate(zip(target.volumes, scopes, strict=True)):
        if not scope.included:
            continue
        units += [Unit(volume, index, s) for s in volume.book.sections
                  if s.paragraphs and scope.allows(s) and is_story(s)]
    return units


def pending(target: Target, store: Store, pass_: Pass,
            scopes: list[Scope]) -> tuple[list[Unit], Unit | None]:
    """Sections still to do for a pass, and the first one waiting for the core pass."""
    todo: list[Unit] = []
    for unit in units_within(target, scopes):
        if unit.origin(pass_) in store.done:
            continue
        if pass_ is not Pass.CORE and unit.origin(Pass.CORE) not in store.done:
            return todo, unit
        todo.append(unit)
    return todo, None


Keep = Callable[[Origin], bool]  # decides whether a record's origin is visible


def known_names(store: Store, keep: Keep) -> dict[str, list[str]]:
    """Names and aliases of the entities whose records pass `keep(origin)`."""
    names = {e.id: [e.name] for e in store.entities() if keep(e.origin)}
    for alias in store.aliases():
        if keep(alias.origin) and alias.entity in names and alias.name not in names[alias.entity]:
            names[alias.entity].append(alias.name)
    return names


@dataclass
class Context:
    story: Recap | None
    recent: list[Recap]
    entities: list[Entity]
    names: dict[str, list[str]]
    kinds: list[tuple[str, int]]  # entity kinds in use, most used first
    total: int


def build_context(target: Target, store: Store, cutoff: Position, inclusive: bool,
                  units: list[Unit]) -> Context:
    """What the notes know before (or through) a point, for the next pass to read."""

    def keep(origin: Origin) -> bool:
        p = position(target, origin)
        return p <= cutoff if inclusive else p < cutoff

    recaps = sorted((r for r in store.recaps() if keep(r.origin)),
                    key=lambda r: position(target, r.origin))
    entities = [e for e in store.entities() if keep(e.origin)]
    names = known_names(store, keep)
    kinds = Counter(e.kind for e in entities).most_common()
    recent = recaps[-RECENT_RECAPS:]

    chosen = entities
    if len(entities) > CAST_LIMIT:
        text = normalize(" ".join(p for u in units for p in u.section.paragraphs))
        recent_points = {position(target, r.origin) for r in recent}
        active: set[str] = set()
        for kind in (RecordType.ENTITIES, RecordType.ALIASES, RecordType.NOTES):
            for record in store.records[kind]:
                if keep(record.origin) and position(target, record.origin) in recent_points:
                    active.update(record.references())
                    if isinstance(record, Entity):
                        active.add(record.id)
        chosen = [e for e in entities if e.id in active or any(
            re.search(rf"\b{re.escape(normalize(name))}\b", text) for name in names[e.id])]
    return Context(recaps[-1] if recaps else None, recent, chosen, names, kinds, len(entities))
