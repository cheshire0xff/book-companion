---
name: book-memory-extraction
description: "Use when the user has finished a book in their library and wants its book memory, a recap of a finished book, or to condense an existing book memory. Produces compact, spoiler-complete notes (chapters.md and reference.md in the book's folder, and chapters-condensed.md on request) for accurately recalling the story later, especially when continuing a series. Not for books still being read. Do not use for developing or modifying the Book Companion application or its scripts."
argument-hint: "[book directory]"
user-invocable: true
---

# Book Memory Extraction

Create a compact, information-dense reference that preserves what a reader may need to remember months or years later, especially when continuing a series. This is not a conventional literary review or a short plot synopsis.

## Inputs and output

1. Use the book's own text in the user's library. If the book is not in the library yet, import it first with the `book-import` skill. Do not substitute another edition, an online synopsis, or remembered plot details.
2. Extract only a book the user has read: `reading-progress.md` shows it as `status: finished`, or it is an earlier volume of the series. If the user says they have finished but the progress disagrees, record it first (see "Updating reading progress" in the `book-companion` skill); otherwise ask. Never extract an unfinished book. While a book is being read, questions about it are answered by searching the text.
3. Write two Markdown files in the book's folder, next to `book.txt`: `chapters.md` and `reference.md`. If either already exists, do not silently overwrite it; ask the user what to do.
4. Do not alter the source book.
5. Read the text with `book-search`, run as `book-search <command> <book folder> …` from the library root (the folder that holds `books/`). `chapters` lists the book's sections. `read` prints a chapter (`--chapter N`, plus `--part P` when numbering restarts) or a section (`--section N`); when it stops at its output limit, rerun it with the continuation it prints until you have every paragraph. `search` finds passages. Each command's `--help` lists its options.
6. If the source cannot be read with available tools, explain the limitation. Do not invent missing content.

## Extraction procedure

1. **Map the source.** Identify the title, author, parts, chapter headings, epigraphs or frame sections, and the beginning and end of the actual story. Skip front matter and back matter unless they contain story-relevant material. Judge a section by its text, not its heading: an unnumbered section with paragraphs (one headed "Map", say) may hold story, so look before skipping it. For very large files, inspect bounded sections and process the book in manageable ranges.
2. **Track two timelines.** Record events in the order the narrative presents them, by chapter. Separately reconstruct chronological order wherever flashbacks, interviews, time jumps, simultaneous events, or retrospective revelations make it differ. Keep frame events distinct from the embedded past.
3. **Record events causally.** For each chapter, capture the consequential actions, discoveries, decisions, reversals, deaths, and their causes or results. Compress dialogue into what was revealed, claimed, concealed, decided, or implied. Preserve exact wording only when a phrase, oath, riddle, prophecy, password, or repeated motif may matter later, and put it in the reference on what it is about: an oath on the character who swore it, a prophecy or motto on its concept or group.
4. **Build a character reference.** For each significant character, note:
   - Full name, aliases, titles, and any identity reveal; distinguish aliases clearly.
   - Role, identifying traits, background, abilities, limitations, motives, and goals.
   - Relationships, allegiance, changes, important secrets, and end-of-book status.
   - What the character knows, believes, claims, or misunderstands when that distinction matters.

   Do not collect detailed physical descriptions; they are found in the text when needed.
5. **Record the world and its rules.** Preserve exact terminology, geography, dates, numbers, factions, history, technologies, magic or supernatural rules, costs, limitations, and exceptions. Note fauna and flora. Distinguish rules explained as fact from characters' theories or beliefs.
6. **Keep relationship and clue threads.** Track alliances, rivalries, betrayals, debts, promises, plans, secrets, suspicious behaviour, clues, contradictions, foreshadowing, and unresolved questions. Do not discard a detail merely because its importance is uncertain.
7. **Inventory consequential specifics.** Note important objects, who holds them, their condition, and when they change hands. Include other concrete details (names, dates, numbers, routes, titles, and terminology) that may affect later books.
8. **Write the end state.** State where significant characters stand, what changed, who knows what, which plans or conflicts remain active, and which major mysteries are still unresolved.
9. **Compress and audit.** Remove repetition and ornamental prose without deleting potentially consequential facts. Check names, aliases, sequence, causal links, numbers, and end states against the source. Mark inference and uncertainty; never convert speculation into fact or resolve an open mystery.
10. **Verify the deliverable.** Confirm both files exist, are non-empty, and have the expected sections. Check `chapters.md` against `book-search chapters`: every story section, unnumbered ones included, has exactly one note, in reading order, naming the part where chapter numbering restarts. Report their paths and any source limitations.

## The two files

**`chapters.md`** holds only the chapter-by-chapter notes, in reading order and grouped by part when the book has parts. If chapter numbering restarts in each part, identify both the part and the chapter. Sections without a chapter number (prologue, interludes, epilogue) keep the source's own headings.

**`reference.md`** holds everything else. A useful default is:

1. Title, author, spoiler note, and source.
2. Narrative structure and chronology, including a separate chronological sequence if needed.
3. Characters and their end states.
4. World, factions, terminology, and system rules.
5. Relationships, objects, clues, open questions, and unresolved plans.
6. Final story state and important knowledge held by each side.

Adapt the structure to the book; omit irrelevant sections rather than filling them with empty entries. Use compact bullets, tables, and short labels where they improve retrieval. Do not add source references or quote links: the chapter notes place events, and any detail can be found again in the text when needed.

In a series, each book's files stand on their own: a returning character, place, or rule gets its entry again, with what this book adds. Earlier books' memories may help to recognise them; never use a book the user has not read.

## Length, style, and accuracy

- There is no length target: coverage comes first. The user may ask for a condensed version later (see "Condensing").
- Prefer precise factual notes over polished prose. Compress wording, not coverage.
- Use original wording. Avoid reproducing extended passages from the book; quote only short, story-significant wording.
- Clearly distinguish established facts from a character's claim, belief, reasonable inference, or unresolved question.
- Preserve uncertainty: do not infer motives, relationships, rules, or outcomes the text leaves ambiguous.
- For a series, retain details that could matter in later installments, even if they seem minor in this volume.

## Condensing

When the user asks to condense a book memory, write `chapters-condensed.md` next to `chapters.md`.

- Work from `chapters.md`, not from the book, keeping its headings and order. Leave `chapters.md` and `reference.md` in place. If `chapters-condensed.md` already exists, ask before replacing it.
- When condensing turns up an inconsistency, check it against the text with `book-search` and fix it in `chapters.md` or `reference.md` as well, so the files agree. Report what you changed.
