---
name: book-notes
description: "Use when extracting or catching up the per-chapter notes of a book in the user's library (recaps, cast, appearances, world, threads) with the book-notes tool, when the user asks to update or catch up their notes, or when another book skill needs notes that are behind. Do not use for developing or modifying the Book Companion application or its scripts."
argument-hint: "[series directory] [pass]"
---

# Book Notes

Before starting, read `.github/skills/book-companion/library.md` and `.github/skills/book-companion/spoiler-rules.md`.

Notes are short, free-text notes taken from the book **one section at a time, in reading order, never past the user's recorded progress**. They live in the series' `notes/` folder (or the standalone book's).

Each note is linked to the entries it is about, and points to the paragraph and the exact words it comes from. The tool checks those words against the book when the note is stored, and shows them from the book text when it is queried. The boundary therefore applies to notes exactly as it does to the text.

Never open the `notes/*.jsonl` files directly. Query them with the tool, which filters by the boundary:

```powershell
uv run book-notes status      <series-dir>                 # how far each pass has got
uv run book-notes cast        <series-dir> [--kind character]
uv run book-notes appearances <series-dir> valka-onderra   # or a name
uv run book-notes notes       <series-dir> valka-onderra [--pass world]
uv run book-notes notes       <series-dir> --pass threads --start-book 1 --start-chapter 60
uv run book-notes recap       <series-dir> --story-so-far
```

Queries take the same story-point flags as `book-search` (`--book/--chapter/--part/--section`) to see what was known at an earlier point.

## The four passes

| Pass | Notes on | Needed for |
| --- | --- | --- |
| `core` | the recap and story so far; everything named (entities, aliases); deaths, injuries, captivity, titles, offices, family roles, changes of side; identity reveals | everything; always runs first for each section |
| `appearance` | how anything looks: people, places, skylines, ship interiors, creatures, objects, landscapes | image prompts and backgrounds, "what does X look like" |
| `world` | what something is and how it works: geography, climate, terrain, fauna and flora, history, politics, religion and belief, rules of magic or technology, terms | setting, factions, religion, lore questions |
| `threads` | open questions, plans, promises, secrets, clues, prophecies, debts, and when they are settled; relationships; who knows what; exact wording of oaths, riddles, prophecies and mottos | relationships, mysteries, "remind me what is unresolved", summaries |

## When to run them

Notes are extracted only when something needs them; recording progress never triggers extraction by itself.

1. **When a request needs them.** Before answering, run `status` and catch up only the passes that request needs:
   - an image needs `core` and `appearance`;
   - a setting or lore question needs `core` and `world`;
   - a relationship or "what's unresolved" question needs `core` and `threads`;
   - a full-book summary needs all four.
2. **When the user asks**, for example "update my notes" or "catch up the notes for book 1": run every pass, or the ones they name, up to their progress.

If catching up would take long (many sections behind) and the user only wants a quick answer, say so and offer to answer from `book-search` now instead.

## The loop (coordinator)

The coordinating agent does not read chapter text itself. For each pass needed, in order (`core` first):

1. Run `uv run book-notes next <series-dir> --pass <pass> --sections <n>`. Choose `n` so the listed sections total roughly 60 KB (usually 3–5 chapters).
2. Give that batch to a **fresh worker** (a subagent where available; otherwise a new chat). The worker follows "Doing a pass" below, ingests its results, and reports one line such as "core, book 1, sections 12–16: 3 entities, 14 notes".
3. Repeat until `next` says "Up to date". For passes other than `core`, `next` says when it is waiting for the core pass.

A fresh worker per batch keeps every worker's context small: the notes so far are handed over by `next`, not carried in memory. Afterwards, report briefly what was caught up (passes, sections, counts).

## Doing a pass (worker)

1. Run the `next` command you were given. It prints the story so far, recent recaps, the known entities with their ids and kinds, and the exact `book-search read` command for each section.
2. Read each listed section completely with that command. If the output is cut off, follow the continuation it prints until you have every paragraph.
   - When something is unclear, you may also read the end of the previous section, or use `book-search search` for an earlier mention.
   - Never read past the listed sections.
3. Write one result object per section (a JSON list for several) in your scratch directory. `uv run book-notes schema <series-dir> <pass>` shows every field and an example.
4. Run `uv run book-notes ingest <series-dir> <file>`. If it reports an error, fix the result and ingest again; never work around a rejection. A batch is stored all-or-nothing.

### Rules for every pass

- **Only the text.** Record what these sections say. Never use knowledge of later chapters, other books you were not handed, memory of the novel, or outside sources.
- **Every paragraph counts.** Do not drop a detail because its importance is unclear; note it and let the user decide later.
- **One detail per note.** `text` (up to 80 words) says it in your own words. `about` lists every entry it concerns.
- **Refs.** Each note needs at least one ref, `{"paragraph": N, "quote": "exact words"}`. N is the ¶ number shown by `read`, and the quote a short, exact, contiguous excerpt of that paragraph. A detail spread over several paragraphs gets one ref for each. The tool checks every quote and stores only where it is.
- **Say who says it, and how sure.** Write it into the text: "Gibson claims…", "Hadrian suspects…", "seems to", "is said to". A first-person narrator's statements are narration; a character's beliefs about the world are claims. Do not turn a claim into a fact.
- **Ids.** Reuse the ids listed by `next`. A new id is lowercase with hyphens, from the fullest name known at that point (`valka-onderra`). An unnamed recurring figure gets a descriptive id (`the-masked-stranger`).
- **Names as written.** An entity's `name`, and an alias, must appear in that section as the text gives it.
- **Nothing found is fine.** Return empty lists; the section is still marked done.

### What becomes an entity

An entity is something the text names, or a figure it keeps referring to ("the hound"), that a reader would ask about by name. Unnamed or ordinary things (an unnamed desert, horses, pine forests) are not entities; note them on the nearest named entry, usually a place.

`kind` is a short lowercase label. Reuse the kinds `next` shows; these are a starting point:

| Kind | For |
| --- | --- |
| `character` | people, and animal companions that act in the story |
| `place` | planets, cities, regions, buildings (a note says which) |
| `group` | factions, houses, orders, religions |
| `species` | peoples, creatures, plants |
| `ship` | named ships and vessels |
| `object` | notable objects |
| `concept` | magic, technology, terms, titles |

Add another label only when none of these fits. Where something is, is a note about both entries: "Ostrel is a port city on the Grey Coast" with `about: ["ostrel", "the-grey-coast"]`.

### Core

- `recap.text` (up to 150 words): what happens in the section: events, decisions, discoveries, reversals, and their causes and results. Say when the section is the narrator's present rather than the story being told, and note explicit time cues ("three years later", a date).
- `recap.story_so_far` (up to 400 words): rewrite the previous story so far (shown by `next`) to include this section, compressing older events as needed. It must cover the whole story up to the end of this section, not just this section.
- `entities`: everything named for the first time (see "What becomes an entity").
- `aliases`: new names, epithets or titles for entries already known.
- `notes`: deaths, injuries, captivity, titles and offices, family roles, and changes of side.
- **Reveals:** when the text establishes that two entries are the same, write a note about both ("The masked stranger is Anaïs"). You can also add the earlier name as an alias of the real entry in that section.

### Appearance

- Note every physical description of any entry: face, eyes, hair, skin, build, height, clothing, marks (tattoos, scars), voice, age cues, posture.
- Also note how places, ships, objects and creatures look: architecture, light, colours, weather, landscape.
- Clothing and condition belong to their moment; note them each time they are described.
- Every appearance note needs at least one entry in `about`.

### World

- Put each note on the most specific entry (the faction, the religion, the system, the place).
- For rules of magic or technology, note costs, limits and exceptions separately.
- Keep doctrine and belief as claims ("The Chantry teaches…") unless the narration presents them as true.

### Threads

- **Open threads:** anything left open, such as a question, plan, promise, secret, clue, prophecy or debt. Start the text with what it is ("Open question: …", "Promise: …"), and link the entries involved.
- **Settled threads:** when the text answers or settles one, write a note that says so ("Answered: …"). `book-notes notes <series-dir> --pass threads` lists the earlier ones.
- **Relationships:** alliances, rivalries, family, love, betrayal. Put the note on both entries.
- **Knowledge:** who knows, believes or misunderstands what.
- **Wording:** oaths, riddles, prophecies, passwords, mottos and repeated phrases. Ref the exact words, using several refs when they span paragraphs.
