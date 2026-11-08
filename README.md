# Book Companion

A local book library managed by an AI agent (GitHub Copilot or Claude Code) in VS Code. The library itself is ordinary files and folders. Four skills handle the work:

| Skill | Use it for |
| --- | --- |
| `/book-import` | Importing an EPUB from `_incoming/epubs/` |
| `/book-images` | Preparing image prompts and importing generated images |
| `/book-companion` | Spoiler-safe questions, entity profiles, reading progress |
| `/book-memory-extraction` | The book memory of a finished book, and condensing it |

You can also just ask in plain language; the agent picks the skill from its description. Shared rules live in `.github/skills/book-companion/library.md` (layout, file safety) and `spoiler-rules.md` (reading boundary), which the skills read before working.

## One-time setup

1. Open the `book_companion` directory as the VS Code workspace root.
2. The PowerShell converter is included at `tools/epub_to_txt.ps1`. It accepts `-InputFile`, `-OutputFile`, and optional `-Force`. Each conversion produces the requested TXT file plus a sibling `<name>-html/` directory. `-Force` replaces both outputs. Make sure PowerShell (`pwsh`, or `powershell.exe` on Windows) is available.
3. Install [uv](https://docs.astral.sh/uv/) and run `uv sync` once in the project root. This installs the project's `book-search` command, the spoiler-bounded search the agent uses for story questions; run it as `uv run book-search …`. Before committing code changes, run `uv run ruff check`, `uv run mypy` (strict, with the pydantic plugin) and `uv run pytest`.
4. **Copilot:** open **Copilot Chat** in **Agent** mode and type `/` to see the skills. If one does not appear, start a new chat and check that its `SKILL.md` frontmatter `name` matches its folder name.
5. **Claude Code:** it reads skills from `.claude/skills/`, not `.github/skills/`. Link the two once from the project root (a directory junction needs no admin rights), then start a new session:

   ```powershell
   New-Item -ItemType Directory -Force .claude | Out-Null
   New-Item -ItemType Junction -Path .claude\skills -Target "$PWD\.github\skills"
   ```

## Import a book

1. Copy the EPUB into `_incoming/epubs/`.
2. Ask: **`/book-import Import the EPUB in _incoming/epubs/.`**
3. The agent identifies the title and author from the EPUB metadata/front matter, checks reliable bibliographic web sources for missing or ambiguous series/volume information, chooses a destination, moves the EPUB there as `source.epub`, converts it using `tools/epub_to_txt.ps1`, checks `book.txt` and `book-html/`, and creates metadata and reading-progress files.
4. Check the reported destination and any uncertain bibliographic details.

You usually do not need to provide bibliographic details yourself. If the EPUB, front matter, and reliable web sources still do not establish the series or volume, the agent will ask you rather than guess.

Each imported book keeps `book-html/`, from which `book-search` reads both the text and the chapter structure (the EPUB's table of contents), plus `book.txt`, a plain-text copy. The import checks the structure with `book-search check`, which reports only counts, so no chapter titles or story text are seen.

## Keep your reading progress current

After a reading session, tell the agent (`/book-companion`) what you have completed. For example:

- `I finished chapter 18.`
- `I'm partway through chapter 19; last completed chapter is 18. I'm on physical page 247.`
- `I've finished the book.`
- `I finished Book Two, chapter 5.` (for books whose chapter numbering restarts in each part; the import tells you when that applies)

Progress is kept per series, in `books/<author>/<series>/reading-progress.md` (a standalone novel has its own in its book folder). The agent records it in the small `---` block at the top: the book you're on (`book`), its `status`, the last completed `chapter`, and `part` when that book's numbering restarts per part. Earlier books count as read, later ones as unread. The rest of the file is free-form notes. The last completed chapter is the normal spoiler boundary. Physical page numbers are useful context, but do not reliably map to EPUB/TXT positions. If you only provide a page number, the agent may ask which chapter you have completed before researching the story.

## Ask about the book

Examples:

- `What do we know about Valka's appearance so far?`
- `Describe the city where Hadrian first arrives, using only what I've read.`
- `Remind me what this faction is and where it has appeared.`

The agent should check the reading checkpoint first, use the book text only through that boundary, and distinguish details stated in the book from inference. Do not rely on external wikis for story lore.

The agent searches with `book-search`. Pointed at a series directory, it searches every book in the series up to your recorded story point: earlier books fully, the current book up to your boundary, later books not at all. It never returns text past that, including later chapter titles from a book's contents page. You can use it yourself too:

```powershell
uv run book-search search   books/christopher-ruocchio/sun-eater "Valka" --word --count
uv run book-search search   books/christopher-ruocchio/sun-eater "Valka" --book 1 --chapter 46
uv run book-search read     books/christopher-ruocchio/sun-eater --book 1 --chapter 46
uv run book-search chapters books/christopher-ruocchio/sun-eater
uv run book-search check    books/christopher-ruocchio/sun-eater   # structure report, no titles
```

`--book/--chapter` narrows the search to an earlier story point. Anything past your progress is refused unless `--allow-spoilers` is added, which the agent does only when you've explicitly allowed it. `--help` explains chapters, parts and sections.

## Generate an image with ChatGPT

Image generation is manual; the Go subscription is not connected to the OpenAI API or this local workspace.

1. Ask for an image prompt, for example: **`/book-images Prepare a full-body portrait prompt for Valka, based only on what I've read.`**
2. The agent researches the relevant passages and writes a prompt sidecar in the character's or location's `pics/` directory. It tells you to download the image into `_incoming/images/`; you do not need to rename it.
3. Copy the prompt into ChatGPT Images and generate the image.
4. Download the image into `_incoming/images/` and keep ChatGPT's original filename.
5. Ask the agent to import it: **`/book-images Import the new image.`**

The agent matches the filename to the prepared prompt sidecar, moves or renames the image to the prepared versioned filename in the entity's `pics/` folder, and records the original filename in the prompt sidecar metadata. If there is one staged image with a descriptive filename that uniquely matches one pending prompt, the agent can associate it without asking for confirmation. If the filename or prompt association is ambiguous, the agent will ask. ChatGPT cannot send the image directly into this local folder, so the download-and-save step is required.

There is no required number of images per character or location. Create images when they are useful or requested.

## Book memory

When you finish a book, say so and ask for its memory, for example: **`/book-memory-extraction I've finished Empire of Silence.`** The agent records the book as finished in `reading-progress.md` if it isn't yet, reads the whole book with `book-search`, and writes two files in the book's folder:

- `chapters.md`: chapter-by-chapter notes;
- `reference.md`: structure and chronology, characters, world, open threads, and the end state.

They are spoiler-complete notes for recalling the book later, for example before you start the next volume. They are long; for a shorter version, ask to condense it: **`/book-memory-extraction Condense the Empire of Silence memory.`** That writes `chapters-condensed.md` from `chapters.md` and keeps the full files.

There is no memory for a book you haven't finished. While you are reading, questions and recaps are answered from the text up to your progress.

## Where things live

```text
book_companion/
├── README.md
├── .github/
│   └── skills/
│       ├── book-companion/     # SKILL.md + shared library.md and spoiler-rules.md
│       ├── book-import/
│       ├── book-images/
│       └── book-memory-extraction/
├── .claude/skills/             # junction to .github/skills (Claude Code only)
├── pyproject.toml, uv.lock     # uv project; provides the `book-search` command
├── src/book_companion/
│   ├── core/                   # book structure, reading progress, spoiler boundary
│   └── search/                 # the book-search command
├── tests/
├── tools/
│   └── epub_to_txt.ps1         # EPUB-to-TXT and HTML converter
├── _incoming/
│   ├── epubs/                  # EPUBs waiting to be imported
│   └── images/                 # ChatGPT image downloads waiting to be imported
└── books/                      # organized library; created as needed
```

The detailed agent workflows are in the `SKILL.md` files under `.github/skills/`. There is deliberately no root `AGENTS.md`; the book workflow is kept in on-demand skills rather than always-loaded project instructions. After a successful import, `_incoming/epubs/` is empty because the EPUB has been moved into its book directory.
