# app/api/routers/ops.py
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.api.schemas.api_models import (
    ComponentHealthOut,
    HealthResponse,
    MetricsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=['Operations'])


@router.get('/health', response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Shallow health check for all system components.

    Checks vector store size and LLM client configuration without making
    live API calls. Returns HTTP 200 regardless of component status so
    load balancers keep the instance in rotation; inspect the body for
    per-component status.
    """
    svc = request.app.state.components.health_service
    report = svc.check()
    return HealthResponse(
        status=report.status.value,
        vector_store=ComponentHealthOut(
            status=report.vector_store.status.value,
            message=report.vector_store.message,
        ),
        llm=ComponentHealthOut(
            status=report.llm.status.value,
            message=report.llm.message,
        ),
        timestamp=report.timestamp.isoformat(),
    )


@router.get('/metrics', response_model=MetricsResponse)
async def metrics(request: Request) -> MetricsResponse:
    """In-memory request count and latency percentiles.

    Metrics reset when the server restarts. For persistent monitoring,
    scrape this endpoint with Prometheus or a cron job.
    """
    store = request.app.state.metrics_store
    snap = store.snapshot()
    return MetricsResponse(
        ask_request_count=snap['ask_request_count'],
        ask_p50_ms=snap['ask_p50_ms'],
        ask_p95_ms=snap['ask_p95_ms'],
        rebuild_request_count=snap['rebuild_request_count'],
        rebuild_p50_ms=snap['rebuild_p50_ms'],
        rebuild_p95_ms=snap['rebuild_p95_ms'],
    )
