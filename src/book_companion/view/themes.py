"""Color palettes for book-view.

The stylesheet (static/style.css) uses only the CSS custom properties named by
`Colors`; a palette supplies their values for light and dark mode, and the
browser picks the mode from the system setting. Add a palette by adding an
entry to PALETTES; the tests check every palette for readable contrast.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Colors:
    """The values of the stylesheet's color properties (--bg, --surface, ...)."""

    bg: str
    surface: str
    text: str
    muted: str
    border: str
    accent: str
    warn_bg: str
    warn_text: str
    error_bg: str
    error_text: str
    placeholder: str

    def declarations(self) -> str:
        return " ".join(f"--{field.name.replace('_', '-')}: {getattr(self, field.name)};"
                        for field in fields(self))


@dataclass(frozen=True)
class Palette:
    key: str  # stored in the palette cookie and sent by the picker
    name: str
    description: str
    light: Colors
    dark: Colors

    def css(self) -> str:
        return (f":root {{ {self.light.declarations()} }}\n"
                f"@media (prefers-color-scheme: dark) {{ :root {{ {self.dark.declarations()} }} }}")


PALETTES: tuple[Palette, ...] = (
    Palette(
        key="forest", name="Forest & Moss", description="Dark green-black with a sage accent.",
        light=Colors(bg="#f2f5f0", surface="#ffffff", text="#18211b", muted="#59665c",
                     border="#dbe3d8", accent="#2f6b3f", warn_bg="#fff3d6", warn_text="#7a5200",
                     error_bg="#fbe7e5", error_text="#9a2a1c", placeholder="#e3e9e0"),
        dark=Colors(bg="#101512", surface="#18201b", text="#e4ebe5", muted="#9aaa9e",
                    border="#26322a", accent="#a8cf98", warn_bg="#3a2f12", warn_text="#f2d27e",
                    error_bg="#3d1d1d", error_text="#f3b1a9", placeholder="#1f2922"),
    ),
    Palette(
        key="midnight", name="Midnight & Gold", description="Cool navy night with gilt highlights.",
        light=Colors(bg="#f3f5f9", surface="#ffffff", text="#151b2b", muted="#5b6475",
                     border="#dde2eb", accent="#2d4f8a", warn_bg="#fff3d6", warn_text="#7a5200",
                     error_bg="#fde8ea", error_text="#9b1c2c", placeholder="#e4e8f0"),
        dark=Colors(bg="#0e1320", surface="#161d2e", text="#e6e9f0", muted="#9aa3b5",
                    border="#262f44", accent="#e2b85c", warn_bg="#3a2f12", warn_text="#f2d27e",
                    error_bg="#3b1c22", error_text="#f4b0b8", placeholder="#1f2738"),
    ),
    Palette(
        key="parchment", name="Parchment & Oxblood",
        description="Old-book cream pages with a deep red accent.",
        light=Colors(bg="#f4ecdc", surface="#fbf7ee", text="#2a211b", muted="#6b5d4f",
                     border="#e0d3bb", accent="#8b1e2d", warn_bg="#fbe7c2", warn_text="#74470a",
                     error_bg="#f7dcd8", error_text="#8b1e1e", placeholder="#e8dcc4"),
        dark=Colors(bg="#1b1714", surface="#25201b", text="#efe6d6", muted="#b0a28f",
                    border="#3a3229", accent="#e8858a", warn_bg="#3d2d14", warn_text="#f0cf8e",
                    error_bg="#401d1d", error_text="#f3b1a9", placeholder="#2f2822"),
    ),
    Palette(
        key="graphite", name="Graphite & Indigo",
        description="Neutral greys, so the images carry the color.",
        light=Colors(bg="#f7f7f8", surface="#ffffff", text="#18181b", muted="#61616b",
                     border="#e4e4e7", accent="#4450c9", warn_bg="#fef3d7", warn_text="#7a5300",
                     error_bg="#fde8e8", error_text="#a11d1d", placeholder="#ececef"),
        dark=Colors(bg="#111113", surface="#1a1a1e", text="#ececf1", muted="#9d9da8",
                    border="#2c2c33", accent="#959fff", warn_bg="#3a3014", warn_text="#f2d382",
                    error_bg="#3d1d1f", error_text="#f6b3b3", placeholder="#232329"),
    ),
    Palette(
        key="velvet", name="Velvet Plum", description="Gothic aubergine with a rose accent.",
        light=Colors(bg="#f8f3f6", surface="#ffffff", text="#22161f", muted="#6a5a66",
                     border="#e8dbe3", accent="#8e2a5c", warn_bg="#fff2d9", warn_text="#7a5000",
                     error_bg="#fde6ea", error_text="#9b1c3a", placeholder="#eee3ea"),
        dark=Colors(bg="#151018", surface="#1f1823", text="#efe6ee", muted="#ab9dab",
                    border="#342a39", accent="#ec8fb1", warn_bg="#3b2c15", warn_text="#f1cf86",
                    error_bg="#401c25", error_text="#f6b2c0", placeholder="#2a2130"),
    ),
    Palette(
        key="leather", name="Leather", description="Warm brown paper and an amber accent.",
        light=Colors(bg="#f6f3ee", surface="#ffffff", text="#1f1c18", muted="#6d675e",
                     border="#e2dcd2", accent="#8a4a1f", warn_bg="#fff4dc", warn_text="#7a4b00",
                     error_bg="#fde8e6", error_text="#8c1d12", placeholder="#ece6dc"),
        dark=Colors(bg="#161412", surface="#201d1a", text="#ece7df", muted="#a59e93",
                    border="#36312b", accent="#e3a66f", warn_bg="#3a2c12", warn_text="#f3cd85",
                    error_bg="#3d1c18", error_text="#f5b3aa", placeholder="#2b2723"),
    ),
)

DEFAULT_PALETTE = "forest"
_BY_KEY = {palette.key: palette for palette in PALETTES}


def find_palette(key: str | None) -> Palette | None:
    return _BY_KEY.get(key) if key is not None else None


def palette_or_default(key: str | None) -> Palette:
    """The palette with this key, or the default one for a missing or unknown key."""
    return find_palette(key) or _BY_KEY[DEFAULT_PALETTE]
