---
name: book-memory-extraction
description: "Use when creating, updating or catching up the reading memory of a book or series in the user's library (story so far, chapter-by-chapter log, cast with appearances, world reference), always up to the user's reading progress. Use it when the user asks to update their memory, for a recap or summary, or for the book memory after finishing a book, and when another book skill needs the memory to be current. Do not use for developing or modifying the Book Companion application or its scripts."
argument-hint: "[series directory]"
user-invocable: true
---

# Book Memory

The memory is a compact reference of everything the user has read so far. It is what a reader needs to remember months or years later, especially when continuing a series. It is not a review or a short synopsis.

The memory grows chapter by chapter as the user reads, **never past their recorded progress**. When a book is finished, its memory is complete; there is no separate summary step.

Before starting, read `.github/skills/book-companion/library.md` and `.github/skills/book-companion/spoiler-rules.md`. If the book is not in the library yet, import it first with the `book-import` skill.

## The files

The memory lives in a `memory/` folder next to the series' `reading-progress.md` (or the standalone book's):

| File | What it holds | How it changes |
| --- | --- | --- |
| `story-so-far.md` | the whole story so far, its structure and chronology, where things stand, what is still open | rewritten each update |
| `chapters/book-<N>.md` (`chapters/book.md` for a standalone) | chapter-by-chapter notes for one book | append-only |
| `cast.md` | people and animal companions: who they are, relationships, what they know, and every description of how they look | targeted edits |
| `world.md` | places, groups, species, ships, objects and concepts: what they are, how they work, how they look | targeted edits |

Every file starts with the same front-matter block, using the keys of `reading-progress.md`. It records the last section the memory covers:

```markdown
---
book: 1          # volume number; empty for a standalone book
chapter: 72      # the last chapter covered, or empty and use section
part:            # with chapter, when numbering restarts in each part
section:         # for a last section without a chapter number
updated: 2026-11-08
---
```

All memory files always carry the same values. The point they record must never be past the reading progress.

## When to run

Recording progress never triggers an update by itself. Update the memory:

1. **When the user asks:** "update my memory", "catch up the memory", "recap", "I finished the book, create the memory".
2. **When a request needs it:** before preparing an image or answering from the memory, if the memory is behind the progress.
   - If it is more than about 10 sections behind and the user only wants a quick answer, say so, and offer to answer from `book-search` now instead.

## The loop (coordinator)

The coordinating agent does not read chapter text itself.

1. **Find where the memory ends.**
   - Read the front matter of `memory/story-so-far.md`.
   - If there is no `memory/` folder, the memory starts at the first story section of the first book.
   - In a series, earlier books count as read in full, so their memory comes first, in order.
2. **List what comes next.**
   - Run `uv run book-search chapters <series-dir> --start-book <B> --start-section <S>`, with S the section after the memory's last one. The listing stops at the reading progress.
   - Skip front and back matter (contents, copyright, acknowledgements, "also by"). Sections without a chapter number (prologue, interludes, epilogue) are story.
3. **Choose a batch** of sections totalling roughly 60 KB, usually 3–5 chapters. The ¶ counts in the listing help.
4. **Give the batch to a fresh worker** (a subagent where available; otherwise a new chat). The worker follows "Updating the memory" and reports one line, such as "book 1, chapters 12–15: 3 new cast entries, 2 new world entries, 9 quotes checked".
5. **Repeat** until the memory reaches the reading progress.

A fresh worker per batch keeps every worker's context small: the memory files carry everything forward. Afterwards, report briefly what was caught up.

## Updating the memory (worker)

1. **Load what the memory knows.**
   - Read `story-so-far.md` completely, plus the last three entries of the current chapter log.
   - List the entry headings of `cast.md` and `world.md` (the `## ` lines), then read the full entries of everyone and everything that appears in your sections.
   - Do not load the whole of a large file.
2. **Read each section completely** with `uv run book-search read <series-dir> --book <B> --section <S>`. If the output is cut off, follow the continuation it prints until you have every paragraph.
   - When something is unclear, you may search earlier text with `book-search search`.
   - Never read past your batch.
