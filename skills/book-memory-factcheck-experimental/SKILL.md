---
name: book-memory-factcheck-experimental
description: "Experimental; run only when the user invokes it by name. A report-only fact check of a finished book's memory (chapters.md, chapters-condensed.md, reference.md) against the book's text, done chapter by chapter by subagents on a small, cheap model. Reports what the text contradicts or doesn't support, fixes only what the user confirms, and logs the pass in the book's metadata.md. Do not use for developing or modifying the Book Companion application or its scripts."
argument-hint: "[book] [files to check; default: every memory file]"
disable-model-invocation: true
---

# Book Memory Fact Check (experimental)

Paths that start with `../` are relative to this skill's own folder (the one holding this `SKILL.md`). All other paths are relative to the library root, the folder you run commands from.

Before starting, read `../book-companion/library.md` (layout, file safety).

A book memory (see `../book-memory-extraction/SKILL.md`) is written once and then trusted for years, so a wrong name or number in it lingers. This skill checks it cheaply. Checking is easier than writing: a checker doesn't decide what matters, it only asks whether the text supports each note. And each note in `chapters.md` covers one section of the book, so it can be checked against that section alone, in small, independent jobs that a small model can do.

Your part is the planning and the judgment: split the work into jobs, hand them to checker subagents on a small model, weed out their false alarms, and report to the user. Keep the book's text out of your own context and read only the paragraphs a flag points to. That is where the savings come from, since you are likely running on a larger, costlier model than the checkers.

This is an experiment: the user wants to learn whether a cheap pass finds real errors. Report the numbers that show it (section 5), also when nothing was found.

## 1. Find the book and its memory

1. Identify the volume from the user's request; `reading-progress.md` and the `volumes/` folder names help. Ask if it is still ambiguous.
2. Its folder must hold `chapters.md`. If the book has no memory, say so; writing one is the `book-memory-extraction` skill's job.
3. The book must be finished: its `reading-progress.md` shows it as `status: finished`, or it is an earlier volume of the series. If the progress disagrees, stop and tell the user. Never pass `--allow-spoilers`, and tell the checkers not to.
4. Check the memory files the user names; by default, all that exist of `chapters.md`, `chapters-condensed.md` and `reference.md`.
5. Run `book-search chapters <volume directory>` and match each note heading in `chapters.md` to its section number. Sections without notes (the contents, part title pages) need no check.

## 2. Plan the jobs

- **`chapters.md` against the book.** Split the noted sections into batches of consecutive sections, about 100,000 characters of text each. The size of `book.txt` divided by the number of chapters gives the average chapter length; a short book may be a single batch. Smaller batches keep each checker's context small and its attention on the text.
- **`chapters-condensed.md` against `chapters.md`.** One job, or two for a long book, split by part. It needs no book text: the condensed file is made from `chapters.md`, so an error the two share is caught by the job above, and this job catches only what condensing changed.
- **`reference.md` against the book.** Look through its character list and pick the main characters, the few the story follows throughout. Their entries draw on the whole book and are too spread out to check this way, so skip them. Give the rest (minor characters, places, objects, factions, terms) to checkers, about 25 entries per job.

Run all the jobs in one turn, so they run in parallel, as subagents on the smallest model available (in Claude Code, the Agent tool with `model: "haiku"`). Each starts with no context, so its brief must hold everything it needs. Without subagents, do the jobs yourself one at a time, and tell the user that the pass is only cheap when this session itself runs on a small model.

## 3. The checkers' briefs

Fill in these briefs and send them. Give the library root as an absolute path, so the checker runs `book-search` from there.

A `chapters.md` job:

```text
Fact-check notes about a novel against its text. This is report-only: don't edit, create or delete any file.

Run commands from the library root: <absolute path>.
Read the book's sections <N> to <M> with:
  book-search read "<volume directory>" --from "section <N>" --to "section <M>"
It prints a page at a time; run the command it prints to get the next page. Read nothing outside these sections, and never pass --allow-spoilers.

The notes to check are the bullets under these headings of <volume directory>/chapters.md, one heading per section: <headings, each with its section number>. Each bullet is one note.
The notes cover the whole book, so a note may call a character by a name the text reveals only later. Read the character names and aliases in <volume directory>/reference.md first, and don't flag a name that reference.md gives for the same person.

Check each note's hard facts against its own section's text: names, titles, numbers, places, objects, who did what to whom, who holds what, the order of events, and quoted wording.
Flag a note only when it is
- contradicted: the text says otherwise, or
- not found: you read the whole section and nothing in it supports the note.
Don't flag paraphrase or compression that keeps the meaning, omissions, motives or interpretation, or anything the note marks as inference or uncertain ("implied", "likely", "not stated", "inference").

Reply with one line per flag:
FLAG | <heading> | contradicted or not found | note: "<the note's words>" | text: "<one sentence from the book, or nothing>" | section <s> ¶<p>
The ¶ numbers are the paragraph numbers book-search prints. End with one line:
CHECKED <number of notes> notes in sections <N>-<M>, <number of flags> flags
```

