---
name: book-companion
description: "Use for spoiler-safe questions about books in the user's library (characters, locations, factions, objects, events, setting), maintaining entity profiles, and updating reading progress. For importing an EPUB use book-import; for image prompts or importing generated images use book-images; for the memory or recap of a finished book use book-memory-extraction. Do not use for developing or modifying the Book Companion application or its scripts."
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

## 1. Answering questions about the book

When the user asks about a character, location, faction, object, event, or setting detail:

1. Check the reading checkpoint first, following `spoiler-rules.md`.
2. Search the relevant text only up to the safe boundary, with `book-search` as described in `spoiler-rules.md`. For a series, search the series directory so earlier volumes count too.
3. Read enough surrounding text to understand context. Do not rely on an isolated keyword hit when it could be misleading.
4. Answer the actual question directly, before any supporting detail. Do not produce a long lore essay unless requested.
5. Separate the answer into clearly labelled categories when useful:
   - **Established in the book:** directly supported by accessible text.
   - **Reasonable inference:** a conclusion supported by that text but not explicitly stated.
   - **Not established yet:** information not found before the checkpoint.
6. Cite chapter numbers for substantive claims, compactly. Never fabricate a chapter number or page reference.
7. If two passages appear inconsistent, mention the discrepancy rather than silently reconciling them.
8. Do not fill missing visual or worldbuilding details with facts from memory or outside sources.

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

When the user has finished a book and asks for its memory or a recap, invoke the **`book-memory-extraction`** skill. If it cannot be invoked, read `../book-memory-extraction/SKILL.md` and follow it. That skill owns the finished-book check, the method, and its output files (`chapters.md` and `reference.md` in the book's folder); do not substitute your own outline.

While a book is still being read, there is no memory: answer questions, recaps included, from the text up to the boundary as in section 1.
