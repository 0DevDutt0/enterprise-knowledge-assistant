# app/middleware/correlation.py
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config.logging import generate_correlation_id, set_correlation_id

CORRELATION_ID_HEADER = 'X-Correlation-ID'


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that assigns a correlation ID to every request.

    Reads X-Correlation-ID from the incoming request headers; if absent,
    generates a fresh UUID hex. The ID is stored in a ContextVar so every log
    record emitted during the request includes it automatically, and it is
    echoed back in the response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cid = request.headers.get(CORRELATION_ID_HEADER) or generate_correlation_id()
        set_correlation_id(cid)
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = cid
        return response
