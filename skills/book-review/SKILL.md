---
name: book-review
description: "Use when the user wants to write down what they thought of a book in their library that they have finished (or stopped reading for good): interview them one question at a time and write their thoughts, in their own words, into review.md in the book's folder, with an optional star rating. Also for adding to or revising an existing review, such as after a reread. Use it whenever the user wants to talk through, rate or record their opinion of a book, even if they don't say 'review'. Not for recapping the story (book-companion) or for the book memory, including checking or fixing the memory files (book-memory-extraction). Do not use for developing or modifying the Book Companion application or its scripts."
argument-hint: "[book or book directory]"
user-invocable: true
---

# Book Review

Paths that start with `../` are relative to this skill's own folder (the one holding this `SKILL.md`). All other paths are relative to the library root, the folder you run commands from.

Before starting, read `../book-companion/library.md` (layout, file safety).

Interview the user about a book they have finished and write their review into `review.md` in the book's folder. The review records what *the user* thought, so that months later, perhaps before the next volume, they can read their own reaction again. Your part is to draw it out with good questions and write it down faithfully. Your own opinion of the book, other people's reviews, and what you know of the book from training don't belong in it.

## 1. Find the book

1. Identify the volume from the user's request; `reading-progress.md` and the `volumes/` folder names help. Ask if it is still ambiguous. If the book is not in the library, say so and offer to import it with the `book-import` skill; don't create a book folder for it.
2. The user should be done with the book: the series' (or standalone book's) `reading-progress.md` shows it as `status: finished`, or it is an earlier volume.
   - If the user says they finished it but the progress disagrees, record it first (see "Updating reading progress" in the `book-companion` skill; if that skill is not loaded, read `../book-companion/SKILL.md`).
   - If they stopped reading it for good and want to review it anyway, that's fine: leave the progress as it is, say in the review where they stopped, and keep your questions to what they read.
   - If they are still reading it, ask whether they'd rather wait until they've finished.
3. If `review.md` already exists, read it and ask whether to revise it, add to it (see section 5), or replace it. Replace it only when the user says so.

## 2. Prepare, without reading the book

Don't read the book's text (`book-search read` or `search`, `book.txt`, `book-html/`). The interview runs on the user's memory of a book they have just read, not yours, and reading even part of the text costs many tokens for little gain.

Prepare from what the library already holds, so that your questions can be specific ("How did the ending on the bridge land for you?" rather than "What did you think of the ending?"):

- `metadata.md`: title, author, series and volume.
- The book memory, if one has been made: `chapters-condensed.md` if it exists, and `reference.md`. Don't read the full `chapters.md`; if a question needs a detail from it, search that file for the detail.
- Earlier volumes' `review.md` files in the same series, if any. You can ask how this book compares and pick up on what the user said then. Never open anything of a later volume.

Without a memory, don't prepare: ask open questions and follow up on the characters, scenes and names the user brings up.

Don't use your own knowledge of the book or outside sources such as reviews and wikis. They may be wrong about this edition, they bring in other people's opinions, and in a series they can give away later volumes the user hasn't read.

## 3. Interview

Ask one question at a time, two at most when they belong together. Start broad, with the user's gut reaction, then go where their answers lead. If the user opened with their thoughts on the book, treat those as the first answer: don't ask for the gut reaction again, follow up on what they said. When an answer carries an opinion, a follow-up ("What made it drag?", "Which scene?", "Why didn't she work for you?") usually brings out the best material; ask one before moving to the next topic. Use the memory's specifics to make questions concrete, but don't quiz the user on the plot.

Topics to draw on, in no fixed order. Pick what fits the book and what the user cares about, and skip what they have already covered:

- **Overall:** gut reaction; whether it met their expectations.
- **Characters:** who worked and who didn't, arcs, relationships, favourites.
- **Moments:** scenes that hit hard, dragged, or surprised them.
- **Story:** pacing, structure, twists (did they see them coming?), the ending.
- **World and writing:** setting, its rules, prose, tone, dialogue.
- **In a series:** how it compares with the earlier volumes; what they expect, hope or fear from the next one, and the questions they carry into it. These are worth asking, because they are what the user will want to reread before starting the next volume.
- **Recommendation:** would they recommend it, and to whom; would they reread it.
- **Rating:** out of 5 stars, halves allowed. Ask near the end, once they have talked it through, so the number reflects the conversation rather than anchoring it. They may skip it.

How to ask:

- Ask open questions and don't lead with a view of your own ("Wasn't the ending brilliant?"). If the user asks what you think, say it clearly as your view; it stays out of the review.
- If the user gets a story fact wrong (a name, who did what) and the memory shows otherwise, mention it gently. The opinion stays theirs.
- A good interview is usually somewhere between a handful and a dozen exchanges. When the main topics are covered, ask whether there's anything else, then write. The user can stop at any point ("that's enough", "write it up"); then write with what you have.

## 4. Write review.md

Write `review.md` in the book's folder, next to `metadata.md`. For example:

```markdown
# Review: First Night

- Author: Jane Doe
- Series: The Night Saga, volume 1
- Rating: 4.5/5 ★★★★½
- Reviewed: 2026-11-10

## Overall

Best thing I've read this year. The first third is slow, but the siege more than made up for it.

## Characters

- Mira: finally stopped second-guessing everyone, and her scenes with the captain were the heart of the book for me.
- The abbess: still don't trust her. Too helpful.

## Going into volume 2

I want to know what was in the letter, and I'm expecting the tower to come back.
```

- **Header lines:** title, author, the series and volume (leave out for a standalone book), the rating (leave out if the user skipped it) and today's date. For a book the user stopped reading, add a `- Stopped at:` line with where they stopped. Write the rating as the number and five symbols, full ★, half ½ and empty ☆: `3.5/5 ★★★½☆`.
- **Headings** follow what the user talked about, such as Overall, Characters, Moments, Story and ending, World and writing, The series so far, Going into the next volume, Recommendation. Leave out topics they didn't touch.
- **The user's words, tidied:** write in the first person and keep their phrasing, slang, strong opinions and hedges. Fix typos and grammar, join fragments into sentences, and put related remarks together. Don't upgrade the vocabulary, add adjectives, or soften or sharpen what they said. Don't add reasons, examples or opinions they didn't give; if a gap matters, ask rather than fill it.
- **Spoilers:** the review covers the whole book, so name characters and events plainly, as the user did. Spell names as the memory does when there is one.
- **Length** follows what the user said. Don't pad a short interview into a long review.

Then give the user the file's path, ask them to read it, and make the changes they ask for in the file. Keep the review in `review.md` only; it doesn't go into `metadata.md` or the memory log.

## 5. Adding to a review later

The user may come back after a reread or with second thoughts. Read the existing review, interview them about what changed, and add a dated section at the end, such as `## Reread, 2027-03-01` or `## Later thoughts, 2026-12-02`, keeping the earlier text so they can see how their view moved. A new rating goes in that section; change the `Rating` line at the top only if they ask. Small corrections, such as a misspelt name or a sentence they want reworded, are made in place.
