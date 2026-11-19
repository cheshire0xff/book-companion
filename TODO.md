# TODO

## Deferred

- [ ] Maybe: a report-only fact check of a finished memory. No refs are written into the files; extraction stays reference-free.
  - A cheap model (such as Haiku) could do it, especially for `chapters.md` and `chapters-condensed.md`: both keep the book's chapter headings, so each chapter's notes can be checked against that chapter's text alone, in small, independent jobs.
  - For `reference.md`, check hard facts (names, aliases, titles, numbers, terms, who holds what, who killed whom) entity by entity: one search per minor character, place or object confirms everything said about it. Skip main characters and spread-out, negative or interpretive claims.
  - Report only what couldn't be confirmed or was contradicted; fix the files only where the user confirms.
  - After the pass, add an entry to the Book memory log in `metadata.md` (see `skills/book-memory-extraction/memory-log.md`): which files were checked, the models (subagents included), how many claims were flagged and how many fixes the user confirmed. As with every log entry, no story details.
  - Try it once on Empire of the Vampire, as with condensing, and keep it only if it finds real errors cheaply. Reading `chapters-condensed.md` and `reference.md` after finishing a book may make it unnecessary.
