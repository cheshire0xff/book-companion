# TODO

## Deferred

- [ ] Create a tool that parses image prompt sidecars (`pics/*.prompt.md`).
  - Uses:
    - list a series' images with their entity, depicted story point, reading progress at preparation, status and dates;
    - find pending prompts when importing from `_incoming/images/`;
    - flag images prepared past a given story point (spoiler check);
    - validate sidecars.
  - Move the sidecar metadata into a strict front-matter block first, like `reading-progress.md`, with typed keys (book, chapter, part, section, status, prepared, imported, original filename, prompt model, image model, cost). The tool then validates typed fields with pydantic instead of parsing the current prose bullets.
  - Update the `book-images` skill to match.
- [x] Revise the `book-memory-extraction` skill.
  - Done 2026-11-08: back to v1 (the skill before commit 5bdac05), which says what the memory must capture and leaves the how to the agent.
  - Only finished books get a memory. While a book is being read, on-demand `book-search` covers questions, images and recaps.
  - Two files per book, in its folder: `chapters.md` (only the chapter notes) and `reference.md` (structure and chronology, cast, world, threads, end state). In a series, each book's files stand on their own.
  - Dropped: progress-bounded catch-up, the coordinator/worker loop, `story-so-far.md`, `cast.md`/`world.md`, front matter, appearance notes, source references and quote links.
  - Added to v1: fauna and flora, who holds an object and when it changes hands, and exact wording placed on what it is about.
- [ ] Maybe: a report-only fact check of a finished memory's `reference.md`. No refs are written into the files; extraction stays reference-free.
  - Check hard facts (names, aliases, titles, numbers, terms, who holds what, who killed whom) entity by entity: one search per minor character, place or object confirms everything said about it. Skip main characters and spread-out, negative or interpretive claims.
  - Report only what couldn't be confirmed or was contradicted; fix the files only where the user confirms.
  - Try it once on Empire of the Vampire, as with condensing, and keep it only if it finds real errors cheaply. Reading `chapters-condensed.md` and `reference.md` after finishing a book may make it unnecessary.
- [x] Remove `book-notes`, which the memory replaces; it confuses agents.
  - Done 2026-11-08, but `book-images`, `book-companion`, `spoiler-rules.md` and README went back to on-demand `book-search` instead of pointing at the memory; `library.md` just drops `notes/`. Pointing them at the memory is still open.
  - No `notes/` data exists anywhere, and the code stays in git history.
  - Delete `.github/skills/book-notes/`, `src/book_companion/notes/`, `tests/test_book_notes.py` and the `book-notes` script in `pyproject.toml`. Keep `locate`/`normalize` in `core/text.py` for the quote checker.
  - Point everything at the memory instead (a finished book's `chapters.md` and `reference.md`):
    - `book-images` keeps taking looks from `book-search`, because the memory has no appearance notes;
    - `book-companion` answers about a finished book from its memory first, then search (its §4 already just invokes `book-memory-extraction`, done 2026-11-08);
    - ~~the `library.md` layout shows `chapters.md` and `reference.md` in place of `summary.md`~~ (done 2026-11-08);
    - `spoiler-rules.md` gets a Memory section in place of Notes;
    - README the same.
  - Wait until the other agent is no longer using `book-images`. Run ruff, mypy and pytest afterwards.
