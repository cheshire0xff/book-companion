---
name: book-companion
description: "Use for spoiler-safe questions about books in the user's library (characters, locations, factions, objects, events, setting), recaps included, answered from a finished book's memory when it has one; maintaining entity profiles; and updating reading progress. For importing an EPUB use book-import; for image prompts or importing generated images use book-images; to write, condense or log the memory of a finished book use book-memory-extraction; for the user's own review of a book they've finished use book-review. Do not use for developing or modifying the Book Companion application or its scripts."
---

# Book Companion

Paths that start with `../` are relative to this skill's own folder (the one holding this `SKILL.md`). All other paths are relative to the library root, the folder you run commands from.

Before starting, read both shared rule files in this skill's folder:

- `library.md`: library layout, file safety, core principles.
- `spoiler-rules.md`: reading progress, safe boundary, and retrieval discipline.

Related skills:

- **`book-import`**: importing an EPUB. If that skill is not loaded, read `../book-import/SKILL.md` and follow it.
- **`book-images`**: preparing image prompts and importing generated images. If that skill is not loaded, read `../book-images/SKILL.md` and follow it.
- **`book-memory-extraction`**: the book memory of a finished book (see section 4).
- **`book-review`**: interviewing the user about a book they've finished and writing their review. If that skill is not loaded, read `../book-review/SKILL.md` and follow it.

## 1. Answering questions about the book

When the user asks about a character, location, faction, object, event, or setting detail:

1. Check the reading checkpoint first, following `spoiler-rules.md`.
2. If the question is about a book read in full that has a book memory, start from the memory, as section 4 describes. It often answers a recap or a who-is-who question on its own.
3. Search the relevant text only up to the safe boundary, with `book-search` as described in `spoiler-rules.md`: for what the memory doesn't cover or there is no memory for, such as the volume being read, and to confirm what you cite. For a series, search the series directory so earlier volumes count too.
4. Read enough surrounding text to understand context. Do not rely on an isolated keyword hit when it could be misleading.
5. Answer the actual question directly, before any supporting detail. Do not produce a long lore essay unless requested.
6. Separate the answer into clearly labelled categories when useful:
   - **Established in the book:** directly supported by accessible text.
   - **Reasonable inference:** a conclusion supported by that text but not explicitly stated.
   - **Not established yet:** information not found before the checkpoint.
7. Cite chapter numbers for substantive claims, compactly. Never fabricate a chapter number or page reference.
8. If two passages appear inconsistent, mention the discrepancy rather than silently reconciling them.
9. Do not fill missing visual or worldbuilding details from your own recollection of the book or from outside sources.

## 2. Entity profiles

Create or update an entity profile when it will be useful for future questions or image generation, not for every passing mention.

A `description.md` should be concise, cumulative, and source-aware. A useful structure is:

```markdown
# Entity name

## Established details
- Detail — [Book title, chapter N]

## Reasonable inferences
- Inference — based on [Book title, chapter N]

## Unknown / not established
- Important visual or contextual details that remain unspecified.

## Continuity notes
- Distinguish changes across time, books, disguises, or appearances.
```

Rules:

- Update profiles only with information available at the user's current reading checkpoint.
- Preserve the provenance of details. Add chapter references rather than replacing them with unsupported summaries.
- Do not turn inferences into established facts during later edits.
- For recurring characters, note which version or point in the story an image represents when that distinction matters.
- Do not assume that every character or location belongs to the whole series; some are specific to one book.

## 3. Updating reading progress

When the user reports progress ("I've finished chapter 18", "I'm on page 247", "I finished the book"), update the front matter of the series' `reading-progress.md` (or the standalone book's) following the "Recording progress" rules in `spoiler-rules.md`, and set `updated`. Then run `book-search check <series-dir>` and tell the user the boundary it reports.

## 4. Book memory

A book the user has finished can have a **book memory** in its folder: `chapters.md` (notes chapter by chapter), `reference.md` (structure, characters, world, open threads, end state) and, on request, `chapters-condensed.md`. It covers the whole book, ending included.

### Using it

- Read a book's memory only when `reading-progress.md` records that book as read in full: in a series, a volume before the one being read, or the one being read with `status: finished`; a standalone book with `status: finished`. Otherwise do not open it, even if it exists. `book-library check` warns about a memory of a book not read in full.
- Use it for what it is good at: recaps, who is who, how threads stand at the end, and where in the book to look. In a series, the memories of earlier volumes cover them; search the text for what the volume being read adds.
- It is notes, not the book. Confirm a specific claim, a quotation or a chapter you cite with `book-search` before relying on it. If the memory and the text disagree, the text wins; tell the user, since the memory may need a fix.
- It describes the whole book, so it can't answer as of an earlier story point ("as of chapter 12"). Use `book-search --to` for that.
- It has no physical descriptions: take appearance from the text with `book-search`, as section 2 and the `book-images` skill do.

### Writing it

When the user has finished a book and asks for its memory, or for a recap of a finished book that has no memory yet, invoke the **`book-memory-extraction`** skill. If it cannot be invoked, read `../book-memory-extraction/SKILL.md` and follow it. That skill owns the finished-book check, the method, and its output files; do not substitute your own outline. Write a memory again only if the user asks.

While a book is still being read, there is no memory: answer questions, recaps included, from the text up to the boundary as in section 1.