3. **Append** one chapter-log entry per section.
4. **Update `cast.md` and `world.md` with targeted edits:** add entries, and add lines to existing ones.
   - Never rewrite or regenerate a whole file.
   - Never delete an earlier detail because it is superseded. Add the new state with its reference instead (a new title, an injury, a change of clothes).
5. **Rewrite `story-so-far.md`** so it includes your sections.
6. **Check every quote** you added or changed (see "Checking quotes").
7. **Set the front matter** of every memory file to the last section you covered, with today's date in `updated`.
8. **Report** one line to the coordinator.

## Rules for every file

- **Only the text.** Write only what the sections you were given and earlier ones say. Never use memory of the novel, later chapters, books not yet read, or outside sources.
- **Everything counts.** Do not drop a detail because its importance is unclear, especially in a series, where minor details may matter later. Compress the wording, not the coverage.
- **Say who says it, and how sure.** Write it into the text: "Gibson claims…", "Hadrian suspects…", "seems to", "is said to". A first-person narrator's statements are narration; a character's beliefs about the world are claims. Never turn a claim into a fact, and never resolve a mystery the text leaves open.
- **References.** Every fact in `cast.md` and `world.md` carries where it comes from:
  - `(B1 ch 46)`;
  - `(B1 p2 ch 5)` when numbering restarts in each part;
  - `(B1 §4)` for a section without a chapter number (the section number from `book-search`).
- **Quotes are links.** An exact quote is written as a Markdown link to where it is: `["cropped hair, grey at the temples"](ref:b1/s14/p7)`.
  - `b` is the book number (left out for a standalone book: `ref:s14/p7`), `s` the section, and `p` the ¶ number shown by `read`.
  - The link text is an exact, contiguous excerpt of that one paragraph, up to 300 characters. For a description spread over several paragraphs, use one link for each.
  - Quotes are **required** on every Appearance line, and for exact wording that may matter later: oaths, riddles, prophecies, passwords, mottos, repeated phrases.
  - Elsewhere, paraphrase. Never reproduce long passages.
- **Ids.** Every cast and world entry has an id: lowercase with hyphens, from the fullest name known when it first appears (`mara-voss`). An unnamed recurring figure gets a descriptive id (`the-masked-stranger`).
  - Never change an id later; add the new name as an alias instead.
  - The id matches the entity's folder name in the library (`characters/<id>/`) where one exists.

## story-so-far.md

```markdown
# Story so far

## Structure
## The story
## Where things stand
## Still open
```

- **Structure:**
  - how the book is told (for example, an older narrator looking back, or several viewpoints);
  - time jumps;
  - the chronological order of events, where it differs from the order they are told in.
  - Keep frame events separate from the story being told.
- **The story** (up to about 1,200 words): the whole story up to the memory's point, not just the latest chapters. Compress older events as the story grows.
- **Where things stand:** for each main character, where they are, their state and what they are trying to do.
- **Still open:**
  - one line per open question, plan, promise, secret, debt, clue or prophecy, with where it was raised (`(B1 ch 12)`);
  - remove a line when the story settles it, because the chapter log records the answer.

## Chapter log (`chapters/book-<N>.md`)

One entry per section, appended in reading order. Use `# <Part name>` headings when the book is divided into parts:

```markdown
## Chapter 46: <chapter title>  (B1 ch 46 · §51)
- …
```

Typically 60–150 words per chapter, more for dense ones, as compact bullets:

- **What happened:** events, decisions, discoveries, reversals, deaths, injuries and captures, with their causes and results.
- **Knowledge:** who learns, conceals, claims or misunderstands what.
- **Threads:**
  - new open threads ("Open: who sealed the letter?");
  - settled ones ("Answered: … (raised B1 ch 12)");
  - clues, contradictions and foreshadowing.
- **Relationships:** alliances, rivalries, betrayals, debts, promises, and how relationships change.
- **Wording:** exact wording that may matter later, as quote links.
- **Time:** time cues ("three years later", dates), and moves between the narrator's present and the story.

## cast.md

