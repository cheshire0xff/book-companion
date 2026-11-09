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
- [ ] Idea: a library check command (e.g. `book-library check`, or `book-search check` with no series dir) that walks the whole library and reports what our tools and skills can't use as-is. Report-only; it never moves or fixes files.
  - Layout: the folder has `books/`; each series has `reading-progress.md` and `volumes/<volume>-<book-slug>/`; standalones live under `standalone/<book-slug>/` with their own `reading-progress.md`; no leftover pre-`volumes/` book folders.
  - Each volume: `source.epub`, `book.txt` and `book-html/` exist, and `book-html/` has a contents `book-search` can read (chapters found, numbering where it restarts tied to a part); `metadata.md` is present.
  - Reading progress: front matter is valid (reuse the existing `book-search check` per series) and points at a volume that exists.
  - Book memory: `chapters.md`/`reference.md` only where the progress says the book is finished; flag a memory past the reading point as a spoiler risk.
  - Entities: slugs are lowercase-hyphenated, each entity folder has `description.md`, every `pics/*.png` has a matching `.prompt.md` and vice versa (sidecar fields once the sidecar tool above exists).
  - `_incoming/`: list anything waiting to be imported.
  - Output: one line per problem with its path and what to do about it, grouped by series; non-zero exit when there are errors, so agents can run it after `book-import` or `book-images` and before trusting the library.
  - Mention it in `library.md` and the README once built.
- [ ] Maybe: a report-only fact check of a finished memory's `reference.md`. No refs are written into the files; extraction stays reference-free.
  - Check hard facts (names, aliases, titles, numbers, terms, who holds what, who killed whom) entity by entity: one search per minor character, place or object confirms everything said about it. Skip main characters and spread-out, negative or interpretive claims.
  - Report only what couldn't be confirmed or was contradicted; fix the files only where the user confirms.
  - Try it once on Empire of the Vampire, as with condensing, and keep it only if it finds real errors cheaply. Reading `chapters-condensed.md` and `reference.md` after finishing a book may make it unnecessary.
- [ ] Point the skills at the book memory (left over from removing `book-notes`).
  - `book-companion` answers about a finished book from its memory (`chapters.md`, `reference.md`) first, then search; `book-images` keeps taking looks from `book-search`, because the memory has no appearance notes.
  - `spoiler-rules.md` gets a Memory section in place of Notes; README the same.
