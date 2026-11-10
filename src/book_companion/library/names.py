"""Library check: folder names are readable, lowercase, hyphen-separated slugs."""

from __future__ import annotations

from pathlib import Path

from book_companion.core.layout import SLUG, slugify, volume_slug
from book_companion.library.findings import Code, Finding


def check_slug(folder: Path, *, volume: bool = False) -> list[Finding]:
    """A folder named other than a slug; for a volume, the name after its number prefix."""
    name = volume_slug(folder) if volume else folder.name
    if SLUG.fullmatch(name):
        return []
    prefix = folder.name.removesuffix(name)
    return [Finding(Code.SLUG, folder, "not a lowercase, hyphen-separated slug.",
                    f"Rename it {prefix}{slugify(name)}, if the user agrees.")]
