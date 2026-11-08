"""Errors the caller must resolve."""

from __future__ import annotations

from pydantic import ValidationError


class BookError(Exception):
    """A problem the caller must resolve; printed without a traceback."""


def explain(error: ValidationError, where: str) -> BookError:
    """Turn a pydantic validation error into one readable BookError."""
    problems = []
    for item in error.errors():
        location = ""
        for part in item["loc"]:
            if isinstance(part, int):
                location += f"[{part}]"
            else:
                location += f".{part}" if location else str(part)
        message = item["msg"].removeprefix("Value error, ")
        if item["type"] == "extra_forbidden":
            message = "unknown field"
        problems.append(f"{location}: {message}" if location else message)
    return BookError(f"{where}: " + "; ".join(problems))
