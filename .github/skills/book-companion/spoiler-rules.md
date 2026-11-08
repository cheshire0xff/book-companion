# Spoiler protection and reading progress

These rules are shared by the `book-companion` and `book-images` skills, and `book-import` uses the reading-progress template. The tool's `--help` explains the same terms. Spoiler protection is a primary requirement, not a stylistic preference.

## Terms

- **Chapter:** the number a reader uses ("chapter 46"). The search tool reads it from the book's table of contents.
- **Part:** only for books whose chapter numbering restarts in each part. "Book Two, chapter 5" is part 2, chapter 5. The import `check` reports when this applies.
- **Section:** every item of the book's table of contents, numbered 1, 2, 3… in reading order: cover, prologue, part pages, chapters, interludes, epilogue. Every chapter is also a section. Section numbers are needed only for a place without a chapter number, such as a prologue or interlude. `chapters` lists them.
- **Book:** in a series, the volume number from the book folder's prefix (`01-empire-of-silence` is book 1).

## Reading-progress file

There is **one `reading-progress.md` per series**, in the series directory (`books/<author>/<series>/`). A standalone novel has its own in its book directory. The file records a single **story point**: the book being read and how far into it. Books before it count as read, books after it as unread. This assumes the series is read in volume order.

The search tool reads **only the front-matter block** between the `---` lines; everything below it is free-form notes for the user. Use this template:

```markdown
---
book: 1             # the book being read (volume number from its folder prefix)
status: not started # that book: not started | reading | finished
chapter:            # last completed chapter in that book
part:               # only if that book's chapter numbering restarts in each part
section:            # instead of chapter, for a place without a chapter number
updated: YYYY-MM-DD
---

# Reading progress: <series name>

- Current: <book title>, chapter <n>
- Current physical page: unknown

## Notes

- Physical page numbers refer to the user's physical edition; EPUB/TXT pagination has not been assumed to match it.
```

For a standalone novel, leave out the `book:` line.

The front matter is strict, and the tool refuses to search when it is invalid:

- `book` is required in a series and not allowed for a standalone novel. It may be one past the highest imported volume (the user is reading a book that is not in the library yet).
- `status` is exactly `not started`, `reading` or `finished`, and describes that book.
- `chapter`, `part` and `section` are whole numbers or empty. Set `chapter` or `section`, never both. `part` is only used together with `chapter`.
- `updated` is a date (`YYYY-MM-DD`) or empty.
- Unknown or repeated keys are errors. Comments after `#` are ignored.

`status: finished` makes the whole of that book searchable, so `chapter` no longer matters. `status: reading` with no chapter or section means nothing of that book is completed yet.

## Recording progress

Update this file only when the user explicitly tells you their progress or asks you to record it. Never advance the checkpoint based on assumptions, inferred reading speed, elapsed time, or what the user asks about.

The user may update progress informally, for example "I've finished chapter 18", "I'm on page 247, in chapter 19", or "I finished the book". Interpret updates conservatively:

- "Finished chapter 18" means `chapter: 18` in the current book.
- "I finished book 1" means `book: 1`, `status: finished`. "I started book 2" means `book: 2`, `status: reading`, with `chapter` and `section` empty.
- "I'm on page 247" does not mean the whole chapter containing that page is complete. Record the page in the notes, and ask for the last completed chapter if that is necessary to answer a story question safely.
- If the user says they are partway through a chapter, keep the last completed chapter as the boundary.
- If the user says they have finished the book, set `status: finished`.
- For a book whose numbering restarts in each part, record both: "finished Book Two, chapter 5" is `part: 2` and `chapter: 5`. If the user gives only a chapter number for such a book, ask which part.
- For a place without a chapter number, such as "I finished the prologue", find its section number with `chapters` and record `section:` instead of `chapter:`.
- Do not advance progress just because the user asks about a character or location.
- If the user corrects an earlier checkpoint, use the latest explicit correction and update the file.
- After every update, run `check` on the series (or standalone book) and confirm the reported boundary matches what the user said.

## Safe boundary

