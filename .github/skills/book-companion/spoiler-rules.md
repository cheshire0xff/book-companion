# Spoiler protection and reading progress

These rules are shared by the `book-companion` and `book-images` skills, and `book-import` uses the reading-progress template. Spoiler protection is a primary requirement, not a stylistic preference.

## Reading-progress file

Each book must have a `reading-progress.md` file. Use this structure:

```markdown
# Reading progress

- Status: not started
- Last completed chapter: none
- Current chapter: unknown
- Current physical page: unknown
- Edition: unknown
- Safe-through boundary: none
- Last updated: YYYY-MM-DD

## Notes

- Physical page numbers refer to the user's physical edition.
- The EPUB/TXT pagination has not been assumed to match the physical edition.
```

Valid statuses are `not started`, `reading`, and `finished`.

## Recording progress

Update this file only when the user explicitly tells you their progress or asks you to record it. Never advance the checkpoint based on assumptions, inferred reading speed, elapsed time, or what the user asks about.

The user may update progress informally, for example "I've finished chapter 18", "I'm on page 247, in chapter 19", or "I finished the book". Interpret updates conservatively:

- "Finished chapter 18" means the safe boundary may advance through chapter 18.
- "I'm on page 247" does not mean the whole chapter containing that page is complete. Record the page, and ask for the last completed chapter if that is necessary to answer a story question safely.
- If the user says they are partway through a chapter, keep the last completed chapter as the safe boundary.
- If the user says they have finished the book, set the status to `finished` and the safe boundary to the end of the book.
- Do not advance progress just because the user asks about a character or location.
- If the user corrects an earlier checkpoint, use the latest explicit correction and update the file.

## Safe boundary

- The default safe boundary is the **last completed chapter**. Treat the end of that chapter as the furthest point the user has definitely read.
- A physical page number is useful context, but EPUB/TXT text does not reliably map to pages in a particular print edition. Do not pretend that it does. A page is not by itself a reliable digital retrieval boundary unless the exact edition has a verified page map.
- If the user is partway through a chapter, do not use the rest of that chapter unless the user provides a verified passage boundary or explicitly says the entire chapter may be used. The simplest safe default is to use only fully completed chapters.
- If the checkpoint is `not started` or `none`, do not research story content from the book. Ask the user what they have read.
- The user may explicitly authorize a spoiler, a later chapter, or the whole book for a particular request. Treat that as a one-request exception unless they explicitly ask to change their ongoing reading progress.

## Retrieval discipline

Before answering a question about the story, a character, a location, a faction, an object, or an image:

1. Read the relevant book's `reading-progress.md`.
2. Identify the safe-through chapter.
3. When TXT headings or a table of contents make chapter boundaries ambiguous, use `book-html/` as a structural reference. Follow its XHTML documents and, when available, navigation or package metadata in reading order to distinguish front matter or TOC entries from narrative chapters. Inspect only through the safe boundary; do not dump later filenames/titles or inspect later chapter content.
4. Search and inspect only text at or before that boundary.
5. Do not inspect later chapters to check whether a guess is correct.
6. Do not use external sources for fictional-world information. They commonly contain spoilers and may mix canon with fan interpretation.
7. If neither `book-html/` nor `book.txt` provides reliable chapter boundaries, stop and explain the limitation. Do not perform an unrestricted search across the full TXT and hope not to notice spoilers.
8. If the relevant information has not appeared by the checkpoint, say that it has not been established in the material the user has read. Do not hint that something is revealed later.
9. When referring to evidence, give the book and chapter. Give a physical page only if it is explicitly available and verified for the user's edition.

If a spoiler boundary prevents an answer, say so plainly without hinting at what lies beyond it.

These rules reduce accidental spoilers but are not a hard technical security boundary: the agent may have filesystem access to the complete TXT. Follow the retrieval rules deliberately. Never claim that later text is technically inaccessible unless the environment actually enforces that restriction.
