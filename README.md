# Book Companion

A local book library managed by an AI agent (GitHub Copilot or Claude Code) in VS Code. The library itself is ordinary files and folders. Three skills handle the work:

| Skill | Use it for |
| --- | --- |
| `/book-import` | Importing an EPUB from `_incoming/epubs/` |
| `/book-images` | Preparing image prompts and importing generated images |
| `/book-companion` | Spoiler-safe questions, entity profiles, reading progress, summaries |

You can also just ask in plain language; the agent picks the skill from its description. Shared rules live in `.github/skills/book-companion/library.md` (layout, file safety) and `spoiler-rules.md` (reading boundary), which the skills read before working.

## One-time setup

1. Open the `book_companion` directory as the VS Code workspace root.
2. The PowerShell converter is included at `tools/epub_to_txt.ps1`. It accepts `-InputFile`, `-OutputFile`, and optional `-Force`. Each conversion produces the requested TXT file plus a sibling `<name>-html/` directory. `-Force` replaces both outputs. Make sure PowerShell (`pwsh`, or `powershell.exe` on Windows) is available.
3. **Copilot:** open **Copilot Chat** in **Agent** mode and type `/` to see the skills. If one does not appear, start a new chat and check that its `SKILL.md` frontmatter `name` matches its folder name.
4. **Claude Code:** it reads skills from `.claude/skills/`, not `.github/skills/`. Link the two once from the project root (a directory junction needs no admin rights), then start a new session:

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

Each imported book keeps `book.txt` for full-text search and extraction, plus `book-html/` for structural checks such as chapter order and boundaries. The HTML package contains separate XHTML documents and related package files. If TXT headings are ambiguous because of a table of contents or repeated markers, the agent should use that output to verify narrative order while respecting your spoiler boundary; it must not inspect later chapter titles or content.

## Keep your reading progress current

After a reading session, tell the agent (`/book-companion`) what you have completed. For example:

- `I finished chapter 18.`
- `I'm partway through chapter 19; last completed chapter is 18. I'm on physical page 247.`
- `I've finished the book.`

The agent records this in that book's `reading-progress.md`. The last completed chapter is the normal spoiler boundary. Physical page numbers are useful context, but do not reliably map to EPUB/TXT positions. If you only provide a page number, the agent may ask which chapter you have completed before researching the story.

## Ask about the book

Examples:

- `What do we know about Valka's appearance so far?`
- `Describe the city where Hadrian first arrives, using only what I've read.`
- `Remind me what this faction is and where it has appeared.`

The agent should check the reading checkpoint first, use the book text only through that boundary, and distinguish details stated in the book from inference. Do not rely on external wikis for story lore.

## Generate an image with ChatGPT

Image generation is manual; the Go subscription is not connected to the OpenAI API or this local workspace.

1. Ask for an image prompt, for example: **`/book-images Prepare a full-body portrait prompt for Valka, based only on what I've read.`**
2. The agent researches the relevant passages and writes a prompt sidecar in the character's or location's `pics/` directory. It tells you to download the image into `_incoming/images/`; you do not need to rename it.
3. Copy the prompt into ChatGPT Images and generate the image.
4. Download the image into `_incoming/images/` and keep ChatGPT's original filename.
5. Ask the agent to import it: **`/book-images Import the new image.`**

The agent matches the filename to the prepared prompt sidecar, moves or renames the image to the prepared versioned filename in the entity's `pics/` folder, and records the original filename in the prompt sidecar metadata. If there is one staged image with a descriptive filename that uniquely matches one pending prompt, the agent can associate it without asking for confirmation. If the filename or prompt association is ambiguous, the agent will ask. ChatGPT cannot send the image directly into this local folder, so the download-and-save step is required.

There is no required number of images per character or location. Create images when they are useful or requested.

## Summaries

Full-book summaries and memory extraction use the **`book-memory-extraction`** skill, located alongside `book-companion` under `.github/skills/`. The Book Companion skill handles the library and spoiler checks, then delegates the actual extraction methodology to its sibling skill.

When you finish a book, say so explicitly and ask for a summary, for example: **`/book-companion I've finished Empire of Silence. Create the book memory.`** The agent should check `reading-progress.md`, invoke the extraction skill with the book's `book.txt`, and preserve any memory artifacts it produces. The primary summary is saved as Markdown in `summary.md` unless you specify another structure.

The agent must not run full-book extraction before you have finished the book or explicitly authorized spoilers.

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
├── tools/
│   └── epub_to_txt.ps1         # EPUB-to-TXT and HTML converter
├── _incoming/
│   ├── epubs/                  # EPUBs waiting to be imported
│   └── images/                 # ChatGPT image downloads waiting to be imported
└── books/                      # organized library; created as needed
```

The detailed agent workflows are in the `SKILL.md` files under `.github/skills/`. There is deliberately no root `AGENTS.md`; the book workflow is kept in on-demand skills rather than always-loaded project instructions. After a successful import, `_incoming/epubs/` is empty because the EPUB has been moved into its book directory.
