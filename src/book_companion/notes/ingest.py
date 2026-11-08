"""Checking pass results against the book and the existing notes, then storing them.

Field types, names and quotes are validated by the pydantic models in model.py, with
the section's text as the validation context; this module adds what needs the
notes: reading order, the reading boundary, and references to entities.
"""

from __future__ import annotations

from typing import Any

from book_companion.core.boundary import recorded_scopes
from book_companion.core.errors import BookError
from book_companion.core.library import Target
from book_companion.notes.model import (
    Origin,
    Pass,
    SectionResult,
    Source,
    parse_header,
    parse_result,
)
from book_companion.notes.plan import is_story, units_within
from book_companion.notes.store import Store, position


def ingest(target: Target, store: Store, results: list[Any]) -> list[str]:
    """Validate every result, apply them in order, and save only if all of them pass."""
    scopes = recorded_scopes(target)
    units = units_within(target, scopes)
    by_key = {(u.book, u.section.number): u for u in units}
    summaries = []
    for number, data in enumerate(results, start=1):
        header = parse_header(data, f"result {number}")
        if target.is_series and header.book is None:
            raise BookError(f"result {number}: 'book' is required in a series.")
        if not target.is_series and header.book is not None:
            raise BookError(f"result {number}: 'book' is only used in a series.")
        volume = target.volumes[target.volume_index(header.book)]
        section = volume.book.section(header.section)
        label = (f"book {header.book}, section {header.section}" if header.book
                 else f"section {header.section}")
        where = f"result {number} ({header.pass_} pass, {label})"

        unit = by_key.get((header.book, header.section))
        if unit is None:
            if not section.paragraphs or not is_story(section):
                raise BookError(f"{where}: this section has no story text (it is empty, or "
                                "front or back matter), so there is nothing to record.")
            raise BookError(f"{where}: beyond the recorded reading progress; notes are only "
                            "taken from text that has been read.")
        origin = header.origin()
        if header.pass_ is not Pass.CORE and unit.origin(Pass.CORE) not in store.done:
            raise BookError(f"{where}: run the core pass for this section first.")
        if origin not in store.done:
            for earlier in units:
                if earlier is unit:
                    break
                if earlier.origin(header.pass_) not in store.done:
                    raise BookError(
                        f"{where}: sections are processed in reading order; do "
                        f"{earlier.volume.name}, section {earlier.section.number} first "
                        "(see 'book-notes next').")

        result = parse_result(data, where, Source.of(section.paragraphs))
        records = {kind: [r.placed(origin) for r in items]
                   for kind, items in result.records().items()}
        _check_references(target, store, origin, result, where)
        store.replace(origin, records)
        counts = ", ".join(f"{len(v)} {k}" for k, v in records.items() if v) or "nothing found"
        summaries.append(f"{header.pass_} pass, {volume.name}, section {header.section}: "
                         f"{counts}")
    _check_integrity(target, store)
    store.save()
    return summaries


def _check_references(target: Target, store: Store, origin: Origin, result: SectionResult,
                      where: str) -> None:
    """New entity ids are unique, and every reference is to an entity known by now."""
    here = position(target, origin)
    existing = {e.id: e for e in store.entities() if e.origin != origin}
    new_ids: set[str] = set()
    for entity in result.entities:
        if entity.id in existing:
            seen = existing[entity.id].origin
            raise BookError(f"{where}: entity id '{entity.id}' already exists (first recorded "
                            f"in section {seen.section}); refer to it instead, or pick another id.")
        if entity.id in new_ids:
            raise BookError(f"{where}: entity id '{entity.id}' is listed twice.")
        new_ids.add(entity.id)

    def known(entity_id: str) -> bool:
        if entity_id in new_ids:
            return True
        entity = existing.get(entity_id)
        return entity is not None and position(target, entity.origin) <= here

    for kind, items in result.records().items():
        for i, record in enumerate(items):
            for reference in record.references():
                if not known(reference):
                    raise BookError(
                        f"{where}, {kind}[{i}]: unknown entity id '{reference}'. Existing ids "
                        "are listed by 'book-notes next' and 'book-notes cast'; if it is new "
                        "here, add it under 'entities'.")


def _check_integrity(target: Target, store: Store) -> None:
    """After all replacements, every reference must still point to something earlier."""
    created = {e.id: position(target, e.origin) for e in store.entities()}
    for kind, items in store.records.items():
        for record in items:
            here = position(target, record.origin)
            for reference in record.references():
                if reference not in created or created[reference] > here:
                    raise BookError(
                        f"Redoing that section would leave a {kind} record in section "
                        f"{record.origin.section} pointing at '{reference}', which would no "
                        "longer exist at that point. Keep the entity in the redone section, "
                        "or redo the later section too.")
