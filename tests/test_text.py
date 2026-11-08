"""Tests for the quote-matching helpers in core/text.py."""

from __future__ import annotations

from book_companion.core.text import locate, normalize


def test_normalize_ignores_accents_case_quotes_and_whitespace() -> None:
    assert normalize("  Café’s\n\tDOOR — ajar ") == "cafe's door - ajar"


def test_locate_returns_the_span_in_the_original_text() -> None:
    text = "She wore a  Café-coloured\ncloak, “frayed” at the hem."
    span = locate(text, "cafe-coloured cloak, \"frayed\"")
    assert span is not None
    assert text[span[0]:span[1]] == "Café-coloured\ncloak, “frayed”"


def test_locate_misses() -> None:
    assert locate("a grey coat", "a green coat") is None
    assert locate("a grey coat", "   ") is None
