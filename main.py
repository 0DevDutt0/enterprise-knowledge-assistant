# main.py
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api.metrics import MetricsStore
from app.api.routers import admin, ask, ops
from app.config.logging import configure_logging
from app.config.settings import settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.errors import register_error_handlers
from app.services.factory import create_app_components


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise all heavy resources once at startup; clean up on shutdown."""
    configure_logging(level=settings.log_level, fmt=settings.log_format)
    app.state.components = create_app_components(settings)
    app.state.metrics_store = MetricsStore()
    yield


app = FastAPI(
    title='Enterprise Knowledge Assistant',
    description=(
        'RAG over enterprise PDFs — grounded answers with citations '
        'and confidence scores.'
    ),
    version='0.1.0',
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)

app.include_router(ask.router)
app.include_router(admin.router)
app.include_router(ops.router)
