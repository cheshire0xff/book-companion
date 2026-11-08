"""Errors the caller must resolve."""

from __future__ import annotations


class BookError(Exception):
    """A problem the caller must resolve; printed without a traceback."""
