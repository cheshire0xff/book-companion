"""Reading chapter and part numbers from table-of-contents labels."""

from __future__ import annotations

import re

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}


_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}


_ROMAN = re.compile(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})")


_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _words_to_int(tokens: list[str]) -> int | None:
    """Parse leading English number words ("one hundred and five"); None if none."""
    total = current = 0
    used = False
    for token in tokens:
        word = token.lower()
        if word in _UNITS:
            current += _UNITS[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred" and used:
            current *= 100
        elif word == "thousand" and used:
            total += current * 1000
            current = 0
        elif word == "and" and used:
            continue
        else:
            break
        used = True
    return total + current if used else None


def _roman_to_int(token: str) -> int | None:
    if not token or not _ROMAN.fullmatch(token):
        return None
    values = [_ROMAN_VALUES[c] for c in token]
    return sum(-v if i + 1 < len(values) and v < values[i + 1] else v
               for i, v in enumerate(values))


def parse_number(text: str) -> int | None:
    """Parse a leading number written as digits, upper-case Roman numerals or words."""
    text = text.strip()
    digits = re.match(r"(\d+)\b", text)
    if digits:
        return int(digits.group(1))
    first = re.match(r"([A-Za-z]+)\b", text)
    if first and first.group(1).isupper():
        roman = _roman_to_int(first.group(1))
        if roman:
            return roman
    return _words_to_int(re.findall(r"[A-Za-z]+", re.split(r"[:,;.]", text)[0]))


def parse_chapter_number(label: str) -> int | None:
    """Return the chapter number a TOC label names, or None.

    Handles "Chapter 12: Title", "Chapter Twelve", "Chapter XII", "12. Title"
    and bare "12". Labels such as "Prologue" or "Book One: ..." return None.
    """
    text = " ".join(label.split())
    match = re.match(r"(?i)(?:chapter|ch\.)\s+(.*)", text)
    if not match:
        bare = re.match(r"(\d+)(?:$|[\s.:)\-–—])", text)
        return int(bare.group(1)) if bare else None
    return parse_number(match.group(1))


def parse_part_number(label: str) -> int | None:
    """Return the part number of a label such as "Book One: Title" or "Part II"."""
    match = re.match(r"(?i)(?:book|part|volume|act)\s+(.*)", " ".join(label.split()))
    return parse_number(match.group(1)) if match else None
