# app/middleware/errors.py
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.logging import get_correlation_id


class AppError(Exception):
    """Base class for all domain errors that map to structured HTTP responses.

    Subclasses set status_code on the class; the message is per-instance.
    """

    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DocumentNotFoundError(AppError):
    """Raised when a requested document ID does not exist in the store."""

    status_code = 404


class IndexNotReadyError(AppError):
    """Raised when the vector index has not been built or cannot be loaded."""

    status_code = 503


class IngestionError(AppError):
    """Raised when PDF ingestion fails (extraction or chunking step)."""

    status_code = 422


class RetrievalError(AppError):
    """Raised when the retrieval pipeline fails for a non-transient reason."""

    status_code = 500


class LLMError(AppError):
    """Raised when the Groq LLM call fails after exhausting retries."""

    status_code = 502


async def _app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map any AppError subclass to a structured JSON error response."""
    app_exc = exc if isinstance(exc, AppError) else AppError(str(exc))
    return JSONResponse(
        status_code=app_exc.status_code,
        content={
            'error': type(app_exc).__name__,
            'message': app_exc.message,
            'correlation_id': get_correlation_id() or '-',
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach all domain exception handlers to a FastAPI application instance."""
    app.add_exception_handler(AppError, _app_error_handler)  # type: ignore[arg-type]
