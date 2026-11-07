---
name: book-memory-extraction
description: "Use when creating a book memory, book summary, novel recap, series reference, or chapter-by-chapter notes from a user-provided book. Produces compact, spoiler-complete notes for accurately recalling the story later."
argument-hint: "<book-file> [output-file]"
user-invocable: true
---

# Book Memory Extraction

Create a compact, information-dense reference that preserves what a reader may need to remember months or years later, especially when continuing a series. This is not a conventional literary review or a short plot synopsis.

## Inputs and output

1. Use the book file named or provided by the user. If the source file is unclear or unavailable, ask for its path; do not substitute another edition, an online synopsis, or remembered plot details.
2. Use the requested output path. If none is given, create `summary.txt` beside the source file.
3. Before writing, check whether the output already exists. Do not silently overwrite existing notes; ask the user what to do.
4. Do not alter the source book. Write the reference in plain text unless the user requests another format.
5. If the source format cannot be read with available tools, explain the limitation and ask for an accessible text or file. Do not invent missing content.

## Extraction procedure

1. **Map the source.** Identify the title, author, parts/books, chapter headings, epigraphs or frame sections, and the beginning and end of the actual story. Skip front matter and back matter unless they contain story-relevant material. For very large files, inspect bounded sections and process the book in manageable ranges.
2. **Track two timelines.** Record events in the order the narrative presents them, preferably by chapter. Separately reconstruct chronological order wherever flashbacks, interviews, time jumps, simultaneous events, or retrospective revelations make it differ. Keep frame events distinct from the embedded past.
3. **Record events causally.** For each chapter, capture the consequential actions, discoveries, decisions, reversals, deaths, and their causes or results. Compress dialogue into what was revealed, claimed, concealed, decided, or implied. Preserve exact wording only when a phrase, oath, riddle, prophecy, password, or repeated motif may matter later.
4. **Build a character reference.** For each significant character, note:
   - Full name, aliases, titles, and any identity reveal; distinguish aliases clearly.
   - Role, appearance or identifying traits, background, abilities, limitations, motives, and goals.
   - Relationships, allegiance, changes, important secrets, and end-of-book status.
   - What the character knows, believes, claims, or misunderstands when that distinction matters.
5. **Record the world and its rules.** Preserve exact terminology, geography, dates, numbers, factions, history, technologies, magic or supernatural rules, costs, limitations, and exceptions. Distinguish rules explained as fact from characters' theories or beliefs.
6. **Keep relationship and clue threads.** Track alliances, rivalries, betrayals, debts, promises, plans, secrets, suspicious behaviour, clues, contradictions, foreshadowing, and unresolved questions. Do not discard a detail merely because its importance is uncertain.
7. **Inventory consequential specifics.** Note important objects, abilities, ownership, locations, condition, and transfers. Include other concrete details—names, dates, numbers, routes, titles, and terminology—that may affect later books.
8. **Write the end state.** State where significant characters stand, what changed, who knows what, which plans or conflicts remain active, and which major mysteries are still unresolved.
9. **Compress and audit.** Remove repetition and ornamental prose without deleting potentially consequential facts. Check names, aliases, sequence, chapter references, causal links, numbers, and end states against the source. Mark inference and uncertainty; never convert speculation into fact or resolve an open mystery.
10. **Verify the deliverable.** Confirm the output exists, is non-empty, and has the expected sections. Report its path and any source limitations.

## Reference organization

Adapt the structure to the book; omit irrelevant sections rather than filling them with empty entries. A useful default is:

1. Title, author, spoiler note, and source.
2. Narrative structure and chronology, including a separate chronological sequence if needed.
3. Chapter-by-chapter events, grouped by part/book when applicable.
4. Characters and their end states.
5. World, factions, terminology, and system rules.
6. Relationships, objects, clues, open questions, and unresolved plans.
7. Final story state and important knowledge held by each side.

Use compact bullets, tables, and short labels where they improve retrieval. Keep chapter or source-location references beside important details whenever available. If chapter numbering restarts in each part, identify both the part and chapter. If there are no chapters, use the source's section headings or other stable locations.

## Length, style, and accuracy

- Aim for about ten dense pages for a typical 600-page novel, scaling down for shorter works and up when necessary for completeness.
- Prefer precise factual notes over polished prose. Compress wording, not coverage.
- Use original wording. Avoid reproducing extended passages from the book; quote only short, story-significant wording.
- Clearly distinguish established facts from a character's claim, belief, reasonable inference, or unresolved question.
- Preserve uncertainty: do not infer motives, relationships, rules, or outcomes the text leaves ambiguous.
- For a series, retain details that could matter in later installments, even if they seem minor in this volume.
