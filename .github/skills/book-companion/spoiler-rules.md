# Spoiler protection and reading progress

These rules are shared by the `book-companion` and `book-images` skills, and `book-import` uses the reading-progress template. Spoiler protection is a primary requirement, not a stylistic preference.

## Terms

- **Chapter:** the number a reader uses ("chapter 46"). The search tool reads it from the book's table of contents.
- **Part:** only for books whose chapter numbering restarts in each part. "Book Two, chapter 5" is part 2, chapter 5. The import `check` reports when this applies.
- **Section:** every item of the book's table of contents, numbered 1, 2, 3… in reading order: cover, prologue, part pages, chapters, interludes, epilogue. Every chapter is also a section. Section numbers are needed only for a place without a chapter number, such as a prologue or interlude. `chapters` lists them.
- **Book:** in a series, the volume number from the book folder's prefix (`01-empire-of-silence` is book 1).

## Reading-progress file

Each book must have a `reading-progress.md`. The search tool reads **only the front-matter block** between the `---` lines; everything below it is free-form notes for the user. Use this template:

```markdown
---
status: not started # not started | reading | finished
chapter:            # last completed chapter
part:               # only if chapter numbering restarts in each part
section:            # instead of chapter, for a place without a chapter number
updated: YYYY-MM-DD
---

# Reading progress

- Current chapter: unknown
- Current physical page: unknown
- Edition: unknown

## Notes

- Physical page numbers refer to the user's physical edition.
- The EPUB/TXT pagination has not been assumed to match the physical edition.
```

The front matter is strict, and the tool refuses to search when it is invalid:

- `status` is exactly `not started`, `reading` or `finished`.
- `chapter`, `part` and `section` are whole numbers or empty. Set `chapter` or `section`, never both. `part` is only used together with `chapter`.
- `updated` is a date (`YYYY-MM-DD`) or empty.
- Unknown or repeated keys are errors. Comments after `#` are ignored.

Use `status: finished` for a finished book; it makes the whole book searchable, so `chapter` no longer matters. `status: reading` with no chapter or section means nothing is completed yet.

## Recording progress

Update this file only when the user explicitly tells you their progress or asks you to record it. Never advance the checkpoint based on assumptions, inferred reading speed, elapsed time, or what the user asks about.

The user may update progress informally, for example "I've finished chapter 18", "I'm on page 247, in chapter 19", or "I finished the book". Interpret updates conservatively:

- "Finished chapter 18" means `chapter: 18`.
- "I'm on page 247" does not mean the whole chapter containing that page is complete. Record the page in the notes, and ask for the last completed chapter if that is necessary to answer a story question safely.
- If the user says they are partway through a chapter, keep the last completed chapter as the boundary.
- If the user says they have finished the book, set `status: finished`.
- For a book whose numbering restarts in each part, record both: "finished Book Two, chapter 5" is `part: 2` and `chapter: 5`. If the user gives only a chapter number for such a book, ask which part.
- For a place without a chapter number, such as "I finished the prologue", find its section number with `chapters` and record `section:` instead of `chapter:`.
- Do not advance progress just because the user asks about a character or location.
- If the user corrects an earlier checkpoint, use the latest explicit correction and update the file.
- After every update, run `check` on the book and confirm the reported boundary matches what the user said.

## Safe boundary

- The boundary is the end of the last completed chapter or section, or the whole book when it is finished.
- A physical page number is useful context, but EPUB/TXT text does not reliably map to pages in a particular print edition. Do not pretend that it does.
- If the user is partway through a chapter, do not use the rest of that chapter unless the user provides a verified passage boundary or explicitly says the entire chapter may be used.
- If nothing is completed yet, do not research story content from the book. Ask the user what they have read.
- The user may explicitly authorize a spoiler, a later chapter, or the whole book for a particular request. Treat that as a one-request exception unless they explicitly ask to change their ongoing reading progress.

## Retrieval discipline

Search and read story text with the bounded search tool, run from the project root. Point it at the **series directory** (`books/<author>/<series>/`) so that facts from earlier books in the series are found too; point it at a book directory for a standalone novel or to search one book only.

```powershell
uv run tools/book_search.py search   <series-dir> "<query>"                  # whole series, within progress
uv run tools/book_search.py search   <series-dir> "<query>" --book 1 --chapter 46   # as of an earlier story point
uv run tools/book_search.py read     <series-dir> --book 1 --chapter 46       # a whole chapter
uv run tools/book_search.py chapters <series-dir>                             # sections within the boundary
```

Each book is limited by its own `reading-progress.md`: finished books in full, the current book up to its boundary, unstarted books not at all. Results name the book, chapter and section. The tool also skips each book's contents page, so later chapter titles cannot surface. Useful search options: `--word`, `--regex`, `--context N` (whole paragraphs around each hit), `--count` (matches per section), `--max N`. `read` also takes `--section N` and `--from P --to Q` (paragraphs). Run `--help` for the rest.

`--book/--chapter/--part/--section` on `search` and `chapters` **narrow** the boundary to an earlier story point: earlier books up to their progress, the given book up to that point, later books not at all. Narrowing is always allowed. Use it when an answer or image should reflect an earlier point in the story.

Before answering a question about the story, a character, a location, a faction, an object, or an image:

1. Read the relevant book's `reading-progress.md`, so you know the boundary you are answering from.
2. Use the tool for every story search and read. Do not grep or open `book.txt` or the `book-html/` chapter files directly for story questions; they contain the whole book.
3. Read enough around a hit (`--context` or `read`) to understand it; do not rely on an isolated keyword match.
4. If the tool reports a boundary error (invalid progress file, nothing completed, ambiguous chapter number), resolve it with the user. Do not work around it by reading the files directly.
5. Going past recorded progress (`--all`, or a later story point) requires `--allow-spoilers`. Add it only when the user explicitly authorized that for this request. Never use it to check whether a guess is correct.
6. If the tool notes that an earlier book in the series is not marked finished, ask the user whether to mark it finished rather than reading it anyway.
7. Do not use external sources for fictional-world information. They commonly contain spoilers and may mix canon with fan interpretation.
8. If the tool cannot determine chapter boundaries for a book, stop and explain the limitation. Do not fall back to an unrestricted search of the full text.
9. If the relevant information has not appeared by the checkpoint, say that it has not been established in the material the user has read. Do not hint that something is revealed later.
10. When referring to evidence, give the book and chapter, as shown in the tool's section headings. Give a physical page only if it is explicitly available and verified for the user's edition.

If a spoiler boundary prevents an answer, say so plainly without hinting at what lies beyond it.

These rules and the tool reduce accidental spoilers but are not a hard technical security boundary: the agent still has filesystem access to the complete text. Follow the retrieval rules deliberately. Never claim that later text is technically inaccessible.
