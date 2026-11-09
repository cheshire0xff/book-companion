# Book Companion

[![CI](https://github.com/cheshire0xff/book-companion/actions/workflows/ci.yml/badge.svg)](https://github.com/cheshire0xff/book-companion/actions/workflows/ci.yml)

A spoiler-safe companion for your own EPUB library, run by an AI agent (Claude Code). The library is ordinary files and folders on your machine; this repository holds only the tools and skills, never any books. Four skills handle the work:

| Skill | Use it for |
| --- | --- |
| `/book-companion:book-import` | Importing an EPUB from `_incoming/epubs/` |
| `/book-companion:book-images` | Preparing image prompts and importing generated images |
| `/book-companion:book-companion` | Spoiler-safe questions, entity profiles, reading progress |
| `/book-companion:book-memory-extraction` | The book memory of a finished book, and condensing it |

You can also just ask in plain language; the agent picks the skill from its description. Shared rules live in `skills/book-companion/library.md` (layout, file safety) and `spoiler-rules.md` (reading boundary), which the skills read before working.

## Setup

The tools and the library are separate. You install the plugin and the `book-search` command once, then work from your library folder.

1. **Prerequisites:** [uv](https://docs.astral.sh/uv/) and [Calibre](https://calibre-ebook.com/) (its `ebook-convert` does the conversion). Both run on Windows, macOS and Linux; on Linux, make sure `ebook-convert` is on your PATH.
2. **Install the commands** `book-search` (the spoiler-bounded search the skills use for story questions), `book-convert` (EPUB conversion) and `book-view` (a local viewer for your notes and images):

   ```shell
   uv tool install git+https://github.com/cheshire0xff/book-companion
   ```

3. **Install the skills** as a Claude Code plugin. In a Claude Code session:

   ```text
   /plugin marketplace add cheshire0xff/book-companion
   /plugin install book-companion@cheshire0xff
   ```

4. **Create your library:** an empty folder with `_incoming/epubs/` and `_incoming/images/` inside. Open that folder in VS Code (or start `claude` in it). The skills treat the current folder as the library. Keeping it in a private git repository is a good way to back it up; never publish it, since it holds your books.

**Other agents.** The skills follow the [Agent Skills](https://agentskills.io) format and refer to their own files by paths relative to the skill folder, so other agents that support skills can use them too. For GitHub Copilot in VS Code, put the four folders from `skills/` in `~/.copilot/skills/` (copies, or junctions to a clone so updates apply), or in your library's `.github/skills/`. Install `book-search` the same way as above. Don't also put them in `~/.claude/skills/` if you use the Claude Code plugin, or Claude Code loads them twice.

## Import a book

1. Copy the EPUB into `_incoming/epubs/`.
2. Ask: **`/book-companion:book-import Import the EPUB in _incoming/epubs/.`**
3. The agent identifies the title and author from the EPUB metadata/front matter, checks reliable bibliographic web sources for missing or ambiguous series/volume information, chooses a destination, moves the EPUB there as `source.epub`, converts it with `book-convert`, checks `book.txt` and `book-html/`, and creates metadata and reading-progress files.
4. Check the reported destination and any uncertain bibliographic details.

You usually do not need to provide bibliographic details yourself. If the EPUB, front matter, and reliable web sources still do not establish the series or volume, the agent will ask you rather than guess.

Each imported book keeps `book-html/`, from which `book-search` reads both the text and the chapter structure (the EPUB's table of contents), plus `book.txt`, a plain-text copy. The import checks the structure with `book-search check`, which reports only counts, so no chapter titles or story text are seen.

## Keep your reading progress current

After a reading session, tell the agent (`/book-companion:book-companion`) what you have completed. For example:

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
book-search search   books/christopher-ruocchio/sun-eater "Valka" --word --count
book-search search   books/christopher-ruocchio/sun-eater "Valka" --book 1 --chapter 46
book-search read     books/christopher-ruocchio/sun-eater --book 1 --chapter 46
book-search chapters books/christopher-ruocchio/sun-eater
book-search check    books/christopher-ruocchio/sun-eater   # structure report, no titles
```

`--book/--chapter` narrows the search to an earlier story point. Anything past your progress is refused unless `--allow-spoilers` is added, which the agent does only when you've explicitly allowed it. `--help` explains chapters, parts and sections.

## Generate an image with ChatGPT

Image generation is manual; the Go subscription is not connected to the OpenAI API or this local library.

1. Ask for an image prompt, for example: **`/book-companion:book-images Prepare a full-body portrait prompt for Valka, based only on what I've read.`**
2. The agent researches the relevant passages and writes a prompt sidecar in the character's or location's `pics/` directory. From the same research it writes `description.md` if there isn't one yet, or adds details the existing one lacks. It tells you to download the image into `_incoming/images/`; you do not need to rename it.
3. Copy the prompt into ChatGPT Images and generate the image.
4. Download the image into `_incoming/images/` and keep ChatGPT's original filename.
5. Ask the agent to import it: **`/book-companion:book-images Import the new image.`**

The agent matches the filename to the prepared prompt sidecar, moves or renames the image to the prepared versioned filename in the entity's `pics/` folder, and records the original filename in the prompt sidecar metadata, along with the image model and cost if you mention them (now or later). If there is one staged image with a descriptive filename that uniquely matches one pending prompt, the agent can associate it without asking for confirmation. If the filename or prompt association is ambiguous, the agent will ask. ChatGPT cannot send the image directly into this local folder, so the download-and-save step is required.

There is no required number of images per character or location. Create images when they are useful or requested.

## Book memory

When you finish a book, say so and ask for its memory, for example: **`/book-companion:book-memory-extraction I've finished Empire of Silence.`** The agent records the book as finished in `reading-progress.md` if it isn't yet, reads the whole book with `book-search`, and writes two files in the book's folder:

- `chapters.md`: chapter-by-chapter notes;
- `reference.md`: structure and chronology, characters, world, open threads, and the end state.

They are spoiler-complete notes for recalling the book later, for example before you start the next volume. They are long; for a shorter version, ask to condense it: **`/book-companion:book-memory-extraction Condense the Empire of Silence memory.`** That writes `chapters-condensed.md` from `chapters.md` and keeps the full files.

The book's `metadata.md` ends with a short log of its memory: each run adds a dated entry with the files and the model. The agent can't see what a run cost, so tell it afterwards, for example **`/book-companion:book-memory-extraction The Empire of Silence memory cost $4.20.`**, and it fills it in. You can also note your own work there, such as having read the files through or fixed something by hand, by telling the agent or by editing the log yourself.

There is no memory for a book you haven't finished. While you are reading, questions and recaps are answered from the text up to your progress.

## Browse the library

Run `book-view` in your library folder (or `book-view path/to/library`). It starts a small web server on this computer only (`http://127.0.0.1:8765/`), opens your browser, and runs until you press Ctrl+C:

- **Library:** every series and standalone book, with your reading progress and image thumbnails.
- **Series:** the books with their notes (metadata, reference, chapter notes), and a card for each character, location, faction or object.
- **Entity:** its images, each with its prompt in a collapsible box, next to the rendered `description.md`, plus any prompts still waiting for an image.

Pages are rendered from the files on every request, so reload after adding an image or editing a note. Memory notes of books past your recorded progress stay behind a "⚠ Spoilers … Show anyway" box until you open it. The viewer never shows a book's text (`book.txt`, `book-html/`, `source.epub`) or anything outside the library. Use `--port N` if 8765 is taken, and `--no-browser` to only print the address.

The "Palette" menu at the top right switches the color palette: Forest & Moss (the default), Midnight & Gold, Parchment & Oxblood, Graphite & Indigo, Velvet Plum or Leather. Your browser remembers the choice in a cookie; light or dark follows your system setting. Palettes are defined in `src/book_companion/view/themes.py`; adding one there adds it to the picker, and the tests check that its text stays readable.

## Where things live

This repository (the plugin and the `book-search` package):

```text
book-companion/
├── .claude-plugin/
│   ├── plugin.json             # Claude Code plugin manifest
│   └── marketplace.json        # lets `/plugin marketplace add` install it from this repo
├── skills/
│   ├── book-companion/         # SKILL.md + shared library.md and spoiler-rules.md
│   ├── book-import/
│   ├── book-images/
│   └── book-memory-extraction/ # SKILL.md + condensing.md and memory-log.md
├── pyproject.toml, uv.lock     # uv project; provides the `book-search`, `book-convert` and `book-view` commands
├── src/book_companion/
│   ├── core/                   # book structure, reading progress, spoiler boundary
│   ├── search/                 # the book-search command
│   ├── convert/                # the book-convert command
│   └── view/                   # the book-view command (local notes and image viewer)
└── tests/
```

Your library (your own folder, not part of this repository):

```text
<library>/
├── _incoming/
│   ├── epubs/                  # EPUBs waiting to be imported
│   └── images/                 # ChatGPT image downloads waiting to be imported
└── books/                      # organized library; created as needed
```

The detailed agent workflows are in the `SKILL.md` files under `skills/`. The book workflow is kept in on-demand skills rather than always-loaded project instructions. After a successful import, `_incoming/epubs/` is empty because the EPUB has been moved into its book directory.

## Development

Run `uv sync` in this repository. Before committing, run `uv run ruff check`, `uv run mypy` (strict, with the pydantic plugin) and `uv run pytest`.

To use your working copy directly, without the plugin, install `book-search` in editable mode and link each skill folder into your personal skills folders (Windows; directory junctions need no admin rights):

```powershell
uv tool install --editable <path-to-this-repo>
foreach ($dir in "$HOME\.claude\skills", "$HOME\.copilot\skills") {
    New-Item -ItemType Directory -Force $dir | Out-Null
    Get-ChildItem <path-to-this-repo>\skills -Directory |
        ForEach-Object { New-Item -ItemType Junction -Path "$dir\$($_.Name)" -Target $_.FullName }
}
```

The skills then work in every folder without a plugin prefix (`/book-import`), and edits apply at the next session. Don't install the plugin as well, or each skill loads twice.
