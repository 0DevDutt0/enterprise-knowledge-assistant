# app/utils/hashing.py
from __future__ import annotations

import hashlib
import os


def content_hash(text: str) -> str:
    """Return the full SHA-256 hex digest of a UTF-8 encoded string."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def doc_id_from_path(path: str) -> str:
    """Derive a stable, human-readable document ID from a file path.

    Format: <stem>-<8-char hash of the full path>.
    The hash disambiguates files with the same name in different directories.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    short_hash = content_hash(path)[:8]
    return f'{stem}-{short_hash}'


def chunk_id_from_content(doc_id: str, page: int, index: int, text: str) -> str:
    """Generate a stable 16-char chunk ID from its provenance and content.

    Inputs are combined so that the ID changes if any of them changes,
    making it safe to detect duplicates across re-ingestion runs.
    """
    seed = f'{doc_id}:{page}:{index}:{text}'
    return content_hash(seed)[:16]
