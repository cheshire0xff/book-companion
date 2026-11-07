# Book Companion

A local book library managed with GitHub Copilot in VS Code. The Copilot skill handles book imports, spoiler-aware research, image prompts, downloaded-image organization, and summaries. The library itself is ordinary files and folders.

## One-time setup

1. Open the `book_companion` directory as the VS Code workspace root.
2. Put your PowerShell converter at `tools/epub_to_txt.ps1`. The converter is user-provided; it is not included here. It accepts `-InputFile`, `-OutputFile`, and optional `-Force`. Make sure PowerShell (`pwsh`, or `powershell.exe` on Windows) is available.
3. Open **Copilot Chat** in **Agent** mode. Type `/` and look for `book-companion`. You can invoke it explicitly with `/book-companion`. If it does not appear, start a new chat and check that the skill is at `.github/skills/book-companion/SKILL.md` and that its frontmatter `name` is `book-companion`.

## Import a book

1. Copy the EPUB into `_incoming/epubs/`.
2. In Copilot Chat, ask: **`/book-companion Import the EPUB in _incoming/epubs/.`**
3. The agent identifies the title, author, series and volume from the EPUB metadata/front matter, chooses a destination, moves the EPUB there as `source.epub`, converts it using `tools/epub_to_txt.ps1`, checks the TXT, and creates metadata and reading-progress files.
4. Check the reported destination and any uncertain bibliographic details.

You do not need to name the author or series yourself unless the EPUB does not provide enough evidence to identify them.

## Keep your reading progress current

After a reading session, tell Copilot what you have completed. For example:

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

1. Ask Copilot to prepare an image prompt, for example: **`Prepare a full-body portrait prompt for Valka, based only on what I've read.`**
2. Copilot researches the relevant passages and writes a prompt sidecar in the character's or location's `pics/` directory. It tells you to download the image into `_incoming/images/`; you do not need to rename it.
3. Copy the prompt into ChatGPT Images and generate the image.
4. Download the image into `_incoming/images/` and keep ChatGPT's original filename.
5. Ask Copilot to import the generated image.

The agent matches the filename to the prepared prompt sidecar, moves or renames the image to the prepared versioned filename in the entity's `pics/` folder, and records the original filename in the prompt sidecar metadata. If there is one staged image with a descriptive filename that uniquely matches one pending prompt, the agent can associate it without asking for confirmation. If the filename or prompt association is ambiguous, the agent will ask. ChatGPT cannot send the image directly into this local folder, so the download-and-save step is required.

There is no required number of images per character or location. Create images when they are useful or requested.

## Summaries

Full-book summaries and memory extraction use your existing **`book-memory-extraction-skills`** skill, located alongside `book-companion` under `.github/skills/`. The Book Companion skill handles the library and spoiler checks, then delegates the actual extraction methodology to its sibling skill.

When you finish a book, say so explicitly and ask for a summary, for example: **`I've finished Empire of Silence. Use book-memory-extraction-skills to create the book memory.`** Copilot should check `reading-progress.md`, invoke the sibling extraction skill with the book's `book.txt` and output directory, and preserve any memory artifacts it produces. The primary summary should be saved as `summary.md` unless that skill or you specify another structure.

The agent must not run full-book extraction before you have finished the book or explicitly authorized spoilers.

## Where things live

```text
book_companion/
├── README.md
├── .github/
│   └── skills/
│       └── book-companion/
│           └── SKILL.md
├── tools/
│   └── epub_to_txt.ps1         # add your converter here
├── _incoming/
│   ├── epubs/                  # EPUBs waiting to be imported
│   └── images/                 # ChatGPT image downloads waiting to be imported
└── books/                      # organized library; created as needed
```

The detailed agent workflow is in `.github/skills/book-companion/SKILL.md`. There is deliberately no root `AGENTS.md`; the book workflow is kept in the on-demand skill rather than always-loaded project instructions. After a successful import, `_incoming/epubs/` is empty because the EPUB has been moved into its book directory.
