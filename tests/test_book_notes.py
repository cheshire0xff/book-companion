"""Tests for the book-notes command, using small synthetic books (no real book text)."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from book_companion.notes.cli import main
from helpers import Builder, Capture, progress

# In the series fixture, book 1 is the flat book. Its story sections, each with a heading
# as paragraph 1 and its text as paragraph 2:
# 2 Ch1 "Anaïs arrives at the gate.", 3 Ch2 "Valka’s tattoo is very fine.",
# 4 Interlude (nested in Ch2), 5 Ch3 "Gilliam plans something.", 6 Ch4, 7 Ch5.
# Section 1 is the contents page, which is skipped.

Json = dict[str, object]
Outcome = tuple[int, str, str]  # exit code, stdout, stderr
Ingest = Callable[..., Outcome]
Notes = tuple[str, Ingest]  # series directory, and a helper that ingests results


def run(capsys: Capture, *argv: str) -> Outcome:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.fixture
def notes(series: Builder, tmp_path: Path, capsys: Capture) -> Notes:
    """A series read through book 1, chapter 3, plus a helper that ingests results."""
    root = series(progress("reading", chapter="3", book="1"))
    counter = iter(range(1000))

    def ingest(*results: Json) -> Outcome:
        path = tmp_path / f"result-{next(counter)}.json"
        path.write_text(json.dumps(list(results)), encoding="utf-8")
        return run(capsys, "ingest", root, str(path))

    return root, ingest


def note(about: Sequence[str], paragraph: int, quote: str, text: str = "A note.") -> Json:
    return {"about": list(about), "text": text,
            "refs": [{"paragraph": paragraph, "quote": quote}]}


def core(section: int, *, entities: Sequence[Json] = (), notes: Sequence[Json] = (),
         aliases: Sequence[Json] = (), story: str = "The story so far.") -> Json:
    return {"pass": "core", "book": 1, "section": section,
            "recap": {"text": f"Recap of section {section}.", "story_so_far": story},
            "entities": list(entities), "notes": list(notes), "aliases": list(aliases)}


def look(entity: str, section: int, paragraph: int, quote: str) -> Json:
    return {"pass": "appearance", "book": 1, "section": section,
            "notes": [note([entity], paragraph, quote)]}


ANAIS: Json = {"id": "anais", "kind": "character", "name": "Anaïs"}  # named in section 2
VALKA: Json = {"id": "valka", "kind": "character", "name": "Valka"}  # named in section 3


# -- next and status ----------------------------------------------------------

def test_next_starts_at_the_first_story_section(notes: Notes, capsys: Capture) -> None:
    root, _ = notes
    out = run(capsys, "next", root, "--pass", "core")[1]
    assert "Chapter 1: Arrival  (book 1, section 2)" in out
    assert "--book 1 --section 2 --from 1 --to 2" in out
    assert "No notes yet" in out and "Contents" not in out


def test_next_hands_over_the_notes_so_far(notes: Notes, capsys: Capture) -> None:
    root, ingest = notes
    assert ingest(core(2, entities=[ANAIS], story="Anaïs arrives."))[0] == 0
    out = run(capsys, "next", root, "--pass", "core")[1]
    assert "section 3" in out and "Anaïs arrives." in out
    assert "anais" in out and "Recap of section 2." in out
    assert "Kinds in use: character (1)" in out


def test_other_passes_wait_for_core(notes: Notes, capsys: Capture) -> None:
    root, ingest = notes
    assert "waiting for the core pass" in run(capsys, "next", root, "--pass", "appearance")[1]
    ingest(core(2, entities=[ANAIS]))
    out = run(capsys, "next", root, "--pass", "appearance")[1]
    assert "section 2" in out and "anais" in out


def test_status_counts_each_pass(notes: Notes, capsys: Capture) -> None:
    root, ingest = notes
    ingest(core(2, entities=[ANAIS]))
    out = run(capsys, "status", root)[1]
    assert "4 story sections" in out  # sections 2, 3, 4 and 5; the contents page is skipped
    assert "core          1 done" in out and "appearance    0 done" in out


def test_up_to_date_at_the_boundary(notes: Notes, capsys: Capture) -> None:
    root, ingest = notes
    for section in (2, 3, 4, 5):
        assert ingest(core(section))[0] == 0
    assert "Up to date" in run(capsys, "next", root, "--pass", "core")[1]


# -- ingest: order and boundary -------------------------------------------------

def test_sections_go_in_reading_order(notes: Notes) -> None:
    code, _, err = notes[1](core(3))
    assert code == 2 and "reading order" in err and "section 2 first" in err


def test_nothing_past_reading_progress(notes: Notes) -> None:
    _, ingest = notes
    for section in (2, 3, 4, 5):
        ingest(core(section))
    code, _, err = ingest(core(6))
    assert code == 2 and "beyond the recorded reading progress" in err


def test_appearance_needs_core_first(notes: Notes) -> None:
    code, _, err = notes[1](look("anais", 2, 2, "arrives"))
    assert code == 2 and "core pass for this section first" in err


# -- ingest: refs and names are checked against the text --------------------------

def test_quotes_must_be_in_the_cited_paragraph(notes: Notes) -> None:
    _, ingest = notes
    ingest(core(2, entities=[ANAIS]))
    code, _, err = ingest(look("anais", 2, 2, "golden eyes"))
    assert code == 2 and "notes[0].refs[0]: the quote is not in paragraph 2" in err
    assert "Anaïs arrives" in err
    assert ingest(look("anais", 2, 2, "ANAIS  arrives at the gate"))[0] == 0  # accents folded


def test_paragraph_must_exist(notes: Notes) -> None:
    _, ingest = notes
    ingest(core(2, entities=[ANAIS]))
    code, _, err = ingest(look("anais", 2, 9, "gate"))
    assert code == 2 and "paragraph 9 does not exist; this section has 2" in err


def test_refs_are_stored_as_spans_and_shown_from_the_book(notes: Notes,
                                                          capsys: Capture) -> None:
    root, ingest = notes
    ingest(core(2, entities=[ANAIS]))
    assert ingest(look("anais", 2, 2, "anais arrives"))[0] == 0
    stored = (Path(root) / "notes" / "notes.jsonl").read_text(encoding="utf-8")
    assert json.loads(stored)["refs"] == [{"paragraph": 2, "start": 0, "end": 13}]
    assert "quote" not in stored and "arrives" not in stored
    out = run(capsys, "appearances", root, "anais")[1]
    assert '"Anaïs arrives"' in out  # the book's own spelling, cut from the text


def test_refs_take_a_quote_not_offsets(notes: Notes) -> None:
    _, ingest = notes
    ingest(core(2, entities=[ANAIS]))
    bad = look("anais", 2, 2, "gate")
    bad["notes"] = [{"about": ["anais"], "text": "x",
                     "refs": [{"paragraph": 2, "start": 0, "end": 5}]}]
    code, _, err = ingest(bad)
    assert code == 2 and "notes[0].refs[0].quote: Field required" in err
    assert "notes[0].refs[0].start: unknown field" in err


def test_names_must_appear_in_the_section(notes: Notes) -> None:
    _, ingest = notes
    code, _, err = ingest(core(2, entities=[VALKA]))
    assert code == 2 and "entities[0]: the name 'Valka' does not appear in this section" in err
    code, _, err = ingest(core(2, entities=[ANAIS], aliases=[
        {"entity": "anais", "name": "the xenologist"}]))
    assert code == 2 and "aliases[0]: the name 'the xenologist' does not appear" in err
    assert ingest(core(2, entities=[ANAIS], aliases=[
        {"entity": "anais", "name": "the gate"}]))[0] == 0


# -- ingest: structure ----------------------------------------------------------

def test_unknown_and_duplicate_entities(notes: Notes) -> None:
    _, ingest = notes
    code, _, err = ingest(core(2, notes=[note(["nobody"], 2, "gate")]))
    assert code == 2 and "notes[0]: unknown entity id 'nobody'" in err
    ingest(core(2, entities=[ANAIS]))
    code, _, err = ingest(core(3, entities=[dict(ANAIS, name="Valka")]))
    assert code == 2 and "already exists" in err


def test_records_belong_to_their_pass(notes: Notes) -> None:
    _, ingest = notes
    ingest(core(2, entities=[ANAIS]))
    code, _, err = ingest({"pass": "appearance", "book": 1, "section": 2,
                           "aliases": [{"entity": "anais", "name": "Anaïs"}]})
    assert code == 2 and "the appearance pass does not record aliases" in err


def test_typed_fields_are_strict(notes: Notes) -> None:
    _, ingest = notes
    code, _, err = ingest(core(2, entities=[dict(ANAIS, kind="Main Character")]))
    assert code == 2 and "entities[0].kind: String should match pattern" in err
    bad_ref: Json = {"about": [], "text": "x", "refs": [{"paragraph": "2", "quote": "gate"}]}
    code, _, err = ingest(core(2, notes=[bad_ref]))
    assert code == 2 and "notes[0].refs[0].paragraph: Input should be a valid integer" in err
    bad = core(2)
    bad["mood"] = "tense"
    code, _, err = ingest(bad)
    assert code == 2 and "mood: unknown field" in err


def test_note_rules(notes: Notes) -> None:
    _, ingest = notes
    ingest(core(2, entities=[ANAIS]))
    code, _, err = ingest(dict(look("anais", 2, 2, "gate"), notes=[note([], 2, "gate")]))
    assert code == 2 and "an appearance note needs at least one entity in 'about'" in err
    code, _, err = ingest(core(3, notes=[{"about": [], "text": "x", "refs": []}]))
    assert code == 2 and "notes[0].refs: List should have at least 1 item" in err
    code, _, err = ingest(core(3, notes=[note([], 2, "tattoo", text="word " * 81)]))
    assert code == 2 and "has 81 words; the limit is 80" in err
    no_recap = core(3)
    del no_recap["recap"]
    code, _, err = ingest(no_recap)
    assert code == 2 and "the core pass needs a 'recap'" in err


def test_a_failing_batch_saves_nothing(notes: Notes, capsys: Capture) -> None:
    root, ingest = notes
    code, _, _ = ingest(core(2, entities=[ANAIS]), core(3, entities=[ANAIS]))
    assert code == 2
    assert "core          0 done" in run(capsys, "status", root)[1]


def test_redo_replaces_a_sections_records(notes: Notes, capsys: Capture) -> None:
    root, ingest = notes
    ingest(core(2, entities=[ANAIS]))
    ingest(look("anais", 2, 2, "arrives"))
    ingest(look("anais", 2, 2, "gate"))
    out = run(capsys, "appearances", root, "anais")[1]
    assert '"gate"' in out and '"arrives"' not in out


def test_redo_may_not_orphan_later_records(notes: Notes) -> None:
    _, ingest = notes
    ingest(core(2, entities=[ANAIS]))
    ingest(core(3, notes=[note(["anais"], 2, "tattoo")]))
    code, _, err = ingest(core(2))
    assert code == 2 and "would no longer exist" in err


# -- queries ------------------------------------------------------------------

def test_appearances_cite_book_chapter_and_paragraph(notes: Notes, capsys: Capture) -> None:
    root, ingest = notes
    ingest(core(2, entities=[ANAIS]), core(3, entities=[VALKA]))
    ingest(look("anais", 2, 2, "gate"), look("valka", 3, 2, "tattoo"))
    out = run(capsys, "appearances", root, "Valka")[1]
    assert "## appearance" in out and '"tattoo"' in out and '"gate"' not in out
    assert "Flat Book · Chapter 2: The Garden  (book 1, section 3) ¶2" in out


def test_queries_respect_an_earlier_story_point(notes: Notes, capsys: Capture) -> None:
    root, ingest = notes
    ingest(core(2, entities=[ANAIS]), core(3, entities=[VALKA]))
    code, _, err = run(capsys, "appearances", root, "valka", "--book", "1", "--chapter", "1")
    assert code == 2 and "No notes about 'valka' within the reading boundary" in err
    _, _, unknown = run(capsys, "appearances", root, "nobody-at-all")
    assert "No notes about 'nobody-at-all' within the reading boundary" in unknown


def test_notes_of_a_pass_in_reading_order(notes: Notes, capsys: Capture) -> None:
    root, ingest = notes
    ingest(core(2, entities=[ANAIS]), core(3))
    ingest({"pass": "threads", "book": 1, "section": 2,
            "notes": [note(["anais"], 2, "gate", text="Open question: why the gate?")]},
           {"pass": "threads", "book": 1, "section": 3,
            "notes": [note([], 2, "tattoo", text="Answered: because of the tattoo.")]})
    out = run(capsys, "notes", root, "--pass", "threads")[1]
    assert out.index("Open question") < out.index("Answered")
    early = run(capsys, "notes", root, "--pass", "threads", "--book", "1", "--chapter", "1")[1]
    assert "Open question" in early and "Answered" not in early
    about = run(capsys, "notes", root, "anais")[1]
    assert "## threads" in about and "Open question" in about and "Answered" not in about


def test_cast_and_recap(notes: Notes, capsys: Capture) -> None:
    root, ingest = notes
    place: Json = {"id": "the-gate", "kind": "place", "name": "the gate"}
    ingest(core(2, entities=[ANAIS, place], story="First."),
           core(3, entities=[VALKA], story="Second."))
    cast = run(capsys, "cast", root)[1]
    assert "## character (2)" in cast and "## place (1)" in cast and "first noted:" in cast
    assert "the-gate" not in run(capsys, "cast", root, "--kind", "character")[1]
    assert run(capsys, "cast", root, "--book", "1", "--chapter", "1")[1].count("valka") == 0
    assert "Second." in run(capsys, "recap", root, "--story-so-far")[1]
    recap = run(capsys, "recap", root, "--start-book", "1", "--start-chapter", "2")[1]
    assert "Recap of section 3." in recap and "Recap of section 2." not in recap


def test_schema_shows_fields_and_an_example(notes: Notes, capsys: Capture) -> None:
    out = run(capsys, "schema", notes[0], "appearance")[1]
    assert "refs (one or more {paragraph, quote})" in out and '"quote":' in out
    assert "story_so_far" not in out
