"""book-notes: notes extracted pass by pass, section by section, within reading progress."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from book_companion.core.boundary import Scope, recorded_scopes, resolve_scopes, resolve_start
from book_companion.core.cli import (
    CONCEPTS,
    FORMATTER,
    add_point,
    add_spoilers,
    add_start,
    add_target,
    positive_int,
    print_scopes,
    run,
)
from book_companion.core.errors import BookError
from book_companion.core.library import Target, location
from book_companion.core.text import normalize
from book_companion.notes.ingest import ingest
from book_companion.notes.model import (
    NOTE_WORDS,
    PASS_RECORDS,
    QUOTE_MAX,
    Note,
    Origin,
    Pass,
    RecordType,
    Ref,
)
from book_companion.notes.plan import Keep, build_context, known_names, pending, units_within
from book_companion.notes.store import Store, position

SKILL = ".github/skills/book-notes/SKILL.md"

FIELD_HELP = {
    RecordType.ENTITIES: "id (lowercase-hyphen, unique in the series), kind (a short "
                         "lowercase label: reuse the kinds in use, e.g. character, place, "
                         "group, species, ship, object, concept), name (as this section "
                         "gives it)",
    RecordType.ALIASES: "entity (id), name (a new name, epithet or title, as this section "
                        "gives it)",
    RecordType.NOTES: f"about (entity ids; at least one in the appearance pass), text (<= "
                      f"{NOTE_WORDS} words in your own words; say who claims it and how "
                      "sure it is), refs (one or more {paragraph, quote})",
    RecordType.RECAP: "text (<= 150 words: what happens in this section), story_so_far "
                      "(<= 400 words: the whole story up to the end of this section)",
}


def _ref(paragraph: int, quote: str) -> dict[str, object]:
    return {"paragraph": paragraph, "quote": quote}


# Invented names, so that no example carries facts from a real book.
EXAMPLES: dict[Pass, dict[str, object]] = {
    Pass.CORE: {
        "pass": "core", "book": 1, "section": 12,
        "recap": {"text": "Mara reaches Ostrel and ...",
                  "story_so_far": "Mara Voss, a courier from ..."},
        "entities": [{"id": "ostrel", "kind": "place", "name": "Ostrel"}],
        "aliases": [{"entity": "mara-voss", "name": "the courier"}],
        "notes": [{"about": ["ostrel"], "text": "Ostrel is a port city on the Grey Coast.",
                   "refs": [_ref(3, "the port of Ostrel")]}],
    },
    Pass.APPEARANCE: {
        "pass": "appearance", "book": 1, "section": 14,
        "notes": [{"about": ["mara-voss"], "text": "Mara's hair is cropped short and grey "
                   "at the temples.", "refs": [_ref(7, "cropped hair, grey at the temples")]}],
    },
    Pass.WORLD: {
        "pass": "world", "book": 1, "section": 20,
        "notes": [{"about": ["the-tide-church", "ostrel"], "text": "A priest claims the Tide "
                   "Church forbids building below the high-water mark in Ostrel.",
                   "refs": [_ref(5, "no stone below the line of the tide")]}],
    },
    Pass.THREADS: {
        "pass": "threads", "book": 1, "section": 30,
        "notes": [
            {"about": ["mara-voss"], "text": "Open question: who sealed the letter Mara "
             "carries?", "refs": [_ref(2, "a seal she did not know")]},
            {"about": ["mara-voss", "ostrel"], "text": "Mara promises to return to Ostrel "
             "before winter.", "refs": [_ref(9, "before the first snow")]},
        ],
    },
}


class Command(StrEnum):
    STATUS = "status"
    NEXT = "next"
    SCHEMA = "schema"
    INGEST = "ingest"
    CAST = "cast"
    NOTES = "notes"
    APPEARANCES = "appearances"
    RECAP = "recap"


# -- helpers --------------------------------------------------------------------


def _visibility(target: Target, scopes: list[Scope],
                restrict: bool) -> Callable[[Origin], bool]:
    """Whether a record is within the scopes (and, if restrict, within the target book)."""

    def keep(origin: Origin) -> bool:
        index = target.volume_index(origin.book)
        if restrict and target.only is not None and target.volumes[index].number != target.only:
            return False
        scope = scopes[index]
        return scope.included and (scope.limit is None or origin.section <= scope.limit)

    return keep


def _from_start(target: Target, args: argparse.Namespace) -> Callable[[Origin], bool]:
    start = resolve_start(target, args)
    if start is None:
        return lambda origin: True
    return lambda origin: position(target, origin) >= (start.volume_index, start.section)


def _cite(target: Target, origin: Origin, paragraph: int | None = None) -> str:
    volume = target.volumes[target.volume_index(origin.book)]
    where = location(target, volume, volume.book.section(origin.section))
    return f"{where} ¶{paragraph}" if paragraph else where


def _quoted(target: Target, origin: Origin, ref: Ref) -> str:
    """The referenced words, cut from the book text, and where they are."""
    volume = target.volumes[target.volume_index(origin.book)]
    paragraphs = volume.book.section(origin.section).paragraphs
    where = _cite(target, origin, ref.paragraph)
    if ref.paragraph > len(paragraphs) or ref.end > len(paragraphs[ref.paragraph - 1]):
        return f"(this reference no longer fits the text; was the book re-imported?)  {where}"
    return f"\"{paragraphs[ref.paragraph - 1][ref.start:ref.end]}\"  {where}"


def _find_entity(store: Store, keep: Keep, query: str) -> str:
    """An entity id from an id, a name or alias, or a word of one."""
    names = known_names(store, keep)
    if query in names:
        return query
    wanted = normalize(query)
    hits = [eid for eid, ns in names.items() if any(normalize(n) == wanted for n in ns)]
    if not hits:
        pattern = re.compile(rf"\b{re.escape(wanted)}\b")
        hits = [eid for eid, ns in names.items() if any(pattern.search(normalize(n)) for n in ns)]
    if not hits:
        raise BookError(f"No notes about {query!r} within the reading boundary.")
    if len(hits) > 1:
        listed = "; ".join(f"{eid} ({', '.join(names[eid])})" for eid in sorted(hits))
        raise BookError(f"{query!r} matches several entries: {listed}. Use the id.")
    return hits[0]


def _print_limited(lines: list[str], max_chars: int, hint: str) -> None:
    used = 0
    for i, line in enumerate(lines):
        if i and used + len(line) > max_chars:
            print(f"\n--- Output limit reached (--max-chars {max_chars}); "
                  f"{len(lines) - i} more lines. {hint}")
            return
        print(line)
        used += len(line) + 1


# -- workers: status, next, schema, ingest ---------------------------------------


def cmd_status(target: Target, args: argparse.Namespace) -> None:
    store = Store.load(target)
    scopes = recorded_scopes(target)
    print_scopes(target, scopes, "Notes for")
    units = units_within(target, scopes)
    print(f"  notes folder: {store.directory}")
    print(f"\n{len(units)} story sections are within the reading progress "
          "(front and back matter is skipped).")
    for pass_ in Pass:
        todo, blocked = pending(target, store, pass_, scopes)
        done = sum(1 for unit in units if unit.origin(pass_) in store.done)
        line = f"  {pass_:<10} {done:>4} done"
        if todo:
            line += f"; next: {_cite(target, todo[0].origin(pass_))}"
        elif blocked is not None:
            line += "; waiting for the core pass"
        else:
            line += "; up to date"
        print(line)
    counts = ", ".join(f"{len(store.records[k])} {k}" for k in RecordType if store.records[k])
    print(f"\nRecords: {counts or 'none yet'}")


def cmd_next(target: Target, args: argparse.Namespace) -> None:
    pass_ = Pass(args.pass_)
    store = Store.load(target)
    scopes = recorded_scopes(target)
    print_scopes(target, scopes, f"Next for the {pass_} pass in")
    todo, blocked = pending(target, store, pass_, scopes)
    units = todo[:args.sections]
    if not units:
        if blocked is not None:
            print(f"\nThe {pass_} pass is waiting for the core pass, which has not done "
                  f"{_cite(target, blocked.origin(Pass.CORE))} yet. Run 'next --pass core'.")
        else:
            print(f"\nUp to date: the {pass_} pass has done every section within the "
                  "reading progress.")
        return

    first = units[0].position
    last = units[-1].position
    context = build_context(target, store, first if pass_ is Pass.CORE else last,
                            inclusive=pass_ is not Pass.CORE, units=units)
    if context.story is None:
        print("\n== Story so far ==\n(No notes yet: this is the start.)")
    else:
        print(f"\n== Story so far (notes through {_cite(target, context.story.origin)}) ==")
        print(context.story.story_so_far)
    if context.recent:
        print("\n== Recent sections ==")
        for recap in context.recent:
            print(f"- {_cite(target, recap.origin)}: {recap.text}")
    if context.total:
        shown = (f"all {context.total}" if len(context.entities) == context.total else
                 f"{len(context.entities)} of {context.total}: named in these sections "
                 "or recently active")
        print(f"\n== Known entities ({shown}) ==")
        for entity in context.entities:
            print(f"  {entity.id:<32} {entity.kind:<10} {'; '.join(context.names[entity.id])}")
        kinds = ", ".join(f"{kind} ({count})" for kind, count in context.kinds)
        print(f"Kinds in use: {kinds}")

    print("\n== To do ==")
    for n, unit in enumerate(units, start=1):
        size = sum(len(p) for p in unit.section.paragraphs) // 1000 + 1
        book_flag = f" --book {unit.book}" if target.is_series and target.only is None else ""
        count = len(unit.section.paragraphs)
        print(f"{n}. {_cite(target, unit.origin(pass_))}: {count} paragraphs, ~{size} KB")
        print(f"   read: uv run book-search read {args.target.as_posix()}{book_flag} "
              f"--section {unit.section.number} --from 1 --to {count}")
    remaining = len(todo) - len(units)
    if remaining:
        print(f"({remaining} more sections after these.)")

    records = ", ".join(sorted(PASS_RECORDS[pass_]))
    target_path = args.target.as_posix()
    print("\n== When done ==")
    print("Write one JSON object per section (a JSON list for several), then run:")
    print(f"  uv run book-notes ingest {target_path} <result.json>")
    print(f"The {pass_} pass records {records}.")
    print(f"Field reference and an example: uv run book-notes schema {target_path} {pass_}")
    print(f"How to do this pass: {SKILL}")


def cmd_schema(target: Target, args: argparse.Namespace) -> None:
    pass_ = Pass(args.pass_)
    print(f"Result of the {pass_} pass for one section: an object with pass, book (in a series), "
          "section, and these lists:")
    for kind in RecordType:
        if kind in PASS_RECORDS[pass_]:
            required = " (required)" if kind is RecordType.RECAP else ""
            shape = "object" if kind is RecordType.RECAP else "list"
            print(f"\n  {kind} ({shape}){required}: {FIELD_HELP[kind]}")
    print(f"\nRules: a ref is {{\"paragraph\": N, \"quote\": \"...\"}}. N is the ¶ number shown "
          f"by book-search read, and the quote an exact, contiguous excerpt of that paragraph "
          f"(up to {QUOTE_MAX} characters). The tool checks it and stores only where it is. "
          "Names must appear in the section as written. Refer to entities by id; create new "
          "ones under 'entities'. Empty lists are fine when nothing was found.")
    print("\nExample:")
    print(json.dumps(EXAMPLES[pass_], ensure_ascii=False, indent=2))


def cmd_ingest(target: Target, args: argparse.Namespace) -> None:
    path: Path = args.result
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise BookError(f"Cannot read {path}: {exc}") from None
    except json.JSONDecodeError as exc:
        raise BookError(f"{path} is not valid JSON: {exc}") from None
    results = data if isinstance(data, list) else [data]
    store = Store.load(target)
    for line in ingest(target, store, results):
        print(f"stored: {line}")
    print(f"Notes saved in {store.directory}.")


# -- queries: cast, notes, appearances, recap ------------------------------------


def cmd_cast(target: Target, args: argparse.Namespace) -> None:
    scopes = resolve_scopes(target, args)
    print_scopes(target, scopes, "Cast of")
    store = Store.load(target)
    keep = _visibility(target, scopes, restrict=False)
    names = known_names(store, keep)
    entities = [e for e in store.entities() if keep(e.origin)
                and (args.kind is None or e.kind == args.kind)]
    if not entities:
        print("\nNo entries within the reading boundary.")
        return
    for kind, count in Counter(e.kind for e in entities).most_common():
        print(f"\n## {kind} ({count})")
        for entity in (e for e in entities if e.kind == kind):
            print(f"  {entity.id:<32} {'; '.join(names[entity.id])}")
            print(f"  {'':<32} first noted: {_cite(target, entity.origin)}")


def _show_notes(target: Target, args: argparse.Namespace, pass_: Pass | None) -> None:
    scopes = resolve_scopes(target, args)
    print_scopes(target, scopes, "Notes from")
    store = Store.load(target)
    keep_entity = _visibility(target, scopes, restrict=False)
    keep = _visibility(target, scopes, restrict=True)
    after = _from_start(target, args)
    entity = _find_entity(store, keep_entity, args.entity) if args.entity else None
    names = known_names(store, keep_entity)
    notes: list[Note] = [n for n in store.notes()
                         if keep(n.origin) and after(n.origin)
                         and (pass_ is None or n.origin.pass_ is pass_)
                         and (entity is None or entity in n.about)]
    if entity is not None:
        print(f"\n# {'; '.join(names[entity])} ({entity})")
    if not notes:
        print("\nNo notes of that kind within the reading boundary.")
        return
    notes.sort(key=lambda n: (list(Pass).index(n.origin.pass_), position(target, n.origin)))
    lines: list[str] = []
    heading = None
    for note in notes:
        if note.origin.pass_ != heading:
            heading = note.origin.pass_
            lines.append(f"\n## {heading}")
        others = [e for e in note.about if e != entity]
        about = f"  (about: {', '.join(others)})" if others else ""
        refs = "".join(f"\n    {_quoted(target, note.origin, ref)}" for ref in note.refs)
        lines.append(f"- {note.text}{about}{refs}")
    _print_limited(lines, args.max_chars,
                   "Narrow it with --pass, --start-chapter or a story point.")


def cmd_notes(target: Target, args: argparse.Namespace) -> None:
    _show_notes(target, args, Pass(args.pass_) if args.pass_ else None)


def cmd_appearances(target: Target, args: argparse.Namespace) -> None:
    _show_notes(target, args, Pass.APPEARANCE)


def cmd_recap(target: Target, args: argparse.Namespace) -> None:
    scopes = resolve_scopes(target, args)
    print_scopes(target, scopes, "Recap of")
    store = Store.load(target)
    keep = _visibility(target, scopes, restrict=True)
    after = _from_start(target, args)
    recaps = sorted((r for r in store.recaps() if keep(r.origin) and after(r.origin)),
                    key=lambda r: position(target, r.origin))
    if not recaps:
        print("\nNo recaps within the reading boundary yet (run the core pass).")
        return
    if args.story_so_far:
        print(f"\n## Story so far, through {_cite(target, recaps[-1].origin)}\n")
        print(recaps[-1].story_so_far)
        return
    lines = [f"\n## {_cite(target, recap.origin)}\n{recap.text}" for recap in recaps]
    _print_limited(lines, args.max_chars, "Narrow it with --start-chapter or a story point.")


# -- command line -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Notes extracted from books pass by pass, within reading progress.",
        epilog=CONCEPTS, formatter_class=FORMATTER)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_pass(p: argparse.ArgumentParser, positional: bool = False) -> None:
        if positional:
            p.add_argument("pass_", metavar="pass", choices=list(Pass))
        else:
            p.add_argument("--pass", dest="pass_", required=True, choices=list(Pass))

    def add_query(p: argparse.ArgumentParser, with_start: bool) -> None:
        add_point(p, "story point (narrows the boundary; default: reading progress)")
        if with_start:
            add_start(p, with_paragraph=False)
        add_spoilers(p, with_all=False)
        p.add_argument("--max-chars", type=positive_int, default=12000, metavar="N",
                       help="stop after about N characters (default 12000)")

    status = sub.add_parser(Command.STATUS, help="how far each pass has got",
                            epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(status)

    nxt = sub.add_parser(Command.NEXT, help="what a pass should do next, with the notes so far",
                         epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(nxt)
    add_pass(nxt)
    nxt.add_argument("--sections", type=positive_int, default=1, metavar="N",
                     help="hand out up to N sections at once (default 1)")

    schema = sub.add_parser(Command.SCHEMA, help="the result format for a pass, with an example")
    add_target(schema)
    add_pass(schema, positional=True)

    ingest_parser = sub.add_parser(Command.INGEST, help="validate and store a pass result")
    add_target(ingest_parser)
    ingest_parser.add_argument("result", type=Path, help="JSON file: one result or a list")

    cast = sub.add_parser(Command.CAST, help="characters, places and other entries known so far",
                          epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(cast)
    cast.add_argument("--kind", help="only entries of this kind (e.g. character, place)")
    add_query(cast, with_start=False)

    notes = sub.add_parser(Command.NOTES, help="notes about one entry, or every note of a pass",
                           epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(notes)
    notes.add_argument("entity", nargs="?", help="an id from 'cast', or a name (default: all)")
    notes.add_argument("--pass", dest="pass_", choices=list(Pass),
                       help="only notes from this pass (threads: open questions, promises, "
                            "secrets, relationships)")
    add_query(notes, with_start=True)

    appearances = sub.add_parser(Command.APPEARANCES, help="how one entry looks",
                                 epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(appearances)
    appearances.add_argument("entity", help="an id from 'cast', or a name")
    add_query(appearances, with_start=True)

    recap = sub.add_parser(Command.RECAP, help="what happened, section by section",
                           epilog=CONCEPTS, formatter_class=FORMATTER)
    add_target(recap)
    recap.add_argument("--story-so-far", action="store_true",
                       help="only the latest rolling summary of the whole story")
    add_query(recap, with_start=True)
    return parser


COMMANDS = {
    Command.STATUS: cmd_status,
    Command.NEXT: cmd_next,
    Command.SCHEMA: cmd_schema,
    Command.INGEST: cmd_ingest,
    Command.CAST: cmd_cast,
    Command.NOTES: cmd_notes,
    Command.APPEARANCES: cmd_appearances,
    Command.RECAP: cmd_recap,
}


def main(argv: list[str] | None = None) -> int:
    return run(build_parser(), COMMANDS, argv)
