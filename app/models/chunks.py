# app/models/chunks.py
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.elements import ElementType


class ChunkMetadata(BaseModel, frozen=True):
    """All metadata attached to a chunk, per the SPEC indexing requirements.

    Fields: document, page, section, element_type, chunk_id, source,
    char_count, created_at.
    """

    document: str
    page: int
    section: str = ''
    element_type: ElementType
    chunk_id: str
    source: str
    char_count: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Chunk(BaseModel, frozen=True):
    """A text chunk ready for embedding, carrying its full provenance metadata.

    text — the raw string passed to the embedder.
    metadata — all provenance and indexing fields.
    """

    text: str
    metadata: ChunkMetadata
