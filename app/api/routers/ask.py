# app/api/routers/ask.py
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Request

from app.api.schemas.api_models import AskRequest, AskResponse, CitationOut
from app.models.conversation import ConversationTurn

logger = logging.getLogger(__name__)

router = APIRouter(tags=['Query'])


@router.post('/ask', response_model=AskResponse)
async def ask(body: AskRequest, request: Request) -> AskResponse:
    """Answer a user question from the indexed knowledge base.

    Retrieves the most relevant document chunks, reranks them, and generates
    a grounded, cited answer. Returns the canonical refusal if no relevant
    content is found above the confidence floor.

    Accepts an optional ``history`` list of prior turns so the LLM can resolve
    follow-up references (pronouns, "the same policy", "that document", etc.).
    """
    svc = request.app.state.components.query_service
    metrics = request.app.state.metrics_store

    history = [
        ConversationTurn(query=t.query, answer=t.answer) for t in body.history
    ] if body.history else None

    start = time.monotonic()
    answer = svc.ask(body.query, history=history)
    elapsed_ms = (time.monotonic() - start) * 1000.0

    metrics.record_ask(elapsed_ms)
    logger.info(
        'api.ask band=%s refusal=%s elapsed_ms=%.1f',
        answer.confidence_band.value,
        answer.is_refusal,
        elapsed_ms,
    )

    return AskResponse(
        answer=answer.text,
        citations=[
            CitationOut(
                document=c.document,
                page=c.page,
                section=c.section,
                chunk_id=c.chunk_id,
            )
            for c in answer.citations
        ],
        confidence_band=answer.confidence_band.value,
        confidence_percent=answer.confidence_percent,
        processing_time_ms=elapsed_ms,
        is_refusal=answer.is_refusal,
    )
