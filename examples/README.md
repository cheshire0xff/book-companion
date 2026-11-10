# Example library

`library/` is a small, complete Book Companion library to try the tools on without importing your own books. It holds three short books written for this repository by invented authors, released under the repository's MIT License. Every file in it was made with the plugin's own skills and tools, just as they would be in your library.

```text
library/
├── _incoming/images/                   # the Tidewatch image, downloaded but not imported yet
└── books/
    ├── odile-fenwright/salt-lanterns/  # a series, being read
    │   ├── reading-progress.md         # volume 2, reading, chapter 3
    │   ├── volumes/
    │   │   ├── 01-tidewatch/           # finished: has its book memory
    │   │   └── 02-drowned-bell/        # being read: a twist waits in chapter 5
    │   ├── characters/
    │   │   ├── nell-harrow/            # profile + a portrait and its prompt
    │   │   └── tamsin-reed/            # profile only
    │   └── locations/tidewatch/        # profile + a prompt waiting for its image
    └── hesper-quayle/standalone/map-of-small-rains/   # a standalone novel, chapter 2
```

## What it shows

- **Import** (`book-import`): each volume folder has `source.epub`, `book.txt`, `book-html/` and `metadata.md`; each series or standalone book has one `reading-progress.md`.
- **Parts:** *The Tidewatch* numbers its chapters again in each part, and has a prologue and an interlude without chapter numbers. Places name the part: `"v1 pt2 ch1"`.
- **The spoiler boundary:** the reading progress stops at volume 2, chapter 3, so the twist in chapter 5 can't be found or read without `--allow-spoilers`.
- **Entity profiles** (`book-companion`): established details, inferences and unknowns, each with its chapter.
- **Images** (`book-images`): a prompt for Nell and one for the Tidewatch, each researched within the reading progress and generated in ChatGPT Images.
  - Nell's portrait is imported next to its prompt sidecar, which records the original filename, the model and where the image departs from the book.
  - The Tidewatch image is still in `_incoming/images/`, as if just downloaded, so you can try the import yourself (see below).
  - Both are saved as JPEGs to keep the repository small.
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

Or open `examples/library/` in Claude Code and talk to the skills:

- "What do we know about Tamsin so far?" answers from volume 1's memory and a search of volume 2 up to chapter 3.
- "Remind me how The Tidewatch ended." answers from the memory.
- "Import the new image." moves the Tidewatch image into `locations/tidewatch/pics/` and fills in its sidecar. Undo it with `git checkout -- examples/library` and `git clean -fd examples/library`.

The tests in `tests/test_example_library.py` keep this library as it is: `book-library check` finds no errors or warnings, only the Tidewatch image and its prompt waiting, and the twist stays behind the reading progress. If you change a book here, convert it again with `book-convert --force` and run the tests.
