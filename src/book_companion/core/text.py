"""Accent/quote folding, query compilation, matching and highlighting."""

from __future__ import annotations

import re
import unicodedata

from book_companion.core.errors import BookError

_FOLD_TABLE = str.maketrans({
    "‘": "'", "’": "'", "‛": "'", "′": "'", "“": '"', "”": '"', "„": '"',
    "‐": "-", "‑": "-", "–": "-", "—": "-", "\xa0": " ",
})


def fold(text: str) -> tuple[str, list[int]]:
    """Strip accents and normalize quotes/dashes; map folded indices to originals."""
    out: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        if ord(ch) < 128:
            out.append(ch)
            origin.append(i)
            continue
        for c in unicodedata.normalize("NFKD", ch.translate(_FOLD_TABLE)):
            if not unicodedata.combining(c):
                out.append(c)
                origin.append(i)
    return "".join(out), origin


def normalized(text: str) -> tuple[str, list[int]]:
    """Folded, casefolded text with whitespace runs collapsed to one space (and trimmed);
    maps each character to its index in the original text."""
    folded, origin = fold(text)
    out: list[str] = []
    where: list[int] = []
    space: int | None = None  # index of a pending whitespace run
    for ch, i in zip(folded, origin, strict=True):
        if ch.isspace():
            if out and space is None:
                space = i
            continue
        if space is not None:
            out.append(" ")
            where.append(space)
            space = None
        for c in ch.casefold():
            out.append(c)
            where.append(i)
    return "".join(out), where


def normalize(text: str) -> str:
    """Text for comparing quotes and names: no accents, case or whitespace differences."""
    return normalized(text)[0]


def locate(text: str, quote: str) -> Span | None:
    """Where `quote` occurs in `text`, ignoring accents, case and whitespace, as a raw span."""
    haystack, where = normalized(text)
    needle = normalize(quote)
    at = haystack.find(needle) if needle else -1
    if at < 0:
        return None
    return where[at], where[at + len(needle) - 1] + 1


def compile_query(query: str, regex: bool, word: bool, case_sensitive: bool) -> re.Pattern[str]:
    pattern = fold(query)[0] if regex else re.escape(fold(query)[0])
    if word:
        pattern = rf"\b(?:{pattern})\b"
    try:
        return re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)
    except re.error as exc:
        raise BookError(f"Invalid regular expression: {exc}") from exc


Span = tuple[int, int]


Match = list[Span]  # the spans to highlight for one match


def _merge(spans: list[Span]) -> list[Span]:
    merged: list[Span] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def find_matches(text: str, pattern: re.Pattern[str]) -> list[Match]:
    """Every match in `text`, each as the spans to highlight.

    When the pattern has capture groups, only the groups are highlighted, so
    `(Anaïs).{0,300}(hair|eyes)` bolds the two keywords rather than the gap.
    """
    folded, origin = fold(text)
    matches: list[Match] = []
    for m in pattern.finditer(folded):
        if m.end() <= m.start():
            continue
        raw = [m.span(g) for g in range(1, pattern.groups + 1)
               if m.start(g) != -1 and m.end(g) > m.start(g)] or [m.span()]
        matches.append(_merge([(origin[s], origin[e - 1] + 1) for s, e in raw]))
    return matches


def highlight(text: str, spans: list[Span]) -> str:
    out, pos = [], 0
    for start, end in _merge(spans):
        out += [text[pos:start], "**", text[start:end], "**"]
        pos = end
    return "".join(out + [text[pos:]])


def snippet(text: str, matches: list[Match], width: int = 160) -> str:
    """The first match with some context on either side, all matches highlighted."""
    start, end = matches[0][0][0], matches[0][-1][1]
    a, b = max(0, start - width), min(len(text), end + width)
    if a > 0:
        space = text.find(" ", a, start)
        a = space + 1 if space != -1 else a
    if b < len(text):
        space = text.rfind(" ", end, b)
        b = space if space != -1 else b
    inside = [(s - a, e - a) for match in matches for s, e in match if s >= a and e <= b]
    return ("…" if a > 0 else "") + highlight(text[a:b], inside) + ("…" if b < len(text) else "")