- The boundary is the end of the last completed chapter or section, or the whole book when it is finished.
- A physical page number is useful context, but EPUB/TXT text does not reliably map to pages in a particular print edition. Do not pretend that it does.
- If the user is partway through a chapter, do not use the rest of that chapter unless the user provides a verified passage boundary or explicitly says the entire chapter may be used.
- If nothing is completed yet, do not research story content from the book. Ask the user what they have read.
- The user may explicitly authorize a spoiler, a later chapter, or the whole book for a particular request. Treat that as a one-request exception unless they explicitly ask to change their ongoing reading progress.

## Retrieval discipline

Search and read story text with the bounded search tool, run from the project root. Point it at the **series directory** (`books/<author>/<series>/`) so that facts from earlier books in the series are found too. Point it at one book directory inside the series to search only that book (the series' progress still applies), or at a standalone novel's book directory.

```powershell
uv run book-search search   <series-dir> "<query>"                  # whole series, within progress
uv run book-search search   <series-dir> "<query>" --book 1 --chapter 46   # as of an earlier story point
uv run book-search read     <series-dir> --book 1 --chapter 46       # a whole chapter
uv run book-search chapters <series-dir>                             # sections within the boundary
```

The recorded story point decides what is searchable: earlier books in full, the current book up to its boundary, later books not at all. Results name the book, chapter and section. The tool also skips each book's contents page, so later chapter titles cannot surface. Useful search options: `--word`, `--regex`, `--context N` (whole paragraphs around each hit), `--count` (matches per section). `read` also takes `--section N` and `--from P --to Q` (paragraphs). Run `--help` for the rest.

`--book/--chapter/--part/--section` on `search` and `chapters` **narrow** the boundary to an earlier story point: earlier books up to their progress, the given book up to that point, later books not at all. `--start-book/--start-chapter/--start-part/--start-section` make the search begin later. Together they give a range, for example only chapters 66–71:

```powershell
uv run book-search search <series-dir> "Kalima" --word --start-book 1 --start-chapter 66 --book 1 --chapter 71
```

Narrowing and start points are always allowed; they never widen past recorded progress. Use them when an answer or image should reflect a particular stretch of the story.

Search efficiently:

1. Start with `--count` to see which chapters a name or term appears in, then search or `read` just those.
2. Use `--word` for names and short terms, so they do not match inside other words. It also works with `--regex`, where it applies to the two ends of the whole pattern.
3. For descriptive passages, search for a name near a keyword, with capture groups so only the keywords are highlighted: `"(Anaïs).{0,300}(hair|eyes|silk)" --regex`.
4. Output stops after `--max-chars` (default 12000). The tool then lists the remaining matches by section and prints the `--start-book/--start-section/--start-paragraph` flags that continue from the next hit. Rerun with those flags to read the next page, or narrow the search instead if the remaining sections are not relevant.

Before answering a question about the story, a character, a location, a faction, an object, or an image:

1. Read the series' (or standalone book's) `reading-progress.md`, so you know the story point you are answering from.
2. Use the tool for every story search and read. Do not grep or open `book.txt` or the `book-html/` chapter files directly for story questions; they contain the whole book.
3. Read enough around a hit (`--context` or `read`) to understand it; do not rely on an isolated keyword match.
4. If the tool reports a boundary error (invalid progress file, nothing completed, ambiguous chapter number), resolve it with the user. Do not work around it by reading the files directly.
5. Going past recorded progress (`--all`, or a later story point) requires `--allow-spoilers`. Add it only when the user explicitly authorized that for this request. Never use it to check whether a guess is correct.
6. Do not use external sources for fictional-world information. They commonly contain spoilers and may mix canon with fan interpretation.
7. If the tool cannot determine chapter boundaries for a book, stop and explain the limitation. Do not fall back to an unrestricted search of the full text.
8. If the relevant information has not appeared by the checkpoint, say that it has not been established in the material the user has read. Do not hint that something is revealed later.
9. When referring to evidence, give the book and chapter, as shown in the tool's section headings. Give a physical page only if it is explicitly available and verified for the user's edition.

If a spoiler boundary prevents an answer, say so plainly without hinting at what lies beyond it.

These rules and the tool reduce accidental spoilers but are not a hard technical security boundary: the agent still has filesystem access to the complete text. Follow the retrieval rules deliberately. Never claim that later text is technically inaccessible.
