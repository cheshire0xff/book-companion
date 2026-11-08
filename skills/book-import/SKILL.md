---
name: book-import
description: "Use when importing an EPUB into the user's book library: identifying its title, author, series and volume, filing it in the library, converting it to TXT and HTML with the bundled epub_to_txt.ps1, and writing its metadata and reading-progress notes. Do not use for developing or modifying the Book Companion application or its scripts."
argument-hint: "[path to EPUB, default _incoming/epubs/]"
---

# Book Import

Paths that start with `../` or `scripts/` are relative to this skill's own folder (the one holding this `SKILL.md`). All other paths are relative to the library root, the folder you run commands from.

Before starting, read `../book-companion/library.md` for the library layout, file-safety rules, and core principles. Use the reading-progress template in `../book-companion/spoiler-rules.md`.

The user may simply place an EPUB in `_incoming/epubs/` and ask you to import it. They should not have to provide its author, title, series, or destination path when those can be established from the file.

## 1. Inspect and identify

1. Identify the exact EPUB file. Do not scan unrelated folders or the user's whole home directory.
2. Inspect the EPUB's embedded metadata first. Use available tools such as Calibre's `ebook-meta` if installed, or inspect the archive's standard metadata files with ordinary utilities if needed.
3. Check the title page, copyright page, series information, and other front matter in the EPUB when metadata is incomplete or contradictory.
4. Establish, where possible:
   - title;
   - author or authors;
   - series name and volume number;
   - publisher and publication year;
   - edition or language;
   - ISBN, if present.
5. Distinguish original publication information from the particular edition represented by the EPUB. Do not silently combine them.
6. Do not read story content to identify bibliographic details. Prefer the EPUB's metadata and front matter.
7. When series or volume information is missing or ambiguous, use a narrow web lookup based on the exact ISBN, title, and author. Prefer the publisher's official book or series page and the author's official bibliography; use library catalog records to corroborate when needed. Treat retailer and aggregator records as secondary, and never rely on search-result snippets alone. Record source URLs, dates checked, and any conflicts in `metadata.md`. Keep lookups limited to bibliographic facts; do not read plot summaries, reviews, wiki pages, character pages, or other material that could spoil the book.
8. If the EPUB, front matter, and reasonable web lookup still do not establish the series or volume, ask the user to confirm them before choosing a series directory. Record the answer as user-confirmed. Do not infer a series from the title or default to volume 1. If the user cannot confirm, leave the fields unknown and ask how they want the book filed rather than guessing.

## 2. Choose the destination and move the EPUB

1. Check whether the book already exists in the library before creating anything. If it exists, compare the files and metadata. Do not overwrite existing files or create a duplicate without explaining the situation.
2. If it is a series book, use `books/<author-slug>/<series-slug>/books/<volume>-<book-slug>/`. If it is standalone, use the standalone layout in `library.md`.
3. If series membership or volume order remains uncertain after the lookup and user fallback in step 1, do not choose a definitive series directory. Keep the EPUB in `_incoming/epubs/` until the user clarifies how to file it.
4. Preserve the original EPUB byte-for-byte. Move the incoming EPUB into the destination as `source.epub`; do not make a second copy, and do not leave one in `_incoming/epubs/`. Verify the moved file exists and has a plausible size. If a `source.epub` already exists, do not overwrite it; investigate the duplicate or edition and ask if needed.

## 3. Convert EPUB to TXT and HTML

Use the PowerShell script `scripts/epub_to_txt.ps1` in this skill's folder; call it by its full path, since commands run from the library root. Each conversion creates both `book.txt` and a sibling `book-html/` directory containing Calibre's XHTML documents and related package files. `book-search` reads the book from `book-html/`: its text, and its table of contents for the chapter boundaries. `book.txt` is a plain-text copy. Do not invoke Calibre directly and do not implement another converter unless the user explicitly asks you to.

The script accepts `-InputFile`, `-OutputFile`, and `-Force`. Use the PowerShell executable available in the environment (normally `pwsh`; on Windows, `powershell.exe` may also be available):

```powershell
pwsh -NoProfile -File "<this skill's folder>/scripts/epub_to_txt.ps1" -InputFile '<book-directory>/source.epub' -OutputFile '<book-directory>/book.txt'
```

1. Confirm that `scripts/epub_to_txt.ps1` exists. If the script or a usable PowerShell interpreter is missing, do not silently substitute another conversion method. Tell the user exactly what is missing and ask them to provide/install it or authorize an alternative.
2. Use the documented parameter names exactly. Quote paths, especially paths containing spaces.
3. Do not pass `-Force` during normal import; it replaces both the TXT file and its HTML directory. Neither output should exist yet; if either already exists, inspect it and resolve the conflict rather than overwriting it. Use `-Force` only when the user explicitly authorizes replacing those outputs.
4. Do not modify the script itself unless the user asks you to.
5. If the script fails, report the actual error and do not mark the import as complete. Do not silently fall back to Calibre or another tool.

Conversion quality:

- Ensure the TXT is readable as UTF-8. If conversion produces an unexpected encoding or garbled text, report the issue and inspect the script's documented options before making changes.
- Preserve chapter headings, chapter order, paragraph boundaries, scene breaks, and meaningful front/back matter as well as the supplied converter allows.
- Do not remove or rewrite prose, normalize the author's style, or summarize during conversion.

## 4. Write import notes

Create `metadata.md` with known information and label unknown fields explicitly:

```markdown
# Book metadata

- Title:
- Author(s):
- Series:
- Series number:
- Publisher:
- Edition / publication year:
- Language:
- ISBN:
- Source EPUB: source.epub
- Converted text: book.txt
- Converted HTML: book-html/
- Import status: imported

## Metadata notes

- Record discrepancies, uncertain fields, source URLs and dates checked, and how each field was resolved.
```

Reading progress lives in one `reading-progress.md` per series, in the series directory; a standalone novel has its own in its book directory. Do not create one inside a series book's directory.

- If the series (or standalone book) has no `reading-progress.md` yet, create it from the template in `spoiler-rules.md` with `book: 1` (omitted for a standalone), `status: not started`, the other numbers empty, and `updated` set to today. If the user says they have already read earlier books, record that instead.
- If it already exists, do not change it. Importing a later volume never advances or resets progress.

Do not assume that importing a book means the user has read any of it.

Only create `series.md` when it has a useful purpose. It can record neutral series-level bibliographic facts and, after the user has read enough material, spoiler-safe world information. Do not use it as a place to dump plot information from unread books.

## 5. Verify and report

The import is complete only when all of these hold:

- `source.epub` exists in the final book directory and `_incoming/epubs/` holds no extra copy;
- `book.txt` exists, is non-empty, begins with plausible book content, and contains later chapter headings or other evidence that the conversion did not truncate the book (check headings only; do not read story content);
- `book-html/` exists and contains at least one non-empty HTML file;
- `book-search check <series-or-standalone-directory>` succeeds. It prints only counts, never titles or text, and also validates `reading-progress.md`. Record any warning in `metadata.md`. If it reports that chapter numbering restarts in each part, add a note to `reading-progress.md` and tell the user that progress in that book needs the part (for example "Book Two, chapter 5");
- `metadata.md` is written, and the series (or standalone book) has a valid `reading-progress.md`.

If conversion fails, keep `source.epub` in the final directory, leave the import marked incomplete, report the error, and do not move or delete the EPUB as a cleanup step.

Report the identified title, author, series/volume (including uncertainty), destination, and whether conversion succeeded.
