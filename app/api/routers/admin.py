# app/api/routers/admin.py
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Request

from app.api.schemas.api_models import RebuildResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=['Admin'])


@router.post('/rebuild-index', response_model=RebuildResponse)
async def rebuild_index(request: Request) -> RebuildResponse:
    """Rebuild the FAISS vector index from all PDFs in the raw data directory.

    Clears the current in-memory index, re-ingests every PDF in raw_dir,
    re-embeds all chunks, and persists the new index to disk. Idempotent.
    """
    svc = request.app.state.components.indexing_service
    metrics = request.app.state.metrics_store

    start = time.monotonic()
    stats = svc.rebuild()
    elapsed_ms = (time.monotonic() - start) * 1000.0

    metrics.record_rebuild(elapsed_ms)
    logger.info(
        'api.rebuild docs=%d chunks=%d elapsed_ms=%.1f',
        len(stats.documents),
        stats.total_chunks,
        elapsed_ms,
    )

    return RebuildResponse(
        total_chunks=stats.total_chunks,
        documents=stats.documents,
        elapsed_ms=stats.elapsed_ms,
        message=f'Indexed {stats.total_chunks} chunks from {len(stats.documents)} document(s).',
    )
