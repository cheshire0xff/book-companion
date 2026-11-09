# Memory log

The book's `metadata.md` ends with a **Book memory** section: a short log of how the memory was made and checked. Each entry is one dated bullet in plain sentences, oldest first:

```markdown
## Book memory

- 2026-11-08: Extracted chapters.md and reference.md. Model: Claude Opus 5.5, high effort. Cost: not supplied.
- 2026-11-09: Condensed into chapters-condensed.md; fixed two aliases in reference.md. Model: Claude Opus 5.5. Cost: $1.10.
- 2026-11-12: The user read chapters-condensed.md through and fixed one name by hand.
```

If the section is missing, add it after the existing ones; if there is no `metadata.md`, create one with a `# Book metadata` heading and this section. Never rewrite or remove an entry, except to fill in what the user reports for it. The user may also edit the log themselves; keep what they write.

## Your runs

After every run that writes or changes the memory files (extracting, condensing, or a later fix), add an entry saying what you did and to which files, followed by:

- **Model**: the model that did the work, with its reasoning effort if you know it. Write it only when you know it for certain; otherwise `unknown`. If subagents ran on other models, name each.
- **Cost**: `not supplied`. You cannot see what a run cost.

Then say in one line that the user can tell you its cost (and the model, if you wrote `unknown`).

## What the user tells you

- **A run's model or cost**, now or in a later conversation: fill it into that entry as they give it (dollars, tokens, a share of a plan's limit). If more than one entry could match, ask which they mean. If the memory predates the log, add an entry with what they tell you.
- **Their own work on the memory**, such as reading the files through or fixing something by hand: add an entry in their words, dated today unless they give another date.

## No story details

`book-view` shows `metadata.md` even for books the user has not read, so the log never names characters, events or other story details: "fixed two aliases", not which ones. If the user's note includes story details, record it without them.
