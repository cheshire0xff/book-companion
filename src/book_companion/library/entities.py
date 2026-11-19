"""Library check: entity profiles and their pictures (characters/, locations/, ...)."""

from __future__ import annotations

from pathlib import Path

from book_companion.core.layout import (
    DESCRIPTION_FILE,
    IMAGE_SUFFIXES,
    PICS,
    PROMPT_SUFFIX,
    subdirs,
)
from book_companion.library.findings import Code, Finding
from book_companion.library.names import check_slug


def check_entities(categories: list[Path]) -> list[Finding]:
    """Every entity folder in these category folders (characters/, locations/, ...)."""
    found: list[Finding] = []
    for category in categories:
        for entity in subdirs(category):
            found += _entity(entity)
    return found


def _entity(entity: Path) -> list[Finding]:
    found = check_slug(entity)
    if not (entity / DESCRIPTION_FILE).is_file():
        found.append(Finding(
            Code.NO_DESCRIPTION, entity, f"has no {DESCRIPTION_FILE}.",
            "Write its profile from source-backed details only (book-companion section 2), "
            "or leave it until research or a prompt sidecar provides them."))
    if (entity / PICS).is_dir():
        found += _pics(entity / PICS)
    return found


def _pics(pics: Path) -> list[Finding]:
    files = sorted(path for path in pics.iterdir()
                   if path.is_file() and not path.name.startswith("."))
    image_stems = {path.stem for path in files if path.suffix.lower() in IMAGE_SUFFIXES}
    prompt_stems = {path.name.removesuffix(PROMPT_SUFFIX) for path in files
                    if path.name.endswith(PROMPT_SUFFIX)}
    found = []
    for path in files:
        if path.suffix.lower() in IMAGE_SUFFIXES:
            if path.stem not in prompt_stems:
                found.append(Finding(
                    Code.IMAGE_WITHOUT_PROMPT, path, f"has no {path.stem}{PROMPT_SUFFIX} sidecar.",
                    "Write one from the information available, marking unknowns as unknown "
                    "(book-images, importing step 6)."))
        elif path.name.endswith(PROMPT_SUFFIX):
            if path.name.removesuffix(PROMPT_SUFFIX) not in image_stems:
                found.append(Finding(
                    Code.PENDING_PROMPT, path, "a prompt prepared; its image is not imported yet.",
                    "Generate the image from it, save it in _incoming/images/ and import it "
                    "with book-images."))
        else:
            found.append(Finding(Code.STRAY_FILE, path,
                                 f"neither an image nor a {PROMPT_SUFFIX} sidecar.",
                                 f"Move it out of {PICS}/."))
    return found