A `chapters-condensed.md` job:

```text
Compare two versions of chapter notes about a novel. This is report-only: don't edit, create or delete any file.

<volume directory>/chapters-condensed.md is a condensed version of <volume directory>/chapters.md, with the same headings in the same order. Check the headings from <first> to <last>.
For each heading, check every statement in the condensed notes against the full notes under the same heading. Flag a statement when the full notes contradict it, or don't contain it. If the full notes have it under another heading, say which. Don't flag what the condensed version leaves out, or wording that keeps the meaning.

Reply with one line per flag:
FLAG | <heading> | contradicted or not found | condensed: "<its words>" | full: "<the full notes' words, or nothing>"
End with one line:
CHECKED <number of headings> headings, <number of flags> flags
```

A `reference.md` job:

```text
Fact-check entries of a novel's reference notes against its text. This is report-only: don't edit, create or delete any file.

Run commands from the library root: <absolute path>.
The entries to check are in <volume directory>/reference.md: <entry names>.
For each entry, search the whole book for its name, once:
  book-search search "<volume directory>" "<name>" --full
Search for an alias only if the name finds nothing. Never pass --allow-spoilers.
Check the entry's hard facts against what the hits say: names, aliases, titles, numbers, terms, who holds what, who did what to whom. Skip what the hits can't settle: claims spread over the whole book, negative claims ("never", "no one knows") and interpretation. Don't flag anything the entry marks as inference or uncertain.
Flag a claim as contradicted when a hit says otherwise. Flag it as not found only when it is a name, alias, title or term that the book never uses.

Reply with one line per flag:
FLAG | <entry> | contradicted or not found | note: "<the entry's words>" | text: "<one sentence from the book, or nothing>" | section <s> ¶<p>
Each hit's heading ends with its section number; the ¶ numbers are the paragraph numbers. End with one line:
CHECKED <number of entries> entries, <number of searches> searches, <number of flags> flags
```

## 4. Weed out false alarms

Small models raise false alarms, and the report is only as useful as your judgment of them. For each flag:

- **Contradicted:** read the cited paragraph, `book-search read "<volume directory>" "section <s> paragraph <p>" --max-chars 1500`, and compare it with the note. Keep the flag if the note is wrong. Drop it if the checker misread, the note is a fair paraphrase, or it uses a name revealed later.
- **Not found:** search for the claim's most distinctive word, first in its section, then in the whole book. Drop the flag if its section supports the note after all. If only another section does, keep it as a note under the wrong heading.
- **Condensed against full:** where the two files disagree, the book decides; settle it with a search. If the full notes turn out to be the wrong ones (say the user fixed the condensed file by hand), the finding is in `chapters.md`.

Don't read whole chapters to settle a flag. If a paragraph or two can't settle it, list it as unresolved. Keep count of the flags you drop and why (paraphrase, alias, misread): that tells the user how noisy the checkers are.

## 5. Report

Reply in chat; don't write a report file. Start with one line of numbers: the files checked, the number of jobs and their model, the flags raised, and the flags kept. Then the kept findings, numbered so that the user can answer "fix 1 and 3":

```text
1. <file>, <heading or entry>
   Note: "<the note's words>"
   Book (section <s> ¶<p>): "<the sentence that shows it>"
   Fix: <the corrected wording>
   Also in: <other memory files that repeat it, or none>
```

For "Also in", search the other memory files for the same wrong name, word or number. After the findings, list the unresolved flags briefly, then the dropped ones as a count with their reasons ("6 dropped: 4 paraphrase, 2 aliases"). If you kept nothing, say so plainly: a clean result is a result too.

Ask which findings to fix.

## 6. Fix and log

1. Fix only the findings the user confirms, in every memory file that repeats the error, with the smallest edit that makes the note right. Don't rewrite the notes around it.
2. Add an entry to the book's memory log in `metadata.md`, following `../book-memory-extraction/memory-log.md`, also when nothing was found or fixed. Say which files were checked, how many flags the checkers raised, how many you kept, and how many the user had fixed, and name both models: yours and the checkers'. Like every log entry, it names no story details. For example:

   `- 2026-11-12: Fact check of chapters.md, chapters-condensed.md and reference.md: 14 flags from the checkers, 3 kept, 2 fixed with the user's confirmation. Model: Claude Opus 5.5; checkers: Claude Haiku 5.5 subagents. Cost: not supplied.`

3. Say in one line that the user can tell you the pass's cost.
