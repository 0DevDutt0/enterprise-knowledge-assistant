# app/api/schemas/api_models.py
from __future__ import annotations

from pydantic import BaseModel, Field


class ConversationTurnIn(BaseModel):
    """A prior Q&A turn sent by the client for context injection."""

    query: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1, max_length=10000)


class AskRequest(BaseModel):
    """Request body for POST /ask."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description='The user question to answer from the indexed knowledge base.',
    )
    history: list[ConversationTurnIn] = Field(
        default_factory=list,
        description='Prior conversation turns (oldest first). Only non-refusal turns '
        'should be included. The server trims to max_history_turns before injection.',
    )


class CitationOut(BaseModel):
    """A single source reference attached to an answer."""

    document: str
    page: int
    section: str
    chunk_id: str


class AskResponse(BaseModel):
    """Response body for POST /ask."""

    answer: str
    citations: list[CitationOut]
    confidence_band: str
    confidence_percent: float
    processing_time_ms: float
    is_refusal: bool


class RebuildResponse(BaseModel):
    """Response body for POST /rebuild-index."""

    total_chunks: int
    documents: list[str]
    elapsed_ms: float
    message: str


class ComponentHealthOut(BaseModel):
    """Health status of a single system component."""

    status: str
    message: str


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    vector_store: ComponentHealthOut
    llm: ComponentHealthOut
    timestamp: str


class MetricsResponse(BaseModel):
    """Response body for GET /metrics."""

    ask_request_count: int
    ask_p50_ms: float
    ask_p95_ms: float
    rebuild_request_count: int
    rebuild_p50_ms: float
    rebuild_p95_ms: float
