---
name: book-companion
description: "Use for spoiler-safe questions about books in the user's library (characters, locations, factions, objects, events, setting), maintaining entity profiles, updating reading progress, and creating post-reading summaries. For importing an EPUB use book-import; for image prompts or importing generated images use book-images. Do not use for developing or modifying the Book Companion application or its scripts."
---

# Book Companion

Before starting, read both shared rule files in this skill's folder:

- `.github/skills/book-companion/library.md`: library layout, file safety, core principles.
- `.github/skills/book-companion/spoiler-rules.md`: reading progress, safe boundary, and retrieval discipline.

Related skills:

- **`book-import`**: importing an EPUB. If that skill is not loaded, read `.github/skills/book-import/SKILL.md` and follow it.
- **`book-images`**: preparing image prompts and importing generated images. If that skill is not loaded, read `.github/skills/book-images/SKILL.md` and follow it.
- **`book-memory-extraction`**: full-book summaries (see section 4).

## 1. Answering questions about the book

When the user asks about a character, location, faction, object, event, or setting detail:

1. Check the reading checkpoint first, following `spoiler-rules.md`.
2. Search the relevant text only up to the safe boundary, with `tools/book_search.py` as described in `spoiler-rules.md`. For a series, search the series directory so earlier books count too.
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

When the user reports progress ("I've finished chapter 18", "I'm on page 247", "I finished the book"), update the front matter of the series' `reading-progress.md` (or the standalone book's) following the "Recording progress" rules in `spoiler-rules.md`, and set `updated`. Then run `uv run tools/book_search.py check <series-dir>` and tell the user the boundary it reports.

## 4. Summaries and reading notes

The sibling **`book-memory-extraction`** skill (`.github/skills/book-memory-extraction/SKILL.md`) owns the full-book memory extraction and summary methodology. This skill owns the library workflow and the spoiler gate.

### 4.1 Spoiler gate

- Do not create or request a full-book memory summary until the user says they have finished the book or explicitly authorizes a spoiler-inclusive extraction.
- Before invoking the extraction skill, check `reading-progress.md` (or run `check`). If the book is not finished according to it (an earlier book in the series, or the current book with `status: finished`), stop and ask whether the user has finished it or explicitly wants a spoiler-inclusive summary. Do not infer completion from the request alone.
- Chapter-limited notes for already-read material are allowed, but do not run the full-book extraction skill for those notes unless the user asks for it and the skill supports that limited scope.

### 4.2 Delegate summary creation

When the spoiler gate is satisfied:

1. Confirm that `reading-progress.md` shows the book as read; if the user has just finished it, record `status: finished` for it.
2. Invoke `book-memory-extraction` (or read its `SKILL.md` and follow it if it cannot be invoked). Do not recreate its process or substitute your own summary outline.
3. Give it the book's `book.txt` path and bibliographic metadata, and explicitly request **Markdown output at `<book-directory>/summary.md`**. That skill otherwise defaults to plain-text `summary.txt`.
4. Preserve any additional memory files or artifacts that the extraction skill produces. Do not flatten or discard its structure just to fit this example.
5. After extraction, verify that the expected output files exist and report their locations. Do not silently overwrite an existing summary or memory file; preserve it, create a versioned output, or ask the user how to handle the conflict.

Do not import revelations from later books into a summary of an earlier book unless the user explicitly requests series-wide spoilers. Keep each book's summary grounded in that book's text unless the user requests a series-wide memory extraction.
