"""Strict front-matter blocks: the typed fields at the top of a Markdown file.

A Markdown file whose fields a tool reads starts with a block like

    ---
    status: reading   # a comment
    chapter: 12
    ---

and free-form Markdown after it. The block is read line by line into plain
strings, so that a repeated key is caught and no value is guessed into a type
(YAML would make `no` False and `1.10` 1.1). A pydantic model then validates
the strings and gives them their types.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ValidationError

from book_companion.core.errors import BookError, explain


def read_front_matter(path: Path, template: str) -> dict[str, str]:
    """The block's keys (lowercased) and values, as written; `template` says where the
    file's template is documented, for the error messages."""
    if not path.is_file():
        raise BookError(f"{path} is missing.")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].strip() != "---":
        raise BookError(f"{path} must start with a '---' front-matter block "
                        f"(see the template in {template}).")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise BookError(f"{path}: the front-matter block is not closed with '---'.")

    values: dict[str, str] = {}
    for line_no, raw in enumerate(lines[1:end], start=2):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name, sep, value = line.partition(":")
        if not sep:
            raise BookError(f"{path}:{line_no}: expected 'key: value'.")
        key = name.strip().lower()
        if key in values:
            raise BookError(f"{path}:{line_no}: {key!r} is set twice.")
        values[key] = value.strip()
    return values


def load_front_matter[M: BaseModel](path: Path, model: type[M], template: str) -> M:
    """Read a file's front-matter block and validate it with `model`."""
    values = read_front_matter(path, template)
    try:
        return model.model_validate(values)
    except ValidationError as error:
        raise explain(error, str(path)) from None
