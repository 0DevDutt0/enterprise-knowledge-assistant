# app/utils/text.py
from __future__ import annotations

import re

_CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')


def strip_control_chars(text: str) -> str:
    """Remove non-printable control characters, keeping tab, LF, and CR."""
    return _CONTROL_CHAR_RE.sub('', text)


def normalize_whitespace(text: str) -> str:
    """Collapse all runs of whitespace to a single space and strip ends."""
    return ' '.join(text.split())


def clean_query(text: str) -> str:
    """Prepare a user query for embedding: remove control chars, normalize whitespace.

    This is the canonical pre-embedding step for all query strings, per SPEC.
    """
    return normalize_whitespace(strip_control_chars(text))


def char_count(text: str) -> int:
    """Return the number of Unicode characters in text."""
    return len(text)
