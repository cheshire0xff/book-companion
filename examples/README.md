# Example library

`library/` is a small, complete Book Companion library to try the tools on without importing your own books. It holds three short books written for this repository by invented authors, released under the repository's MIT License. Every file in it was made with the plugin's own skills and tools, just as they would be in your library.

```text
library/
├── _incoming/                          # empty: everything has been imported
└── books/
    ├── odile-fenwright/salt-lanterns/  # a series, being read
    │   ├── reading-progress.md         # volume 2, reading, chapter 3
    │   ├── volumes/
    │   │   ├── 01-tidewatch/           # finished: has its book memory
    │   │   └── 02-drowned-bell/        # being read: a twist waits in chapter 5
    │   ├── characters/
    │   │   ├── nell-harrow/            # profile + a prepared image prompt
    │   │   └── tamsin-reed/
    │   └── locations/tidewatch/        # profile + a prepared image prompt
    └── hesper-quayle/standalone/map-of-small-rains/   # a standalone novel, chapter 2
```

## What it shows

- **Import** (`book-import`): each volume folder has `source.epub`, `book.txt`, `book-html/` and `metadata.md`; each series or standalone book has one `reading-progress.md`.
- **Parts:** *The Tidewatch* numbers its chapters again in each part, and has a prologue and an interlude without chapter numbers. Places name the part: `"v1 pt2 ch1"`.
- **The spoiler boundary:** the reading progress stops at volume 2, chapter 3, so the twist in chapter 5 can't be found or read without `--allow-spoilers`.
- **Entity profiles** (`book-companion`): established details, inferences and unknowns, each with its chapter.
- **Image prompts** (`book-images`): two sidecars waiting for their images. Generate one in ChatGPT, save it in `_incoming/images/`, and ask the agent to import it.
- **Book memory** (`book-memory-extraction`): `chapters.md` and `reference.md` for the finished volume 1, logged in its `metadata.md`.

## Try it

From the repository root:

```shell
book-library check examples/library
book-view examples/library
book-search check    examples/library/books/odile-fenwright/salt-lanterns
book-search chapters examples/library/books/odile-fenwright/salt-lanterns
book-search search   examples/library/books/odile-fenwright/salt-lanterns "fogglass" --count
book-search read     examples/library/books/odile-fenwright/salt-lanterns "v1 pt2 ch1"
book-search search   examples/library/books/odile-fenwright/salt-lanterns "bell-ringer" --all   # refused: past the progress
```

Or open `examples/library/` in Claude Code and ask the skills questions, such as "What do we know about Tamsin so far?"

The tests in `tests/test_example_library.py` keep this library clean: `book-library check` finds no errors or warnings, and the twist stays behind the reading progress. If you change a book here, convert it again with `book-convert --force` and run the tests.
