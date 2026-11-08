"""The notes files of a series (or standalone book), loaded and saved as a whole."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from book_companion.core.errors import BookError
from book_companion.core.library import Target
from book_companion.notes.model import (
    Alias,
    Entity,
    Note,
    Origin,
    Pass,
    Recap,
    Record,
    RecordType,
    record_from_json,
    record_to_json,
)

FILES: dict[RecordType, str] = {
    RecordType.ENTITIES: "entities.jsonl",
    RecordType.ALIASES: "aliases.jsonl",
    RecordType.NOTES: "notes.jsonl",
    RecordType.RECAP: "recaps.jsonl",
}
DONE_FILE = "done.jsonl"

Position = tuple[int, int]  # (volume index, section number): reading order


@dataclass
class Store:
    directory: Path
    records: dict[RecordType, list[Record]] = field(default_factory=dict)
    done: set[Origin] = field(default_factory=set)

    @classmethod
    def load(cls, target: Target) -> Store:
        store = cls(target.notes_dir, {kind: [] for kind in FILES})
        for kind, name in FILES.items():
            for line_no, data in _read_jsonl(store.directory / name):
                where = f"{store.directory / name}:{line_no}"
                store.records[kind].append(record_from_json(kind, data, where))
        for line_no, data in _read_jsonl(store.directory / DONE_FILE):
            try:
                store.done.add(Origin.model_validate(data))
            except ValidationError:
                where = f"{store.directory / DONE_FILE}:{line_no}"
                raise BookError(f"{where}: invalid entry.") from None
        return store

    def of[R: Record](self, kind: RecordType, model: type[R]) -> list[R]:
        """The records of one kind, typed as their model."""
        return [record for record in self.records[kind] if isinstance(record, model)]

    def entities(self) -> list[Entity]:
        return self.of(RecordType.ENTITIES, Entity)

    def aliases(self) -> list[Alias]:
        return self.of(RecordType.ALIASES, Alias)

    def notes(self) -> list[Note]:
        return self.of(RecordType.NOTES, Note)

    def recaps(self) -> list[Recap]:
        return self.of(RecordType.RECAP, Recap)

    def replace(self, origin: Origin, new: dict[RecordType, list[Record]]) -> None:
        """Swap in one pass's records for one section and mark it done."""
        for kind in FILES:
            kept = [r for r in self.records[kind] if r.origin != origin]
            self.records[kind] = kept + new.get(kind, [])
        self.done.add(origin)

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        outputs = {name: [record_to_json(r) for r in self.records[kind]]
                   for kind, name in FILES.items()}
        outputs[DONE_FILE] = [o.model_dump(mode="json", by_alias=True)
                              for o in sorted(self.done, key=_origin_key)]
        temporary = []
        for name, rows in outputs.items():
            path = self.directory / f"{name}.tmp"
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                            encoding="utf-8")
            temporary.append((path, self.directory / name))
        for path, final in temporary:
            os.replace(path, final)


def _origin_key(origin: Origin) -> tuple[int, int, int]:
    return (origin.book or 0, origin.section, list(Pass).index(origin.pass_))


def _read_jsonl(path: Path) -> list[tuple[int, object]]:
    if not path.is_file():
        return []
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append((line_no, json.loads(line)))
        except json.JSONDecodeError as exc:
            raise BookError(f"{path}:{line_no}: invalid JSON ({exc.msg}).") from None
    return rows


def position(target: Target, origin: Origin) -> Position:
    return (target.volume_index(origin.book), origin.section)
