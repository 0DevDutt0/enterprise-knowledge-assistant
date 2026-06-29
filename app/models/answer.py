# app/models/answer.py
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ConfidenceBand(str, Enum):
    """Human-readable confidence label returned alongside the numeric percent.

    HIGH   >= 70 %
    MEDIUM >= 40 %
    LOW    <  40 %
    Thresholds are applied in AnswerAssembler and are not encoded here.
    """

    HIGH = 'High'
    MEDIUM = 'Medium'
    LOW = 'Low'


class Citation(BaseModel, frozen=True):
    """Source attribution for a single factual claim in an Answer.

    Mirrors the citation format in the system prompt:
    [doc: <document>, page: <page>]
    """

    document: str
    page: int
    section: str = ''
    chunk_id: str


class Answer(BaseModel, frozen=True):
    """The complete response payload returned by POST /ask.

    text              — the LLM-generated (or canonical refusal) answer.
    citations         — list of attributed source chunks.
    confidence_band   — High / Medium / Low glanceable label.
    confidence_percent — numeric score in [0, 100].
    processing_time_ms — wall-clock time for the full /ask pipeline.
    is_refusal        — True when the system returned the canonical
                        'not found' response without invoking the LLM.
    """

    text: str
    citations: list[Citation]
    confidence_band: ConfidenceBand
    confidence_percent: float = Field(ge=0.0, le=100.0)
    processing_time_ms: float = Field(ge=0.0)
    is_refusal: bool = False
