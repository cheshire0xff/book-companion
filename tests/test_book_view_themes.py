"""book-view palettes: complete, uniquely keyed, and readable in light and dark mode."""

from __future__ import annotations

import re
from dataclasses import fields

import pytest

from book_companion.view.themes import (
    DEFAULT_PALETTE,
    PALETTES,
    Colors,
    Palette,
    palette_or_default,
)

# Text drawn on a background in the stylesheet; each must reach WCAG AA (4.5:1).
PAIRS = [("text", "bg"), ("text", "surface"), ("muted", "bg"), ("muted", "surface"),
         ("accent", "bg"), ("accent", "surface"), ("warn_text", "warn_bg"),
         ("warn_text", "bg"), ("error_text", "error_bg")]


def luminance(color: str) -> float:
    def channel(value: int) -> float:
        s = value / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def modes() -> list[tuple[str, Colors]]:
    return [(f"{p.key}-{mode}", colors) for p in PALETTES
            for mode, colors in (("light", p.light), ("dark", p.dark))]


def test_keys_are_unique_and_the_default_exists() -> None:
    keys = [palette.key for palette in PALETTES]
    assert len(keys) == len(set(keys))
    assert DEFAULT_PALETTE in keys
    assert palette_or_default(None).key == palette_or_default("unknown").key == DEFAULT_PALETTE


@pytest.mark.parametrize(("name", "colors"), modes(), ids=[name for name, _ in modes()])
def test_every_color_is_a_hex_value_and_text_is_readable(name: str, colors: Colors) -> None:
    for field in fields(colors):
        assert re.fullmatch(r"#[0-9a-f]{6}", getattr(colors, field.name)), field.name
    for text, background in PAIRS:
        ratio = contrast(getattr(colors, text), getattr(colors, background))
        assert ratio >= 4.5, f"{name}: {text} on {background} is {ratio:.2f}:1"


def test_css_sets_every_property_for_both_modes() -> None:
    palette: Palette = PALETTES[0]
    css = palette.css()
    for field in fields(Colors):
        assert css.count(f"--{field.name.replace('_', '-')}:") == 2
    assert "@media (prefers-color-scheme: dark)" in css