People, and animal companions that act in the story. After the `# Cast` title, one line lists the main cast in order of importance. Then come the entries: main characters in full, minor ones in a line or two.

```markdown
## Mara Voss (`mara-voss`)
- Also: the courier (B1 ch 3)
- Who: courier for the harbour guild, from Ostrel (B1 ch 3)
- Status: wounded in the shoulder (B1 ch 9)
- Relationships: owes a debt to … (B1 ch 7)
- Knows / believes: believes the letter is from her brother (B1 ch 4)

### Appearance
- Hair: ["cropped hair, grey at the temples"](ref:b1/s14/p7)
- Eyes: ["…"](ref:b1/s14/p8)
- Clothing, B1 ch 9: ["a salt-stained oilskin coat"](ref:b1/s20/p3)
```

- **Appearance** records every physical description: face, eyes, hair, skin, build, height, clothing, marks (tattoos, scars), voice, age cues and posture.
  - Clothing and condition belong to their moment, so label them with the chapter.
  - A description repeated later is a second link on the same line.
- **Reveals:** when two entries turn out to be the same person, add "Revealed (B1 ch 60): is …" to both entries, and keep both.
- **What becomes an entry:** someone the text names, or a figure it keeps referring to ("the hound"), that a reader would ask about by name. Everyone else goes in the chapter log only.

## world.md

Everything else worth asking about by name. Each entry has a kind line. Reuse the kinds below, and add another only when none fits:

| Kind | For |
| --- | --- |
| `place` | planets, cities, regions, buildings; say which |
| `group` | factions, houses, orders, religions |
| `species` | peoples, creatures, plants |
| `ship` | named ships and vessels |
| `object` | notable objects |
| `concept` | magic, technology, terms, titles, calendars |

```markdown
## Ostrel (`ostrel`)
- Kind: place, a port city on the Grey Coast (B1 ch 3)
- Ruled by the harbour guild (B1 ch 3); no stone may be built below the high-water mark, a law the Tide Church claims as its own (B1 ch 20)
- Fauna and flora: gulls, salt marsh (B1 ch 3)

### Appearance
- ["grey roofs stepping down to the water"](ref:b1/s8/p2)
```

- **Places:** what and where they are ("a city on …", which links both entries), who rules them, geography, climate and terrain, fauna and flora. In Appearance: architecture, light, colours, weather, landscape and interiors.
- **Groups:** beliefs, structure, goals, history, and the people who belong to them. Keep doctrine as claims unless the narration presents it as true.
- **Species:** what they are, abilities, how they look.
- **Ships and objects:** what they are, who owns them, their condition, and when they change hands.
- **Concepts:** rules of magic or technology, as separate lines for costs, limits and exceptions; terms and what they mean; calendars, dates, numbers, distances and routes.
- **Ordinary or unnamed things** (an unnamed desert, horses, pine forests) are lines under the place they belong to.

## Checking quotes

Every quote link you add or change must be checked before you finish. Search for its exact words within that one section:

```powershell
uv run book-search search <series-dir> "<the quoted words>" --start-book <B> --start-section <S> --book <B> --section <S>
```

The result must show a match in ¶P. If it does not, fix the quote (it must be the exact words) or the reference. Never leave a quote unchecked.

## Finishing a book

When the memory reaches the last chapter of a book the user has finished, do a final review with targeted edits; never regenerate anything:

- **`story-so-far.md`:** "Where things stand" describes the end of the book, "Still open" lists what the book leaves unresolved, and the story is compressed but complete.
- **Main cast entries:** each one's status reflects the end of the book.
- **The whole memory:** names, aliases, sequence, references and numbers are consistent across files.

The memory through the last chapter is the book memory. The next book gets its own chapter log; `cast.md` and `world.md` continue, with `B2` references.

## Using the memory

- The memory never goes past the reading progress, so it is safe to read as a whole.
- For a question about an earlier point (for example, an image of how someone looked at chapter 30), ignore every line whose references come after that point.
- If the reading progress is ever earlier than the memory's front matter (progress was corrected back), do not use the memory beyond the progress. Tell the user instead.
